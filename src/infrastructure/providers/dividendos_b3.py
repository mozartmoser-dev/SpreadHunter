import logging
import requests
import json
from base64 import b64encode
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

B3_BASE_URL = "https://sistemaswebb3-listados.b3.com.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "application/json, text/plain, */*",
}

_TRADING_NAME_CACHE = {}


def _get_trading_name(ticker: str) -> str | None:
    if ticker in _TRADING_NAME_CACHE:
        return _TRADING_NAME_CACHE[ticker]

    root = "".join([c for c in ticker if c.isalpha()])
    params = {"language": "pt-br", "pageNumber": 1, "pageSize": 20, "company": root}
    encoded = b64encode(bytes(str(params), encoding="ascii")).decode()
    url = f"{B3_BASE_URL}/listedCompaniesProxy/CompanyCall/GetInitialCompanies/{encoded}"

    try:
        resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("results", []):
                if item.get("issuingCompany", "").lower() == root.lower():
                    name = item["tradingName"].replace("/", "").replace(".", "")
                    _TRADING_NAME_CACHE[ticker] = name
                    return name
    except Exception as e:
        logger.warning(f"Erro ao buscar trading name para {ticker}: {e}")

    return None


def _parse_b3_date(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def _parse_b3_value(val_str: str) -> float | None:
    if not val_str:
        return None
    try:
        return float(val_str.replace(",", "."))
    except ValueError:
        return None


class DividendosB3Provider:
    def buscar_proventos(self, ticker: str, max_pages: int = 5, callback=None) -> list[dict]:
        trading_name = _get_trading_name(ticker)
        if not trading_name:
            return []

        dividendos = []
        page = 1
        while page <= max_pages:
            params = {
                "language": "pt-br",
                "pageNumber": page,
                "pageSize": 100,
                "tradingName": trading_name,
            }
            encoded = b64encode(bytes(str(params), encoding="ascii")).decode()
            url = f"{B3_BASE_URL}/listedCompaniesProxy/CompanyCall/GetListedCashDividends/{encoded}"

            try:
                resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                if resp.status_code != 200:
                    break

                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    div = {
                        "ativo": ticker,
                        "tipo": item.get("corporateAction", ""),
                        "data_ex": _parse_b3_date(item.get("lastDatePriorEx")),
                        "data_aprovacao": _parse_b3_date(item.get("dateApproval")),
                        "valor": _parse_b3_value(item.get("valueCash")),
                        "tipo_acao": item.get("typeStock", ""),
                        "preco_fechamento": _parse_b3_value(item.get("closingPricePriorExDate")),
                    }
                    dividendos.append(div)

                page += 1
                if callback:
                    callback(ticker, page, len(results))
            except Exception as e:
                logger.warning(f"Erro ao buscar proventos pagina {page} para {ticker}: {e}")
                break

        return dividendos

    def buscar_proventos_recentes(self, ticker: str, data_de: str, callback=None) -> list[dict]:
        """Busca apenas proventos recentes (primeira pagina so)."""
        trading_name = _get_trading_name(ticker)
        if not trading_name:
            return []

        params = {
            "language": "pt-br",
            "pageNumber": 1,
            "pageSize": 100,
            "tradingName": trading_name,
        }
        encoded = b64encode(bytes(str(params), encoding="ascii")).decode()
        url = f"{B3_BASE_URL}/listedCompaniesProxy/CompanyCall/GetListedCashDividends/{encoded}"

        dividendos = []
        try:
            resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = data.get("results", [])

            from datetime import date
            data_de_obj = date.fromisoformat(data_de)

            for item in results:
                data_ex_str = _parse_b3_date(item.get("lastDatePriorEx"))
                if data_ex_str:
                    data_ex_obj = date.fromisoformat(data_ex_str)
                    if data_ex_obj >= data_de_obj:
                        div = {
                            "ativo": ticker,
                            "tipo": item.get("corporateAction", ""),
                            "data_ex": data_ex_str,
                            "data_aprovacao": _parse_b3_date(item.get("dateApproval")),
                            "valor": _parse_b3_value(item.get("valueCash")),
                            "tipo_acao": item.get("typeStock", ""),
                            "preco_fechamento": _parse_b3_value(item.get("closingPricePriorExDate")),
                        }
                        dividendos.append(div)
        except Exception as e:
            logger.warning(f"Erro ao buscar proventos recentes para {ticker}: {e}")

        return dividendos
