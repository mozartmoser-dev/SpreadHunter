import re
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


class InvestSiteClient:
    URL_PATTERN = "https://www.investsite.com.br/graficos_aluguel_registro.php?cod_negociacao={ativo}"

    def __init__(self, timeout_seconds: int = 10):
        self.timeout = timeout_seconds

    def fetch_taxa_aluguel(self, ativo: str) -> dict | None:
        url = self.URL_PATTERN.format(ativo=ativo.upper())
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                logger.warning("InvestSite retornou status %d para %s", response.status_code, ativo)
                return None
            
            response.encoding = 'utf-8'
            return self.parse_html(response.text, ativo)
        except Exception as e:
            logger.error("Erro ao acessar InvestSite para %s: %s", ativo, e)
            return None

    def parse_html(self, html_content: str, ativo: str) -> dict | None:
        soup = BeautifulSoup(html_content, "html.parser")
        resumo_sec = soup.find("section", id="resumo")
        if not resumo_sec:
            logger.warning("Seção de resumo não encontrada no InvestSite para %s", ativo)
            return None
        
        texto = resumo_sec.get_text()
        
        match_data = re.search(r"atualmente\s*\((\d{2}/\d{2}/\d{4})\)", texto)
        match_atual = re.search(r"taxa\s+média\s+anualizada\s+de\s+([\d,]+)%", texto, re.IGNORECASE)
        match_7d = re.search(r"últimos\s+7\s+dias\s+foi\s+de\s+([\d,]+)%", texto, re.IGNORECASE)
        match_28d = re.search(r"últimos\s+28\s+dias\s+foi\s+de\s+([\d,]+)%", texto, re.IGNORECASE)
        
        if not (match_data and match_atual and match_7d and match_28d):
            logger.debug("Valores de aluguel incompletos na página para o ativo %s", ativo)
            return None
        
        data_ref = datetime.strptime(match_data.group(1), "%d/%m/%Y").date()
        taxa_atual = float(match_atual.group(1).replace(",", "."))
        taxa_7d = float(match_7d.group(1).replace(",", "."))
        taxa_28d = float(match_28d.group(1).replace(",", "."))
        
        return {
            "ativo": ativo.upper(),
            "data": data_ref,
            "taxa_atual": taxa_atual,
            "taxa_7d": taxa_7d,
            "taxa_28d": taxa_28d
        }
