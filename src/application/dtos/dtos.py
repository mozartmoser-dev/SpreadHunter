from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class TipoExportacao(Enum):
    BASKET_ITM = "BASKET_ITM"
    LOG_OPERACAO = "LOG_OPERACAO"


@dataclass(slots=True)
class ImportarResultado:
    total_importados: int
    total_removidos: int
    ativos: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OportunidadeMonitor:
    instrumento_id: int
    ativo: str
    strike: float
    vencimento: date
    dias: int
    cod_put: str
    cod_call: str
    tipo_opcao: str
    classificacao: str = ""
    operacao: str = ""
    custo_sbth: float = 0.0
    pct_ganho_sbth: float = 0.0
    pct_cdi_sbth: float = 0.0
    pct_cdi_sbth_liquido: float = 0.0
    custo_box: float = 0.0
    pct_ganho_box: float = 0.0
    pct_cdi_box: float = 0.0
    pct_cdi_box_liquido: float = 0.0
    pct_ganho_sbth_bruto: float = 0.0
    pct_ganho_sbth_liquido: float = 0.0
    pct_cdi_sbth_bruto: float = 0.0
    pct_ganho_box_bruto: float = 0.0
    pct_ganho_box_liquido: float = 0.0
    pct_cdi_box_bruto: float = 0.0
    cdi_periodo: float = 0.0
    viavel: bool = False
    preco_compra_ativo: float = 0.0
    of_venda_put: float = 0.0
    of_compra_call: float = 0.0
    em_leilao: bool = False
    liq_put_x_lote: float = 0.0
    liq_call_x_lote: float = 0.0
    of_compra_put: float = 0.0
    of_venda_call: float = 0.0
    qul_put: float = 0.0
    qul_call: float = 0.0
    money_put: float = 0.0
    money_call: float = 0.0
    taxa_aluguel: float = 0.0
    detectado_em: datetime | None = None
    ts_ativo_ask: float | None = None
    ts_ativo_bid: float | None = None
    ts_put_ask: float | None = None
    ts_call_bid: float | None = None
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
    def idade_put_ask(self) -> float | None:
        import time
        if self.ts_put_ask is None:
            return None
        return time.time() - self.ts_put_ask

    @property
    def idade_call_bid(self) -> float | None:
        import time
        if self.ts_call_bid is None:
            return None
        return time.time() - self.ts_call_bid

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
        partes: list[str] = []
        idade = self.idade_ativo_ask
        if idade is not None and idade > 10:
            partes.append(f"preço {int(idade)}s atrás")
        origem = self.label_origem
        if origem:
            partes.append(origem)
        if partes:
            return f"{base} ({', '.join(partes)})"
        return base

    @property
    def custo_sbth_display(self) -> str:
        if self.custo_sbth > 0:
            return "{:.2f}".format(self.custo_sbth)
        return "-"

    @property
    def custo_box_display(self) -> str:
        if self.custo_box > 0:
            return "{:.2f}".format(self.custo_box)
        return "-"

    @property
    def is_box(self) -> bool:
        return self.classificacao in ("1BOX", "3BOXSBTH")

    @property
    def is_sbth(self) -> bool:
        return self.classificacao in ("2SBTH", "3BOXSBTH")

    @property
    def label_tipo(self) -> str:
        labels = {"1BOX": "BOX", "2SBTH": "SBTH", "3BOXSBTH": "BOX+SBTH", "TP.Op": "Outras"}
        return labels.get(self.classificacao, self.classificacao)

    @property
    def label_rentabilidade(self) -> str:
        if self.classificacao == "1BOX":
            base = "{:.2f}x CDI (BOX)".format(self.pct_cdi_box)
        elif self.classificacao == "2SBTH":
            base = "{:.2f}x CDI (SBTH)".format(self.pct_cdi_sbth)
        elif self.classificacao == "3BOXSBTH":
            base = "{:.2f}x CDI".format(max(self.pct_cdi_box, self.pct_cdi_sbth))
        else:
            max_cdi = max(self.pct_cdi_box, self.pct_cdi_sbth)
            base = f"{max_cdi:.2f}x CDI"
        cdi_liq = max(self.pct_cdi_box_liquido, self.pct_cdi_sbth_liquido)
        if cdi_liq > 0:
            return f"{base} (liq: {cdi_liq:.2f}x)"
        return base

    @property
    def ganho_bruto_display(self) -> str:
        if self.classificacao == "1BOX":
            return "{:.2f}% (BOX)".format(self.pct_ganho_box_bruto * 100)
        if self.classificacao == "2SBTH":
            return "{:.2f}% (SBTH)".format(self.pct_ganho_sbth_bruto * 100)
        if self.classificacao == "3BOXSBTH":
            return "{:.2f}% (SBTH) | {:.2f}% (BOX)".format(
                self.pct_ganho_sbth_bruto * 100, self.pct_ganho_box_bruto * 100
            )
        return "-"

    @property
    def ganho_liq_display(self) -> str:
        if self.classificacao == "1BOX":
            return "{:.2f}% (BOX)".format(self.pct_ganho_box_liquido * 100)
        if self.classificacao == "2SBTH":
            return "{:.2f}% (SBTH)".format(self.pct_ganho_sbth_liquido * 100)
        if self.classificacao == "3BOXSBTH":
            return "{:.2f}% (SBTH) | {:.2f}% (BOX)".format(
                self.pct_ganho_sbth_liquido * 100, self.pct_ganho_box_liquido * 100
            )
        return "-"

    @property
    def rent_cdi_bruto_display(self) -> str:
        if self.classificacao == "1BOX":
            return "{:.0f}% CDI (BOX)".format(self.pct_cdi_box_bruto * 100)
        if self.classificacao == "2SBTH":
            return "{:.0f}% CDI (SBTH)".format(self.pct_cdi_sbth_bruto * 100)
        if self.classificacao == "3BOXSBTH":
            return "{:.0f}% CDI (SBTH) | {:.0f}% CDI (BOX)".format(
                self.pct_cdi_sbth_bruto * 100, self.pct_cdi_box_bruto * 100
            )
        return "-"

    @property
    def rent_cdi_liq_display(self) -> str:
        if self.classificacao == "1BOX":
            return "{:.0f}% CDI (BOX)".format(self.pct_cdi_box_liquido * 100)
        if self.classificacao == "2SBTH":
            return "{:.0f}% CDI (SBTH)".format(self.pct_cdi_sbth_liquido * 100)
        if self.classificacao == "3BOXSBTH":
            return "{:.0f}% CDI (SBTH) | {:.0f}% CDI (BOX)".format(
                self.pct_cdi_sbth_liquido * 100, self.pct_cdi_box_liquido * 100
            )
        return "-"

    @property
    def label_dias(self) -> str:
        return "{}d".format(self.dias)

    @property
    def money_display(self) -> str:
        parts = []
        if self.money_put > 0:
            parts.append("P:{:.2f}".format(self.money_put))
        if self.money_call > 0:
            parts.append("C:{:.2f}".format(self.money_call))
        return " | ".join(parts) if parts else "-"

    @property
    def resumo_linha(self) -> str:
        from datetime import date
        venc_str = self.vencimento.strftime("%d/%m/%Y") if isinstance(self.vencimento, date) else str(self.vencimento)
        return "{} | {} {} | {} | {} | %ganho={:.2f}%".format(
            self.ativo, self.label_tipo, self.label_dias,
            venc_str, self.label_rentabilidade,
            (self.pct_ganho_box * 100) if self.classificacao in ("1BOX", "3BOXSBTH") else (self.pct_ganho_sbth * 100),
        )


@dataclass(slots=True)
class BasketGerada:
    estrutura_id: int
    tipo: str
    ativo: str
    strike_atm: float
    strike_itm: float
    pernas: list[dict] = field(default_factory=list)
    coefic_alvo: float = 0.0
    coefic_mercado: float = 0.0


@dataclass(slots=True)
class ExportarResultado:
    estrutura_id: int
    tipo_exportacao: str
    ativo: str
    strike: float
    pernas: list[dict] = field(default_factory=list)
    classificacao: str = ""
    operacao: str = ""
    pct_ganho: float = 0.0
    pct_cdi: float = 0.0
    dias: int = 0
    exportado_em: str = ""
    boleta: dict = field(default_factory=dict)
    oportunidade_id: int = 0


@dataclass(slots=True)
class EngineStatsDTO:
    scan_time_ms: int
    cpu_pct: float
    mem_mb: float
    total_instrumentos: int
    monitored_onda1: int
    monitored_onda2: int
    threads_count: int = 1
    engine_type: str = "NumPy Vectorized"
    registrado: bool = False
    progresso_idx: int = 0
    dados_stale: bool = False
    ultimo_refresh_ha_segundos: int = -1
    ciclos_sem_dados: int = 0
