from PyQt5.QtCore import QAbstractTableModel, QVariant, Qt
from PyQt5.QtGui import QColor


class MppTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Box", "box"),
        ("Score", "score"),
        ("Nível", "nivel"),
        ("Isca", "isca"),
        ("IP", "ip"),
        ("Lote Sug.", "lote"),
        ("Confiança", "confianca"),
        ("Persistência", "persistencia"),
        ("Spread Médio", "spread"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._data):
            return QVariant()
        row = self._data[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.DisplayRole:
            val = row.get(col_key, "")
            if val is None:
                return QVariant()
            return str(val)

        if role == Qt.TextAlignmentRole:
            if col_key in ("score", "ip", "confianca", "lote", "persistencia", "spread"):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ForegroundRole:
            nivel = row.get("nivel", "")
            if nivel == "crítico":
                return QColor("#ef4444")
            elif nivel == "alto":
                return QColor("#f59e0b")
            elif nivel == "médio":
                return QColor("#22d3ee")
            return QVariant()

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section][0]
        return QVariant()

    def atualizar(self, boxes: list, mres: list):
        mre_map = {}
        for m in mres:
            key = (m.ativo, m.strike1, m.strike2)
            mre_map[key] = m

        novos = []
        for b in boxes:
            key = (b.ativo, b.strike1, b.strike2)
            m = mre_map.get(key)
            nivel = b.nivel_risco
            if b.nivel_risco == "crítico":
                nivel = "crítico"
            elif b.nivel_risco == "alto":
                nivel = "alto"
            elif b.nivel_risco == "médio":
                nivel = "médio"
            else:
                nivel = "baixo"

            novos.append({
                "ativo": b.ativo,
                "box": f"{b.strike1:.0f}x{b.strike2:.0f}",
                "score": f"{b.score_final_pct:.0f}",
                "nivel": nivel,
                "isca": m.isca_recomendada if m else "",
                "ip": f"{m.ip_isca:.0f}" if m else "",
                "lote": str(m.lote_sugerido) if m else "",
                "confianca": f"{m.confianca_completar:.0%}" if m else "",
                "persistencia": f"{b.persistencia_ciclos}c" if b.persistencia_ciclos > 0 else "",
                "spread": f"{b.spread_medio:.1%}" if b.spread_medio > 0 else "",
                "_box": b,
                "_mre": m,
            })

        self.beginResetModel()
        self._data = novos
        self.endResetModel()

    def get_box(self, row: int):
        if 0 <= row < len(self._data):
            return self._data[row].get("_box")
        return None

    def get_mre(self, row: int):
        if 0 <= row < len(self._data):
            return self._data[row].get("_mre")
        return None
