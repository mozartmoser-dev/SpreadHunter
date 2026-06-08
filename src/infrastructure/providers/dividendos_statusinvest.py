import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

STATUSINVEST_URL = "https://statusinvest.com.br/acoes/{}"


class DividendosStatusInvestProvider:
    @staticmethod
    def _proximo_dia_util(data_str: str | None) -> str | None:
        if not data_str:
            return None
        try:
            dt = date.fromisoformat(data_str)
        except (ValueError, TypeError):
            return data_str
        try:
            from src.domain.services.calendario_b3 import _feriados_atuais
            feriados = set(_feriados_atuais)
        except Exception:
            feriados = set()
        while True:
            dt += timedelta(days=1)
            if dt.weekday() < 5 and dt.isoformat() not in feriados:
                return dt.isoformat()

    def buscar_proventos(self, ticker: str) -> list[dict]:
        dividendos = []
        url = STATUSINVEST_URL.format(ticker.lower())
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"StatusInvest: HTTP {resp.status_code} para {ticker}")
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')
            tables = soup.find_all('table')
            if not tables:
                return []

            # Tabela 0 = proventos (Tipo, DATA COM, Pagamento, Valor)
            rows = tables[0].find_all('tr')[1:]
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue

                tipo = cols[0].get_text(strip=True)
                data_com_str = cols[1].get_text(strip=True)
                data_pag_str = cols[2].get_text(strip=True)
                valor_str = cols[3].get_text(strip=True)

                data_com = self._parse_date(data_com_str)
                data_pag = self._parse_date(data_pag_str)
                valor = self._parse_valor(valor_str)

                dividendos.append({
                    "ativo": ticker.upper(),
                    "tipo": tipo,
                    "data_com": data_com,
                    "data_ex": self._proximo_dia_util(data_com),
                    "data_pagamento": data_pag,
                    "valor": valor,
                    "fonte": "statusinvest",
                })

            return dividendos
        except Exception as e:
            logger.warning(f"StatusInvest: erro ao buscar {ticker}: {e}")
            return []

    @staticmethod
    def _parse_date(date_str: str) -> str | None:
        if not date_str or date_str == "-":
            return None
        try:
            dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    def _parse_valor(valor_str: str) -> float | None:
        if not valor_str:
            return None
        try:
            return float(valor_str.replace(".", "").replace(",", "."))
        except ValueError:
            return None
