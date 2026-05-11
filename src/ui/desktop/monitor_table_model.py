from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor, QBrush, QFont

from src.application.dtos.dtos import OportunidadeMonitor


class MonitorTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Tipo", "label_tipo"),
        ("Rent. vs CDI", "label_rentabilidade"),
        ("Dias", "label_dias"),
        ("Vencimento", "vencimento"),
        ("Strike", "strike"),
        ("Custo SBTH", "custo_sbth_display"),
        ("Custo BOX", "custo_box_display"),
        ("Ganho %", "ganho_display"),
        ("Cod Put", "cod_put"),
        ("Cod Call", "cod_call"),
        ("Viável", "viavel_display"),
    ]

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
            return self._background_data(opp)

        if role == Qt.ForegroundRole:
            return self._foreground_data(opp, col_key)

        if role == Qt.FontRole:
            return self._font_data(opp, col_key)

        if role == Qt.TextAlignmentRole:
            if col_key in ("strike", "custo_sbth_display", "custo_box_display", "ganho_display", "label_dias", "viavel_display"):
                return Qt.AlignRight | Qt.AlignVCenter
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
        if col_key == "viavel_display":
            return "SIM" if opp.viavel else "-"
        value = getattr(opp, col_key, None)
        if value is None:
            return ""
        return str(value)

    def _background_data(self, opp: OportunidadeMonitor):
        if not opp.viavel:
            return QBrush(QColor(245, 235, 235))
        if opp.classificacao == "1BOX":
            return QBrush(QColor(230, 245, 230))
        if opp.classificacao == "2SBTH":
            return QBrush(QColor(230, 240, 255))
        if opp.classificacao == "3BOXSBTH":
            return QBrush(QColor(230, 245, 245))
        return None

    def _foreground_data(self, opp: OportunidadeMonitor, col_key: str):
        is_box = opp.classificacao in ("1BOX", "3BOXSBTH")
        is_sbth = opp.classificacao in ("2SBTH", "3BOXSBTH")

        if col_key == "viavel_display" and opp.viavel:
            return QBrush(QColor(0, 128, 0))

        if col_key == "custo_sbth_display" and not is_sbth and opp.custo_sbth > 0:
            return QBrush(QColor(180, 180, 180))
        if col_key == "custo_box_display" and not is_box and opp.custo_box > 0:
            return QBrush(QColor(180, 180, 180))

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
        return None

    def _item_key(self, opp: OportunidadeMonitor) -> int:
        return opp.instrumento_id

    def atualizar(self, oportunidades: list[OportunidadeMonitor]):
        new_key_map = {}
        for i, opp in enumerate(oportunidades):
            new_key_map[self._item_key(opp)] = i

        old_count = len(self._oportunidades)
        new_count = len(oportunidades)

        if old_count == 0:
            self.beginInsertRows(QModelIndex(), 0, new_count - 1)
            self._oportunidades = oportunidades
            self._key_map = new_key_map
            self.endInsertRows()
            return

        if new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._oportunidades = oportunidades
            self._key_map = new_key_map
            self.endInsertRows()
        elif new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            self._oportunidades = oportunidades
            self._key_map = new_key_map
            self.endRemoveRows()

        self._oportunidades = oportunidades
        self._key_map = new_key_map

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(new_count - 1, self.columnCount() - 1),
        )

    def get_oportunidade(self, row: int) -> OportunidadeMonitor | None:
        if 0 <= row < len(self._oportunidades):
            return self._oportunidades[row]
        return None
