import logging
import math
import re
import time
import urllib.parse
from typing import Optional
from datetime import datetime

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
# Busca de opções (matrix + MOD)
# ------------------------------------------------------------------
    MATRIZ_TPL = "https://opcoes.net.br/matriz-opcoes-strike-x-vencimento/{tipo}s/{ativo}"
    API_BASE = "https://opcoes.net.br/api/v1"

    def _session_anon(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://opcoes.net.br/",
        })
        return s

    @staticmethod
    def _parse_valor(texto: str) -> float:
        return float(texto.replace(".", "").replace(",", ".").strip())

    @staticmethod
    def _parse_data(texto: str) -> str:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date().isoformat()

    def fetch_matriz(
        self, ativo: str, tipo: str, session: requests.Session | None = None
    ) -> list[dict]:
        """
        Busca grade de opções (strike x vencimento) do opcoes.net.br.
        tipo: 'CALL' ou 'PUT'
        Retorna lista de {ticker, strike, vencimento, tipo, ativo}
        """
        fechar = session is None
        if session is None:
            session = self._session_anon()

        url = self.MATRIZ_TPL.format(tipo=tipo, ativo=ativo.upper())
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return []
        finally:
            if fechar:
                session.close()

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="table")
        if not table:
            return []

        thead = table.find("thead")
        tbody = table.find("tbody")
        if not thead or not tbody:
            return []

        headers = thead.find_all("th")[1:]
        vencimentos = [self._parse_data(th.get_text(strip=True)) for th in headers]

        resultados = []
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            strike = self._parse_valor(tds[0].get_text(strip=True))
            for i, td in enumerate(tds[1:]):
                a = td.find("a")
                if a and a.get("href"):
                    ticker = a.get_text(strip=True)
                    if i < len(vencimentos):
                        resultados.append({
                            "ticker": ticker,
                            "strike": strike,
                            "vencimento": vencimentos[i],
                            "tipo": tipo.upper(),
                            "ativo": ativo.upper(),
                        })
        return resultados

    def fetch_mod_mapping(
        self, ativo: str, session: requests.Session | None = None
    ) -> dict[str, str]:
        """
        Busca o mapping {ticker: 'A'/'E'} (MOD = modelo Americano/Europeu)
        via API do opcoes.net.br.
        """
        fechar = session is None
        if session is None:
            s = self._session_anon()
        else:
            s = session

        z = str(math.floor(time.time() / 10))
        r0 = "r0t=LastQuotesInfo"
        params = {
            "underlying_asset_id": ativo.upper(),
            "skip": "0",
            "columns_info": "true",
            "underlying_quotes": "true",
        }
        r1 = "r1t=OptionsChain"
        for k, v in sorted(params.items()):
            r1 += "&r1p." + k + "=" + urllib.parse.quote(v)
        qs = "z=" + z + "&" + r0 + "&" + r1
        url = self.API_BASE + "?" + qs

        # API endpoint expects JSON; ensure correct Accept header
        old_accept = s.headers.get("Accept", "")
        s.headers["Accept"] = "application/json"
        result: dict[str, str] = {}
        try:
            resp = s.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return result
        finally:
            s.headers["Accept"] = old_accept
            if fechar:
                s.close()

        if not data.get("success"):
            return result

        for req in (data.get("requests") or []):
            if req.get("type") == "OptionsChain" and not req.get("error"):
                for exp in ((req.get("results") or {}).get("expirations") or []):
                    for opt in (exp.get("calls") or []):
                        if len(opt) >= 3 and opt[0]:
                            result[str(opt[0]).strip()] = str(opt[2]).strip().upper()
                    for opt in (exp.get("puts") or []):
                        if len(opt) >= 3 and opt[0]:
                            result[str(opt[0]).strip()] = str(opt[2]).strip().upper()
        return result

    def fetch_available_assets(self) -> list[str]:
        """Retorna lista de todos os ativos com opções disponíveis em opcoes.net.br."""
        s = self._session_anon()
        try:
            resp = s.get("https://opcoes.net.br/opcoes/bovespa", timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Tenta primeiro o data-acoes do "Todos ativos" (lista completa)
            select_lista = soup.find("select", {"name": "IdLista"})
            if select_lista:
                for opt in select_lista.find_all("option"):
                    if opt.get("value") == "TA":
                        acoes = opt.get("data-acoes", "")
                        if acoes:
                            return [a.strip().upper() for a in acoes.split(",") if a.strip()]
            # Fallback: options do select IdAcao
            select = soup.find("select", {"name": "IdAcao"})
            if not select:
                return []
            return [opt["value"].upper() for opt in select.find_all("option") if opt.get("value")]
        except Exception:
            return []
        finally:
            s.close()

    def fetch_all_options(
        self, ativo: str, delay: float = 0.5
    ) -> list[dict]:
        """
        Busca todas as opções (CALL + PUT) de um ativo com MOD incluso.
        Retorna lista de {ticker, strike, vencimento, tipo, ativo, mod}
        """
        session = self._session_anon()
        try:
            calls = self.fetch_matriz(ativo, "CALL", session)
            if calls:
                time.sleep(delay)
            puts = self.fetch_matriz(ativo, "PUT", session)
            mod_map = self.fetch_mod_mapping(ativo, session)

            # API returns suffix keys like "F380W1" (month+strike+week),
            # matrix returns full tickers like "PETRF380". Strip the
            # trailing week code and match via stem.
            cleaned_mod: dict[str, str] = {}
            for k, v in mod_map.items():
                stem = re.sub(r'W\d+$', '', k)
                if stem not in cleaned_mod:
                    cleaned_mod[stem] = v

            # Option ticker prefix = first 4 chars of asset (PETR4 → PETR)
            asset_prefix = ativo[:4].upper()

            combinados = calls + puts
            for r in combinados:
                t = r["ticker"]
                suffix = t[len(asset_prefix):] if t.startswith(asset_prefix) else t
                r["mod"] = cleaned_mod.get(suffix, "")
            return combinados
        finally:
            session.close()

# ------------------------------------------------------------------
# Histórico de preços (candles)
# ------------------------------------------------------------------
    def get_stock_history(self, ativo: str) -> Optional[dict]:
        """
        Busca histórico de candles + volatilidade do ativo via API.
        Request type: QuotesHistoryByAsset (timeframe=Day).
        Retorna dicionário com data_fields e data_rows, ou None.
        """
        s = self._session_anon()
        z = str(math.floor(time.time() / 10))
        params = {
            "timeframe": "Day",
            "assets_ids": ativo.upper(),
        }
        r0 = "r0t=QuotesHistoryByAsset"
        for k, v in sorted(params.items()):
            r0 += "&r0p." + k + "=" + urllib.parse.quote(v)
        qs = "z=" + z + "&" + r0
        url = self.API_BASE + "?" + qs

        old_accept = s.headers.get("Accept", "")
        s.headers["Accept"] = "application/json"
        try:
            resp = s.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None
        finally:
            s.headers["Accept"] = old_accept
            s.close()

        if not data.get("success"):
            return None

        for req in (data.get("requests") or []):
            if req.get("type") == "QuotesHistoryByAsset" and not req.get("error"):
                results = req.get("results", {})
                asset_data = results.get(ativo.upper())
                if asset_data:
                    return asset_data
        return None

    def get_stock_history_formatted(self, ativo: str, max_days: int = 252) -> Optional[list[dict]]:
        """
        Retorna lista de candles {date, open, high, low, close, change, volume, vol_hist, vol_impl}
        a partir do histórico bruto. max_days controla quantos pregões retornar (default 252 ≈ 12 meses).
        Retorna None se falhar.
        """
        raw = self.get_stock_history(ativo)
        if not raw:
            return None
        fields = raw.get("data_fields", [])
        rows = raw.get("data_rows", [])
        if not fields or not rows:
            return None
        try:
            idx_date = fields.index("date") if "date" in fields else 0
            idx_open = fields.index("open") if "open" in fields else 1
            idx_high = fields.index("high") if "high" in fields else 2
            idx_low = fields.index("low") if "low" in fields else 3
            idx_close = fields.index("close") if "close" in fields else 4
            idx_change = fields.index("change") if "change" in fields else -1
            idx_volume = fields.index("volume") if "volume" in fields else -1
            idx_vol_ewma = fields.index("vol_ewma") if "vol_ewma" in fields else -1
            idx_vol_impl = fields.index("vol_impl") if "vol_impl" in fields else -1
        except ValueError:
            return None

        # Pega apenas os últimos max_days rows
        rows = rows[-max_days:] if len(rows) > max_days else rows

        candles = []
        for row in rows:
            if len(row) <= max(idx_open, idx_high, idx_low, idx_close):
                continue
            c = {
                "date": row[idx_date] if idx_date < len(row) else None,
                "open": row[idx_open],
                "high": row[idx_high],
                "low": row[idx_low],
                "close": row[idx_close],
            }
            if idx_change >= 0 and idx_change < len(row):
                c["change"] = row[idx_change]
            if idx_volume >= 0 and idx_volume < len(row):
                c["volume"] = row[idx_volume]
            if idx_vol_ewma >= 0 and idx_vol_ewma < len(row):
                c["vol_hist"] = row[idx_vol_ewma]
            if idx_vol_impl >= 0 and idx_vol_impl < len(row):
                c["vol_impl"] = row[idx_vol_impl]
            candles.append(c)
        return candles

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
