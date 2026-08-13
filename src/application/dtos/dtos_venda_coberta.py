from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class OportunidadeVendaCoberta:
    ativo: str
    strike: float
    vencimento: date
    dias: int
    cod_put: str
    cod_call: str
    tipo_opcao: str
    classificacao: str = "VENDA_COBERTA"
    recebimento: float = 0.0
    pct_ganho: float = 0.0
    pct_cdi: float = 0.0
    viavel: bool = False
    em_leilao: bool = False
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
    pct_ganho_bruto: float = 0.0
    pct_ganho_liquido: float = 0.0
    pct_cdi_bruto: float = 0.0
    pct_cdi_liquido: float = 0.0
    detectado_em: datetime | None = None
    ts_ativo_ask: float | None = None
    ts_ativo_bid: float | None = None
    ts_origem_ativo: float | None = None
    idade_origem_ativo: float | None = None
    ts_scan: float | None = None
    onda: int | None = None

    @property
    def idade_ativo_ask(self) -> float | None:
        import time
        if self.ts_ativo_ask is None:
            return None
        return time.time() - self.ts_ativo_ask

    @property
    def label_origem(self) -> str:
        if self.idade_origem_ativo is None:
            return ""
        if self.idade_origem_ativo > 10:
            return f"origem {int(self.idade_origem_ativo)}s atrás"
        return f"origem {self.idade_origem_ativo:.1f}s"

    @property
    def label_detectado(self) -> str:
        if self.detectado_em is None:
            return ""
        dt = self.detectado_em
        if dt.tzinfo is None:
            from zoneinfo import ZoneInfo
            dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("America/Sao_Paulo"))
        base = dt.strftime("%d/%m/%Y %H:%M:%S")
        origem = self.label_origem
        return f"{base} ({origem})" if origem else base

    @property
    def label_tipo(self) -> str:
        if self.classificacao == "TAXA_COMPRADA":
            return "COMPRADA"
        return "VENDIDA"

    @property
    def custo_box_display(self) -> str:
        return "-"

    @property
    def custo_sbth_display(self) -> str:
        return "-"

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

    @property
    def ganho_bruto_display(self) -> str:
        return "{:.2f}%".format(self.pct_ganho_bruto * 100)

    @property
    def ganho_liq_display(self) -> str:
        return "{:.2f}%".format(self.pct_ganho_liquido * 100)

    @property
    def rent_cdi_bruto_display(self) -> str:
        return "{:.0f}% CDI".format(self.pct_cdi_bruto * 100)

    @property
    def rent_cdi_liq_display(self) -> str:
        return "{:.0f}% CDI".format(self.pct_cdi_liquido * 100)
