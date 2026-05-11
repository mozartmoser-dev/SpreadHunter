from src.domain.entities.oportunidade import ClassificacaoOp, Oportunidade
from src.domain.services.calculadora_box_sbth import ResultadoBOXSBTH


class ClassificacaoOportunidade:
    @staticmethod
    def classificar(resultado: ResultadoBOXSBTH) -> ClassificacaoOp:
        mapping = {
            "1BOX": ClassificacaoOp.BOX_1,
            "2SBTH": ClassificacaoOp.SBTH_2,
            "TP.Op": ClassificacaoOp.TP_OP,
        }
        return mapping.get(resultado.classificacao, ClassificacaoOp.TP_OP)

    @staticmethod
    def determinar_operacao_viavel(oportunidade: Oportunidade) -> str:
        if oportunidade.classificacao == ClassificacaoOp.BOX_1 and oportunidade.ganho_box > 0:
            return "BOX"
        if oportunidade.classificacao == ClassificacaoOp.SBTH_2 and oportunidade.ganho_sbth > 0:
            return "SBTH"
        if oportunidade.classificacao == ClassificacaoOp.TP_OP:
            return "TP"
        return "NEUTRA"

    @staticmethod
    def filtrar_viaveis(oportunidades: list[Oportunidade]) -> list[Oportunidade]:
        return [op for op in oportunidades if op.operacao in ("BOX", "SBTH")]

    @staticmethod
    def filtrar_por_liquidez(oportunidades: list[Oportunidade], min_liq_put: float = 0, min_liq_call: float = 0) -> list[Oportunidade]:
        return [
            op for op in oportunidades
            if op.liq_put_x_lote >= min_liq_put and op.liq_call_x_lote >= min_liq_call
        ]

    @staticmethod
    def filtrar_sem_leilao(oportunidades: list[Oportunidade]) -> list[Oportunidade]:
        return [op for op in oportunidades if not op.em_leilao]
