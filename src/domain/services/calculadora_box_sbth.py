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
    vov_put_boca: float = 0.0
    voc_call_boca: float = 0.0
    qul_put: float = 0.0
    qul_call: float = 0.0

    @property
    def preco_compra_ativo(self) -> float:
        if self.of_venda_ativo > 0:
            return self.of_venda_ativo
        return self.preco_ativo + 0.01


@dataclass
class ResultadoBOXSBTH:
    custo_sbth: float
    pct_ganho_sbth: float
    pct_cdi_sbth: float
    custo_box: float
    pct_ganho_box: float
    pct_cdi_box: float
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
        return (1 + self.taxa_cdi) ** (dias / 365) - 1

    def calcular(self, dados: DadosMercado) -> ResultadoBOXSBTH:
        cdi_periodo = self.calcular_cdi_periodo(dados.dias)

        custo_sbth = self._calcular_custo_sbth(dados)
        pct_ganho_sbth = self._calcular_pct_ganho_sbth(custo_sbth, dados.strike)
        pct_cdi_sbth = self._calcular_pct_cdi(pct_ganho_sbth, cdi_periodo)

        custo_box = self._calcular_custo_box(dados)
        pct_ganho_box = self._calcular_pct_ganho_box(custo_box, dados.strike)
        pct_cdi_box = self._calcular_pct_cdi(pct_ganho_box, cdi_periodo)

        classificacao = self._classificar(pct_cdi_box, pct_cdi_sbth)
        operacao = self._determinar_operacao(classificacao, pct_ganho_sbth, pct_ganho_box)

        return ResultadoBOXSBTH(
            custo_sbth=round(custo_sbth, 4),
            pct_ganho_sbth=round(pct_ganho_sbth, 6),
            pct_cdi_sbth=round(pct_cdi_sbth, 6),
            custo_box=round(custo_box, 4),
            pct_ganho_box=round(pct_ganho_box, 6),
            pct_cdi_box=round(pct_cdi_box, 6),
            cdi_periodo=round(cdi_periodo, 6),
            classificacao=classificacao,
            operacao=operacao,
        )

    def _calcular_custo_sbth(self, dados: DadosMercado) -> float:
        if dados.of_venda_put <= 0:
            return 0.0
        return dados.preco_compra_ativo + dados.of_venda_put

    def _calcular_pct_ganho_sbth(self, custo: float, strike: float) -> float:
        if custo <= 0:
            return 0.0
        return (strike - custo) / custo

    def _calcular_custo_box(self, dados: DadosMercado) -> float:
        if dados.of_venda_put <= 0 or dados.of_compra_call <= 0:
            return 0.0
        return dados.preco_compra_ativo + dados.of_venda_put - dados.of_compra_call

    def _calcular_pct_ganho_box(self, custo: float, strike: float) -> float:
        if custo <= 0:
            return 0.0
        return (strike - custo) / custo

    def _calcular_pct_cdi(self, pct_ganho: float, cdi_periodo: float) -> float:
        if cdi_periodo <= 0:
            return 0.0
        return pct_ganho / cdi_periodo

    def _classificar(self, pct_cdi_box: float, pct_cdi_sbth: float) -> str:
        box = 0
        sbth = 0
        if pct_cdi_box > self.premio_risco_box:
            box = 1
        if pct_cdi_sbth > self.premio_risco_sbth:
            sbth = 2
        tp_op = box + sbth
        if tp_op == 3:
            return "3BOXSBTH"
        if tp_op == 1:
            return "1BOX"
        if tp_op == 2:
            return "2SBTH"
        return "TP.Op"

    def _determinar_operacao(self, classificacao: str, pct_ganho_sbth: float, pct_ganho_box: float) -> str:
        if classificacao == "1BOX" and pct_ganho_box > 0:
            return "BOX"
        if classificacao == "2SBTH" and pct_ganho_sbth > 0:
            return "SBTH"
        if classificacao == "3BOXSBTH" and pct_ganho_box > 0 and pct_ganho_sbth > 0:
            return "BOXSBTH"
        return "NEUTRA"
