from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QPushButton, QMessageBox, QLabel,
)
from PyQt5.QtCore import Qt

from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.domain.entities.parametro_operacional import ParametroOperacional


class ParametrosWidget(QWidget):
    PARAMETROS_ORDER = [
        ("taxa_cdi", "Taxa CDI"),
        ("premio_risco_box", "Prêmio Risco BOX"),
        ("premio_risco_sbth", "Prêmio Risco SBTH"),
        ("premio_box_sintetico_call_itm", "Prêmio BOX Sintético Call ITM"),
    ]

    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.repo = ParametroRepository(db_path)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._setup_ui()
        self._carregar()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Parâmetros Operacionais")
        form = QFormLayout()

        for chave, label in self.PARAMETROS_ORDER:
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.01)
            self._spins[chave] = spin
            form.addRow(label + ":", spin)

        group.setLayout(form)
        layout.addWidget(group)

        self.btn_salvar = QPushButton("Salvar Parâmetros")
        self.btn_salvar.clicked.connect(self._salvar)
        layout.addWidget(self.btn_salvar)

        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)

    def _carregar(self):
        for chave, spin in self._spins.items():
            param = self.repo.get_by_chave(chave)
            if param:
                spin.setValue(param.valor)

    def _salvar(self):
        try:
            for chave, spin in self._spins.items():
                param = self.repo.get_by_chave(chave)
                if param:
                    param.valor = spin.value()
                    self.repo.save(param)
            self.lbl_status.setText("Parâmetros salvos com sucesso.")
            self.lbl_status.setStyleSheet("color: green;")
        except Exception as e:
            self.lbl_status.setText("Erro: {}".format(str(e)))
            self.lbl_status.setStyleSheet("color: red;")
