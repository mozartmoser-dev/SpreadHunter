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
    ganho_sbth: float = 0.0
    custo_box: float = 0.0
    ganho_box: float = 0.0
    cdi_periodo: float = 0.0
    rent_sbth_vs_cdi: float = 0.0
    rent_box_vs_cdi: float = 0.0
    viavel: bool = False

    @property
    def label_tipo(self) -> str:
        labels = {"1BOX": "BOX", "2SBTH": "SBTH", "TP.Op": "T.Ponto"}
        return labels.get(self.classificacao, self.classificacao)

    @property
    def label_rentabilidade(self) -> str:
        if self.classificacao == "1BOX":
            return "{:.2f}% CDI (BOX)".format(self.rent_box_vs_cdi)
        if self.classificacao == "2SBTH":
            return "{:.2f}% CDI (SBTH)".format(self.rent_sbth_vs_cdi)
        return "-"

    @property
    def label_dias(self) -> str:
        return "{}d".format(self.dias)

    @property
    def resumo_linha(self) -> str:
        return "{} | {} {} | {} | {} | ganho={:.2f}".format(
            self.ativo, self.label_tipo, self.label_dias,
            self.vencimento, self.label_rentabilidade,
            self.ganho_box if self.classificacao == "1BOX" else self.ganho_sbth,
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
    ganho: float = 0.0
    rent_vs_cdi: float = 0.0
    dias: int = 0
    exportado_em: str = ""
    filepath: str = ""
