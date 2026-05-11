from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QProgressBar, QMessageBox,
)
from PyQt5.QtCore import Qt

from src.application.use_cases.importar_base import ImportarBaseUseCase
from src.application.dtos.dtos import ImportarResultado


class ImportDialog(QDialog):
    def __init__(self, use_case: ImportarBaseUseCase, parent=None):
        super().__init__(parent)
        self.use_case = use_case
        self._result: ImportarResultado | None = None

        self.setWindowTitle("Importar Base de Instrumentos")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.lbl_file = QLabel("Nenhum arquivo selecionado")
        self.lbl_file.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.lbl_file)

        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("Selecionar arquivo XLSX...")
        self.btn_select.clicked.connect(self._selecionar_arquivo)
        btn_layout.addWidget(self.btn_select)

        self.btn_import = QPushButton("Importar")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._executar_importacao)
        btn_layout.addWidget(self.btn_import)

        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

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
            self.lbl_file.setStyleSheet("color: black;")
            self.btn_import.setEnabled(True)

    def _executar_importacao(self):
        if not hasattr(self, "_filepath"):
            return

        self.btn_import.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.lbl_status.setText("Importando...")
        self.lbl_status.setStyleSheet("color: blue;")

        try:
            self._result = self.use_case.executar(self._filepath)
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
            self.lbl_status.setText(
                "Importado com sucesso: {} instrumentos, {} removidos, {} ativos".format(
                    self._result.total_importados,
                    self._result.total_removidos,
                    len(self._result.ativos),
                )
            )
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
        except Exception as e:
            self.progress.setVisible(False)
            self.lbl_status.setText("Erro: {}".format(str(e)))
            self.lbl_status.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Erro na importação", str(e))
        finally:
            self.btn_import.setEnabled(True)
            self.btn_select.setEnabled(True)

    @property
    def result(self) -> ImportarResultado | None:
        return self._result
