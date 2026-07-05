from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from src.infrastructure.persistence.repositories.repositories import TaxaAluguelRepository
from src.ui.desktop.theme import Palette


class _AtualizarThread(QThread):
    finished = Signal(dict)
    progress = Signal(int, int, str)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        from src.application.use_cases.coletar_taxas_aluguel import ColetarTaxasAluguelUseCase

        def cb(corrente, total, ativo):
            self.progress.emit(corrente, total, ativo)

        try:
            use_case = ColetarTaxasAluguelUseCase(self.db_path)
            resumo = use_case.executar(callback_progresso=cb)
        except Exception as e:
            resumo = {"status": "erro", "sucessos": 0, "falhas": 0, "erros": [str(e)]}
        self.finished.emit(resumo)


class TaxaAluguelDialog(QDialog):
    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Taxas de Aluguel (BTC) — InvestSite")
        self.setMinimumSize(580, 420)
        self.resize(650, 500)
        self._setup_ui()
        self._carregar()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Ativo", "Taxa Atual", "Taxa 7d", "Taxa 28d", "Data"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Palette.BG_BASE};
                color: {Palette.TEXT_PRIMARY};
                gridline-color: {Palette.BORDER};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Palette.ACCENT_BLUE};
                color: {Palette.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Palette.BG_RAISED};
                color: {Palette.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid {Palette.BORDER_FOCUS};
                padding: 4px 8px;
                font-weight: bold;
            }}
        """)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        font_mono = QFont("Consolas", 10)
        self.table.setFont(font_mono)

        layout.addWidget(self.table, stretch=1)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {Palette.YELLOW}; font-size: 9pt;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_atualizar.setAutoDefault(False)
        self.btn_atualizar.setToolTip("Coletar novamente as taxas de aluguel do InvestSite")
        self.btn_atualizar.setStyleSheet(f"""
            QPushButton {{
                background-color: {Palette.BG_HOVER};
                color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Palette.ACCENT_BLUE};
            }}
        """)
        self.btn_atualizar.clicked.connect(self._atualizar)
        btn_row.addWidget(self.btn_atualizar)
        btn_row.addStretch()
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.setStyleSheet(f"""
            QPushButton {{
                background-color: {Palette.BG_HOVER};
                color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                padding: 6px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Palette.ACCENT_BLUE};
            }}
        """)
        btn_fechar.clicked.connect(self.accept)
        btn_row.addWidget(btn_fechar)
        layout.addLayout(btn_row)

    def _carregar(self):
        repo = TaxaAluguelRepository(self.db_path)
        dados = repo.get_latest_all()
        items = sorted(dados.values(), key=lambda t: t.ativo.lower())

        self.table.setRowCount(len(items))
        for row, taxa in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(taxa.ativo))
            self.table.setItem(row, 1, QTableWidgetItem(f"{taxa.taxa_atual:.2f} %"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{taxa.taxa_7d:.2f} %"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{taxa.taxa_28d:.2f} %"))
            self.table.setItem(row, 4, QTableWidgetItem(taxa.data.isoformat()))

    def _atualizar(self):
        self.btn_atualizar.setEnabled(False)
        self.btn_atualizar.setText("⏳ Coletando...")
        self.lbl_status.setText("InvestSite: Iniciando coleta...")
        self.lbl_status.setVisible(True)

        self._thread = _AtualizarThread(self.db_path)
        self._thread.progress.connect(
            lambda corr, tot, ativo: self.lbl_status.setText(
                f"InvestSite: Coletando {ativo} ({corr}/{tot})..."
            )
        )
        self._thread.finished.connect(self._on_atualizar_finished)
        self._thread.start()

    def _on_atualizar_finished(self, resumo: dict):
        self.btn_atualizar.setEnabled(True)
        self.btn_atualizar.setText("🔄 Atualizar")
        self.lbl_status.setVisible(False)

        status = resumo.get("status", "sucesso")
        if status == "sucesso":
            sucessos = resumo["sucessos"]
            falhas = resumo["falhas"]
            self._carregar()
            QMessageBox.information(
                self,
                "Atualização Concluída",
                f"Coleta concluída!\n\nAtualizados com sucesso: {sucessos}\nFalhas/Não encontrados: {falhas}"
            )
        elif status == "desabilitado":
            QMessageBox.warning(self, "Desabilitado", "A coleta está desabilitada nos Parâmetros.")
        else:
            erros = resumo.get("erros", ["Erro desconhecido"])
            QMessageBox.critical(self, "Erro", f"A coleta falhou:\n{erros[0]}")