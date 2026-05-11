from dataclasses import dataclass


@dataclass
class DadosMercado:
    preco_ativo: float
    of_compra_ativo: float
    of_venda_ativo: float
    of_compra_put: float
    of_venda_put: float
    of_compra_call: float
    of_venda_call: float
    strike: float
    premio_put: float
    premio_call: float
    dias: int
    em_leilao: bool = False
    status_put: str = ""
    status_call: str = ""
    status_ativo: str = ""


@dataclass
class ResultadoBOXSBTH:
    custo_sbth: float
    ganho_sbth: float
    custo_box: float
    ganho_box: float
    cdi_periodo: float
    classificacao: str
    operacao: str


class CalculadoraBoxSbth:
    def __init__(self, taxa_cdi: float, premio_risco_box: float, premio_risco_sbth: float):
        self.taxa_cdi = taxa_cdi
        self.premio_risco_box = premio_risco_box
        self.premio_risco_sbth = premio_risco_sbth

    def calcular_cdi_periodo(self, dias: int) -> float:
        if dias <= 0:
            return 0.0
        return ((1 + self.taxa_cdi) ** (dias / 252) - 1)

    def calcular(self, dados: DadosMercado) -> ResultadoBOXSBTH:
        cdi_periodo = self.calcular_cdi_periodo(dados.dias)

        custo_sbth = dados.strike + dados.premio_put - dados.premio_call
        ganho_sbth_bruto = dados.strike * cdi_periodo
        ganho_sbth = ganho_sbth_bruto - abs(custo_sbth) * (self.premio_risco_sbth / 100) if custo_sbth > 0 else ganho_sbth_bruto

        custo_box = dados.premio_call - dados.premio_put
        ganho_box_bruto = dados.strike - dados.preco_ativo + custo_box if custo_box < 0 else custo_box
        ganho_box = ganho_box_bruto - abs(custo_box) * (self.premio_risco_box / 100) if custo_box > 0 else ganho_box_bruto

        classificacao = self._classificar(custo_sbth, ganho_sbth, custo_box, ganho_box)
        operacao = self._determinar_operacao(classificacao, ganho_sbth, ganho_box)

        return ResultadoBOXSBTH(
            custo_sbth=round(custo_sbth, 4),
            ganho_sbth=round(ganho_sbth, 4),
            custo_box=round(custo_box, 4),
            ganho_box=round(ganho_box, 4),
            cdi_periodo=round(cdi_periodo, 6),
            classificacao=classificacao,
            operacao=operacao,
        )

    def _classificar(self, custo_sbth: float, ganho_sbth: float, custo_box: float, ganho_box: float) -> str:
        if custo_box != 0 and ganho_box / abs(custo_box) > 0.5:
            return "1BOX"
        if custo_sbth != 0 and ganho_sbth / abs(custo_sbth) > 0.3:
            return "2SBTH"
        return "TP.Op"

    def _determinar_operacao(self, classificacao: str, ganho_sbth: float, ganho_box: float) -> str:
        if classificacao == "1BOX" and ganho_box > 0:
            return "BOX"
        if classificacao == "2SBTH" and ganho_sbth > 0:
            return "SBTH"
        return "NEUTRA"
