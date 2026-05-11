import json
from datetime import datetime
from pathlib import Path

from src.application.dtos.dtos import ExportarResultado, TipoExportacao
from src.domain.entities.estrutura_operacional import EstruturaOperacional, TipoEstrutura
from src.domain.entities.perna_operacao import PernaOperacao, Lado
from src.domain.services.montadora_box_itm import MontadoraBoxItm
from src.infrastructure.persistence.repositories.repositories import (
    EstruturaRepository,
    PernaRepository,
    InstrumentoRepository,
)


class ExportarOperacaoUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.est_repo = EstruturaRepository(db_path)
        self.perna_repo = PernaRepository(db_path)
        self.inst_repo = InstrumentoRepository(db_path)
        self.montadora = MontadoraBoxItm(profundidade_call_itm=-1)

    def executar_basket(
        self,
        oportunidade_monitor: dict,
        taxa_ganho: float,
        output_dir: str | Path = "logs",
    ) -> ExportarResultado:
        ativo = oportunidade_monitor["ativo"]
        strike_atm = oportunidade_monitor["strike"]
        vencimento = oportunidade_monitor["vencimento"]

        instrumentos = self.inst_repo.get_by_ativo(ativo)
        cod_put_atm = ""
        cod_call_atm = ""
        cod_call_itm = oportunidade_monitor.get("cod_call_itm", "")
        strike_itm = oportunidade_monitor.get("strike_itm", 0.0)

        for inst in instrumentos:
            if inst.strike == strike_atm and inst.vencimento.isoformat() == vencimento:
                cod_put_atm = inst.cod_put
                cod_call_atm = inst.cod_call
                break

        estrutura = self.est_repo.save(EstruturaOperacional(
            oportunidade_id=None,
            tipo=TipoEstrutura.BOX_ITM_BASKET,
            coefic_alvo=0.0,
            coefic_mercado=0.0,
            taxa_ganho=taxa_ganho,
        ))

        basket = self.montadora.montar_3_pernas(
            cod_call_itm=cod_call_itm,
            cod_put_atm=cod_put_atm,
            cod_call_atm=cod_call_atm,
            estrutura_id=estrutura.id,
            taxa_ganho=taxa_ganho,
        )

        for perna in basket.pernas:
            self.perna_repo.save(perna)

        resultado = ExportarResultado(
            estrutura_id=estrutura.id,
            tipo_exportacao=TipoExportacao.BASKET_ITM.value,
            ativo=ativo,
            strike=strike_atm,
            pernas=[
                {"codigo": p.codigo, "lado": p.lado.value, "quantidade": p.quantidade, "profundidade": p.profundidade}
                for p in basket.pernas
            ],
            classificacao=oportunidade_monitor.get("classificacao", ""),
            operacao="BOX_ITM_BASKET",
            ganho=oportunidade_monitor.get("ganho_box", 0.0),
            rent_vs_cdi=oportunidade_monitor.get("rent_box_vs_cdi", 0.0),
            dias=oportunidade_monitor.get("dias", 0),
        )

        filepath = self._salvar_log(resultado, output_dir)
        resultado.filepath = str(filepath)
        return resultado

    def executar_log(
        self,
        oportunidade_monitor: dict,
        output_dir: str | Path = "logs",
    ) -> ExportarResultado:
        classificacao = oportunidade_monitor.get("classificacao", "")
        operacao = oportunidade_monitor.get("operacao", "")

        resultado = ExportarResultado(
            estrutura_id=0,
            tipo_exportacao=TipoExportacao.LOG_OPERACAO.value,
            ativo=oportunidade_monitor["ativo"],
            strike=oportunidade_monitor["strike"],
            pernas=[
                {"codigo": oportunidade_monitor.get("cod_put", ""), "lado": "C", "quantidade": 100, "profundidade": 0},
                {"codigo": oportunidade_monitor.get("cod_call", ""), "lado": "V", "quantidade": 100, "profundidade": 0},
            ],
            classificacao=classificacao,
            operacao=operacao,
            ganho=oportunidade_monitor.get("ganho_box", 0.0) if classificacao == "1BOX" else oportunidade_monitor.get("ganho_sbth", 0.0),
            rent_vs_cdi=oportunidade_monitor.get("rent_box_vs_cdi", 0.0) if classificacao == "1BOX" else oportunidade_monitor.get("rent_sbth_vs_cdi", 0.0),
            dias=oportunidade_monitor.get("dias", 0),
        )

        filepath = self._salvar_log(resultado, output_dir)
        resultado.filepath = str(filepath)
        return resultado

    def _salvar_log(self, resultado: ExportarResultado, output_dir: str | Path) -> Path:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "{}_{}_{}_{}.json".format(
            resultado.tipo_exportacao,
            resultado.ativo,
            resultado.strike,
            timestamp,
        )
        filepath = out / filename
        payload = {
            "tipo_exportacao": resultado.tipo_exportacao,
            "ativo": resultado.ativo,
            "strike": resultado.strike,
            "classificacao": resultado.classificacao,
            "operacao": resultado.operacao,
            "ganho": resultado.ganho,
            "rent_vs_cdi": resultado.rent_vs_cdi,
            "dias": resultado.dias,
            "pernas": resultado.pernas,
            "exportado_em": datetime.now().isoformat(),
        }
        filepath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return filepath
