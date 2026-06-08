from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.ui.desktop.theme import Palette
from src.domain.entities.parametro_operacional import ParametroOperacional


_REGRAS_CODIGO: dict[str, list[dict]] = {
    "BOX": [
        {"regra": "Viabilidade usa pct_cdi_liquido (pós-IR, 15%)", "origem": "calculadora_box.py"},
        {"regra": "Custos B3: emolumento + liquidacao + registro + ISS", "origem": "calculadora_custos_b3.py"},
        {"regra": "IR incide apenas sobre lucro liquido positivo", "origem": "calculadora_custos_b3.py"},
        {"regra": "Profundidade: cada perna deve ter qtd >= qtd_min_perna", "origem": "calculadora_box.py"},
        {"regra": "Rejeita strikes K1 >= K2", "origem": "calculadora_box.py"},
        {"regra": "Rejeita precos <= 0 em qualquer perna", "origem": "calculadora_box.py"},
        {"regra": "Rejeita em_leilao = True", "origem": "calculadora_box.py"},
        {"regra": "Soh aceita opcoes europeias se box_soh_europeia=1", "origem": "parametro_operacional.py"},
    ],
    "BOX_SINTETICO": [
        {"regra": "Strike maximo = elegibilidade_strike_max_pct do spot", "origem": "elegibilidade_pescaria.py"},
        {"regra": "3 pernas: compra Call ITM + compra Put ATM + venda Call ATM", "origem": "montadora_box_itm.py"},
        {"regra": "Oferta de venda > 0 e liquidez minima", "origem": "elegibilidade_pescaria.py"},
    ],
    "SBTH": [
        {"regra": "Viabilidade usa pct_cdi_liquido (pos-IR, 15%)", "origem": "calculadora_box_sbth.py"},
        {"regra": "Custos B3: 2 pernas", "origem": "calculadora_custos_b3.py"},
        {"regra": "Compra ativo + compra PUT (posicao long)", "origem": "calculadora_box_sbth.py"},
    ],
    "COLAR": [
        {"regra": "Viabilidade usa pct_cdi_liquido (pos-IR)", "origem": "calculadora_colar.py"},
        {"regra": "Melhor retorno sem clamp (calculado real)", "origem": "calculadora_colar.py"},
        {"regra": "Risco de leilao: Baixo/Medio/Alto por VOV+VOC", "origem": "calculadora_colar.py"},
        {"regra": "Strike max dist = colar_dist_max_pct do spot", "origem": "monitor_colares.py"},
        {"regra": "QUL minimo para PUT e CALL via parametros", "origem": "monitor_colares.py"},
        {"regra": "Collar: compra ativo + compra PUT OTM + venda CALL OTM", "origem": "calculadora_colar.py"},
        {"regra": "IV calculada via Brent (raiz de Black-Scholes)", "origem": "calculadora_colar.py"},
    ],
    "COLLAR_CALENDARIO": [
        {"regra": "Viabilidade usa pct_cdi_liquido (pos-IR)", "origem": "calculadora_colar_calendario.py"},
        {"regra": "DTE call entre dte_call_min e dte_call_max", "origem": "monitor_colares_calendario.py"},
        {"regra": "Spread DTE entre put e call entre dte_extra_min e dte_extra_max", "origem": "monitor_colares_calendario.py"},
        {"regra": "Strike diff max = calendario_strike_diff_pct", "origem": "monitor_colares_calendario.py"},
        {"regra": "Call OTM max = calendario_call_otm_max do spot", "origem": "monitor_colares_calendario.py"},
        {"regra": "DTE total max = dte_total_max", "origem": "monitor_colares_calendario.py"},
        {"regra": "Breakevens via Brent com e sem valor intrinseco", "origem": "calculadora_colar_calendario.py"},
        {"regra": "PV futuro descontado por dividendos", "origem": "calculadora_colar_calendario.py"},
    ],
    "BOX_4P": [
        {"regra": "Viabilidade usa pct_cdi_liquido (pos-IR)", "origem": "calculadora_box.py"},
        {"regra": "CLR = (bid C1 + bid P2) - (ask P1 + ask C2)", "origem": "calculadora_box.py"},
        {"regra": "Lucro = CLR - (strike_k2 - strike_k1)", "origem": "calculadora_box.py"},
        {"regra": "4 pernas, 2 strikes (K1 < K2)", "origem": "calculadora_box.py"},
        {"regra": "Profundidade minima = box_qtd_min por perna", "origem": "monitor_box.py"},
        {"regra": "Soh aceita opcoes europeias se box_soh_europeia=1", "origem": "parametro_operacional.py"},
    ],
    "MPP": [
        {"regra": "Score = 35% estrutural + 65% instantaneo x DTE x persistencia x bonus", "origem": "mpp_use_case.py"},
        {"regra": "Erro de paridade normalizado por spread bid-ask total", "origem": "mpp_use_case.py"},
        {"regra": "Persistencia: bonus ate mpp_persistencia_max_mult apos mpp_persistencia_divisor ciclos", "origem": "mpp_use_case.py"},
        {"regra": "MPP usa dados RTD instantaneos + opcoes.net.br estruturais", "origem": "mpp_use_case.py"},
    ],
}

_CUSTOS_FIXOS = (
    "Emolumento: 0,025% | Liquidacao: 0,0275% | "
    "Registro: 0,01% (se configurado) | ISS: 0% (se configurado) | "
    "IR: 15% swing trade"
)


class RegrasDialog(QDialog):
    def __init__(self, estrategia: str, db_path: str | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Regras Ativas — {estrategia}")
        self.setMinimumSize(580, 400)
        self.setStyleSheet(f"background-color: {Palette.BG_PRIMARY}; color: {Palette.TEXT_PRIMARY};")
        self._estrategia = estrategia
        self._db_path = db_path
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl_titulo = QLabel(f"Regras e Filtros — {self._estrategia}")
        lbl_titulo.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel("Parametros ativos lidos do banco de dados + regras do codigo-fonte.")
        lbl_sub.setStyleSheet(f"font-size: 9pt; color: {Palette.TEXT_MUTED};")
        layout.addWidget(lbl_sub)

        custos = QLabel(f"Custos: {_CUSTOS_FIXOS}")
        custos.setStyleSheet(f"font-size: 9pt; color: {Palette.YELLOW}; padding: 4px 8px; "
                             f"background-color: {Palette.BG_SECONDARY}; border-radius: 4px;")
        custos.setWordWrap(True)
        layout.addWidget(custos)

        # Tabela de parametros do DB
        tabela = QTableWidget()
        tabela.setColumnCount(3)
        tabela.setHorizontalHeaderLabels(["Parametro", "Valor Atual", "Descricao"])
        tabela.horizontalHeader().setStretchLastSection(True)
        tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tabela.setAlternatingRowColors(True)
        tabela.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Palette.BG_SECONDARY}; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                font-size: 9pt;
            }}
            QTableWidget::item {{ padding: 4px 8px; }}
            QHeaderView::section {{
                background-color: {Palette.BG_TERTIARY}; color: {Palette.TEXT_MUTED};
                font-weight: bold; border: none; padding: 6px;
            }}
        """)

        self._popular_tabela(tabela)
        layout.addWidget(tabela)

        # Regras do codigo
        lbl_regras = QLabel("Regras do codigo-fonte:")
        lbl_regras.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {Palette.TEXT_PRIMARY}; padding-top: 8px;")
        layout.addWidget(lbl_regras)

        regras_texto = self._montar_regras_codigo()
        txt_regras = QLabel(regras_texto)
        txt_regras.setStyleSheet(f"font-size: 9pt; color: {Palette.TEXT_SECONDARY}; "
                                  f"background-color: {Palette.BG_SECONDARY}; "
                                  f"border: 1px solid {Palette.BORDER}; border-radius: 4px; padding: 8px;")
        txt_regras.setWordWrap(True)
        layout.addWidget(txt_regras)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet(f"""
            QPushButton {{
                background-color: #e74c3c; color: #0d0d1a; border: none;
                border-radius: 4px; padding: 8px 20px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #c0392b; }}
        """)
        btn_fechar.clicked.connect(self.accept)

        hb = QHBoxLayout()
        hb.addStretch()
        hb.addWidget(btn_fechar)
        layout.addLayout(hb)

    def _popular_tabela(self, tabela: QTableWidget):
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self._db_path)
        params = repo.get_by_estrategia(self._estrategia)
        params_dict: dict[str, ParametroOperacional] = {}
        for p in params:
            params_dict[p.chave] = p

        # Busca tambem parametros GERAL que sao relevantes
        if self._estrategia != "GERAL":
            gerais = repo.get_by_estrategia("GERAL")
            for p in gerais:
                if p.chave in ("taxa_cdi", "taxa_emolumento_pct", "taxa_liquidacao_pct",
                               "taxa_registro_pct", "taxa_iss_pct", "taxa_ir_pct"):
                    params_dict[p.chave] = p

        linhas = sorted(params_dict.items(), key=lambda x: x[0])
        tabela.setRowCount(len(linhas))

        font_valor = QFont("Consolas", 9)
        for i, (chave, p) in enumerate(linhas):
            item_chave = QTableWidgetItem(chave)
            item_chave.setToolTip(p.descricao)
            tabela.setItem(i, 0, item_chave)

            item_valor = QTableWidgetItem(str(p.valor))
            item_valor.setFont(font_valor)
            tabela.setItem(i, 1, item_valor)

            item_desc = QTableWidgetItem(p.descricao)
            tabela.setItem(i, 2, item_desc)

    def _montar_regras_codigo(self) -> str:
        regras = _REGRAS_CODIGO.get(self._estrategia)
        if not regras:
            return "(nenhuma regra especifica documentada para esta estrategia)"
        linhas = []
        for r in regras:
            linhas.append(f"  - {r['regra']}  [{r['origem']}]")
        return "\n".join(linhas)
