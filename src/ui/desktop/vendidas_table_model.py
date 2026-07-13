from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

from src.application.dtos.dtos_vendida import OportunidadeVendida
from src.ui.desktop.flag_icons import flag_icon
from src.ui.desktop.theme import Palette


CUSTOS_DISCLOSURE = (
    "\n\n* Custos projetados incluem estimativa de custos B3 e IR."
)


class VendidasTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Tipo (i)", "label_tipo"),
        ("Ativo (i)", "ativo"),
        ("Strike (i)", "strike"),
        ("GANHO%BRUTO", "ganho_bruto_display"),
        ("GANHO%LIQ", "ganho_liq_display"),
        ("RENT.CDIBRUTO", "rent_cdi_bruto_display"),
        ("RENT.CDILIQ", "rent_cdi_liq_display"),
        ("Dias (i)", "label_dias"),
        ("Vencimento (i)", "vencimento"),
        ("Liq (i)", "liq_indicator"),
        ("Leilao", "leilao_display"),
        ("Custo BOX", "custo_box_display"),
        ("Custo SBTH", "custo_sbth_display"),
        ("Liq Put", "liq_put_display"),
        ("Liq Call", "liq_call_display"),
        ("Money (i)", "money_display"),
        ("Of Cp Put", "of_compra_put"),
        ("Of Vd Call", "of_venda_call"),
        ("Qul Put", "qul_put"),
        ("Qul Call", "qul_call"),
        ("MOD", "tipo_opcao"),
        ("Cod Put", "cod_put"),
        ("Cod Call", "cod_call"),
        ("BTC", "taxa_aluguel"),
        ("Detectado", "label_detectado"),
    ]

    HIDDEN_BY_DEFAULT = {
        "custo_box_display", "custo_sbth_display",
        "liq_put_display", "liq_call_display",
        "money_display",
        "of_compra_put", "of_venda_call",
        "qul_put", "qul_call",
        "cod_put", "cod_call",
        "tipo_opcao",
        "label_detectado",
    }

    _BG_VIABLE_BOX = QColor(Palette.ROW_BOX)
    _BG_VIABLE_SBTH = QColor(Palette.ROW_SBTH)
    _BG_VIABLE_BOXSBTH = QColor(Palette.ROW_BOXSBTH)
    _BG_NOT_VIABLE = QColor(Palette.ROW_NOT_VIABLE)
    _BG_LEILAO = QColor(Palette.ROW_LEILAO)
    _FG_GREEN = QBrush(QColor(Palette.LIQ_POSITIVE))
    _FG_RED = QBrush(QColor(Palette.LIQ_NEGATIVE))
    _FG_ORANGE = QBrush(QColor(Palette.ORANGE))
    _FG_PRIMARY = QBrush(QColor(Palette.TEXT_PRIMARY))
    _FG_MUTED = QBrush(QColor(Palette.TEXT_MUTED))
    _FG_YELLOW = QBrush(QColor(Palette.YELLOW))
    _FG_STRIKEOUT = QBrush(QColor(Palette.TEXT_MUTED))
    _FG_BOX = QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
    _FG_SBTH = QBrush(QColor(Palette.CYAN))
    _FG_BOXSBTH = QBrush(QColor(Palette.PURPLE))

    _CENTER_COLS = {
        "strike", "ganho_bruto_display", "ganho_liq_display",
        "rent_cdi_bruto_display", "rent_cdi_liq_display",
        "label_dias", "vencimento", "liq_indicator", "leilao_display",
        "custo_box_display", "custo_sbth_display",
        "liq_put_display", "liq_call_display", "money_display",
        "of_compra_put", "of_venda_call",
        "qul_put", "qul_call", "tipo_opcao", "taxa_aluguel",
        "label_detectado",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[OportunidadeVendida] = []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or not (0 <= section < len(self.COLUMNS)):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
        if role == Qt.ItemDataRole.ToolTipRole:
            tips = {
                "label_tipo": "Tipo de operacao vendida (BOX VENDIDO ou SBTH VENDIDA).",
                "ativo": "Codigo da acao objeto.",
                "strike": "Preco de exercicio das opcoes.",
                "ganho_bruto_display": "Ganho percentual BRUTO — sem descontar taxas B3 nem IR." + CUSTOS_DISCLOSURE,
                "ganho_liq_display": "Ganho percentual LIQUIDO — B3 e IR descontados." + CUSTOS_DISCLOSURE,
                "rent_cdi_bruto_display": "Rentabilidade BRUTA comparada ao CDI." + CUSTOS_DISCLOSURE,
                "rent_cdi_liq_display": "Rentabilidade LIQUIDA comparada ao CDI." + CUSTOS_DISCLOSURE,
                "label_dias": "Dias corridos ate o vencimento.",
                "vencimento": "Data de expiracao das opcoes.",
                "liq_indicator": "Indicador de liquidez: check se ambas as pernas tem volume suficiente.",
                "leilao_display": "Indica se o ativo esta em leilao.",
                "custo_box_display": "Custo B3 projetado para a operacao Box Vendido." + CUSTOS_DISCLOSURE,
                "custo_sbth_display": "Custo B3 projetado para a operacao SBTH Vendida." + CUSTOS_DISCLOSURE,
                "liq_put_display": "Volume PUT disponivel menos lote minimo exigido.",
                "liq_call_display": "Volume CALL disponivel menos lote minimo exigido.",
                "money_display": "Moneyness (ITM): valor intrinseco de cada perna.",
                "of_compra_put": "Oferta de compra (BID) da PUT.",
                "of_venda_call": "Oferta de venda (ASK) da CALL.",
                "qul_put": "Quantidade de PUT no livro de ofertas.",
                "qul_call": "Quantidade de CALL no livro de ofertas.",
                "tipo_opcao": "MOD — estilo da opção: 🇺🇸 = Americana (A) | 🇪🇺 = Europeia (E).",
                "cod_put": "Codigo B3 da opcao de venda (PUT).",
                "cod_call": "Codigo B3 da opcao de compra (CALL).",
                "taxa_aluguel": "Taxa de aluguel do ativo (BTC - Banco de Títulos e Custódia).",
                "label_detectado": "Data e hora (Brasília) em que o monitor detectou a oportunidade pelo RTD (DD/MM/YYYY HH:MM:SS).",
            }
            return tips.get(self.COLUMNS[section][1])
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(item, col_key)

        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background(item, col_key)

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(item, col_key)

        if role == Qt.ItemDataRole.FontRole:
            return self._font(item, col_key)

        if role == Qt.ItemDataRole.DecorationRole and col_key == "tipo_opcao":
            return flag_icon(item.tipo_opcao)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in self._CENTER_COLS:
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def _display(self, item: OportunidadeVendida, col_key: str):
        if col_key == "label_tipo":
            return item.label_tipo
        if col_key == "ativo":
            return item.ativo
        if col_key == "strike":
            return "{:.2f}".format(item.strike)
        if col_key == "ganho_bruto_display":
            return item.ganho_bruto_display
        if col_key == "ganho_liq_display":
            return item.ganho_liq_display
        if col_key == "rent_cdi_bruto_display":
            return item.rent_cdi_bruto_display
        if col_key == "rent_cdi_liq_display":
            return item.rent_cdi_liq_display
        if col_key == "label_dias":
            return item.label_dias
        if col_key == "vencimento":
            return item.vencimento.strftime("%d/%m/%Y") if hasattr(item.vencimento, "strftime") else str(item.vencimento)
        if col_key == "liq_indicator":
            put_ok = item.liq_put_x_lote >= 0
            call_ok = item.liq_call_x_lote >= 0
            if put_ok and call_ok:
                return "\u2713"
            if not put_ok and not call_ok:
                return "\u2717"
            return "\u2713~"
        if col_key == "leilao_display":
            return item.leilao_display
        if col_key == "custo_box_display":
            return item.custo_box_display
        if col_key == "custo_sbth_display":
            return item.custo_sbth_display
        if col_key == "liq_put_display":
            return "{:.0f}".format(item.liq_put_x_lote)
        if col_key == "liq_call_display":
            return "{:.0f}".format(item.liq_call_x_lote)
        if col_key == "money_display":
            return item.money_display
        if col_key == "of_compra_put":
            return "{:.2f}".format(item.of_compra_put) if item.of_compra_put > 0 else "-"
        if col_key == "of_venda_call":
            return "{:.2f}".format(item.of_venda_call) if item.of_venda_call > 0 else "-"
        if col_key == "qul_put":
            return "{:.0f}".format(item.qul_put) if item.qul_put > 0 else "-"
        if col_key == "qul_call":
            return "{:.0f}".format(item.qul_call) if item.qul_call > 0 else "-"
        if col_key == "tipo_opcao":
            return ""
        if col_key == "cod_put":
            return item.cod_put
        if col_key == "cod_call":
            return item.cod_call
        if col_key == "taxa_aluguel":
            return "{:.2f}%".format(item.taxa_aluguel)
        if col_key == "label_detectado":
            return item.label_detectado
        return "-"

    def _background(self, item: OportunidadeVendida, col_key: str):
        if item.em_leilao:
            return QBrush(self._BG_LEILAO)
        if not item.viavel:
            return QBrush(self._BG_NOT_VIABLE)
        if "BOX" in item.classificacao and "SBTH" not in item.classificacao:
            return QBrush(self._BG_VIABLE_BOX)
        return QBrush(self._BG_VIABLE_SBTH)

    def _foreground(self, item: OportunidadeVendida, col_key: str):
        if col_key == "leilao_display" and item.em_leilao:
            return self._FG_RED

        if col_key == "liq_indicator":
            put_ok = item.liq_put_x_lote >= 0
            call_ok = item.liq_call_x_lote >= 0
            if put_ok and call_ok:
                return self._FG_GREEN
            if not put_ok and not call_ok:
                return self._FG_RED
            return self._FG_ORANGE

        if col_key == "liq_put_display":
            return self._FG_RED if item.liq_put_x_lote < 0 else self._FG_GREEN

        if col_key == "liq_call_display":
            return self._FG_RED if item.liq_call_x_lote < 0 else self._FG_GREEN

        if col_key == "ganho_bruto_display":
            return self._FG_GREEN if item.pct_ganho_bruto > 0 else self._FG_MUTED

        if col_key == "ganho_liq_display":
            return self._FG_GREEN if item.pct_ganho_liquido > 0 else self._FG_MUTED

        if col_key == "label_tipo":
            if "BOX" in item.classificacao and "SBTH" not in item.classificacao:
                return self._FG_BOX
            return self._FG_SBTH

        if col_key == "rent_cdi_bruto_display":
            return self._FG_YELLOW if item.pct_cdi_bruto > 0 else self._FG_MUTED

        if col_key == "rent_cdi_liq_display":
            return self._FG_YELLOW if item.pct_cdi_liquido > 0 else self._FG_MUTED

        if col_key == "custo_box_display":
            if "SBTH" in item.classificacao and "BOX" not in item.classificacao:
                return self._FG_STRIKEOUT
            return self._FG_MUTED if item.custo <= 0 else None

        if col_key == "custo_sbth_display":
            if "BOX" in item.classificacao and "SBTH" not in item.classificacao:
                return self._FG_STRIKEOUT
            return self._FG_MUTED if item.custo <= 0 else None

        if not item.viavel and col_key not in ("leilao_display", "label_tipo", "liq_indicator"):
            return self._FG_MUTED

        return None

    def _font(self, item: OportunidadeVendida, col_key: str):
        is_box = "BOX" in item.classificacao and "SBTH" not in item.classificacao
        is_sbth = "SBTH" in item.classificacao and "BOX" not in item.classificacao

        needs_strikethrough = (
            (col_key == "custo_box_display" and is_sbth)
            or (col_key == "custo_sbth_display" and is_box)
        )

        if needs_strikethrough:
            font = QFont()
            font.setStrikeOut(True)
            return font

        if col_key in ("label_tipo", "ganho_bruto_display", "ganho_liq_display",
                       "rent_cdi_bruto_display", "rent_cdi_liq_display", "liq_indicator"):
            font = QFont()
            font.setBold(True)
            return font

        return None

    def atualizar(self, items: list[OportunidadeVendida]):
        self.beginResetModel()
        self._items = items
        self.endResetModel()
