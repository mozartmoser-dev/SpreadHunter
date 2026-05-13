from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar, QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt

from src.application.use_cases.importar_base import ImportarBaseUseCase
from src.application.dtos.dtos import ImportarResultado
from src.ui.desktop.theme import Palette


class ImportDialog(QDialog):
    def __init__(self, use_case: ImportarBaseUseCase, parent=None):
        super().__init__(parent)
        self.use_case = use_case
        self._result: ImportarResultado | None = None

        self.setWindowTitle("Importar Base de Instrumentos")
        self.setMinimumWidth(520)
        self.setMinimumHeight(220)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Importar Base de Instrumentos")
        title.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: {};".format(Palette.TEXT_PRIMARY)
        )
        layout.addWidget(title)

        self.lbl_file = QLabel("Nenhum arquivo selecionado")
        self.lbl_file.setStyleSheet(
            "color: {}; font-style: italic; font-size: 9pt; "
            "background-color: {}; border: 1px dashed {}; "
            "border-radius: 4px; padding: 12px;".format(
                Palette.TEXT_MUTED, Palette.BG_SURFACE, Palette.BORDER
            )
        )
        layout.addWidget(self.lbl_file)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_select = QPushButton("Selecionar arquivo XLSX...")
        self.btn_select.setProperty("class", "primary")
        self.btn_select.clicked.connect(self._selecionar_arquivo)
        btn_layout.addWidget(self.btn_select)

        self.btn_import = QPushButton("Importar")
        self.btn_import.setProperty("class", "success")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._executar_importacao)
        btn_layout.addWidget(self.btn_import)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: {}; max-height: 1px;".format(Palette.BORDER))
        layout.addWidget(sep)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        layout.addWidget(self.btn_fechar)

    def _selecionar_arquivo(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo XLSX", str(Path.home()),
            "Excel Files (*.xlsx);;All Files (*)",
        )
        if filepath:
            self._filepath = filepath
            self.lbl_file.setText(filepath)
            self.lbl_file.setStyleSheet(
                "color: {}; font-size: 9pt; "
                "background-color: {}; border: 1px solid {}; "
                "border-radius: 4px; padding: 12px;".format(
                    Palette.TEXT_PRIMARY, Palette.BG_SURFACE, Palette.BORDER
                )
            )
            self.btn_import.setEnabled(True)

    def _executar_importacao(self):
        if not hasattr(self, "_filepath"):
            return

        self.btn_import.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.lbl_status.setText("Importando...")
        self.lbl_status.setStyleSheet("color: {}; font-weight: bold;".format(Palette.ORANGE))

        try:
            self._result = self.use_case.executar(self._filepath)
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
            self.lbl_status.setText(
                "Importado: {} instrumentos | {} removidos | {} ativos".format(
                    self._result.total_importados,
                    self._result.total_removidos,
                    len(self._result.ativos),
                )
            )
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.GREEN)
            )
        except Exception as e:
            self.progress.setVisible(False)
            self.lbl_status.setText("Erro: {}".format(str(e)))
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.RED)
            )
            QMessageBox.critical(self, "Erro na importacao", str(e))
        finally:
            self.btn_import.setEnabled(True)
            self.btn_select.setEnabled(True)

    @property
    def result(self) -> ImportarResultado | None:
        return self._result
