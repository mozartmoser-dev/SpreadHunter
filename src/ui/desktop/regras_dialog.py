from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.ui.desktop.theme import Palette
from src.domain.entities.parametro_operacional import ParametroOperacional


_REGRAS_ESTRUTURAIS: dict[str, list[str]] = {
    "BOX": [
        "CLR = (Bid_CALL_K1 + Ask_PUT_K1) − (Bid_CALL_K2 + Ask_PUT_K2)",
        "Lucro = CLR − (K2 − K1)",
        "Custos B3: emolumento (0,025%%) + liquidação (0,0275%%) + registro (0,01%%) + ISS (0%%) por perna",
        "IR (15%%) incide apenas sobre lucro líquido positivo — NÃO usado como filtro de viabilidade",
        "Rejeita strikes K1 >= K2",
        "Rejeita preços <= 0 em qualquer perna",
        "Rejeita instrumentos em leilão",
    ],
    "BOX_SINTETICO": [
        "Strike máximo = elegibilidade_strike_max_pct do spot",
        "3 pernas: compra Call ITM + compra Put ATM + venda Call ATM",
        "Oferta de venda > 0 e liquidez mínima",
    ],
    "SBTH": [
        "Custos B3: 2 pernas (opção + ação)",
        "Compra ativo + compra PUT (posição long sintético)",
        "IR (15%%) não usado como filtro de viabilidade",
    ],
    "COLAR": [
        "Collar: compra ativo + compra PUT OTM + venda CALL OTM",
        "Melhor retorno sem clamp (calculado real)",
        "Risco de leilão: Baixo/Médio/Alto por VOV+VOC",
        "IV calculada via Brent (raiz de Black-Scholes)",
    ],
    "COLLAR_CALENDARIO": [
        "Breakevens via Brent com e sem valor intrínseco",
        "PV futuro descontado por dividendos",
        "IR (15%%) não usado como filtro de viabilidade",
    ],
    "BOX_4P": [
        "CLR = (Bid_CALL_K1 + Bid_PUT_K2) − (Ask_PUT_K1 + Ask_CALL_K2)",
        "Lucro = CLR − (K2 − K1)",
        "4 pernas, 2 strikes (K1 < K2)",
        "Custos B3: emolumento + liquidação + registro + ISS por perna",
        "IR (15%%) incide sobre lucro — NÃO usado como filtro de viabilidade",
    ],
    "MPP": [
        "Score = 35%% estrutural + 65%% instantâneo × DTE × persistência × bônus",
        "Erro de paridade normalizado por spread bid-ask total",
        "Persistência: bônus até mpp_persistencia_max_mult após mpp_persistencia_divisor ciclos",
        "MPP usa dados RTD instantâneos + opcoes.net.br estruturais",
    ],
}

_REGRAS_PARAM_MAP: dict[str, dict[str, str]] = {
    "BOX": {
        "premio_risco": "Viabilidade: x CDI (pós B3, antes IR) >= {}",
    },
    "SBTH": {
        "premio_risco_box": "Viabilidade BOX: x CDI (pós B3, antes IR) >= {}",
        "premio_risco_sbth": "Viabilidade SBTH: x CDI (pós B3, antes IR) >= {}",
    },
    "COLAR": {
        "premio_risco_colar": "Viabilidade: x CDI (pós B3, antes IR) >= {}",
        "colar_dist_max_pct": "Strike max distante = {}% do spot",
    },
    "COLLAR_CALENDARIO": {
        "premio_risco": "Viabilidade: x CDI (pós B3, antes IR) >= {}",
        "dte_call_min": "DTE call mínima = {} dias",
        "dte_call_max": "DTE call máxima = {} dias",
        "dte_extra_min": "Diferença DTE put−call mínima = {} dias",
        "dte_extra_max": "Diferença DTE put−call máxima = {} dias",
        "calendario_strike_diff_max": "Diferença máxima de strikes = {} níveis",
        "calendario_call_otm_max": "Call OTM máxima = {}% do spot",
        "dte_total_max": "DTE total máximo = {} dias",
    },
    "BOX_4P": {
        "premio_risco": "Viabilidade: x CDI (pós B3, antes IR) >= {}",
        "box_qtd_min": "Profundidade mínima: qtd por perna >= {}",
        "box_soh_europeia": "Aceita apenas opções europeias = {}",
    },
}


_CUSTOS_FIXOS = (
    "Emolumento: 0,025% | Liquidacao: 0,0275% | "
    "Registro: 0,01% (se configurado) | ISS: 0% (se configurado) | "
    "IR: 15% swing trade (exibido, NÃO usado como filtro)"
)


class RegrasDialog(QDialog):
    def __init__(self, estrategia: str, db_path: str | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Regras Ativas — {estrategia}")
        self.setMinimumSize(580, 400)
        self.setStyleSheet(f"background-color: {Palette.BG_BASE}; color: {Palette.TEXT_PRIMARY};")
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
                             f"background-color: {Palette.BG_SURFACE}; border-radius: 4px;")
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
                background-color: {Palette.BG_SURFACE}; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                font-size: 9pt;
            }}
            QTableWidget::item {{ padding: 4px 8px; }}
            QHeaderView::section {{
                background-color: {Palette.BG_RAISED}; color: {Palette.TEXT_MUTED};
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
                                  f"background-color: {Palette.BG_SURFACE}; "
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
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self._db_path)
        params = repo.get_by_estrategia(self._estrategia)
        param_map = {p.chave: p.valor for p in params}

        linhas = []

        # 1. Regras paramétricas (dinâmicas — valores atuais do DB)
        param_templates = _REGRAS_PARAM_MAP.get(self._estrategia, {})
        for chave, template in param_templates.items():
            valor = param_map.get(chave)
            if valor is not None:
                # Formata porcentagens e decimais
                if isinstance(valor, float):
                    if "x CDI" in template or "Viabilidade" in template:
                        texto = template.format(f"{valor:.2f}")
                    elif "%" in template:
                        texto = template.format(f"{valor * 100:.2f}")
                    else:
                        texto = template.format(str(valor))
                else:
                    texto = template.format(str(valor))
                linhas.append(texto)

        # 2. Regras estruturais (fixas — fórmulas, definições)
        estruturais = _REGRAS_ESTRUTURAIS.get(self._estrategia, [])
        linhas.extend(estruturais)

        if not linhas:
            return "(nenhuma regra específica documentada para esta estratégia)"

        return "\n".join(f"  - {l}" for l in linhas)
