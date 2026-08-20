from dataclasses import dataclass
from datetime import date, datetime

from src.application.dtos.dtos import montar_leilao_label

from src.application.dtos.dtos import montar_leilao_label


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
    pct_ganho_bruto: float = 0.0
    pct_ganho_liquido: float = 0.0
    pct_cdi_bruto: float = 0.0
    pct_cdi_liquido: float = 0.0
    status_put: str = ""
    status_call: str = ""
    status_ativo: str = ""
    detectado_em: datetime | None = None
    ts_ativo_ask: float | None = None
    ts_ativo_bid: float | None = None
    ts_origem_ativo: float | None = None
    ts_time_ativo: float | None = None
    ts_timeng_ativo: float | None = None
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
        if not self.em_leilao:
            return ""
        label = montar_leilao_label(self.status_ativo, self.status_put, self.status_call)
        return "\u26a0 " + label if label else "\u26a0 LEILAO"

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
