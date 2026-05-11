from PyQt5.QtCore import Qt, QAbstractTableModel, QVariant
from PyQt5.QtGui import QColor, QBrush

from src.application.dtos.dtos import OportunidadeMonitor


class MonitorTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Tipo", "label_tipo"),
        ("Rent. vs CDI", "label_rentabilidade"),
        ("Dias", "label_dias"),
        ("Vencimento", "vencimento"),
        ("Strike", "strike"),
        ("Cod Put", "cod_put"),
        ("Cod Call", "cod_call"),
        ("Ganho", "ganho_display"),
        ("Viável", "viavel_display"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._oportunidades: list[OportunidadeMonitor] = []

    def rowCount(self, parent=None):
        return len(self._oportunidades)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal and 0 <= section < len(self.COLUMNS):
            return self.COLUMNS[section][0]
        return QVariant()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._oportunidades):
            return QVariant()

        opp = self._oportunidades[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.DisplayRole:
            if col_key == "label_tipo":
                return opp.label_tipo
            if col_key == "label_rentabilidade":
                return opp.label_rentabilidade
            if col_key == "label_dias":
                return opp.label_dias
            if col_key == "ganho_display":
                if opp.classificacao == "1BOX":
                    return "{:.2f}".format(opp.ganho_box)
                if opp.classificacao == "2SBTH":
                    return "{:.2f}".format(opp.ganho_sbth)
                return "-"
            if col_key == "viavel_display":
                return "SIM" if opp.viavel else ""
            value = getattr(opp, col_key, "")
            return str(value)

        if role == Qt.BackgroundRole:
            if not opp.viavel:
                return QBrush(QColor(245, 235, 235))
            if opp.classificacao == "1BOX":
                return QBrush(QColor(230, 245, 230))
            if opp.classificacao == "2SBTH":
                return QBrush(QColor(230, 240, 255))
            return QVariant()

        if role == Qt.ForegroundRole:
            if col_key == "viavel_display" and opp.viavel:
                return QBrush(QColor(0, 128, 0))
            return QVariant()

        if role == Qt.TextAlignmentRole:
            if col_key in ("strike", "ganho_display", "label_dias", "viavel_display"):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return QVariant()

    def atualizar(self, oportunidades: list[OportunidadeMonitor]):
        self.beginResetModel()
        self._oportunidades = oportunidades
        self.endResetModel()

    def get_oportunidade(self, row: int) -> OportunidadeMonitor | None:
        if 0 <= row < len(self._oportunidades):
            return self._oportunidades[row]
        return None
