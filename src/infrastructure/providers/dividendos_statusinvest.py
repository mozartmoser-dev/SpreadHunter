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
DADOSMERCADO_URL = "https://www.dadosdemercado.com.br/acoes/{}/dividendos"


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
        for _ in range(365):
            dt += timedelta(days=1)
            if dt.weekday() < 5 and dt.isoformat() not in feriados:
                return dt.isoformat()
        logger.error("Nao encontrou dia util em 365 dias a partir de %s", data_str)
        return data_str

    def buscar_proventos(self, ticker: str) -> list[dict]:
        return self._mesclar(
            self._buscar_statusinvest(ticker),
            self._buscar_dadosdemercado(ticker),
        )

    def _buscar_statusinvest(self, ticker: str) -> list[dict]:
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

    def _buscar_dadosdemercado(self, ticker: str) -> list[dict]:
        dividendos = []
        url = DADOSMERCADO_URL.format(ticker.lower())
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"DadosMercado: HTTP {resp.status_code} para {ticker}")
                return []

            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table', class_='normal-table')
            if table is None:
                return []

            # Colunas: Tipo, Valor, Registro (data com), Ex, Pagamento
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue

                tipo = cols[0].get_text(strip=True)
                data_com = self._parse_date(cols[2].get_text(strip=True))
                data_ex = self._parse_date(cols[3].get_text(strip=True))
                data_pag = self._parse_date(cols[4].get_text(strip=True))

                dividendos.append({
                    "ativo": ticker.upper(),
                    "tipo": tipo,
                    "data_com": data_com,
                    "data_ex": data_ex or self._proximo_dia_util(data_com),
                    "data_pagamento": data_pag,
                    "valor": self._parse_valor(cols[1].get_text(strip=True)),
                    "fonte": "dadosdemercado",
                })

            return dividendos
        except Exception as e:
            logger.warning(f"DadosMercado: erro ao buscar {ticker}: {e}")
            return []

    @staticmethod
    def _mesclar(*listas: list[dict]) -> list[dict]:
        mapa = {}
        for lista in listas:
            for div in lista:
                chave = (div.get("data_com"), div.get("tipo"))
                if chave not in mapa:
                    mapa[chave] = dict(div)
                    continue
                atual = mapa[chave]
                for campo in ("data_ex", "data_pagamento", "valor"):
                    if atual.get(campo) in (None, "-") and div.get(campo) not in (None, "-"):
                        atual[campo] = div.get(campo)
        return list(mapa.values())

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
