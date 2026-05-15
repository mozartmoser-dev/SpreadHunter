from dataclasses import dataclass, field
from enum import Enum


class TipoExportacao(Enum):
    BASKET_ITM = "BASKET_ITM"
    LOG_OPERACAO = "LOG_OPERACAO"


@dataclass
class ImportarResultado:
    total_importados: int
    total_removidos: int
    ativos: list[str] = field(default_factory=list)


@dataclass
class OportunidadeMonitor:
    instrumento_id: int
    ativo: str
    strike: float
    vencimento: str
    dias: int
    cod_put: str
    cod_call: str
    tipo_opcao: str
    classificacao: str = ""
    operacao: str = ""
    custo_sbth: float = 0.0
    pct_ganho_sbth: float = 0.0
    pct_cdi_sbth: float = 0.0
    custo_box: float = 0.0
    pct_ganho_box: float = 0.0
    pct_cdi_box: float = 0.0
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
        labels = {"1BOX": "BOX", "2SBTH": "SBTH", "3BOXSBTH": "BOX+SBTH", "TP.Op": "T.Ponto"}
        return labels.get(self.classificacao, self.classificacao)

    @property
    def label_rentabilidade(self) -> str:
        if self.classificacao == "1BOX":
            return "{:.2f}x CDI (BOX)".format(self.pct_cdi_box)
        if self.classificacao == "2SBTH":
            return "{:.2f}x CDI (SBTH)".format(self.pct_cdi_sbth)
        if self.classificacao == "3BOXSBTH":
            return "{:.2f}x CDI".format(max(self.pct_cdi_box, self.pct_cdi_sbth))
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


@dataclass
class BasketGerada:
    estrutura_id: int
    tipo: str
    ativo: str
    strike_atm: float
    strike_itm: float
    pernas: list[dict] = field(default_factory=list)
    coefic_alvo: float = 0.0
    coefic_mercado: float = 0.0


@dataclass
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


@dataclass
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
