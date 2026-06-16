import winsound

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableView, QHeaderView, QAbstractItemView, QTextEdit, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.ui.desktop.column_utils import salvar_ordem_colunas, restaurar_ordem_colunas
from src.ui.desktop.mpp_table_model import MppTableModel
from src.ui.desktop.theme import Palette
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.domain.entities.parametro_operacional import ParametroOperacional


class MppDialog(QDialog):
    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("MPP — Motor de Priorização de Pescaria")
        self.setMinimumSize(900, 500)
        self.resize(1000, 600)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Palette.BG_DARK};
            }}
            QLabel {{
                color: {Palette.TEXT_PRIMARY};
                font-size: 9pt;
            }}
            QTextEdit {{
                background-color: {Palette.BG_BASE};
                color: {Palette.TEXT_SECONDARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }}
        """)

        self._model = MppTableModel()
        self._som_ativado = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header = QLabel("Ranking de Pescaria — Boxes ordenados por Score Final")
        header.setStyleSheet(f"color: {Palette.CYAN}; font-size: 11pt; font-weight: bold;")
        self._lbl_mpp_status = QLabel("🔴 MPP Desligado")
        self._lbl_mpp_status.setStyleSheet(f"color: {Palette.RED}; font-size: 9pt; font-weight: bold; padding: 2px 8px;")
        header_row.addWidget(self._lbl_mpp_status)

        self.btn_bell = QPushButton("🔔")
        self.btn_bell.setFixedSize(26, 24)
        self.btn_bell.setToolTip("Som: desligado (clique para ligar)")
        self.btn_bell.setCursor(Qt.PointingHandCursor)
        self.btn_bell.setCheckable(True)
        self.btn_bell.setStyleSheet("""
            QPushButton {
                background-color: #3d1a1a; color: #ef4444;
                border: 1px solid #ef4444; border-radius: 4px;
                font-size: 11pt; padding: 0;
            }
            QPushButton:hover { background-color: #5d2a2a; }
            QPushButton:checked {
                background-color: #1a3d1a; color: #22c55e;
                border: 1px solid #22c55e;
            }
            QPushButton:checked:hover { background-color: #2a5d2a; }
        """)
        self.btn_bell.toggled.connect(self._toggle_som)
        header_row.addWidget(self.btn_bell)

        header_row.addStretch()
        layout.addLayout(header_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        table_container = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setModel(self._model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSortingEnabled(False)
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setDragEnabled(True)
        header.sectionMoved.connect(lambda: salvar_ordem_colunas(header, "mpp_table_order"))
        restaurar_ordem_colunas(header, "mpp_table_order")
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(28)
        self.table_view.verticalHeader().hide()
        self.table_view.setShowGrid(True)
        font = QFont("Consolas", 9)
        self.table_view.setFont(font)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setStyleSheet(f"""
            QTableView {{
                background-color: {Palette.BG_DARK};
                alternate-background-color: {Palette.BG_BASE};
                border: 1px solid {Palette.BORDER};
                gridline-color: {Palette.BORDER};
                selection-background-color: {Palette.BG_RAISED};
            }}
            QHeaderView::section {{
                background-color: {Palette.BG_BASE};
                color: {Palette.TEXT_MUTED};
                border: 1px solid {Palette.BORDER};
                padding: 4px;
                font-weight: bold;
            }}
        """)
        self.table_view.selectionModel().selectionChanged.connect(self._on_selecao)
        splitter.addWidget(self.table_view)

        details_container = QVBoxLayout()
        details_header = QLabel("Detalhes da Oportunidade")
        details_header.setStyleSheet(f"color: {Palette.CYAN}; font-size: 10pt; font-weight: bold;")
        details_container.addWidget(details_header)

        self._details_edit = QTextEdit()
        self._details_edit.setReadOnly(True)
        self._details_edit.setMinimumHeight(100)
        self._details_edit.setPlaceholderText("Selecione um box para ver detalhes...")
        details_container.addWidget(self._details_edit)

        details_widget = QLabel()
        details_widget.setLayout(details_container)
        splitter.addWidget(details_widget)

        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_toggle = QPushButton("🟢 Ativar MPP")
        self.btn_toggle.setToolTip("Liga/Desliga o MPP no banco de dados")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a3d1a;
                color: #22c55e;
                border: 1px solid #22c55e; border-radius: 4px;
                padding: 6px 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2a5d2a; }}
            QPushButton:checked {{
                background-color: #3d1a1a; color: #ef4444;
                border: 1px solid #ef4444;
            }}
            QPushButton:checked:hover {{ background-color: #5d2a2a; }}
        """)
        self.btn_toggle.toggled.connect(self._toggle_mpp)
        btn_layout.addWidget(self.btn_toggle)

        self.btn_regras = QPushButton("📋 Regras")
        self.btn_regras.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: #8b8be0;
                border: 1px solid #8b8be066; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #8b8be022; }}
        """)
        self.btn_regras.setVisible(False)
        self.btn_regras.clicked.connect(self._abrir_regras)
        btn_layout.addWidget(self.btn_regras)

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.setStyleSheet(f"""
            QPushButton {{
                background-color: {Palette.BG_RAISED};
                color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {Palette.BG_HOVER};
            }}
        """)
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def atualizar(self, boxes: list, mres: list):
        self._model.atualizar(boxes, mres)
        if self._som_ativado and boxes:
            winsound.Beep(1000, 200)

    def _abrir_regras(self):
        from src.ui.desktop.regras_dialog import RegrasDialog
        dlg = RegrasDialog("MPP", self.db_path, self)
        dlg.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R and event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier):
            self.btn_regras.setVisible(not self.btn_regras.isVisible())
        else:
            super().keyPressEvent(event)

    def set_status_enabled(self, enabled: bool):
        if enabled:
            self._lbl_mpp_status.setText("🟢 MPP Ativo")
            self._lbl_mpp_status.setStyleSheet(f"color: {Palette.GREEN}; font-size: 9pt; font-weight: bold; padding: 2px 8px;")
        else:
            self._lbl_mpp_status.setText("🔴 MPP Desligado")
            self._lbl_mpp_status.setStyleSheet(f"color: {Palette.RED}; font-size: 9pt; font-weight: bold; padding: 2px 8px;")
        self.btn_toggle.blockSignals(True)
        self.btn_toggle.setChecked(enabled)
        self.btn_toggle.setText("🔴 Desativar MPP" if enabled else "🟢 Ativar MPP")
        self.btn_toggle.blockSignals(False)

    def _toggle_mpp(self, ativo: bool):
        repo = ParametroRepository(self.db_path)
        param = repo.get_by_chave("mpp_habilitado")
        if param:
            param.valor = 1.0 if ativo else 0.0
            repo.save(param)
        else:
            d = ParametroOperacional.PARAMETROS_DEFAULT.get("mpp_habilitado", {})
            p = ParametroOperacional(
                chave="mpp_habilitado",
                valor=1.0 if ativo else 0.0,
                estrategia=d.get("estrategia", "BOX_4P"),
                descricao=d.get("descricao", ""),
            )
            repo.save(p)
        self.btn_toggle.setText("🔴 Desativar MPP" if ativo else "🟢 Ativar MPP")
        main = self.parent() if hasattr(self, 'parent') else None
        if main and hasattr(main, '_worker'):
            main._worker.recarregar_parametros()

    def _toggle_som(self, ativo: bool):
        self._som_ativado = ativo
        self.btn_bell.setToolTip("Som: ligado" if ativo else "Som: desligado")

    def _on_selecao(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            return
        row = indexes[0].row()
        box = self._model.get_box(row)
        mre = self._model.get_mre(row)
        self._exibir_detalhes(box, mre)

    FIELD_DESC = {
        "Score Final": "Score final (0-100) = estrutural×35% + instantâneo×65%, ajustado por persistência e bônus histórico",
        "Score Estrutural": "Score estrutural (0-1) — média dos scores OI, volume e curvatura IV. Calculado 1x/dia via opcoes.net.br",
        "Score Instantâneo": "Score instantâneo (0-1) — combina erro de paridade, spread, profundidade, imbalance e anomalia. Atualizado a cada 60s via RTD",
        "Nível de Risco": "crítico (≥85), alto (≥70), médio (≥50), baixo (<50)",
        "Erro de Paridade": "Desvio da put-call parity (C-P vs S-K*e^-rt) usando preços mid. Maior erro = maior distorção",
        "Spread Médio": "Média do spread bid-ask das 4 pernas. Spread alto = book menos eficiente = mais espaço para pescar",
        "Profundidade Mínima": "Score de profundidade (0-1). Menor profundidade = maior score = mais chance de impacto ao entrar",
        "Profundidade (qtd)": "Quantidade mínima de contratos disponíveis entre as 4 pernas (lado mais fraco do book)",
        "Persistência": "Ciclos consecutivos (60s cada) que este par de strikes mantém erro de paridade >2%. Multiplica score final em até 1.5x",
        "Justificativa": "Fatores que mais contribuíram para o score final",
    }

    MRE_DESC = {
        "Isca Recomendada": "Perna com maior Índice de Pescabilidade (IP). É a ordem recomendada para pendurar primeiro",
        "IP da Isca": "Índice de Pescabilidade (0-1). Ponderado: spread (40%), profundidade (30%), persistência (20%), imbalance (10%)",
        "Lote Sugerido": "Lote em contratos = min(lote_base, profundidade_min × 20%). Usa o lado mais fraco do book",
        "Confiança de Completar": "Probabilidade estimada de conseguir montar as 3 pernas restantes. Baseado em profundidade × spread favorável",
        "Nível": "baixa (<30%), média (30-70%), alta (>70%)",
    }

    def _exibir_detalhes(self, box, mre):
        if not box:
            self._details_edit.setText("Nenhum box selecionado.")
            return

        html = []
        html.append(f"<h3 style='color:{Palette.CYAN}; margin:0 0 4px 0;'>{box.ativo} — {box.strike1:.0f} x {box.strike2:.0f}</h3>")

        if box.cod_call_k1:
            html.append("<table style='width:100%; font-size:9pt; margin:0 0 8px 0;'>")
            html.append("<tr style='border-bottom:1px solid #2d2d44;'>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; font-weight:bold; padding:2px 8px 2px 0;'>Perna 1 (K1 Call)</td>")
            html.append(f"  <td style='color:{Palette.TEXT_PRIMARY}; font-family:Consolas; padding:2px 8px;'>{box.cod_call_k1}</td>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; padding:2px 0;'>Strike {box.strike1:.2f}</td>")
            html.append("</tr>")
            html.append("<tr style='border-bottom:1px solid #2d2d44;'>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; font-weight:bold; padding:2px 8px 2px 0;'>Perna 2 (K1 Put)</td>")
            html.append(f"  <td style='color:{Palette.TEXT_PRIMARY}; font-family:Consolas; padding:2px 8px;'>{box.cod_put_k1}</td>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; padding:2px 0;'>Strike {box.strike1:.2f}</td>")
            html.append("</tr>")
            html.append("<tr style='border-bottom:1px solid #2d2d44;'>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; font-weight:bold; padding:2px 8px 2px 0;'>Perna 3 (K2 Call)</td>")
            html.append(f"  <td style='color:{Palette.TEXT_PRIMARY}; font-family:Consolas; padding:2px 8px;'>{box.cod_call_k2}</td>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; padding:2px 0;'>Strike {box.strike2:.2f}</td>")
            html.append("</tr>")
            html.append("<tr style='border-bottom:1px solid #2d2d44;'>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; font-weight:bold; padding:2px 8px 2px 0;'>Perna 4 (K2 Put)</td>")
            html.append(f"  <td style='color:{Palette.TEXT_PRIMARY}; font-family:Consolas; padding:2px 8px;'>{box.cod_put_k2}</td>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; padding:2px 0;'>Strike {box.strike2:.2f}</td>")
            html.append("</tr>")
            html.append("</table>")

        html.append(f"<p style='color:{Palette.TEXT_MUTED}; font-size:8pt; margin:0 0 8px 0;'>Venc: {box.vencimento}</p>")
        html.append("<hr style='border-color:#2d2d44;'>")

        html.append("<table style='width:100%; font-size:9pt;'>")

        items = [
            ("Score Final",             f"<b style='color:{Palette.CYAN};'>{box.score_final_pct:.0f}</b> / 100", self.FIELD_DESC.get("Score Final", "")),
            ("Score Estrutural",        f"{box.score_estrutural_box:.4f}", self.FIELD_DESC.get("Score Estrutural", "")),
            ("Score Instantâneo",       f"{box.score_instantaneo_box:.4f}", self.FIELD_DESC.get("Score Instantâneo", "")),
            ("Nível de Risco",          f"{box.nivel_risco}", self.FIELD_DESC.get("Nível de Risco", "")),
            ("Erro de Paridade",        f"{box.erro_paridade_box:.4f}", self.FIELD_DESC.get("Erro de Paridade", "")),
            ("Spread Médio",            f"{box.spread_medio:.1%}", self.FIELD_DESC.get("Spread Médio", "")),
            ("Profundidade Mínima",     f"{box.profundidade_min:.4f}", self.FIELD_DESC.get("Profundidade Mínima", "")),
            ("Profundidade (qtd)",      f"{box.qtd_min_box} contratos", self.FIELD_DESC.get("Profundidade (qtd)", "")),
            ("Persistência",            f"{box.persistencia_ciclos} ciclos", self.FIELD_DESC.get("Persistência", "")),
        ]

        for label, value, desc in items:
            html.append(f"<tr style='border-bottom:1px solid #1a1a2e;'>")
            html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; font-weight:bold; padding:3px 8px 3px 0; white-space:nowrap;'>{label}</td>")
            html.append(f"  <td style='color:{Palette.TEXT_PRIMARY}; padding:3px 8px;'>{value}</td>")
            html.append(f"  <td style='color:{Palette.TEXT_MUTED}; font-size:8pt; padding:3px 0;'><i>{desc}</i></td>")
            html.append(f"</tr>")

        html.append("</table>")

        if box.justificativa:
            html.append("<hr style='border-color:#2d2d44;'>")
            html.append(f"<p style='color:{Palette.TEXT_MUTED}; font-size:8pt; margin:4px 0;'><b>Justificativa:</b> {box.justificativa} <i>({self.FIELD_DESC.get('Justificativa', '')})</i></p>")

        if mre:
            html.append("<hr style='border-color:#2d2d44;'>")
            html.append(f"<h4 style='color:{Palette.CYAN}; margin:4px 0;'>🎯 Recomendação MRE</h4>")
            html.append("<table style='width:100%; font-size:9pt;'>")
            mre_items = [
                ("Isca Recomendada",       mre.isca_recomendada, self.MRE_DESC.get("Isca Recomendada", "")),
                ("IP da Isca",             f"{mre.ip_isca:.2f}", self.MRE_DESC.get("IP da Isca", "")),
                ("Lote Sugerido",          str(mre.lote_sugerido), self.MRE_DESC.get("Lote Sugerido", "")),
                ("Confiança de Completar", f"{mre.confianca_completar:.1%}", self.MRE_DESC.get("Confiança de Completar", "")),
                ("Nível",                  mre.nivel_recomendacao, self.MRE_DESC.get("Nível", "")),
            ]
            for label, value, desc in mre_items:
                html.append(f"<tr style='border-bottom:1px solid #1a1a2e;'>")
                html.append(f"  <td style='color:{Palette.TEXT_SECONDARY}; font-weight:bold; padding:3px 8px 3px 0; white-space:nowrap;'>{label}</td>")
                html.append(f"  <td style='color:{Palette.TEXT_PRIMARY}; padding:3px 8px;'>{value}</td>")
                html.append(f"  <td style='color:{Palette.TEXT_MUTED}; font-size:8pt; padding:3px 0;'><i>{desc}</i></td>")
                html.append(f"</tr>")
            html.append("</table>")
            if mre.justificativa:
                html.append(f"<p style='color:{Palette.TEXT_MUTED}; font-size:8pt; margin:4px 0;'>{mre.justificativa}</p>")

        self._details_edit.setHtml("\n".join(html))


