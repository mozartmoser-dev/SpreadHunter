from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QColor


COLUMN_TOOLTIPS = {
    "ativo": "Ativo negociado na B3 (ex: PETR4, VALE3)",
    "box": "Par de strikes do Box Spread (K1 x K2)",
    "score": "Score final (0-100). Combina score estrutural (35%) + instantâneo (65%), ajustado por persistência e bônus histórico",
    "nivel": "Nível de risco baseado no score: crítico (≥85), alto (≥70), médio (≥50), baixo (<50)",
    "isca": "Perna recomendada para iniciar a montagem (maior Índice de Pescabilidade)",
    "ip": "Índice de Pescabilidade (0-1). Combina spread (40%), profundidade (30%), persistência (20%) e imbalance (10%)",
    "lote": "Lote sugerido em contratos — baseado no lado mais fraco do book",
    "confianca": "Confiança de completar as 3 pernas restantes após a isca (0-100%)",
    "persistencia": "Ciclos consecutivos com erro de paridade acima do limite (2%)",
    "spread": "Spread médio das 4 pernas do box (bid-ask) em percentual",
    "prof_qtd": "Quantidade mínima de contratos disponíveis entre as 4 pernas (lado mais fraco do book)",
}


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
        ("Prof Mín", "prof_qtd"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._data):
            return None
        row = self._data[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            val = row.get(col_key, "")
            if val is None:
                return None
            return str(val)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("score", "ip", "confianca", "lote", "persistencia", "spread", "prof_qtd"):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            nivel = row.get("nivel", "")
            if nivel == "crítico":
                return QColor("#ef4444")
            elif nivel == "alto":
                return QColor("#f59e0b")
            elif nivel == "médio":
                return QColor("#22d3ee")
            return None

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section][0]
            if role == Qt.ItemDataRole.ToolTipRole:
                return COLUMN_TOOLTIPS.get(self.COLUMNS[section][1], self.COLUMNS[section][0])
        return None

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
                "ip": f"{m.ip_isca * 100:.0f}" if m else "",
                "lote": str(m.lote_sugerido) if m else "",
                "confianca": f"{m.confianca_completar:.0%}" if m else "",
                "persistencia": f"{b.persistencia_ciclos}c" if b.persistencia_ciclos > 0 else "",
                "spread": f"{b.spread_medio:.1%}" if b.spread_medio > 0 else "",
                "prof_qtd": str(b.qtd_min_box) if b.qtd_min_box > 0 else "",
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
