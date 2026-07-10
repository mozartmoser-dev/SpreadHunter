from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QColor, QBrush, QFont

from src.application.dtos.dtos_venda_coberta import OportunidadeVendaCoberta
from src.ui.desktop.theme import Palette


class VendaCobertaTableModel(QAbstractTableModel):
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

    _BG_VIABLE = QColor(Palette.ROW_BOX)
    _BG_NOT_VIABLE = QColor(Palette.ROW_NOT_VIABLE)
    _BG_LEILAO = QColor(Palette.ROW_LEILAO)
    _FG_GREEN = QBrush(QColor(Palette.LIQ_POSITIVE))
    _FG_RED = QBrush(QColor(Palette.LIQ_NEGATIVE))
    _FG_ORANGE = QBrush(QColor(Palette.ORANGE))
    _FG_PRIMARY = QBrush(QColor(Palette.TEXT_PRIMARY))
    _FG_MUTED = QBrush(QColor(Palette.TEXT_MUTED))
    _FG_YELLOW = QBrush(QColor(Palette.YELLOW))
    _FG_TIPO = QBrush(QColor(Palette.CYAN))

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
        self._items: list[OportunidadeVendaCoberta] = []

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
                "label_tipo": "TAXA: vende ativo (bid) + compra CALL (ask).",
                "ativo": "Codigo da acao objeto.",
                "strike": "Preco de exercicio da CALL comprada (cobertura).",
                "ganho_bruto_display": "Ganho percentual BRUTO — sem descontar taxas B3 nem IR.",
                "ganho_liq_display": "Ganho percentual LIQUIDO — B3 e IR descontados.",
                "rent_cdi_bruto_display": "Rentabilidade BRUTA comparada ao CDI do periodo.",
                "rent_cdi_liq_display": "Rentabilidade LIQUIDA comparada ao CDI.",
                "label_dias": "Dias corridos ate o vencimento.",
                "vencimento": "Data de expiracao da CALL.",
                "liq_indicator": "Indicador de liquidez da CALL.",
                "leilao_display": "Indica se o ativo esta em leilao.",
                "liq_call_display": "Volume CALL disponivel menos lote minimo exigido.",
                "money_display": "Moneyness (ITM) da CALL.",
                "of_venda_call": "Oferta de venda (ASK) da CALL.",
                "qul_call": "Quantidade de CALL no livro de ofertas.",
                "tipo_opcao": "MOD — estilo da opção: 🇺🇸 = Americana (A) | 🇪🇺 = Europeia (E).",
                "cod_put": "Codigo B3 da PUT (nao usada nesta estrategia).",
                "cod_call": "Codigo B3 da CALL vendida.",
                "taxa_aluguel": "Taxa de aluguel do ativo (BTC).",
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
            if item.em_leilao:
                return QBrush(self._BG_LEILAO)
            if not item.viavel:
                return QBrush(self._BG_NOT_VIABLE)
            return QBrush(self._BG_VIABLE)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "leilao_display" and item.em_leilao:
                return self._FG_RED
            if col_key == "liq_indicator":
                ok = item.liq_call_x_lote >= 0
                return self._FG_GREEN if ok else self._FG_RED
            if col_key == "liq_call_display":
                return self._FG_RED if item.liq_call_x_lote < 0 else self._FG_GREEN
            if col_key == "ganho_bruto_display":
                return self._FG_GREEN if item.pct_ganho_bruto > 0 else self._FG_MUTED
            if col_key == "ganho_liq_display":
                return self._FG_GREEN if item.pct_ganho_liquido > 0 else self._FG_MUTED
            if col_key == "label_tipo":
                return self._FG_TIPO
            if col_key == "rent_cdi_bruto_display":
                return self._FG_YELLOW if item.pct_cdi_bruto > 0 else self._FG_MUTED
            if col_key == "rent_cdi_liq_display":
                return self._FG_YELLOW if item.pct_cdi_liquido > 0 else self._FG_MUTED
            if not item.viavel and col_key not in ("leilao_display", "label_tipo", "liq_indicator"):
                return self._FG_MUTED
            return None

        if role == Qt.ItemDataRole.FontRole:
            if col_key in ("label_tipo", "ganho_bruto_display", "ganho_liq_display",
                           "rent_cdi_bruto_display", "rent_cdi_liq_display", "liq_indicator"):
                font = QFont()
                font.setBold(True)
                return font
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in self._CENTER_COLS:
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def _display(self, item: OportunidadeVendaCoberta, col_key: str):
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
            ok = item.liq_call_x_lote >= 0
            return "\u2713" if ok else "\u2717"
        if col_key == "leilao_display":
            return item.leilao_display
        if col_key == "custo_box_display":
            return item.custo_box_display
        if col_key == "custo_sbth_display":
            return item.custo_sbth_display
        if col_key == "liq_put_display":
            return "-"
        if col_key == "liq_call_display":
            return "{:.0f}".format(item.liq_call_x_lote)
        if col_key == "money_display":
            return item.money_display
        if col_key == "of_compra_put":
            return "-"
        if col_key == "of_venda_call":
            return "{:.2f}".format(item.of_venda_call) if item.of_venda_call > 0 else "-"
        if col_key == "qul_put":
            return "-"
        if col_key == "qul_call":
            return "{:.0f}".format(item.qul_call) if item.qul_call > 0 else "-"
        if col_key == "tipo_opcao":
            bandeiras = {"A": "🇺🇸", "E": "🇪🇺", "P": "🇪🇺"}
            return bandeiras.get(item.tipo_opcao, "-")
        if col_key == "cod_put":
            return item.cod_put
        if col_key == "cod_call":
            return item.cod_call
        if col_key == "taxa_aluguel":
            return "{:.2f}%".format(item.taxa_aluguel)
        if col_key == "label_detectado":
            return item.label_detectado
        return "-"

    def atualizar(self, items: list[OportunidadeVendaCoberta]):
        self.beginResetModel()
        self._items = items
        self.endResetModel()
