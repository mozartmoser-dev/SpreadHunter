import logging
import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

WEBWALLET_URL = "https://webwallet.com.br/acoes/agenda-resultados/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class CalendarioResultadosWebwalletProvider:
    MAX_PAGINAS = 10

    def buscar_todos(self) -> list[dict]:
        resultados = []
        for pagina in range(1, self.MAX_PAGINAS + 1):
            items = self._buscar_pagina(pagina)
            if not items:
                break
            resultados.extend(items)
            logger.debug("webwallet: página %d/%d → %d registros", pagina, self.MAX_PAGINAS, len(items))
        return resultados

    def _buscar_pagina(self, pagina: int) -> list[dict]:
        url = WEBWALLET_URL
        hoje_br = date.today().strftime("%d/%m/%Y")
        params = {"TBLPF_TBL_AAGR_DT_PUBLICACAO_FINI": hoje_br}
        if pagina > 1:
            params["TBLPL_TBL_PG"] = str(pagina)

        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                logger.warning("webwallet: HTTP %d na página %d", resp.status_code, pagina)
                return []
            return self._parse_html(resp.text)
        except requests.RequestException as e:
            logger.warning("webwallet: erro na página %d: %s", pagina, e)
            return []

    def _parse_html(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items = []

        tbody = soup.select_one("table#TBL tbody")
        if not tbody:
            return []

        for row in tbody.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            data_text = cols[0].get_text(strip=True)
            cnpj_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""

            cols[2].find("div")
            img = cols[2].find("img")
            ticker_text = ""
            nome_text = ""
            if img and img.get("alt"):
                alt_text = img["alt"]
                if " - " in alt_text:
                    ticker_text, nome_text = alt_text.split(" - ", 1)
                else:
                    ticker_text = alt_text
            else:
                span = cols[2].find("span")
                if span and span.get("data-original-title"):
                    title = span["data-original-title"]
                    if " - " in title:
                        ticker_text, nome_text = title.split(" - ", 1)

            if not ticker_text and len(cols) >= 4:
                nome_text = cols[3].get_text(strip=True)
                ticker_text = nome_text

            data_pub = self._parse_date(data_text)
            if not data_pub or not ticker_text:
                continue

            items.append({
                "ativo": ticker_text.upper().strip(),
                "cnpj": self._limpar_cnpj(cnpj_text),
                "nome_empresa": nome_text.strip() if nome_text else "",
                "data_publicacao": data_pub,
                "trimestre_referencia": "",
                "tipo_documento": "ITR",
                "tipo_evento": "previsto",
                "fonte": "webwallet",
            })

        return items

    @staticmethod
    def _parse_date(text: str) -> str | None:
        if not text:
            return None
        text = text.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
        return None

    @staticmethod
    def _limpar_cnpj(text: str) -> str:
        if not text:
            return ""
        digits = re.sub(r"\D", "", text)
        return digits
