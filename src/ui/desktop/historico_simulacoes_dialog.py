import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QHeaderView, QMessageBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QTimer
from PySide6.QtGui import QFont

from src.infrastructure.persistence.database import get_db_path
from src.infrastructure.persistence.repositories.repositories import HistoricoSimulacoesRepository
from src.ui.desktop.column_utils import salvar_ordem_colunas, limpar_e_restaurar_colunas
from src.ui.desktop.theme import Palette

logger = logging.getLogger(__name__)


COLUMNS = [
    ("ID", 40),
    ("Chassi", 80),
    ("Estágio", 120),
    ("Ativo", 70),
    ("Preço", 80),
    ("Strike Call", 80),
    ("Strike Put", 80),
    ("DTE", 50),
    ("IV Call", 65),
    ("R. Call", 60),
    ("R. Put", 60),
    ("PnL Esq", 80),
    ("PnL Dir", 80),
    ("BE Esq", 80),
    ("BE Dir", 80),
    ("%CDI", 70),
    ("Detectado", 140),
]


class HistoricoSimulacoesTableModel(QAbstractTableModel):
    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0: return item.get("id", "")
            if col == 1: return item.get("id_chassi", "")
            if col == 2: return item.get("estagio", "")
            if col == 3: return item.get("ativo", "")
            if col == 4: return f'{item.get("preco_ativo", 0):.2f}'
            if col == 5: return f'{item.get("strike_call", 0):.2f}'
            if col == 6: return f'{item.get("strike_put", 0):.2f}'
            if col == 7: return str(item.get("dte_original", ""))
            if col == 8: return f'{item.get("iv_call", 0):.2f}'
            if col == 9: return f'{item.get("ratio_call", 0):.2f}'
            if col == 10: return f'{item.get("ratio_put", 0):.2f}'
            if col == 11: return f'{item.get("pnl_cauda_esq", 0):.4f}'
            if col == 12: return f'{item.get("pnl_cauda_dir", 0):.4f}'
            if col == 13: return f'{item.get("be_esq", "-"):.2f}' if item.get("be_esq") is not None else "-"
            if col == 14: return f'{item.get("be_dir", "-"):.2f}' if item.get("be_dir") is not None else "-"
            if col == 15: return f'{item.get("pct_cdi", 0):.2%}'
            if col == 16: return str(item.get("detectado_em", ""))[:19] if item.get("detectado_em") else ""
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter if col in (0, 1, 7, 8, 9, 10) else Qt.AlignRight if col >= 4 else Qt.AlignLeft
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section][0]
        return None

    def atualizar(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class HistoricoSimulacoesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histórico de Simulações Otimizadas")
        self.resize(1000, 500)
        self._repo = HistoricoSimulacoesRepository(get_db_path())
        self._setup_style()
        self._setup_ui()
        self._carregar()

    def _setup_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Palette.BG_PRIMARY}; color: {Palette.TEXT_PRIMARY}; }}
            QTableView {{
                background-color: {Palette.TABLE_BG}; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; gridline-color: {Palette.BORDER};
                font-family: 'Consolas', 'Courier New', monospace; font-size: 9pt;
            }}
            QHeaderView::section {{
                background-color: {Palette.HEADER_BG}; color: {Palette.ACCENT};
                font-weight: bold; padding: 4px 6px; border: 1px solid {Palette.BORDER};
            }}
            QPushButton {{
                background-color: {Palette.BUTTON_BG}; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: {Palette.BUTTON_HOVER}; color: {Palette.ACCENT}; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.table_view = QTableView()
        self.model = HistoricoSimulacoesTableModel()
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSortingEnabled(True)
        self.table_view.setFont(QFont("Consolas", 9))
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setDragEnabled(True)
        KEY = "historico_simulacoes_order"
        header.sectionMoved.connect(lambda: QTimer.singleShot(0, lambda: salvar_ordem_colunas(header, KEY)))
        limpar_e_restaurar_colunas(header, KEY, "historico_simulacoes_width")
        header.setSectionResizeMode(QHeaderView.Interactive)
        for i, (_, w) in enumerate(COLUMNS):
            header.resizeSection(i, w)
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.verticalHeader().hide()
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        self.btn_exportar = QPushButton("📤 Exportar Tudo")
        self.btn_exportar.clicked.connect(self._exportar)
        btn_layout.addWidget(self.btn_exportar)
        self.btn_limpar = QPushButton("🗑 Limpar Histórico")
        self.btn_limpar.clicked.connect(self._limpar)
        btn_layout.addWidget(self.btn_limpar)
        self.btn_recarregar = QPushButton("🔄 Recarregar")
        self.btn_recarregar.clicked.connect(self._carregar)
        btn_layout.addWidget(self.btn_recarregar)
        btn_layout.addStretch()
        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)
        layout.addLayout(btn_layout)

    def _carregar(self):
        try:
            items = self._repo.listar(500)
            self.model.atualizar(items)
            self.setWindowTitle(f"Histórico de Simulações Otimizadas ({len(items)} registros)")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar histórico:\n{e}")

    def _on_row_double_clicked(self, index):
        if not index.isValid():
            return
        item = self.model._items[index.row()]
        linhas = "\n".join(f"{COLUMNS[i][0]}: {self.model.data(self.model.index(index.row(), i))}" for i in range(len(COLUMNS)))
        QMessageBox.information(self, "Detalhes do Registro", linhas)

    def _limpar(self):
        resposta = QMessageBox.question(
            self, "Limpar Histórico",
            "Tem certeza que deseja apagar TODOS os registros do histórico de simulações?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            try:
                total = self._repo.limpar()
                self._carregar()
                QMessageBox.information(self, "Limpar", f"{total} registro(s) removido(s).")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao limpar histórico:\n{e}")

    def _exportar(self):
        items = self.model._items
        if not items:
            QMessageBox.information(self, "Exportar", "Nenhum registro para exportar.")
            return
        cabecalho = "\t".join(COLUMNS[i][0] for i in range(len(COLUMNS)))
        linhas = []
        for item in items:
            vals = [
                str(item.get("id", "")),
                item.get("id_chassi", ""),
                item.get("estagio", ""),
                item.get("ativo", ""),
                f'{item.get("preco_ativo", 0):.2f}',
                f'{item.get("strike_call", 0):.2f}',
                f'{item.get("strike_put", 0):.2f}',
                str(item.get("dte_original", "")),
                f'{item.get("iv_call", 0):.2f}',
                f'{item.get("ratio_call", 0):.2f}',
                f'{item.get("ratio_put", 0):.2f}',
                f'{item.get("pnl_cauda_esq", 0):.4f}',
                f'{item.get("pnl_cauda_dir", 0):.4f}',
                f'{item.get("be_esq", ""):.2f}' if item.get("be_esq") is not None else "-",
                f'{item.get("be_dir", ""):.2f}' if item.get("be_dir") is not None else "-",
                f'{item.get("pct_cdi", 0):.2%}',
                str(item.get("detectado_em", ""))[:19] if item.get("detectado_em") else "",
            ]
            linhas.append("\t".join(vals))
        texto_completo = cabecalho + "\n" + "\n".join(linhas)

        from PySide6.QtCore import QMimeData
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        mime = QMimeData()
        mime.setText(texto_completo)
        clipboard.setMimeData(mime)
        QMessageBox.information(self, "Exportar", f"{len(items)} registro(s) copiados para a área de transferência.")
