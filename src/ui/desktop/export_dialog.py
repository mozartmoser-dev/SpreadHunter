from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QMessageBox,
    QDoubleSpinBox,
)
from PyQt5.QtCore import Qt

from src.application.dtos.dtos import OportunidadeMonitor, TipoExportacao
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase


class ExportDialog(QDialog):
    def __init__(
        self,
        oportunidade: OportunidadeMonitor,
        use_case: ExportarOperacaoUseCase,
        output_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self.oportunidade = oportunidade
        self.use_case = use_case
        self.output_dir = output_dir
        self._result = None

        self.setWindowTitle("Exportar Operação - {}".format(oportunidade.ativo))
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info_group = QGroupBox("Oportunidade")
        info_layout = QFormLayout()

        info_layout.addRow("Ativo:", QLabel(self.oportunidade.ativo))
        info_layout.addRow("Tipo:", QLabel(self.oportunidade.label_tipo))
        info_layout.addRow("Rentabilidade:", QLabel(self.oportunidade.label_rentabilidade))
        info_layout.addRow("Dias:", QLabel(self.oportunidade.label_dias))
        info_layout.addRow("Strike:", QLabel(str(self.oportunidade.strike)))
        info_layout.addRow("Vencimento:", QLabel(self.oportunidade.vencimento))
        info_layout.addRow("Cod Put:", QLabel(self.oportunidade.cod_put))
        info_layout.addRow("Cod Call:", QLabel(self.oportunidade.cod_call))

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        params_group = QGroupBox("Parâmetros BASKET")
        params_layout = QFormLayout()
        self.spin_taxa_ganho = QDoubleSpinBox()
        self.spin_taxa_ganho.setRange(0.0, 100.0)
        self.spin_taxa_ganho.setValue(10.0)
        self.spin_taxa_ganho.setSuffix(" %")
        self.spin_taxa_ganho.setDecimals(1)
        params_layout.addRow("Taxa Ganho:", self.spin_taxa_ganho)
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        btn_layout = QHBoxLayout()

        self.btn_log = QPushButton("Exportar LOG")
        self.btn_log.setStyleSheet("background-color: #4a90d9; color: white; padding: 8px; font-weight: bold;")
        self.btn_log.clicked.connect(self._exportar_log)
        btn_layout.addWidget(self.btn_log)

        self.btn_basket = QPushButton("Exportar BASKET ITM")
        self.btn_basket.setStyleSheet("background-color: #d94a4a; color: white; padding: 8px; font-weight: bold;")
        self.btn_basket.clicked.connect(self._exportar_basket)
        btn_layout.addWidget(self.btn_basket)

        layout.addLayout(btn_layout)

        self.btn_fechar = QPushButton("Cancelar")
        self.btn_fechar.clicked.connect(self.reject)
        layout.addWidget(self.btn_fechar)

    def _make_opp_dict(self) -> dict:
        return {
            "instrumento_id": self.oportunidade.instrumento_id,
            "ativo": self.oportunidade.ativo,
            "strike": self.oportunidade.strike,
            "vencimento": self.oportunidade.vencimento,
            "dias": self.oportunidade.dias,
            "cod_put": self.oportunidade.cod_put,
            "cod_call": self.oportunidade.cod_call,
            "classificacao": self.oportunidade.classificacao,
            "operacao": self.oportunidade.operacao,
            "ganho_box": self.oportunidade.ganho_box,
            "ganho_sbth": self.oportunidade.ganho_sbth,
            "rent_box_vs_cdi": self.oportunidade.rent_box_vs_cdi,
            "rent_sbth_vs_cdi": self.oportunidade.rent_sbth_vs_cdi,
        }

    def _exportar_log(self):
        try:
            self._result = self.use_case.executar_log(
                self._make_opp_dict(),
                output_dir=self.output_dir,
            )
            QMessageBox.information(
                self, "LOG Exportado",
                "Log exportado com sucesso!\n\nArquivo: {}".format(self._result.filepath),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao exportar LOG", str(e))

    def _exportar_basket(self):
        opp_dict = self._make_opp_dict()
        opp_dict["taxa_ganho"] = self.spin_taxa_ganho.value()
        try:
            self._result = self.use_case.executar_basket(
                opp_dict,
                taxa_ganho=self.spin_taxa_ganho.value(),
                output_dir=self.output_dir,
            )
            QMessageBox.information(
                self, "BASKET Exportado",
                "Basket exportado com sucesso!\n\nEstrutura ID: {}\nArquivo: {}".format(
                    self._result.estrutura_id, self._result.filepath
                ),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao exportar BASKET", str(e))

    @property
    def result(self):
        return self._result
