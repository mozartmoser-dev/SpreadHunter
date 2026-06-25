from dataclasses import dataclass

from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


@dataclass(slots=True)
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
        return 0.0


@dataclass(slots=True)
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
    pct_cdi_sbth_liquido: float = 0.0
    pct_cdi_box_liquido: float = 0.0


class CalculadoraBoxSbth:
    def __init__(self, taxa_cdi: float, premio_risco_box: float, premio_risco_sbth: float,
                 taxa_emolumento: float | None = None, taxa_liquidacao: float | None = None,
                 taxa_ir: float | None = None):
        self.taxa_cdi = taxa_cdi
        self.premio_risco_box = premio_risco_box
        self.premio_risco_sbth = premio_risco_sbth
        self.custos_b3 = CalculadoraCustosB3(taxa_emolumento, taxa_liquidacao, taxa_ir)

    def calcular_cdi_periodo(self, dias_uteis: int) -> float:
        if dias_uteis <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (dias_uteis / 252) - 1

    def calcular(self, dados: DadosMercado) -> ResultadoBOXSBTH:
        cdi_periodo = self.calcular_cdi_periodo(dc_to_du(None, None, dados.dias))

        custo_sbth = self._calcular_custo_sbth(dados)
        ganho_sbth_bruto = dados.strike - custo_sbth if custo_sbth > 0 else 0
        custo_b3_sbth = (self.custos_b3.custos_opcao(dados.of_venda_put, n_pernas=1) +
                         self.custos_b3.custos_stock(dados.preco_compra_ativo, n_acoes=1))
        ganho_sbth = ganho_sbth_bruto - custo_b3_sbth
        ir_sbth = self.custos_b3.ajustar_ir(max(ganho_sbth, 0.0))
        ganho_sbth_liq = ganho_sbth - ir_sbth
        pct_ganho_sbth_bruto = ganho_sbth_bruto / custo_sbth if custo_sbth > 0 else 0.0
        pct_ganho_sbth = ganho_sbth / custo_sbth if custo_sbth > 0 else 0.0
        pct_ganho_sbth_liq = ganho_sbth_liq / custo_sbth if custo_sbth > 0 else 0.0
        pct_cdi_sbth_bruto = self._calcular_pct_cdi(pct_ganho_sbth_bruto, cdi_periodo)
        pct_cdi_sbth = self._calcular_pct_cdi(pct_ganho_sbth, cdi_periodo)
        pct_cdi_sbth_liquido = self._calcular_pct_cdi(pct_ganho_sbth_liq, cdi_periodo)

        custo_box = self._calcular_custo_box(dados)
        ganho_box_bruto = dados.strike - custo_box
        premio_medio_box = (dados.of_venda_put + dados.of_compra_call) / 2
        custo_b3_box = (self.custos_b3.custos_opcao(premio_medio_box, n_pernas=2) +
                        self.custos_b3.custos_stock(dados.preco_compra_ativo, n_acoes=1))
        ganho_box = ganho_box_bruto - custo_b3_box
        ir_box = self.custos_b3.ajustar_ir(max(ganho_box, 0.0))
        ganho_box_liq = ganho_box - ir_box
        pct_ganho_box_bruto = ganho_box_bruto / max(custo_box, 0.01) if custo_box != 0 else 0.0
        pct_ganho_box = ganho_box / max(custo_box, 0.01) if custo_box != 0 else 0.0
        pct_ganho_box_liq = ganho_box_liq / max(custo_box, 0.01) if custo_box != 0 else 0.0
        pct_cdi_box_bruto = self._calcular_pct_cdi(pct_ganho_box_bruto, cdi_periodo)
        pct_cdi_box = self._calcular_pct_cdi(pct_ganho_box, cdi_periodo)
        pct_cdi_box_liquido = self._calcular_pct_cdi(pct_ganho_box_liq, cdi_periodo)

        classificacao = self._classificar(pct_cdi_box_bruto, pct_cdi_sbth_bruto)
        operacao = self._determinar_operacao(classificacao, pct_ganho_sbth, pct_ganho_box)

        return ResultadoBOXSBTH(
            custo_sbth=round(custo_sbth, 4),
            pct_ganho_sbth=round(pct_ganho_sbth, 6),
            pct_cdi_sbth=round(pct_cdi_sbth, 6),
            pct_cdi_sbth_liquido=round(pct_cdi_sbth_liquido, 6),
            custo_box=round(custo_box, 4),
            pct_ganho_box=round(pct_ganho_box, 6),
            pct_cdi_box=round(pct_cdi_box, 6),
            pct_cdi_box_liquido=round(pct_cdi_box_liquido, 6),
            cdi_periodo=round(cdi_periodo, 6),
            classificacao=classificacao,
            operacao=operacao,
        )

    def _calcular_custo_sbth(self, dados: DadosMercado) -> float:
        if dados.of_venda_put <= 0 or dados.preco_compra_ativo <= 0:
            return 0.0
        return dados.preco_compra_ativo + dados.of_venda_put

    def _calcular_custo_box(self, dados: DadosMercado) -> float:
        if dados.of_venda_put <= 0 or dados.of_compra_call <= 0 or dados.preco_compra_ativo <= 0:
            return 0.0
        return dados.preco_compra_ativo + dados.of_venda_put - dados.of_compra_call

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
