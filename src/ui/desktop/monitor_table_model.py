from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor, QBrush, QFont

from src.application.dtos.dtos import OportunidadeMonitor
from src.ui.desktop.theme import Palette


class MonitorTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Tipo", "label_tipo"),
        ("Ativo", "ativo"),
        ("Strike", "strike"),
        ("Ganho %", "ganho_display"),
        ("Rent. vs CDI", "label_rentabilidade"),
        ("Dias", "label_dias"),
        ("Vencimento", "vencimento"),
        ("Liq", "liq_indicator"),
        ("Leilao", "leilao_display"),
        ("Custo BOX", "custo_box_display"),
        ("Custo SBTH", "custo_sbth_display"),
        ("Liq Put", "liq_put_display"),
        ("Liq Call", "liq_call_display"),
        ("Money", "money_display"),
        ("Of Cp Put", "of_compra_put"),
        ("Of Vd Call", "of_venda_call"),
        ("Qul Put", "qul_put"),
        ("Qul Call", "qul_call"),
        ("Tipo Op.", "tipo_opcao"),
        ("Cod Put", "cod_put"),
        ("Cod Call", "cod_call"),
    ]

    HIDDEN_BY_DEFAULT = {
        "custo_box_display", "custo_sbth_display",
        "liq_put_display", "liq_call_display",
        "money_display",
        "of_compra_put", "of_venda_call",
        "qul_put", "qul_call",
        "tipo_opcao", "cod_put", "cod_call",
        "leilao_display",
    }

    _BG_VIABLE_BOX = QColor(Palette.ROW_BOX)
    _BG_VIABLE_SBTH = QColor(Palette.ROW_SBTH)
    _BG_VIABLE_BOXSBTH = QColor(Palette.ROW_BOXSBTH)
    _BG_NOT_VIABLE = QColor(Palette.ROW_NOT_VIABLE)
    _BG_LEILAO = QColor(Palette.ROW_LEILAO)

    _FG_GREEN = QBrush(QColor(Palette.LIQ_POSITIVE))
    _FG_RED = QBrush(QColor(Palette.LIQ_NEGATIVE))
    _FG_STRIKEOUT = QBrush(QColor(Palette.STRIKEOUT_COLOR))
    _FG_PRIMARY = QBrush(QColor(Palette.TEXT_PRIMARY))
    _FG_MUTED = QBrush(QColor(Palette.TEXT_MUTED))

    _CENTER_COLS = {
        "strike", "custo_sbth_display", "custo_box_display", "ganho_display",
        "label_dias", "leilao_display", "liq_indicator",
        "liq_put_display", "liq_call_display", "of_compra_put", "of_venda_call",
        "qul_put", "qul_call", "money_display", "tipo_opcao",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._oportunidades: list[OportunidadeMonitor] = []
        self._key_map: dict[int, int] = {}

    def rowCount(self, parent=None):
        return len(self._oportunidades)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._oportunidades):
            return None

        opp = self._oportunidades[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.DisplayRole:
            return self._display_data(opp, col_key)

        if role == Qt.BackgroundRole:
            return self._background_data(opp, col_key)

        if role == Qt.ForegroundRole:
            return self._foreground_data(opp, col_key)

        if role == Qt.FontRole:
            return self._font_data(opp, col_key)

        if role == Qt.TextAlignmentRole:
            if col_key in self._CENTER_COLS:
                return Qt.AlignCenter | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def _display_data(self, opp: OportunidadeMonitor, col_key: str):
        if col_key == "label_tipo":
            return opp.label_tipo
        if col_key == "label_rentabilidade":
            return opp.label_rentabilidade
        if col_key == "label_dias":
            return opp.label_dias
        if col_key == "strike":
            return "{:.2f}".format(opp.strike)
        if col_key == "custo_sbth_display":
            return opp.custo_sbth_display
        if col_key == "custo_box_display":
            return opp.custo_box_display
        if col_key == "ganho_display":
            if opp.classificacao in ("1BOX", "3BOXSBTH"):
                return "{:.2f}%".format(opp.pct_ganho_box * 100)
            if opp.classificacao == "2SBTH":
                return "{:.2f}%".format(opp.pct_ganho_sbth * 100)
            return "-"
        if col_key == "leilao_display":
            return "\u26a0 LEILAO" if opp.em_leilao else ""
        if col_key == "liq_indicator":
            put_ok = opp.liq_put_x_lote >= 0
            call_ok = opp.liq_call_x_lote >= 0
            if put_ok and call_ok:
                return "\u2713"
            if not put_ok and not call_ok:
                return "\u2717"
            return "\u2713~"
        if col_key == "liq_put_display":
            return "{:.0f}".format(opp.liq_put_x_lote)
        if col_key == "liq_call_display":
            return "{:.0f}".format(opp.liq_call_x_lote)
        if col_key == "of_compra_put":
            return "{:.2f}".format(opp.of_compra_put) if opp.of_compra_put > 0 else "-"
        if col_key == "of_venda_call":
            return "{:.2f}".format(opp.of_venda_call) if opp.of_venda_call > 0 else "-"
        if col_key == "qul_put":
            return "{:.0f}".format(opp.qul_put) if opp.qul_put > 0 else "-"
        if col_key == "qul_call":
            return "{:.0f}".format(opp.qul_call) if opp.qul_call > 0 else "-"
        if col_key == "money_display":
            return opp.money_display
        if col_key == "tipo_opcao":
            labels = {"A": "AMER", "E": "EUR", "P": "PUT"}
            return labels.get(opp.tipo_opcao, opp.tipo_opcao)
        value = getattr(opp, col_key, None)
        if value is None:
            return ""
        return str(value)

    def _background_data(self, opp: OportunidadeMonitor, col_key: str):
        if opp.em_leilao:
            return QBrush(self._BG_LEILAO)
        if not opp.viavel:
            return QBrush(self._BG_NOT_VIABLE)
        if opp.classificacao == "1BOX":
            return QBrush(self._BG_VIABLE_BOX)
        if opp.classificacao == "2SBTH":
            return QBrush(self._BG_VIABLE_SBTH)
        if opp.classificacao == "3BOXSBTH":
            return QBrush(self._BG_VIABLE_BOXSBTH)
        return None

    def _foreground_data(self, opp: OportunidadeMonitor, col_key: str):
        is_box = opp.classificacao in ("1BOX", "3BOXSBTH")
        is_sbth = opp.classificacao in ("2SBTH", "3BOXSBTH")

        if col_key == "leilao_display" and opp.em_leilao:
            return self._FG_RED

        if col_key == "liq_indicator":
            put_ok = opp.liq_put_x_lote >= 0
            call_ok = opp.liq_call_x_lote >= 0
            if put_ok and call_ok:
                return self._FG_GREEN
            if not put_ok and not call_ok:
                return self._FG_RED
            return QBrush(QColor(Palette.ORANGE))

        if col_key == "liq_put_display":
            return self._FG_RED if opp.liq_put_x_lote < 0 else self._FG_GREEN

        if col_key == "liq_call_display":
            return self._FG_RED if opp.liq_call_x_lote < 0 else self._FG_GREEN

        if col_key == "ganho_display":
            if opp.classificacao in ("1BOX", "3BOXSBTH") and opp.pct_ganho_box > 0:
                return self._FG_GREEN
            if opp.classificacao == "2SBTH" and opp.pct_ganho_sbth > 0:
                return self._FG_GREEN
            return self._FG_MUTED

        if col_key == "label_tipo":
            if opp.classificacao == "1BOX":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            if opp.classificacao == "2SBTH":
                return QBrush(QColor(Palette.CYAN))
            if opp.classificacao == "3BOXSBTH":
                return QBrush(QColor(Palette.PURPLE))
            return self._FG_MUTED

        if col_key == "label_rentabilidade":
            if opp.pct_cdi_box > 0 or opp.pct_cdi_sbth > 0:
                return QBrush(QColor(Palette.YELLOW))
            return self._FG_MUTED

        if col_key == "custo_sbth_display" and not is_sbth and opp.custo_sbth > 0:
            return self._FG_STRIKEOUT
        if col_key == "custo_box_display" and not is_box and opp.custo_box > 0:
            return self._FG_STRIKEOUT

        if not opp.viavel and col_key not in ("leilao_display", "label_tipo", "liq_indicator"):
            return self._FG_MUTED

        return None

    def _font_data(self, opp: OportunidadeMonitor, col_key: str):
        is_box = opp.classificacao in ("1BOX", "3BOXSBTH")
        is_sbth = opp.classificacao in ("2SBTH", "3BOXSBTH")

        needs_strikethrough = (
            (col_key == "custo_sbth_display" and not is_sbth and opp.custo_sbth > 0)
            or (col_key == "custo_box_display" and not is_box and opp.custo_box > 0)
        )
        if needs_strikethrough:
            font = QFont()
            font.setStrikeOut(True)
            return font

        if col_key == "leilao_display" and opp.em_leilao:
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "label_tipo":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "ganho_display":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "liq_indicator":
            font = QFont()
            font.setBold(True)
            font.setPointSize(11)
            return font

        return None

    def _item_key(self, opp: OportunidadeMonitor) -> int:
        return opp.instrumento_id

    def atualizar(self, oportunidades: list[OportunidadeMonitor]):
        self.layoutAboutToBeChanged.emit()
        self._oportunidades = oportunidades
        self._key_map = {self._item_key(opp): i for i, opp in enumerate(oportunidades)}
        self.layoutChanged.emit()

    @staticmethod
    def _opp_equal(a: OportunidadeMonitor, b: OportunidadeMonitor) -> bool:
        return (
            a.viavel == b.viavel
            and a.classificacao == b.classificacao
            and a.em_leilao == b.em_leilao
            and a.pct_ganho_box == b.pct_ganho_box
            and a.pct_ganho_sbth == b.pct_ganho_sbth
            and a.pct_cdi_box == b.pct_cdi_box
            and a.pct_cdi_sbth == b.pct_cdi_sbth
            and a.of_venda_put == b.of_venda_put
            and a.of_compra_call == b.of_compra_call
            and a.liq_put_x_lote == b.liq_put_x_lote
            and a.liq_call_x_lote == b.liq_call_x_lote
            and a.preco_compra_ativo == b.preco_compra_ativo
            and a.qul_put == b.qul_put
            and a.qul_call == b.qul_call
        )

    def get_oportunidade(self, row: int) -> OportunidadeMonitor | None:
        if 0 <= row < len(self._oportunidades):
            return self._oportunidades[row]
        return None
