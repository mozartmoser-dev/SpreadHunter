from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QLineEdit, QMessageBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.domain.entities.parametro_operacional import ParametroOperacional
from src.ui.desktop.theme import Palette


CHAVE_BLACKLIST = "black_list_import"
ESTRATEGIA = "IMPORTACAO"
DESCRICAO = "Ativos excluidos do ImportFlash (separados por virgula)"


def ler_blacklist(db_path: str | None = None) -> list[str]:
    repo = ParametroRepository(db_path)
    param = repo.get_by_chave(CHAVE_BLACKLIST)
    if param and param.valor:
        raw = str(param.valor)
        return [a.strip().upper() for a in raw.split(",") if a.strip()]
    return []


def salvar_blacklist(ativos: list[str], db_path: str | None = None):
    repo = ParametroRepository(db_path)
    valor = ",".join(sorted(set(a.upper() for a in ativos if a.strip())))
    param = ParametroOperacional(
        chave=CHAVE_BLACKLIST,
        valor=valor,
        estrategia=ESTRATEGIA,
        descricao=DESCRICAO,
    )
    repo.save(param)


class BlacklistImportDialog(QDialog):
    def __init__(self, db_path: str | None = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Blacklist de Importação")
        self.setMinimumSize(420, 380)
        self._setup_ui()
        self._carregar_lista()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Blacklist do ImportFlash")
        title.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: {};".format(Palette.TEXT_PRIMARY)
        )
        layout.addWidget(title)

        desc = QLabel(
            "Ativos nesta lista ser\u00e3o EXCLU\u00cdDOS da importa\u00e7\u00e3o "
            "do opcoes.net.br."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED))
        layout.addWidget(desc)

        self.lista = QListWidget()
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista.setStyleSheet("""
            QListWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                font-family: Consolas;
                font-size: 10pt;
            }
            QListWidget::item:selected {
                background-color: #2d4a6e;
                color: #ffffff;
            }
        """)
        layout.addWidget(self.lista, stretch=1)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.txt_ativo = QLineEdit()
        self.txt_ativo.setPlaceholderText("C\u00f3digo do ativo (ex: PETR4)")
        self.txt_ativo.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e2f;
                color: #e0e0e0;
                border: 1px solid #2d2d44;
                border-radius: 4px;
                padding: 6px 8px;
                font-family: Consolas;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #4fc3f7;
            }
        """)
        self.txt_ativo.returnPressed.connect(self._adicionar)
        input_layout.addWidget(self.txt_ativo, stretch=1)

        self.btn_adicionar = QPushButton("Adicionar")
        self.btn_adicionar.setProperty("class", "primary")
        self.btn_adicionar.clicked.connect(self._adicionar)
        input_layout.addWidget(self.btn_adicionar)

        layout.addLayout(input_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_remover = QPushButton("Remover Selecionado(s)")
        self.btn_remover.setStyleSheet(f"""
            QPushButton {{
                background-color: #3d0e0e; color: {Palette.TEXT_PRIMARY};
                border: 1px solid #e74c3c; border-radius: 4px;
                padding: 6px 12px; font-size: 9pt; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #5d1e1e; }}
        """)
        self.btn_remover.clicked.connect(self._remover)
        btn_layout.addWidget(self.btn_remover)

        btn_layout.addStretch()

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setProperty("class", "success")
        self.btn_ok.clicked.connect(self._confirmar)
        btn_layout.addWidget(self.btn_ok)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancelar)

        layout.addLayout(btn_layout)

    def _carregar_lista(self):
        self.lista.clear()
        ativos = ler_blacklist(self.db_path)
        for a in sorted(ativos):
            self.lista.addItem(a)

    def _adicionar(self):
        texto = self.txt_ativo.text().strip().upper()
        if not texto:
            return
        itens = [self.lista.item(i).text() for i in range(self.lista.count())]
        if texto in itens:
            QMessageBox.information(self, "Aviso", f"'{texto}' j\u00e1 est\u00e1 na blacklist.")
            self.txt_ativo.clear()
            return
        self.lista.addItem(texto)
        self.txt_ativo.clear()

    def _remover(self):
        for item in self.lista.selectedItems():
            self.lista.takeItem(self.lista.row(item))

    def _confirmar(self):
        ativos = [self.lista.item(i).text() for i in range(self.lista.count())]
        salvar_blacklist(ativos, self.db_path)
        self.accept()
