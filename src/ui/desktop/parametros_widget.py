from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QPushButton, QLabel, QScrollArea, QFrame,
)
from PyQt5.QtCore import Qt

from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.domain.entities.parametro_operacional import ParametroOperacional
from src.ui.desktop.theme import Palette


ESTRATEGIA_LABELS = {
    "GERAL": "Geral",
    "SBTH": "SBTH (Synthetic Buy & Hold)",
    "BOX": "BOX Comprado 3 Pontas",
    "BOX_SINTETICO": "BOX Sintetico / Pescaria Basket",
}

ESTRATEGIA_COLORS = {
    "GERAL": Palette.TEXT_PRIMARY,
    "SBTH": Palette.CYAN,
    "BOX": Palette.ACCENT_BLUE_BRIGHT,
    "BOX_SINTETICO": Palette.PURPLE,
}

PARAMETROS_POR_ESTRATEGIA = {
    "GERAL": [
        ("taxa_cdi", "Taxa CDI/Selic"),
    ],
    "BOX": [
        ("premio_risco_box", "Premio risco BOX (x CDI)"),
        ("box_qtd_ativo", "Qtd compra ativo"),
        ("box_prof_ativo", "Profund. book ativo"),
        ("box_qtd_put", "Qtd compra PUT"),
        ("box_prof_put", "Profund. book PUT"),
        ("box_qtd_call", "Qtd venda Call"),
        ("box_prof_call", "Profund. book Call"),
    ],
    "SBTH": [
        ("premio_risco_sbth", "Premio risco SBTH (x CDI)"),
        ("sbth_qtd_ativo", "Qtd compra ativo"),
        ("sbth_prof_ativo", "Profund. book ativo"),
        ("sbth_qtd_put", "Qtd compra PUT"),
        ("sbth_prof_put", "Profund. book PUT"),
    ],
    "BOX_SINTETICO": [
        ("premio_box_sintetico_call_itm", "Premio risco Box sintetico (x CDI)"),
        ("basket_qtd_call_itm", "Qtd compra Call ITM"),
        ("basket_prof_call_itm", "Profund. Call ITM"),
        ("basket_qtd_put", "Qtd compra PUT"),
        ("basket_prof_put", "Profund. PUT"),
        ("basket_qtd_call", "Qtd venda Call ATM"),
        ("basket_prof_call", "Profund. Call ATM"),
    ],
}


class ParametrosWidget(QWidget):
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.repo = ParametroRepository(db_path)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._setup_ui()
        self._carregar()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        for estrategia, params in PARAMETROS_POR_ESTRATEGIA.items():
            label = ESTRATEGIA_LABELS.get(estrategia, estrategia)
            color = ESTRATEGIA_COLORS.get(estrategia, Palette.TEXT_PRIMARY)
            group = QGroupBox(label)
            group.setStyleSheet(
                "QGroupBox::title {{ color: {}; }}".format(color)
            )
            form = QFormLayout()
            form.setSpacing(10)
            form.setContentsMargins(12, 20, 12, 12)

            for chave, display in params:
                spin = QDoubleSpinBox()
                spin.setRange(-100.0, 100000.0)
                if "prof" in chave:
                    spin.setDecimals(0)
                    spin.setSingleStep(1)
                elif "qtd" in chave:
                    spin.setDecimals(0)
                    spin.setSingleStep(100)
                else:
                    spin.setDecimals(4)
                    spin.setSingleStep(0.01)

                param_label = QLabel(display + ":")
                param_label.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_SECONDARY))
                form.addRow(param_label, spin)
                self._spins[chave] = spin

            group.setLayout(form)
            layout.addWidget(group)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: {}; max-height: 1px;".format(Palette.BORDER))
        outer_layout.addWidget(sep)

        self.btn_salvar = QPushButton("Salvar Parametros")
        self.btn_salvar.setProperty("class", "primary")
        self.btn_salvar.clicked.connect(self._salvar)
        outer_layout.addWidget(self.btn_salvar)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        outer_layout.addWidget(self.lbl_status)

    def _carregar(self):
        for chave, spin in self._spins.items():
            param = self.repo.get_by_chave(chave)
            if param:
                spin.setValue(param.valor)
            else:
                defaults = ParametroOperacional.PARAMETROS_DEFAULT
                if chave in defaults:
                    spin.setValue(defaults[chave]["valor"])

    def _salvar(self):
        try:
            for chave, spin in self._spins.items():
                param = self.repo.get_by_chave(chave)
                if param:
                    param.valor = spin.value()
                    self.repo.save(param)
                else:
                    defaults = ParametroOperacional.PARAMETROS_DEFAULT
                    if chave in defaults:
                        d = defaults[chave]
                        p = ParametroOperacional(
                            chave=chave,
                            valor=spin.value(),
                            estrategia=d["estrategia"],
                            descricao=d["descricao"],
                        )
                        self.repo.save(p)
            self.lbl_status.setText("Parametros salvos com sucesso.")
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold; padding: 4px;".format(Palette.GREEN)
            )
        except Exception as e:
            self.lbl_status.setText("Erro: {}".format(str(e)))
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold; padding: 4px;".format(Palette.RED)
            )
