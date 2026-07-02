from PySide6.QtWidgets import (
    QApplication,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QMessageBox,
    QDoubleSpinBox, QComboBox, QFrame, QTabWidget, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.application.dtos.dtos import OportunidadeMonitor, TipoExportacao
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.ui.desktop.theme import Palette


class ExportDialog(QDialog):
    def __init__(
        self,
        oportunidade: OportunidadeMonitor,
        use_case: ExportarOperacaoUseCase,
        parent=None,
        db_path=None,
    ):
        super().__init__(parent)
        self.oportunidade = oportunidade
        self.use_case = use_case
        self.db_path = db_path
        self._result = None

        self.setWindowTitle("Exportar Operacao - {}".format(oportunidade.ativo))
        self.setMinimumWidth(520)
        self.setMinimumHeight(580)
        self._setup_ui()
        self._verificar_ex_dividendo()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        venc_display = "-"
        if self.oportunidade.vencimento:
            from datetime import date
            venc_date = None
            if isinstance(self.oportunidade.vencimento, date):
                venc_date = self.oportunidade.vencimento
                venc_display = venc_date.strftime("%d/%m/%Y")
            else:
                venc_display = str(self.oportunidade.vencimento)
                try:
                    from datetime import datetime
                    if "/" in venc_display:
                        venc_date = datetime.strptime(venc_display, "%d/%m/%Y").date()
                    else:
                        venc_date = datetime.strptime(venc_display[:10], "%Y-%m-%d").date()
                except Exception:
                    pass

            if venc_date:
                dte = (venc_date - date.today()).days
                dte = max(dte, 0)
                venc_display = "{} ({} DTE)".format(venc_display, dte)
            elif hasattr(self.oportunidade, "dias") and self.oportunidade.dias is not None:
                venc_display = "{} ({} DTE)".format(venc_display, self.oportunidade.dias)

        header = QLabel("{}  |  {}  |  Strike {:.2f}  |  {}".format(
            self.oportunidade.ativo,
            self.oportunidade.label_tipo,
            self.oportunidade.strike,
            venc_display,
        ))
        header.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 6px 0;".format(Palette.TEXT_PRIMARY)
        )
        layout.addWidget(header)

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        tabs.addTab(self._build_pernas_tab(), "Pernas & Custos")
        tabs.addTab(self._build_mercado_tab(), "Dados de Mercado")
        tabs.addTab(self._build_operacao_tab(), "Operacao")

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_log = QPushButton("Registrar Operacao")
        self.btn_log.setProperty("class", "primary")
        self.btn_log.clicked.connect(self._exportar_log)
        btn_layout.addWidget(self.btn_log)

        self.btn_basket = QPushButton("Exportar BASKET ITM")
        self.btn_basket.setProperty("class", "danger")
        self.btn_basket.clicked.connect(self._exportar_basket)
        btn_layout.addWidget(self.btn_basket)

        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Cancelar")
        self.btn_fechar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def _build_pernas_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)

        opp = self.oportunidade

        pernas_group = QGroupBox("Pernas da Estrutura")
        pernas_form = QFormLayout()
        pernas_form.setSpacing(8)
        pernas_form.addRow(self._label_muted("Compra Ativo ({}):".format(opp.ativo)), QLabel("{:.2f} (of. venda)".format(opp.preco_compra_ativo)))
        
        # Compra Put com Strike à direita
        put_layout = QHBoxLayout()
        put_layout.setContentsMargins(0, 0, 0, 0)
        lbl_put_val = QLabel("{:.2f} (of. venda)".format(opp.of_venda_put))
        lbl_put_strike = QLabel("Strike: {:.2f}".format(opp.strike))
        lbl_put_strike.setStyleSheet("color: {}; font-weight: bold;".format(Palette.TEXT_SECONDARY))
        put_layout.addWidget(lbl_put_val)
        put_layout.addStretch()
        put_layout.addWidget(lbl_put_strike)
        pernas_form.addRow(self._label_muted("Compra Put ({}):".format(opp.cod_put)), put_layout)

        # Venda Call com Strike à direita
        call_layout = QHBoxLayout()
        call_layout.setContentsMargins(0, 0, 0, 0)
        lbl_call_val = QLabel("{:.2f} (of. compra)".format(opp.of_compra_call))
        lbl_call_strike = QLabel("Strike: {:.2f}".format(opp.strike))
        lbl_call_strike.setStyleSheet("color: {}; font-weight: bold;".format(Palette.TEXT_SECONDARY))
        call_layout.addWidget(lbl_call_val)
        call_layout.addStretch()
        call_layout.addWidget(lbl_call_strike)
        pernas_form.addRow(self._label_muted("Venda Call ({}):".format(opp.cod_call)), call_layout)

        pernas_group.setLayout(pernas_form)
        layout.addWidget(pernas_group)

        custos_group = QGroupBox("Custos e Rentabilidade")
        custos_form = QFormLayout()
        custos_form.setSpacing(8)

        is_box = opp.is_box
        is_sbth = opp.is_sbth

        lbl_custo_sbth = QLabel("{:.2f}".format(opp.custo_sbth) if opp.custo_sbth > 0 else "-")
        lbl_ganho_sbth = QLabel("{:.2f}%".format(opp.pct_ganho_sbth * 100) if opp.pct_ganho_sbth > 0 else "-")
        lbl_cdi_sbth = QLabel("{:.2f}x CDI".format(opp.pct_cdi_sbth) if opp.pct_cdi_sbth > 0 else "-")

        if is_sbth:
            lbl_custo_sbth.setStyleSheet("color: {}; font-weight: bold;".format(Palette.CYAN))
            lbl_ganho_sbth.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
            lbl_cdi_sbth.setStyleSheet("color: {}; font-weight: bold;".format(Palette.YELLOW))
        else:
            strike_font = lbl_custo_sbth.font()
            strike_font.setStrikeOut(True)
            for w in (lbl_custo_sbth, lbl_ganho_sbth, lbl_cdi_sbth):
                w.setFont(strike_font)
                w.setStyleSheet("color: {};".format(Palette.STRIKEOUT_COLOR))

        custos_form.addRow(self._label_muted("Custo SBTH:"), lbl_custo_sbth)
        custos_form.addRow(self._label_muted("Ganho % SBTH:"), lbl_ganho_sbth)
        custos_form.addRow(self._label_muted("vs CDI SBTH:"), lbl_cdi_sbth)

        custos_form.addRow(self._spacer(), QLabel(""))

        lbl_custo_box = QLabel("{:.2f}".format(opp.custo_box) if opp.custo_box > 0 else "-")
        lbl_ganho_box = QLabel("{:.2f}%".format(opp.pct_ganho_box * 100) if opp.pct_ganho_box > 0 else "-")
        lbl_cdi_box = QLabel("{:.2f}x CDI".format(opp.pct_cdi_box) if opp.pct_cdi_box > 0 else "-")

        if is_box:
            lbl_custo_box.setStyleSheet("color: {}; font-weight: bold;".format(Palette.ACCENT_BLUE_BRIGHT))
            lbl_ganho_box.setStyleSheet("color: {}; font-weight: bold;".format(Palette.GREEN))
            lbl_cdi_box.setStyleSheet("color: {}; font-weight: bold;".format(Palette.YELLOW))
        else:
            strike_font = lbl_custo_box.font()
            strike_font.setStrikeOut(True)
            for w in (lbl_custo_box, lbl_ganho_box, lbl_cdi_box):
                w.setFont(strike_font)
                w.setStyleSheet("color: {};".format(Palette.STRIKEOUT_COLOR))

        custos_form.addRow(self._label_muted("Custo BOX:"), lbl_custo_box)
        custos_form.addRow(self._label_muted("Ganho % BOX:"), lbl_ganho_box)
        custos_form.addRow(self._label_muted("vs CDI BOX:"), lbl_cdi_box)

        custos_group.setLayout(custos_form)
        layout.addWidget(custos_group)
        layout.addStretch()
        return widget

    def _build_mercado_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)

        opp = self.oportunidade

        ofertas_group = QGroupBox("Ofertas")
        ofertas_form = QFormLayout()
        ofertas_form.setSpacing(8)
        ofertas_form.addRow(
            self._label_muted("Compra Put:"),
            self._value_label(opp.of_compra_put),
        )
        ofertas_form.addRow(
            self._label_muted("Venda Put:"),
            self._value_label(opp.of_venda_put),
        )
        ofertas_form.addRow(
            self._label_muted("Compra Call:"),
            self._value_label(opp.of_compra_call),
        )
        ofertas_form.addRow(
            self._label_muted("Venda Call:"),
            self._value_label(opp.of_venda_call),
        )
        ofertas_group.setLayout(ofertas_form)
        layout.addWidget(ofertas_group)

        liquidez_group = QGroupBox("Liquidez & Quantidade")
        liq_form = QFormLayout()
        liq_form.setSpacing(8)

        liq_put_lbl = QLabel("{:.0f}".format(opp.liq_put_x_lote))
        liq_put_lbl.setStyleSheet(
            "color: {}; font-weight: bold;".format(
                Palette.LIQ_POSITIVE if opp.liq_put_x_lote >= 0 else Palette.LIQ_NEGATIVE
            )
        )
        liq_call_lbl = QLabel("{:.0f}".format(opp.liq_call_x_lote))
        liq_call_lbl.setStyleSheet(
            "color: {}; font-weight: bold;".format(
                Palette.LIQ_POSITIVE if opp.liq_call_x_lote >= 0 else Palette.LIQ_NEGATIVE
            )
        )

        liq_form.addRow(self._label_muted("Liq Put x Lote:"), liq_put_lbl)
        liq_form.addRow(self._label_muted("Liq Call x Lote:"), liq_call_lbl)
        liq_form.addRow(self._label_muted("Qul Put:"), self._value_label(opp.qul_put, is_int=True))
        liq_form.addRow(self._label_muted("Qul Call:"), self._value_label(opp.qul_call, is_int=True))
        liquidez_group.setLayout(liq_form)
        layout.addWidget(liquidez_group)

        info_group = QGroupBox("Moneyness & Status")
        info_form = QFormLayout()
        info_form.setSpacing(8)
        info_form.addRow(self._label_muted("Money Put:"), self._value_label(opp.money_put))
        info_form.addRow(self._label_muted("Money Call:"), self._value_label(opp.money_call))

        lbl_leilao = QLabel("BLOQUEADO" if opp.em_leilao else "OK")
        if opp.em_leilao:
            lbl_leilao.setStyleSheet(
                "color: {}; background-color: {}; border-radius: 3px; "
                "padding: 2px 8px; font-weight: bold;".format("#ffffff", Palette.RED_DIM)
            )
        else:
            lbl_leilao.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.GREEN)
            )
        info_form.addRow(self._label_muted("Status:"), lbl_leilao)

        info_group.setLayout(info_form)
        layout.addWidget(info_group)
        layout.addStretch()
        return widget

    def _build_operacao_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 12, 8, 8)

        opp = self.oportunidade

        operacao_group = QGroupBox("Configurar Operacao")
        operacao_layout = QFormLayout()
        operacao_layout.setSpacing(10)

        self.combo_operacao = QComboBox()
        if opp.is_box:
            self.combo_operacao.addItem("BOX Comprado", "BOX")
        if opp.is_sbth:
            self.combo_operacao.addItem("SBTH (Synthetic Buy & Hold)", "SBTH")
        if opp.is_box and opp.is_sbth:
            self.combo_operacao.addItem("BOX + SBTH", "BOXSBTH")
        if self.combo_operacao.count() == 0:
            self.combo_operacao.addItem("BOX", "BOX")
        operacao_layout.addRow(self._label_muted("Estrategia:"), self.combo_operacao)

        self.spin_taxa_ganho = QDoubleSpinBox()
        self.spin_taxa_ganho.setRange(0.0, 100.0)
        self.spin_taxa_ganho.setValue(10.0)
        self.spin_taxa_ganho.setSuffix(" %")
        self.spin_taxa_ganho.setDecimals(1)
        self.spin_taxa_ganho.valueChanged.connect(self._atualizar_coeficientes)
        operacao_layout.addRow(self._label_muted("Taxa Ganho:"), self.spin_taxa_ganho)

        self.lbl_coefic_alvo = QLabel("-")
        self.lbl_coefic_alvo.setStyleSheet("color: {}; font-weight: bold; font-family: Consolas, monospace;".format(Palette.CYAN))
        self.lbl_coefic_mercado = QLabel("-")
        self.lbl_coefic_mercado.setStyleSheet("font-family: Consolas, monospace;")
        operacao_layout.addRow(self._label_muted("Coefic. Alvo:"), self.lbl_coefic_alvo)
        operacao_layout.addRow(self._label_muted("Coefic. Mercado:"), self.lbl_coefic_mercado)

        operacao_group.setLayout(operacao_layout)
        layout.addWidget(operacao_group)

        layout.addStretch()

        self._atualizar_coeficientes()
        return widget

    @staticmethod
    def _label_muted(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_SECONDARY))
        return lbl

    @staticmethod
    def _spacer() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: {}; max-height: 1px;".format(Palette.BORDER))
        return sep

    @staticmethod
    def _value_label(value: float, is_int: bool = False) -> QLabel:
        if is_int:
            text = "{:.0f}".format(value) if value > 0 else "-"
        else:
            text = "{:.2f}".format(value) if value > 0 else "-"
        lbl = QLabel(text)
        if value > 0:
            lbl.setStyleSheet("color: {}; font-family: Consolas, monospace;".format(Palette.TEXT_PRIMARY))
        else:
            lbl.setStyleSheet("color: {}; font-family: Consolas, monospace;".format(Palette.TEXT_MUTED))
        return lbl

    def _atualizar_coeficientes(self):
        opp = self.oportunidade
        taxa = self.spin_taxa_ganho.value()

        # coefic_mercado: custo real da estrutura (Call ITM + PUT - Call ATM)
        # No contexto do monitor, usamos of_venda_put - of_compra_call (pernas do BOX)
        coefic_mercado = opp.of_venda_put - opp.of_compra_call
        self.lbl_coefic_mercado.setText("{:.4f}".format(coefic_mercado))

        # coefic_alvo só pode ser calculado com o spread (strike_atm - strike_itm),
        # que não está disponível neste contexto (requer seleção de Call ITM).
        self.lbl_coefic_alvo.setText("Requer Strike ITM")
        self.lbl_coefic_alvo.setStyleSheet(
            "color: {}; font-style: italic; font-family: Consolas, monospace;".format(Palette.TEXT_MUTED)
        )

        # indica se o custo de mercado é aceitável (negativo = CALL rende mais que PUT custa)
        if coefic_mercado <= 0:
            self.lbl_coefic_mercado.setStyleSheet(
                "color: {}; font-weight: bold; font-family: Consolas, monospace;".format(Palette.GREEN)
            )
        else:
            self.lbl_coefic_mercado.setStyleSheet(
                "color: {}; font-weight: bold; font-family: Consolas, monospace;".format(Palette.RED)
            )

    def _make_opp_dict(self) -> dict:
        return {
            "instrumento_id": self.oportunidade.instrumento_id,
            "ativo": self.oportunidade.ativo,
            "strike": self.oportunidade.strike,
            "vencimento": self.oportunidade.vencimento,
            "dias": self.oportunidade.dias,
            "cod_put": self.oportunidade.cod_put,
            "cod_call": self.oportunidade.cod_call,
            "tipo_opcao": self.oportunidade.tipo_opcao,
            "classificacao": self.oportunidade.classificacao,
            "operacao": self.combo_operacao.currentData() or self.oportunidade.operacao,
            "pct_ganho_box": self.oportunidade.pct_ganho_box,
            "pct_ganho_sbth": self.oportunidade.pct_ganho_sbth,
            "pct_cdi_box": self.oportunidade.pct_cdi_box,
            "pct_cdi_sbth": self.oportunidade.pct_cdi_sbth,
            "pct_cdi_sbth_liquido": self.oportunidade.pct_cdi_sbth_liquido,
            "pct_cdi_box_liquido": self.oportunidade.pct_cdi_box_liquido,
            "rent_box_vs_cdi": self.oportunidade.pct_cdi_box,
            "rent_sbth_vs_cdi": self.oportunidade.pct_cdi_sbth,
            "preco_compra_ativo": self.oportunidade.preco_compra_ativo,
            "of_venda_put": self.oportunidade.of_venda_put,
            "of_compra_call": self.oportunidade.of_compra_call,
            "of_compra_put": self.oportunidade.of_compra_put,
            "of_venda_call": self.oportunidade.of_venda_call,
            "qul_put": self.oportunidade.qul_put,
            "qul_call": self.oportunidade.qul_call,
            "liq_put_x_lote": self.oportunidade.liq_put_x_lote,
            "liq_call_x_lote": self.oportunidade.liq_call_x_lote,
            "money_put": self.oportunidade.money_put,
            "money_call": self.oportunidade.money_call,
            "em_leilao": self.oportunidade.em_leilao,
        }

    def _exportar_log(self):
        try:
            self._result = self.use_case.executar_log(
                self._make_opp_dict(),
            )
            QMessageBox.information(
                self, "Operacao Registrada",
                "Operacao registrada com sucesso!\n\nID: {}".format(self._result.estrutura_id),
            )
            # Aciona a integração visual com o PNT logo após salvar no banco
            self._enviar_para_pnt()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao registrar", str(e))

    def _enviar_para_pnt(self):
        """Aciona a integração visual com o PNT com feedback de progresso."""
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog("Enviando para PNT...", None, 0, 100, self)
        progress.setWindowTitle("Automação PNT")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()

        try:
            from src.infrastructure.integrations.pnt import PNTIntegration
            pnt = PNTIntegration(
                db_path=self.db_path,
                progress_callback=lambda pct, msg: (
                    progress.setValue(pct),
                    progress.setLabelText(msg),
                    QApplication.processEvents() if pct % 25 == 0 else None,
                )
            )
            pnt.enviar_oportunidade(self.oportunidade)
        except Exception as e:
            progress.close()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Automação PNT",
                f"Erro na automação PNT:\n{e}\n\nOs dados foram copiados para a área de transferência.")
        finally:
            progress.close()

    def _exportar_basket(self):
        opp_dict = self._make_opp_dict()
        opp_dict["taxa_ganho"] = self.spin_taxa_ganho.value()
        try:
            self._result = self.use_case.executar_basket(
                opp_dict,
                taxa_ganho=self.spin_taxa_ganho.value(),
            )
            QMessageBox.information(
                self, "BASKET Exportado",
                "Basket exportado com sucesso!\n\nEstrutura ID: {}".format(
                    self._result.estrutura_id
                ),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao exportar BASKET", str(e))

    @property
    def result(self):
        return self._result

    def _verificar_ex_dividendo(self):
        """Nível 3: Alerta se o ativo estiver em dia ex de dividendo hoje."""
        if not self.db_path:
            return

        try:
            from src.infrastructure.persistence.repositories.repositories import DividendoRepository
            from datetime import date

            div_repo = DividendoRepository(self.db_path)
            divs_hoje = div_repo.get_ex_hoje()
            divs_ativo = [d for d in divs_hoje if d["ativo"] == self.oportunidade.ativo]

            if divs_ativo:
                tipos = ", ".join(set(d.get("tipo", "") for d in divs_ativo if d.get("tipo")))
                valores = ", ".join("{:.4f}".format(d.get("valor", 0)) for d in divs_ativo if d.get("valor"))

                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("⚠️ Atenção — Dia Ex de Dividendo")
                msg_box.setText(
                    f"O ativo <b>{self.oportunidade.ativo}</b> está em <b>dia ex de dividendo</b> hoje.\n\n"
                    f"Tipo(s): {tipos or 'N/A'}\n"
                    f"Valor(es): {valores or 'N/A'}\n\n"
                    "O strike da opção pode ter sido ajustado pela B3.\n"
                    "Verifique o valor do strike na grade do Profit Pro antes de operar."
                )
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.setDefaultButton(QMessageBox.Ok)
                msg_box.exec_()
        except Exception as e:
            # Falha silenciosa para não bloquear o fluxo
            pass
