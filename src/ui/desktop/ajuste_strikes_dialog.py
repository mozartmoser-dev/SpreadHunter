import time
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableView,
    QAbstractItemView, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFont, QColor, QBrush

from src.domain.services.market_data_source import FieldName
from src.ui.desktop.theme import Palette


class AjusteStrikesTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Ativo", "ativo"),
        ("Código", "cod"),
        ("Strike Banco", "strike_banco"),
        ("Strike OpenFast", "strike_openfast"),
        ("Provento", "provento"),
        ("Data EX", "data_ex"),
        ("Esperado", "esperado"),
    ]

    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key in ("strike_banco", "strike_openfast", "esperado"):
                v = item.get(col_key)
                return "{:.2f}".format(v) if v is not None else "-"
            if col_key == "provento":
                v = item.get(col_key)
                return "{:.4f}".format(v) if v else "-"
            if col_key == "data_ex":
                v = item.get(col_key)
                if v:
                    try:
                        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y")
                    except ValueError:
                        return str(v)
                return "-"
            return str(item.get(col_key, "-"))

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "strike_banco":
                return QBrush(QColor("#e74c3c"))
            if col_key == "strike_openfast":
                return QBrush(QColor("#2ecc71"))
            if col_key == "ativo":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("strike_banco", "strike_openfast", "provento", "esperado"):
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class AjusteStrikesDialog(QDialog):
    def __init__(self, db_path, parent=None, divergencias=None):
        super().__init__(parent)
        self.db_path = db_path
        self.divergencias = divergencias or []
        self.aplicou = False
        self._items = []
        self.setWindowTitle("Ajustar Strikes (divergência por provento)")
        self.setMinimumSize(760, 420)
        self._setup_ui()
        self._consultar()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.lbl_topo = QLabel("Consultando OpenFast...")
        self.lbl_topo.setStyleSheet("font-size: 9.5pt; color: {};".format(Palette.TEXT_PRIMARY))
        layout.addWidget(self.lbl_topo)

        self.table_view = QTableView()
        self.model = AjusteStrikesTableModel()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 9))
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().hide()
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addStretch()

        self.btn_selecionar_todos = QPushButton("☑ Selecionar todos")
        self.btn_selecionar_todos.setEnabled(False)
        self.btn_selecionar_todos.clicked.connect(self._selecionar_todos)
        btn_layout.addWidget(self.btn_selecionar_todos)

        self.btn_aplicar = QPushButton("✔ Aplicar selecionados")
        self.btn_aplicar.setProperty("class", "primary")
        self.btn_aplicar.clicked.connect(self._aplicar)
        self.btn_aplicar.setEnabled(False)
        btn_layout.addWidget(self.btn_aplicar)

        self.btn_aplicar_todos = QPushButton("✔✔ Aplicar todos")
        self.btn_aplicar_todos.setEnabled(False)
        self.btn_aplicar_todos.clicked.connect(self._aplicar_todos)
        btn_layout.addWidget(self.btn_aplicar_todos)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def _obter_source(self):
        parent = self.parent()
        if parent is None:
            return None
        worker = getattr(parent, "_worker", None)
        if worker is None:
            return None
        return worker.market_data_source

    def _consultar(self):
        source = self._obter_source()
        if source is None or not getattr(source, "disponivel", False):
            self.lbl_topo.setText("❌ OpenFast desconectado — não é possível consultar os strikes.")
            self.lbl_topo.setStyleSheet("color: {}; font-weight: bold;".format(Palette.RED))
            return

        from src.infrastructure.persistence.database import get_connection
        from datetime import date
        hoje = date.today().isoformat()

        try:
            conn = get_connection(self.db_path)
            proventos = conn.execute(
                "SELECT ativo, valor FROM dividendos WHERE data_ex = ? AND valor > 0",
                (hoje,),
            ).fetchall()
            provento_por_ativo = {}
            for a, v in proventos:
                provento_por_ativo[a] = provento_por_ativo.get(a, 0.0) + float(v)
            ativos = sorted(set(provento_por_ativo))
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler dividendos:\n{e}")
            return

        if not ativos:
            self.lbl_topo.setText("Nenhum ativo com data_ex hoje. Nada a ajustar.")
            self.lbl_status.setText("0 registros")
            return

        self.lbl_topo.setText(
            f"Consultando PEX no OpenFast para: {', '.join(ativos)} (aguarde ~2s)..."
        )
        import time as _time

        itens: list[dict] = []
        codigos = []
        pares = []
        conn = get_connection(self.db_path)
        for ativo in ativos:
            insts = conn.execute(
                "SELECT cod_put, cod_call, strike FROM instrumentos_base WHERE ativo = ? AND strike IS NOT NULL",
                (ativo,),
            ).fetchall()
            for cp, cc, st in insts:
                if cp:
                    codigos.append((cp, FieldName.STRIKE))
                if cc:
                    codigos.append((cc, FieldName.STRIKE))
                pares.append((ativo, cp, cc, st, provento_por_ativo.get(ativo, 0.0)))

        if not codigos:
            self.lbl_topo.setText("Nenhum instrumento no banco para os ativos com data_ex hoje.")
            return

        try:
            source.registrar_lista(codigos)
            _time.sleep(2.0)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao assinar PEX no OpenFast:\n{e}")
            return

        for ativo, cp, cc, st, provento in pares:
            pex_put = source.ler_campos(cp, FieldName.STRIKE, allow_stale=True).get(FieldName.STRIKE) if cp else None
            pex_call = source.ler_campos(cc, FieldName.STRIKE, allow_stale=True).get(FieldName.STRIKE) if cc else None
            pex = pex_put if pex_put else pex_call
            cod = cp or cc
            if pex is None or not st:
                continue
            if abs(float(pex) - float(st)) > 0.005:
                itens.append({
                    "ativo": ativo,
                    "cod": cod,
                    "strike_banco": float(st),
                    "strike_openfast": float(pex),
                    "provento": provento,
                    "data_ex": hoje,
                    "esperado": float(st) - float(provento),
                })

        self._items = itens
        self.model.atualizar(itens)
        self.lbl_topo.setText(
            f"Divergências encontradas: {len(itens)}"
            if itens
            else "Nenhuma divergência entre banco e OpenFast nos ativos com data_ex hoje."
        )
        self.lbl_status.setText(f"{len(itens)} registros")
        self.btn_aplicar.setEnabled(bool(itens))
        self.btn_aplicar_todos.setEnabled(bool(itens))
        self.btn_selecionar_todos.setEnabled(bool(itens))

    def _selecionar_todos(self):
        self.table_view.selectAll()

    def _aplicar_todos(self):
        if not self._items:
            return
        resp = QMessageBox.question(
            self, "Aplicar todos",
            f"Aplicar o ajuste em TODOS os {len(self._items)} registros?\n\n"
            "O strike do banco será substituído pelo valor do OpenFast.\n"
            "O opcoes.net corrige em 1-2 dias; a próxima importação substitui pelo valor do site.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        self._aplicar(indices=range(len(self._items)))

    def _aplicar(self, indices=None):
        if indices is None:
            indices = {idx.row() for idx in self.table_view.selectionModel().selectedRows()}
            if not indices:
                QMessageBox.information(self, "Aviso", "Selecione ao menos uma linha.")
                return

        from src.infrastructure.persistence.database import get_connection
        conn = get_connection(self.db_path)
        aplicados = 0
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for r in indices:
            item = self._items[r]
            try:
                cur = conn.execute(
                    "UPDATE instrumentos_base SET strike = ?, strike_ajustado_em = ? "
                    "WHERE ativo = ? AND (cod_put = ? OR cod_call = ?)",
                    (item["strike_openfast"], agora, item["ativo"], item["cod"], item["cod"]),
                )
                aplicados += cur.rowcount
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao ajustar {item['cod']}:\n{e}")
        conn.commit()

        self.aplicou = aplicados > 0
        if self.aplicou:
            QMessageBox.information(
                self, "Concluído",
                f"{aplicados} strike(s) ajustado(s) para o valor do OpenFast.\n"
                "O opcoes.net corrige em 1-2 dias; a próxima importação substitui pelo valor do site."
            )
            self.accept()
        else:
            QMessageBox.warning(self, "Aviso", "Nenhuma linha foi atualizada.")