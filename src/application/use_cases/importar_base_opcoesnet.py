import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from dateutil.relativedelta import relativedelta

from src.application.dtos.dtos import ImportarResultado
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository


LISTA_PADRAO = [
    "ABCB4","ABEV3","ALOS3","ASAI3","AZZA3","B3SA3","BBAS3","BBDC3","BBDC4",
    "BBSE3","BEEF3","BHIA3","BPAC11","BRAP4","BRAV3","BRKM5","BRSR6","CEAB3",
    "CMIG4","CMIN3","COGN3","CPFE3","CPLE3","CSAN3","CSMG3","CSNA3","CURY3",
    "CVCB3","CXSE3","CYRE3","DIRR3","EGIE3","EMBJ3","ENEV3","EQTL3","EZTC3",
    "FLRY3","GGBR4","GOAU4","HAPV3","HYPE3","IRBR3","ISAE4","ITSA4","ITUB4",
    "JBSS32","JHSF3","KLBN11","LREN3","MBRF3","MGLU3","MOVI3","MRVE3","MULT3",
    "NATU3","PCAR3","PETR3","PETR4","POMO4","PRIO3","PSSA3","RADL3","RAIL3",
    "RAIZ4","RDOR3","RECV3","RENT3","SANB11","SAPR11","SBSP3","SLCE3","SMTO3",
    "SUZB3","TAEE11","TOTS3","TTEN3","TUPY3","UGPA3","USIM5","VALE3","VAMO3",
    "VBBR3","VIVA3","VIVT3","WEGE3","XPBR31","YDUQ3",
]


class ImportarBaseOpcoesNetUseCase:
    def __init__(self, db_path: str | Path | None = None):
        self.client = OpcoesNetClient()
        self.repo = InstrumentoRepository(db_path)

    def executar(
        self,
        ativos: list[str] | None = None,
        delay: float = 0.5,
        progress_callback=None,
    ) -> ImportarResultado:
        if ativos is None:
            ativos = LISTA_PADRAO

        import_max_months = 9
        try:
            from src.infrastructure.persistence.repositories.repositories import ParametroRepository
            param = ParametroRepository(self.repo.db_path).get_by_chave("import_max_months")
            if param:
                import_max_months = int(float(param.valor))
        except Exception:
            pass
        data_limite = date.today() + relativedelta(months=import_max_months)

        todos_instrumentos: list[InstrumentoOpcional] = []
        total = len(ativos)

        for idx, ativo in enumerate(ativos, 1):
            if progress_callback:
                progress_callback(idx, total, ativo)

            try:
                opcoes = self.client.fetch_all_options(ativo, delay=delay)
            except Exception:
                continue

            if idx < total:
                time.sleep(delay)

            if not opcoes:
                continue

            opcoes = [r for r in opcoes if r.get("vencimento", "") <= data_limite.isoformat()]
            if not opcoes:
                continue

            grupos: dict = defaultdict(lambda: {"PUT": "", "CALL": "", "MOD": ""})
            for r in opcoes:
                key = (r["ativo"], r["vencimento"], r["strike"])
                if r["tipo"] == "PUT":
                    grupos[key]["PUT"] = r["ticker"]
                else:
                    grupos[key]["CALL"] = r["ticker"]
                if r["mod"]:
                    grupos[key]["MOD"] = r["mod"]

            for (ativo_key, ven, strike), p in grupos.items():
                cod_put = p["PUT"]
                cod_call = p["CALL"]
                if not cod_put or not cod_call:
                    continue

                mod = p.get("MOD", "")
                if mod == "E":
                    tipo = TipoOpcao.EUROPEIA
                elif mod == "A":
                    tipo = TipoOpcao.AMERICANA
                else:
                    continue

                try:
                    venc = date.fromisoformat(ven)
                except (ValueError, TypeError):
                    continue

                todos_instrumentos.append(InstrumentoOpcional(
                    ativo=ativo_key,
                    cod_put=cod_put,
                    cod_call=cod_call,
                    vencimento=venc,
                    tipo_opcao=tipo,
                    strike=strike,
                ))

        removidos = self.repo.delete_all()
        total_inseridos = self.repo.save_batch(todos_instrumentos)

        ativos_unicos = sorted(set(i.ativo for i in todos_instrumentos))
        return ImportarResultado(
            total_importados=total_inseridos,
            total_removidos=removidos,
            ativos=ativos_unicos,
        )
