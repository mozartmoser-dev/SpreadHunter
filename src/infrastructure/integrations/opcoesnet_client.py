import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)


load_dotenv()


class OpcoesNetClient:
    BASE = "https://opcoes.net.br"
    LOGIN_URL = f"{BASE}/v1/login"
    VARIACAO_URL = f"{BASE}/acoes/dados-estudo-variacao"

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._logged_in = False
        self._last_login_attempt = 0.0
        self._login_cooldown = 30.0
        self._csrf_token: Optional[str] = None
        self._csrf_updated_at = 0.0

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    @property
    def cpf(self) -> str:
        return os.getenv("OPCOESNET_CPF", "").strip()

    @property
    def senha(self) -> str:
        return os.getenv("OPCOESNET_SENHA", "").strip()

    def _criar_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://opcoes.net.br/",
        })
        return s

    def _extrair_csrf(self, html: str) -> Optional[str]:
        match = re.search(
            r'<input[^>]*name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']',
            html,
        )
        return match.group(1) if match else None

    def login(self, force: bool = False) -> bool:
        if self._logged_in and not force:
            return True

        agora = time.time()
        if agora - self._last_login_attempt < self._login_cooldown:
            return self._logged_in

        self._last_login_attempt = agora

        if not self.cpf or not self.senha:
            logger.warning("OPCOESNET_CPF/OPCOESNET_SENHA não configurados no .env")
            self._logged_in = False
            return False

        session = self._criar_session()

        try:
            resp = session.get(self.LOGIN_URL, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Falha ao carregar página de login: {e}")
            self._logged_in = False
            return False

        token = self._extrair_csrf(resp.text)
        if not token:
            logger.error("CSRF token não encontrado na página de login")
            self._logged_in = False
            return False

        payload = {
            "CPF": self.cpf,
            "Password": self.senha,
            "RememberMe": "true",
            "__RequestVerificationToken": token,
        }

        try:
            login_resp = session.post(
                self.LOGIN_URL,
                data=payload,
                allow_redirects=True,
                timeout=20,
            )
            login_resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Falha no login: {e}")
            self._logged_in = False
            return False

        if "/login" in login_resp.url.lower() and login_resp.status_code == 200:
            soup2 = BeautifulSoup(login_resp.text, "html.parser")
            if soup2.find("input", {"name": "CPF"}):
                logger.error("Login falhou — credenciais inválidas?")
                self._logged_in = False
                return False

        self._session = session
        self._logged_in = True
        self._csrf_token = None
        logger.info("Login opcoes.net.br OK")
        return True

    def _garantir_csrf(self) -> Optional[str]:
        if self._csrf_token and time.time() - self._csrf_updated_at < 300:
            return self._csrf_token
        if not self._session and not self.login():
            return None
        try:
            resp = self._session.get(
                "https://opcoes.net.br/acoes/estudo-variacao",
                timeout=15,
            )
            token = self._extrair_csrf(resp.text)
            if token:
                self._csrf_token = token
                self._csrf_updated_at = time.time()
                return token
        except requests.RequestException as e:
            logger.error(f"Falha ao obter CSRF: {e}")
        return None

    # ------------------------------------------------------------------
    # Consulta de variação
    # ------------------------------------------------------------------
    def get_variacao(
        self,
        ativo: str,
        data_inicial: Optional[str] = None,
        data_final: Optional[str] = None,
        referencia_inicial: str = "PrecoFechamento",
        tipo_variacao: str = "Amplitude",
        faixas: str = "2,5,10",
    ) -> Optional[dict]:
        if not self._session:
            if not self.login():
                return None

        token = self._garantir_csrf()
        if not token:
            logger.error("Não foi possível obter CSRF token")
            return None

        payload = {
            "referenciaInicial": referencia_inicial,
            "tipoVariacao": tipo_variacao,
            "IdAcao": ativo.upper(),
            "dataInicial": data_inicial or "",
            "dataFinal": data_final or "",
            "faixasVariacao": faixas,
            "__RequestVerificationToken": token,
        }

        try:
            resp = self._session.post(
                self.VARIACAO_URL,
                data=payload,
                timeout=60,
            )
            if resp.status_code == 401:
                logger.info("Sessão expirou, tentando relogin...")
                self._logged_in = False
                if self.login(force=True):
                    return self.get_variacao(
                        ativo, data_inicial, data_final,
                        referencia_inicial, tipo_variacao, faixas,
                    )
                return None
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                logger.error(
                    f"API error: {data.get('errorMessage', 'desconhecido')}"
                )
                return None
            return data
        except requests.RequestException as e:
            logger.error(f"Falha na consulta de variação: {e}")
            return None
        except ValueError as e:
            logger.error(f"Erro ao parsear JSON: {e}")
            return None

    def get_variacao_formatada(
        self,
        ativo: str,
        n_sessoes: int = 21,
    ) -> Optional[dict]:
        raw = self.get_variacao(ativo)
        if not raw:
            return None

        dados = raw.get("data", {})
        dias_corridos = raw.get("diasCorridos", 0)
        dias_negociacao = raw.get("diasComNegociacao", 0)

        # Encontra a chave para o intervalo desejado
        chave_alvo = None
        for chave in dados:
            if str(n_sessoes) in chave:
                chave_alvo = chave
                break
        if not chave_alvo:
            # Pega a chave com o maior número de sessões disponível
            import re as re2
            max_n = 0
            for chave in dados:
                nums = re2.findall(r'\d+', chave)
                if nums:
                    n = int(nums[-1])
                    if n > max_n:
                        max_n = n
                        chave_alvo = chave
            if not chave_alvo:
                chave_alvo = list(dados.keys())[0]

        bins = dados.get(chave_alvo, [])

        # Calcula média e desvio padrão a partir dos bins
        total_obs = sum(b.get("quantidade", 0) for b in bins)
        media_pond = 0.0
        var_pond = 0.0

        if total_obs > 0:
            # Aproximação: valor médio de cada bin
            bin_centers = []
            bin_weights = []
            for b in bins:
                qtd = b.get("quantidade", 0)
                if qtd <= 0:
                    continue
                rotulo = b.get("classificação", "")
                nums = [float(x) for x in re.findall(r'[-]?[\d,.]+', rotulo.replace(".", "").replace(",", "."))]
                # Ponto médio do bin
                if "Menos" in rotulo:
                    centro = nums[0] / 2 if nums else 1.0
                elif "Mais" in rotulo:
                    centro = nums[0] * 1.5 if nums else 10.0
                elif len(nums) >= 2:
                    centro = (nums[0] + nums[1]) / 2
                else:
                    centro = nums[0] if nums else 5.0
                bin_centers.append(centro)
                bin_weights.append(qtd)

            if bin_weights:
                total_w = sum(bin_weights)
                media_pond = sum(c * w for c, w in zip(bin_centers, bin_weights)) / total_w
                var_pond = sum(w * (c - media_pond) ** 2 for c, w in zip(bin_centers, bin_weights)) / total_w

        desvio = (var_pond ** 0.5) if var_pond > 0 else 0.0

        # Níveis de strike sugeridos (em % de variação)
        strikes_pct = {
            "1sigma_alta": round(media_pond + desvio, 2),
            "1sigma_baixa": round(max(media_pond - desvio, 0), 2),
            "2sigma_alta": round(media_pond + 2 * desvio, 2),
            "2sigma_baixa": round(max(media_pond - 2 * desvio, 0), 2),
        }

        return {
            "ativo": ativo.upper(),
            "n_sessoes": n_sessoes,
            "intervalo": chave_alvo,
            "dias_corridos": dias_corridos,
            "dias_negociacao": dias_negociacao,
            "bins": bins,
            "total_observacoes": total_obs,
            "media_var": round(media_pond, 2),
            "desvio_padrao": round(desvio, 2),
            "strikes_pct": strikes_pct,
        }
