import json
from datetime import datetime

from src.application.dtos.dtos import ExportarResultado, TipoExportacao
from src.domain.entities.estrutura_operacional import EstruturaOperacional, TipoEstrutura
from src.domain.entities.oportunidade import Oportunidade, ClassificacaoOp
from src.domain.entities.perna_operacao import PernaOperacao, Lado
from src.domain.services.montadora_box_itm import MontadoraBoxItm
from src.infrastructure.importers.excel_importer import extrair_strike
from src.infrastructure.persistence.repositories.repositories import (
    EstruturaRepository,
    PernaRepository,
    InstrumentoRepository,
    OportunidadeRepository,
)


class ExportarOperacaoUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.est_repo = EstruturaRepository(db_path)
        self.perna_repo = PernaRepository(db_path)
        self.inst_repo = InstrumentoRepository(db_path)
        self.opp_repo = OportunidadeRepository(db_path)
        self.montadora = MontadoraBoxItm(profundidade_call_itm=-1)

    def executar_basket(
        self,
        oportunidade_monitor: dict,
        taxa_ganho: float,
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
            inst_strike = extrair_strike(inst.cod_put)
            if inst.vencimento.isoformat() == vencimento and inst_strike is not None and abs(inst_strike - strike_atm) < 0.01:
                cod_put_atm = inst.cod_put
                cod_call_atm = inst.cod_call
                break

        spread = strike_atm - strike_itm if strike_itm > 0 else 0.0
        coefic_alvo = spread * ((100.0 - taxa_ganho) / 100.0) if spread > 0 else 0.0

        of_venda_call_itm = oportunidade_monitor.get("of_venda_call_itm", 0.0)
        of_venda_put_ref = oportunidade_monitor.get("of_venda_put", 0.0)
        of_compra_call_ref = oportunidade_monitor.get("of_compra_call", 0.0)
        coefic_mercado = of_venda_call_itm + of_venda_put_ref - of_compra_call_ref

        snapshot = {
            "tipo_opcao": oportunidade_monitor.get("tipo_opcao", ""),
            "coefic_alvo": round(coefic_alvo, 4),
            "coefic_mercado": round(coefic_mercado, 4),
            "spread": round(spread, 4),
            "taxa_ganho": taxa_ganho,
            "of_compra_put": oportunidade_monitor.get("of_compra_put", 0.0),
            "of_venda_put": oportunidade_monitor.get("of_venda_put", 0.0),
            "of_compra_call": oportunidade_monitor.get("of_compra_call", 0.0),
            "of_venda_call": oportunidade_monitor.get("of_venda_call", 0.0),
            "qul_put": oportunidade_monitor.get("qul_put", 0.0),
            "qul_call": oportunidade_monitor.get("qul_call", 0.0),
            "liq_put_x_lote": oportunidade_monitor.get("liq_put_x_lote", 0.0),
            "liq_call_x_lote": oportunidade_monitor.get("liq_call_x_lote", 0.0),
            "money_put": oportunidade_monitor.get("money_put", 0.0),
            "money_call": oportunidade_monitor.get("money_call", 0.0),
            "em_leilao": oportunidade_monitor.get("em_leilao", False),
        }

        operacao = oportunidade_monitor.get("operacao", "BOX")
        classificacao = self._operacao_to_classificacao(operacao)

        oportunidade_db = Oportunidade(
            instrumento_id=oportunidade_monitor.get("instrumento_id", 0),
            preco_ativo=oportunidade_monitor.get("preco_compra_ativo", 0.0),
            strike=strike_atm,
            dias=oportunidade_monitor.get("dias", 0),
            cdi_periodo=oportunidade_monitor.get("cdi_periodo", 0.0),
            custo_sbth=oportunidade_monitor.get("custo_sbth", 0.0),
            pct_ganho_sbth=oportunidade_monitor.get("pct_ganho_sbth", 0.0),
            pct_cdi_sbth=oportunidade_monitor.get("pct_cdi_sbth", 0.0),
            custo_box=oportunidade_monitor.get("custo_box", 0.0),
            pct_ganho_box=oportunidade_monitor.get("pct_ganho_box", 0.0),
            pct_cdi_box=oportunidade_monitor.get("pct_cdi_box", 0.0),
            classificacao=classificacao,
            operacao=operacao,
            snapshot_mercado=snapshot,
        )
        oportunidade_db = self.opp_repo.save(oportunidade_db)

        estrutura = self.est_repo.save(EstruturaOperacional(
            oportunidade_id=oportunidade_db.id,
            tipo=TipoEstrutura.BOX_ITM_BASKET,
            coefic_alvo=round(coefic_alvo, 4),
            coefic_mercado=round(coefic_mercado, 4),
            taxa_ganho=taxa_ganho,
        ))

        basket = self.montadora.montar_3_pernas(
            cod_call_itm=cod_call_itm,
            cod_put_atm=cod_put_atm,
            cod_call_atm=cod_call_atm,
            estrutura_id=estrutura.id,
            coefic_alvo=round(coefic_alvo, 4),
            coefic_mercado=round(coefic_mercado, 4),
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
            classificacao=classificacao.value,
            operacao=operacao,
            pct_ganho=oportunidade_monitor.get("pct_ganho_box", 0.0),
            pct_cdi=oportunidade_monitor.get("pct_cdi_box", 0.0),
            dias=oportunidade_monitor.get("dias", 0),
        )

        resultado.boleta = snapshot
        resultado.oportunidade_id = oportunidade_db.id
        return resultado

    def executar_log(
        self,
        oportunidade_monitor: dict,
    ) -> ExportarResultado:
        operacao = oportunidade_monitor.get("operacao", "BOX")
        classificacao = self._operacao_to_classificacao(operacao)

        cod_put = oportunidade_monitor.get("cod_put", "")
        cod_call = oportunidade_monitor.get("cod_call", "")

        tipo_estrutura = TipoEstrutura.SBTH if operacao == "SBTH" else TipoEstrutura.BOX_3_PERNAS

        snapshot = {
            "tipo_opcao": oportunidade_monitor.get("tipo_opcao", ""),
            "of_compra_put": oportunidade_monitor.get("of_compra_put", 0.0),
            "of_venda_put": oportunidade_monitor.get("of_venda_put", 0.0),
            "of_compra_call": oportunidade_monitor.get("of_compra_call", 0.0),
            "of_venda_call": oportunidade_monitor.get("of_venda_call", 0.0),
            "qul_put": oportunidade_monitor.get("qul_put", 0.0),
            "qul_call": oportunidade_monitor.get("qul_call", 0.0),
            "liq_put_x_lote": oportunidade_monitor.get("liq_put_x_lote", 0.0),
            "liq_call_x_lote": oportunidade_monitor.get("liq_call_x_lote", 0.0),
            "money_put": oportunidade_monitor.get("money_put", 0.0),
            "money_call": oportunidade_monitor.get("money_call", 0.0),
            "em_leilao": oportunidade_monitor.get("em_leilao", False),
            "pct_cdi_sbth_liquido": oportunidade_monitor.get("pct_cdi_sbth_liquido", 0.0),
            "pct_cdi_box_liquido": oportunidade_monitor.get("pct_cdi_box_liquido", 0.0),
            "cod_put": cod_put,
            "cod_call": cod_call,
        }

        oportunidade_db = Oportunidade(
            instrumento_id=oportunidade_monitor.get("instrumento_id", 0),
            preco_ativo=oportunidade_monitor.get("preco_compra_ativo", 0.0),
            strike=oportunidade_monitor["strike"],
            dias=oportunidade_monitor.get("dias", 0),
            cdi_periodo=oportunidade_monitor.get("cdi_periodo", 0.0),
            custo_sbth=oportunidade_monitor.get("custo_sbth", 0.0),
            pct_ganho_sbth=oportunidade_monitor.get("pct_ganho_sbth", 0.0),
            pct_cdi_sbth=oportunidade_monitor.get("pct_cdi_sbth", 0.0),
            custo_box=oportunidade_monitor.get("custo_box", 0.0),
            pct_ganho_box=oportunidade_monitor.get("pct_ganho_box", 0.0),
            pct_cdi_box=oportunidade_monitor.get("pct_cdi_box", 0.0),
            classificacao=classificacao,
            operacao=operacao,
            snapshot_mercado=snapshot,
        )
        oportunidade_db = self.opp_repo.save(oportunidade_db)

        estrutura = self.est_repo.save(EstruturaOperacional(
            oportunidade_id=oportunidade_db.id,
            tipo=tipo_estrutura,
            coefic_alvo=oportunidade_monitor.get("coefic_alvo", 0.0),
            coefic_mercado=oportunidade_monitor.get("coefic_mercado", 0.0),
            taxa_ganho=oportunidade_monitor.get("taxa_ganho", 0.0),
        ))

        pernas_data = [
            (cod_put, Lado.COMPRA, 1),
            (cod_call, Lado.VENDA, 2),
        ]
        for codigo, lado, ordem in pernas_data:
            if codigo:
                self.perna_repo.save(PernaOperacao(
                    estrutura_id=estrutura.id,
                    codigo=codigo,
                    lado=lado,
                    quantidade=100,
                    profundidade=0,
                    ordem=ordem,
                ))

        pernas_resultado = [
            {"codigo": cod_put, "lado": "C", "quantidade": 100, "profundidade": 0},
            {"codigo": cod_call, "lado": "V", "quantidade": 100, "profundidade": 0},
        ]

        resultado = ExportarResultado(
            estrutura_id=estrutura.id,
            tipo_exportacao=TipoExportacao.LOG_OPERACAO.value,
            ativo=oportunidade_monitor["ativo"],
            strike=oportunidade_monitor["strike"],
            pernas=pernas_resultado,
            classificacao=classificacao.value,
            operacao=operacao,
            pct_ganho=oportunidade_monitor.get("pct_ganho_box", 0.0) if operacao in ("BOX", "BOXSBTH") else oportunidade_monitor.get("pct_ganho_sbth", 0.0),
            pct_cdi=oportunidade_monitor.get("pct_cdi_box", 0.0) if operacao in ("BOX", "BOXSBTH") else oportunidade_monitor.get("pct_cdi_sbth", 0.0),
            dias=oportunidade_monitor.get("dias", 0),
        )

        resultado.boleta = snapshot
        resultado.oportunidade_id = oportunidade_db.id
        return resultado

    @staticmethod
    def _operacao_to_classificacao(operacao: str) -> ClassificacaoOp:
        mapping = {
            "BOX": ClassificacaoOp.BOX_1,
            "SBTH": ClassificacaoOp.SBTH_2,
            "BOXSBTH": ClassificacaoOp.BOXSBTH_3,
        }
        return mapping.get(operacao, ClassificacaoOp.TP_OP)
