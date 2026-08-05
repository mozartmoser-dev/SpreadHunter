from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView, QFrame, QMessageBox,
    QCheckBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from src.infrastructure.persistence.database import get_db_path
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.ui.desktop.theme import Palette
from src.ui.desktop.pnt_utils import copiar_basket_pnt, fmt_br
from src.infrastructure.integrations.pnt import executar_automacao_pnt

OBSERVACAO = "Spreadhunter"
QTD_APREGoada = 100
_ACCUMULATOR: list[tuple[str, str, str, str]] = []  # (strategy, linha, pernas_str, coeficiente)


def _int_param(repo, chave: str, default: int) -> int:
    p = repo.get_by_chave(chave)
    return int(p.valor) if p else default


def _float_param(repo, chave: str, default: float) -> float:
    p = repo.get_by_chave(chave)
    return float(p.valor) if p else default


class BoletaDialog(QDialog):
    def __init__(self, strategy: str, r, db_path: str | None = None, parent=None):
        super().__init__(parent)
        self.strategy = strategy
        self.r = r
        self._db_path = db_path or get_db_path()
        self.repo = ParametroRepository(self._db_path)

        self.setWindowTitle(f"Boleta Basket — {strategy}")
        self.setMinimumSize(780, 380)
        self._setup_ui()
        self._montar_pernas()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"<b>{self.strategy}</b> — Basket PnT MultiLeg")
        title.setStyleSheet(f"font-size: 13pt; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)
        self.tabela.setHorizontalHeaderLabels([
            "Ativo", "Lado", "Qtd.", "Profund. book",
            "Qtd. apregoada", "Observações",
        ])
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                background-color: #1a1a2e; alternate-background-color: #1e1e34;
                color: #d0d0e0; gridline-color: #2a2a3e;
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                font-family: "JetBrains Mono", "Consolas", monospace; font-size: 9pt;
            }}
            QHeaderView::section {{
                background-color: #0f0f23; color: #a0a0c0;
                border: none; border-bottom: 1px solid {Palette.BORDER};
                padding: 6px 8px; font-weight: bold; font-size: 8.5pt;
            }}
        """)
        layout.addWidget(self.tabela, stretch=1)

        coef_layout = QHBoxLayout()
        coef_layout.setSpacing(12)
        coef_label = QLabel("Coeficiente (Spread):")
        coef_label.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;")
        coef_layout.addWidget(coef_label)
        self.lbl_coeficiente = QLabel("-")
        self.lbl_coeficiente.setStyleSheet(
            f"color: {Palette.CYAN}; font-size: 10pt; font-weight: bold; font-family: Consolas;"
        )
        coef_layout.addWidget(self.lbl_coeficiente)
        coef_layout.addStretch()
        layout.addLayout(coef_layout)

        det_layout = QHBoxLayout()
        det_layout.setSpacing(8)
        det_lbl_caption = QLabel("Detectado pelo monitor:")
        det_lbl_caption.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 8.5pt;")
        det_layout.addWidget(det_lbl_caption)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        det = getattr(self.r, "detectado_em", None)
        det_txt = "-"
        if isinstance(det, datetime):
            if det.tzinfo is None:
                det = det.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
            det_txt = det.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S (Brasília)")
        elif det is not None:
            det_txt = str(det)
        det_lbl = QLabel(det_txt)
        det_lbl.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-family: Consolas, monospace; font-size: 8.5pt;")
        det_layout.addWidget(det_lbl)
        det_layout.addStretch()
        layout.addLayout(det_layout)

        self.lbl_acumulo_header = QLabel("Baskets acumulados:")
        self.lbl_acumulo_header.setStyleSheet(
            f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold; margin-top: 4px;"
        )
        self.lbl_acumulo_header.hide()
        layout.addWidget(self.lbl_acumulo_header)

        self.tbl_acumulo = QTableWidget()
        self.tbl_acumulo.setColumnCount(3)
        self.tbl_acumulo.setHorizontalHeaderLabels(["Estratégia", "Pernas", "Coeficiente"])
        self.tbl_acumulo.horizontalHeader().setStretchLastSection(True)
        self.tbl_acumulo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_acumulo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_acumulo.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.tbl_acumulo.setMaximumHeight(140)
        self.tbl_acumulo.setAlternatingRowColors(True)
        self.tbl_acumulo.setStyleSheet(f"""
            QTableWidget {{
                background-color: #1a1a2e; alternate-background-color: #1e1e34;
                color: #d0d0e0; gridline-color: #2a2a3e;
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                font-family: "JetBrains Mono", "Consolas", monospace; font-size: 8.5pt;
            }}
            QHeaderView::section {{
                background-color: #0f0f23; color: #a0a0c0;
                border: none; border-bottom: 1px solid {Palette.BORDER};
                padding: 3px 6px; font-weight: bold; font-size: 8pt;
            }}
        """)
        self.tbl_acumulo.hide()
        layout.addWidget(self.tbl_acumulo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_copiar = QPushButton("📋 Copiar Basket PNT")
        btn_copiar.setAutoDefault(False)
        btn_copiar.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_copiar.clicked.connect(self._copiar)
        btn_row.addWidget(btn_copiar)

        btn_montar = QPushButton("Monta no PNT")
        btn_montar.setAutoDefault(False)
        btn_montar.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a3d1a; color: {Palette.TEXT_PRIMARY};
                border: 1px solid #2d5a2d; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #2a5a2a; }}
        """)
        btn_montar.clicked.connect(self._montar_pnt)
        btn_row.addWidget(btn_montar)

        self.chk_acumular = QCheckBox("Acumular baskets")
        self.chk_acumular.setStyleSheet(f"""
            QCheckBox {{
                color: {Palette.CYAN}; font-size: 9pt; font-weight: bold;
                background-color: #2d2d44; border: 1px solid {Palette.CYAN};
                border-radius: 4px; padding: 5px 10px;
            }}
            QCheckBox:hover {{
                background-color: #3d3d55;
            }}
        """)
        self.chk_acumular.toggled.connect(self._on_acumular_toggled)
        btn_row.addWidget(self.chk_acumular)

        self.lbl_acumulo = QLabel("")
        self.lbl_acumulo.setStyleSheet(f"color: {Palette.CYAN}; font-size: 9pt; font-weight: bold;")
        btn_row.addWidget(self.lbl_acumulo)

        btn_limpar = QPushButton("Limpar")
        btn_limpar.setAutoDefault(False)
        btn_limpar.setStyleSheet(f"""
            QPushButton {{
                background-color: #3d1a1a; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 4px 10px; font-size: 8pt;
            }}
            QPushButton:hover {{ background-color: #5a2a2a; }}
        """)
        btn_limpar.clicked.connect(self._limpar_acumulo)
        self.btn_limpar = btn_limpar
        btn_row.addWidget(btn_limpar)
        self._atualizar_acumulo_ui()

        btn_row.addStretch()

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.clicked.connect(self.close)
        btn_fechar.setProperty("class", "primary")
        btn_row.addWidget(btn_fechar)

        layout.addLayout(btn_row)

    def _add_perna(self, ativo: str, lado: str, qtd: int, prof: int):
        row = self.tabela.rowCount()
        self.tabela.insertRow(row)

        item_ativo = QTableWidgetItem(ativo)
        item_ativo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 0, item_ativo)

        item_lado = QTableWidgetItem(lado)
        item_lado.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 1, item_lado)

        item_qtd = QTableWidgetItem(str(qtd))
        item_qtd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 2, item_qtd)

        item_prof = QTableWidgetItem(str(prof))
        item_prof.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 3, item_prof)

        item_apreg = QTableWidgetItem(str(QTD_APREGoada))
        item_apreg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 4, item_apreg)

        item_obs = QTableWidgetItem(OBSERVACAO)
        item_obs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabela.setItem(row, 5, item_obs)

    def _montar_pernas(self):
        r = self.r
        self.tabela.setRowCount(0)

        if self.strategy == "BOX 4P":
            qtd_put = _int_param(self.repo, "box_qtd_put", 1000)
            qtd_call = _int_param(self.repo, "box_qtd_call", 1000)
            prof_put = _int_param(self.repo, "box_prof_put", -1)
            prof_call = _int_param(self.repo, "box_prof_call", 1)
            self._add_perna(r.cod_put_k1, "C", qtd_put, prof_put)
            self._add_perna(r.cod_put_k2, "V", qtd_put, prof_put)
            self._add_perna(r.cod_call_k1, "V", qtd_call, prof_call)
            self._add_perna(r.cod_call_k2, "C", qtd_call, prof_call)
            self.lbl_coeficiente.setText(f"R$ {fmt_br(-getattr(r, 'clr', 0))}")

        elif self.strategy == "COLAR":
            qtd_ativo = _int_param(self.repo, "colar_qtd_ativo", 100)
            prof_ativo = _int_param(self.repo, "colar_prof_ativo", 1)
            qtd_call = _int_param(self.repo, "colar_qtd_call", 100)
            prof_call = _int_param(self.repo, "colar_prof_call", -1)
            qtd_put = _int_param(self.repo, "colar_qtd_put", 100)
            prof_put = _int_param(self.repo, "colar_prof_put", -1)
            ratio_call = getattr(r, 'ratio_call', 1.0) or 1.0
            ratio_put = getattr(r, 'ratio_put', 1.0) or 1.0
            self._add_perna(getattr(r, "ativo", ""), "C", qtd_ativo, prof_ativo)
            self._add_perna(getattr(r, "cod_call", ""), "V", int(qtd_call * ratio_call), prof_call)
            self._add_perna(getattr(r, "cod_put", ""), "C", int(qtd_put * ratio_put), prof_put)
            unitario = getattr(r, 'preco_compra', 0) + getattr(r, 'premio_put', 0) - getattr(r, 'premio_call', 0)
            self.lbl_coeficiente.setText(f"R$ {fmt_br(unitario)}")

        elif self.strategy == "COLLAR CALENDARIO":
            qtd_ativo = _int_param(self.repo, "calendario_qtd_ativo", 100)
            prof_ativo = _int_param(self.repo, "calendario_prof_ativo", 1)
            qtd_call = _int_param(self.repo, "calendario_qtd_call", 100)
            prof_call = _int_param(self.repo, "calendario_prof_call", -1)
            qtd_put = _int_param(self.repo, "calendario_qtd_put", 100)
            prof_put = _int_param(self.repo, "calendario_prof_put", -1)
            ratio_call = getattr(r, 'ratio_call', 1.0) or 1.0
            ratio_put = getattr(r, 'ratio_put', 1.0) or 1.0
            self._add_perna(getattr(r, "ativo", ""), "C", qtd_ativo, prof_ativo)
            self._add_perna(getattr(r, "cod_call", ""), "V", int(qtd_call * ratio_call), prof_call)
            self._add_perna(getattr(r, "cod_put", ""), "C", int(qtd_put * ratio_put), prof_put)
            unitario = getattr(r, 'preco_compra', 0) + getattr(r, 'premio_put', 0) - getattr(r, 'premio_call', 0)
            self.lbl_coeficiente.setText(f"R$ {fmt_br(unitario)}")

        elif self.strategy in ("BOX VENDIDO", "SBTH VENDIDA"):
            qtd_ativo = _int_param(self.repo, "vendidas_qtd_ativo", 100)
            prof_ativo = _int_param(self.repo, "vendidas_prof_ativo", 1)
            qtd_put = _int_param(self.repo, "vendidas_qtd_put", 100)
            prof_put = _int_param(self.repo, "vendidas_prof_put", 1)
            self._add_perna(getattr(r, "ativo", ""), "C", qtd_ativo, prof_ativo)
            self._add_perna(getattr(r, "cod_put", ""), "C", qtd_put, prof_put)
            if self.strategy == "BOX VENDIDO":
                qtd_call = _int_param(self.repo, "vendidas_qtd_call", 100)
                prof_call = _int_param(self.repo, "vendidas_prof_call", -1)
                self._add_perna(getattr(r, "cod_call", ""), "V", qtd_call, prof_call)
            self.lbl_coeficiente.setText(f"R$ {fmt_br(-getattr(r, 'recebimento', 0))}")

        elif self.strategy == "TAXA":
            qtd_ativo = _int_param(self.repo, "coberta_qtd_ativo", 100)
            prof_ativo = _int_param(self.repo, "coberta_prof_ativo", 1)
            qtd_call = _int_param(self.repo, "coberta_qtd_call", 100)
            prof_call = _int_param(self.repo, "coberta_prof_call", -1)
            self._add_perna(getattr(r, "ativo", ""), "V", qtd_ativo, prof_ativo)
            self._add_perna(getattr(r, "cod_call", ""), "C", qtd_call, prof_call)
            self.lbl_coeficiente.setText(f"R$ {fmt_br(getattr(r, 'recebimento', 0))}")

        elif self.strategy == "BASKET ITM":
            qtd_itm = _int_param(self.repo, "basket_qtd_call_itm", 100)
            prof_itm = _int_param(self.repo, "basket_prof_call_itm", 1)
            qtd_put = _int_param(self.repo, "basket_qtd_put", 100)
            prof_put = _int_param(self.repo, "basket_prof_put", -1)
            qtd_call = _int_param(self.repo, "basket_qtd_call", 100)
            prof_call = _int_param(self.repo, "basket_prof_call", -1)
            self._add_perna(getattr(r, "cod_call_itm", ""), "C", qtd_itm, prof_itm)
            self._add_perna(getattr(r, "cod_put_atm", ""), "C", qtd_put, prof_put)
            self._add_perna(getattr(r, "cod_call_atm", ""), "V", qtd_call, prof_call)
            self.lbl_coeficiente.setText(f"R$ {fmt_br(-getattr(r, 'coefic_mercado', 0))}")

        self.tabela.resizeColumnsToContents()
        self._leg_ativos = [
            self.tabela.item(row, 0).text()
            for row in range(self.tabela.rowCount())
        ]

    def _montar_linha(self) -> str:
        ativos = []
        lados = []
        qtds = []
        profs = []
        for row in range(self.tabela.rowCount()):
            ativos.append(self.tabela.item(row, 0).text())
            lados.append(self.tabela.item(row, 1).text())
            qtds.append(self.tabela.item(row, 2).text())
            profs.append(self.tabela.item(row, 3).text())
        coef_raw = self.lbl_coeficiente.text().replace("R$ ", "")
        partes = (
            ativos + lados + qtds + profs
            + [coef_raw]
            + [str(QTD_APREGoada)] * self.tabela.rowCount()
            + [OBSERVACAO]
        )
        return "\t".join(partes)

    def _copiar(self):
        linha = self._montar_linha()
        if self.chk_acumular.isChecked():
            _ACCUMULATOR.append((
                self.strategy,
                linha,
                " / ".join(self._leg_ativos),
                self.lbl_coeficiente.text(),
            ))
            copiar_basket_pnt([t[1] for t in _ACCUMULATOR])
            self._atualizar_acumulo_ui()
            texto = f"Basket #{len(_ACCUMULATOR)} adicionado.\n{len(_ACCUMULATOR)} baskets no total — cole no PnT."
        else:
            copiar_basket_pnt([linha])
            texto = "Basket copiado para a área de transferência.\nCole no PnT — Importar Basket."
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Copiado")
        msg.setText(texto)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        QTimer.singleShot(3000, msg.close)
        msg.exec_()

    def _montar_pnt(self):
        linha = self._montar_linha()
        copiar_basket_pnt([linha])
        executar_automacao_pnt()

    def _on_acumular_toggled(self, checked: bool):
        if not checked:
            _ACCUMULATOR.clear()
        self._atualizar_acumulo_ui()

    def _limpar_acumulo(self):
        _ACCUMULATOR.clear()
        self._atualizar_acumulo_ui()

    def _atualizar_acumulo_ui(self):
        n = len(_ACCUMULATOR)
        visible = n > 0
        self.tbl_acumulo.setVisible(visible)
        self.lbl_acumulo_header.setVisible(visible)
        if n:
            from collections import Counter
            contagem = Counter(t[0] for t in _ACCUMULATOR)
            detalhes = ", ".join(f"{v} {k}" for k, v in contagem.most_common())
            self.lbl_acumulo.setText(f"📦 {n} basket{'s' if n > 1 else ''} ({detalhes})")
            self.btn_limpar.show()
            self.tbl_acumulo.setRowCount(n)
            for i, (estr, _, pernas, coef) in enumerate(_ACCUMULATOR):
                self.tbl_acumulo.setItem(i, 0, QTableWidgetItem(estr))
                self.tbl_acumulo.setItem(i, 1, QTableWidgetItem(pernas))
                self.tbl_acumulo.setItem(i, 2, QTableWidgetItem(coef))
                for col in range(3):
                    self.tbl_acumulo.item(i, col).setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
            self.tbl_acumulo.resizeColumnsToContents()
        else:
            self.lbl_acumulo.setText("")
            self.btn_limpar.hide()
