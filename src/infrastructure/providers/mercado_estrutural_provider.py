import logging
import math
import time
import urllib.parse
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)


class MercadoEstruturalProvider:
    API_BASE = "https://opcoes.net.br/api/v1"
    BATCH_SIZE = 5
    BATCH_INTERVAL = 2.0

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://opcoes.net.br/",
        })

    def __del__(self):
        self._session.close()

    def fetch_options_data(self, ativo: str) -> list[dict]:
        z = str(math.floor(time.time() / 10))
        params = {
            "underlying_asset_id": ativo.upper(),
            "skip": "0",
            "columns_info": "true",
            "underlying_quotes": "true",
        }
        r1 = "r1t=OptionsChain"
        for k, v in sorted(params.items()):
            r1 += "&r1p." + k + "=" + urllib.parse.quote(v)
        qs = "z=" + z + "&r0t=LastQuotesInfo&" + r1
        url = self.API_BASE + "?" + qs

        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            logger.warning(f"API falhou para {ativo}: {data.get('errorMessage', 'desconhecido')}")
            return []

        resultados: list[dict] = []
        hoje = date.today()

        for req in (data.get("requests") or []):
            if req.get("type") == "OptionsChain" and not req.get("error"):
                for exp in ((req.get("results") or {}).get("expirations") or []):
                    vencimento_str = exp.get("expiration", "")
                    try:
                        vencimento = datetime.strptime(vencimento_str, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        continue
                    if vencimento <= hoje:
                        continue

                    for opt in (exp.get("calls") or []):
                        item = self._parse_option(opt, "CALL", ativo, vencimento)
                        if item:
                            resultados.append(item)
                    for opt in (exp.get("puts") or []):
                        item = self._parse_option(opt, "PUT", ativo, vencimento)
                        if item:
                            resultados.append(item)

        return resultados

    def _parse_option(self, opt: list, tipo: str, ativo: str, vencimento: date) -> dict | None:
        if not opt or not opt[0]:
            return None
        try:
            return {
                "opcao": str(opt[0]),
                "strike": float(opt[3]) if len(opt) > 3 and opt[3] else 0.0,
                "tipo": tipo,
                "vencimento": vencimento.isoformat(),
                "ativo": ativo.upper(),
                "ultimo_preco": float(opt[6]) if len(opt) > 6 and opt[6] else 0.0,
                "num_negocios": int(opt[9]) if len(opt) > 9 and opt[9] else 0,
                "volume_financeiro": float(opt[10]) if len(opt) > 10 and opt[10] else 0.0,
                "titulares": int(opt[15]) if len(opt) > 15 and opt[15] else 0,
                "lancadores": int(opt[16]) if len(opt) > 16 and opt[16] else 0,
                "iv": float(opt[17]) if len(opt) > 17 and opt[17] else 0.0,
                "delta": float(opt[18]) if len(opt) > 18 and opt[18] else 0.0,
                "gamma": float(opt[19]) if len(opt) > 19 and opt[19] else 0.0,
                "mod": str(opt[2]) if len(opt) > 2 and opt[2] else "",
            }
        except (ValueError, IndexError, TypeError):
            return None

    def fetch_all_whitelist(self, ativos: list[str]) -> dict[str, list[dict] | None]:
        resultados: dict[str, list[dict] | None] = {}
        for i in range(0, len(ativos), self.BATCH_SIZE):
            batch = ativos[i:i + self.BATCH_SIZE]
            for ativo in batch:
                try:
                    resultados[ativo] = self.fetch_options_data(ativo)
                    logger.info(f"Estrutural: {ativo} — {len(resultados[ativo])} opções")
                except requests.RequestException as e:
                    logger.warning(f"Falha ao buscar {ativo}: {e}")
                    resultados[ativo] = None
            if i + self.BATCH_SIZE < len(ativos):
                time.sleep(self.BATCH_INTERVAL)
        return resultados
