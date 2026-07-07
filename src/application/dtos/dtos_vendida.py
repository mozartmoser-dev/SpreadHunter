from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class OportunidadeVendida:
    ativo: str
    strike: float
    vencimento: date
    dias: int
    cod_put: str
    cod_call: str
    tipo_opcao: str
    classificacao: str  # "BOX_VENDIDO" or "SBTH_VENDIDA"
    recebimento: float
    pct_ganho: float
    pct_cdi: float
    viavel: bool
    em_leilao: bool
    liq_put_x_lote: float = 0.0
    liq_call_x_lote: float = 0.0
    preco_ativo: float = 0.0
    of_compra_put: float = 0.0
    of_venda_call: float = 0.0
    qul_put: float = 0.0
    qul_call: float = 0.0
    money_put: float = 0.0
    money_call: float = 0.0
    custo: float = 0.0
    taxa_aluguel: float = 0.0

    @property
    def label_tipo(self) -> str:
        labels = {"BOX_VENDIDO": "BOX VENDIDO", "SBTH_VENDIDA": "SBTH VENDIDA"}
        return labels.get(self.classificacao, self.classificacao)

    @property
    def custo_box_display(self) -> str:
        return "{:.2f}".format(self.custo) if self.custo > 0 and "BOX" in self.classificacao else "-"

    @property
    def custo_sbth_display(self) -> str:
        return "{:.2f}".format(self.custo) if self.custo > 0 and "SBTH" in self.classificacao else "-"

    @property
    def money_display(self) -> str:
        parts = []
        if self.money_put > 0:
            parts.append("P:{:.2f}".format(self.money_put))
        if self.money_call > 0:
            parts.append("C:{:.2f}".format(self.money_call))
        return " | ".join(parts) if parts else "-"

    @property
    def label_rentabilidade(self) -> str:
        return "{:.2f}x CDI".format(self.pct_cdi)

    @property
    def label_dias(self) -> str:
        return "{}d".format(self.dias)

    @property
    def ganho_display(self) -> str:
        return "{:.2f}%".format(self.pct_ganho * 100)

    @property
    def leilao_display(self) -> str:
        return "\u26a0 LEILAO" if self.em_leilao else ""
