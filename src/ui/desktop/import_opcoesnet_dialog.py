from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QMessageBox, QFrame, QTextEdit,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from src.application.use_cases.importar_base_opcoesnet import ImportarBaseOpcoesNetUseCase
from src.ui.desktop.theme import Palette


class ImportWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, use_case: ImportarBaseOpcoesNetUseCase, ativos: list[str] | None = None):
        super().__init__()
        self.use_case = use_case
        self.ativos = ativos

    def run(self):
        try:
            resultado = self.use_case.executar(
                ativos=self.ativos,
                progress_callback=self._on_progress,
            )
            self.finished.emit(resultado)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, idx: int, total: int, ativo: str):
        self.progress.emit(idx, total, ativo)


class ImportOpcoesNetDialog(QDialog):
    def __init__(self, db_path: str | None = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._result = None

        self.setWindowTitle("Importar Base do Opcoes.Net.Br")
        self.setMinimumWidth(560)
        self.setMinimumHeight(340)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Importar Instrumentos Base do Opcoes.Net.Br")
        title.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: {};".format(Palette.TEXT_PRIMARY)
        )
        layout.addWidget(title)

        desc = QLabel(
            "Busca todos os pares CALL+PUT da lista de ativos mais líquidos "
            "diretamente do opcoes.net.br.\n"
            "O modelo (A=Americana / E=Europeia) será obtido automaticamente da CALL."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        layout.addWidget(desc)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "background-color: {}; color: {}; border: 1px solid {}; "
            "border-radius: 4px; font-family: Consolas; font-size: 9pt;".format(
                Palette.BG_SURFACE, Palette.TEXT_PRIMARY, Palette.BORDER
            )
        )
        self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: {}; font-weight: bold;".format(Palette.TEXT_MUTED))
        layout.addWidget(self.lbl_status)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: {}; max-height: 1px;".format(Palette.BORDER))
        layout.addWidget(sep)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_import = QPushButton("Importar Agora")
        self.btn_import.setProperty("class", "primary")
        self.btn_import.clicked.connect(self._executar_importacao)
        btn_layout.addWidget(self.btn_import)

        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def _log(self, msg: str):
        self.log.append(msg)

    def _executar_importacao(self):
        self.btn_import.setEnabled(False)
        self.btn_fechar.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.lbl_status.setText("Iniciando...")
        self.log.clear()

        use_case = ImportarBaseOpcoesNetUseCase(self.db_path)
        self._worker = ImportWorker(use_case)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, idx: int, total: int, ativo: str):
        self.progress.setRange(0, 0)
        self.progress.setValue(0)
        self.lbl_status.setText("Buscando {}/{}: {}...".format(idx, total, ativo))

    def _on_finished(self, resultado):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self._result = resultado

        ativos_str = ", ".join(resultado.ativos[:10])
        if len(resultado.ativos) > 10:
            ativos_str += " e mais {} ativos".format(len(resultado.ativos) - 10)

        self.lbl_status.setText(
            "Importado: {} instrumentos | {} removidos | {} ativos".format(
                resultado.total_importados,
                resultado.total_removidos,
                len(resultado.ativos),
            )
        )
        self.lbl_status.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
        self._log("Concluido! {} instrumentos importados de {} ativos.".format(
            resultado.total_importados, len(resultado.ativos)
        ))

        self.btn_import.setEnabled(True)
        self.btn_fechar.setEnabled(True)

    def _on_error(self, msg: str):
        self.progress.setVisible(False)
        self.lbl_status.setText("Erro: {}".format(msg))
        self.lbl_status.setStyleSheet("color: {}; font-weight: bold;".format(Palette.RED))
        self._log("ERRO: {}".format(msg))
        self.btn_import.setEnabled(True)
        self.btn_fechar.setEnabled(True)
        QMessageBox.critical(self, "Erro na importacao", msg)

    @property
    def result(self):
        return self._result
