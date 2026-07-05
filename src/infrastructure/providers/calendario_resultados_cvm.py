import csv
import io
import logging
import zipfile
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)

CVM_ITR_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip"
CVM_DFP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


class CalendarioResultadosCVMProvider:
    def __init__(self):
        self._cache_cnpj_ticker: dict[str, str] = {}

    def set_cnpj_ticker_map(self, mapa: dict[str, str]):
        self._cache_cnpj_ticker = mapa

    def buscar_itr(self, ano: int = 0) -> list[dict]:
        if ano == 0:
            ano = date.today().year
        return self._buscar_do_zip(CVM_ITR_URL.format(ano=ano), ano, "ITR")

    def buscar_dfp(self, ano: int = 0) -> list[dict]:
        if ano == 0:
            ano = date.today().year
        return self._buscar_do_zip(CVM_DFP_URL.format(ano=ano), ano, "DFP")

    def _buscar_do_zip(self, url: str, ano: int, tipo: str) -> list[dict]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=300)
            if resp.status_code != 200:
                logger.warning("CVM %s %d: HTTP %d", tipo, ano, resp.status_code)
                return []

            results: dict[str, dict] = {}
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]

                for csv_name in csv_files:
                    if "DRE_con" not in csv_name and "DRE_ind" not in csv_name:
                        continue
                    try:
                        with z.open(csv_name) as f:
                            text = f.read()
                            for encoding in ("utf-8", "latin-1", "cp1252"):
                                try:
                                    content = text.decode(encoding)
                                    break
                                except UnicodeDecodeError:
                                    continue
                            else:
                                content = text.decode("latin-1", errors="replace")

                            reader = csv.DictReader(io.StringIO(content))
                            for row in reader:
                                cnpj = row.get("CNPJ_CIA", "").strip()
                                dt_ref = row.get("DT_REFER", "").strip()
                                denom = row.get("DENOM_SOCIAL", "").strip()

                                if not cnpj or not dt_ref:
                                    continue

                                key = f"{cnpj}|{dt_ref}"
                                if key not in results:
                                    ativo = self._cache_cnpj_ticker.get(cnpj, "")
                                    results[key] = {
                                        "ativo": ativo,
                                        "cnpj": cnpj,
                                        "nome_empresa": denom,
                                        "data_publicacao": dt_ref[:10] if len(dt_ref) >= 10 else dt_ref,
                                        "trimestre_referencia": dt_ref[:7] if len(dt_ref) >= 7 else "",
                                        "tipo_documento": tipo,
                                        "tipo_evento": "publicado",
                                        "fonte": "cvm",
                                    }
                    except Exception as e:
                        logger.debug("CVM: erro parse %s: %s", csv_name, e)
                        continue

            return list(results.values())

        except requests.RequestException as e:
            logger.warning("CVM %s %d: req error: %s", tipo, ano, e)
            return []
        except Exception as e:
            logger.warning("CVM %s %d: erro: %s", tipo, ano, e)
            return []


    def buscar_recentes(self, anos: int = 3) -> list[dict]:
        todos = []
        hoje = date.today()
        for i in range(anos):
            ano = hoje.year - i
            todos.extend(self.buscar_itr(ano))
            todos.extend(self.buscar_dfp(ano))
        return todos
