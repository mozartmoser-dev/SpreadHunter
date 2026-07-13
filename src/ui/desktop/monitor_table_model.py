from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

from src.application.dtos.dtos import OportunidadeMonitor
from src.ui.desktop.flag_icons import flag_icon
from src.ui.desktop.theme import Palette


CUSTOS_DISCLOSURE = (
    "\n\n* Custos já incluem taxa B3 (emolumento 0,025% + liquidação 0,0275% por perna) "
    "e IR (15% sobre o lucro líquido)."
)


class MonitorTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Tipo (i)", "label_tipo"),
        ("Ativo (i)", "ativo"),
        ("Strike (i)", "strike"),
        ("GANHO%BRUTO", "ganho_bruto_display"),
        ("GANHO%LIQ", "ganho_liq_display"),
        ("RENT.CDIBRUTO", "rent_cdi_bruto_display"),
        ("RENT.CDILIQ", "rent_cdi_liq_display"),
        ("Dias (i)", "label_dias"),
        ("Vencimento (i)", "vencimento"),
        ("Liq (i)", "liq_indicator"),
        ("Leilao", "leilao_display"),
        ("Custo BOX", "custo_box_display"),
        ("Custo SBTH", "custo_sbth_display"),
        ("Liq Put", "liq_put_display"),
        ("Liq Call", "liq_call_display"),
        ("Money (i)", "money_display"),
        ("Of Cp Put", "of_compra_put"),
        ("Of Vd Call", "of_venda_call"),
        ("Qul Put", "qul_put"),
        ("Qul Call", "qul_call"),
        ("MOD", "tipo_opcao"),
        ("Cod Put", "cod_put"),
        ("Cod Call", "cod_call"),
        ("BTC", "taxa_aluguel"),
        ("Detectado", "label_detectado"),
    ]

    HIDDEN_BY_DEFAULT = {
        "custo_box_display", "custo_sbth_display",
        "liq_put_display", "liq_call_display",
        "money_display",
        "of_compra_put", "of_venda_call",
        "qul_put", "qul_call",
        "tipo_opcao", "cod_put", "cod_call",
        "leilao_display",
        "label_detectado",
    }

    _BG_VIABLE_BOX = QColor(Palette.ROW_BOX)
    _BG_VIABLE_SBTH = QColor(Palette.ROW_SBTH)
    _BG_VIABLE_BOXSBTH = QColor(Palette.ROW_BOXSBTH)
    _BG_NOT_VIABLE = QColor(Palette.ROW_NOT_VIABLE)
    _BG_LEILAO = QColor(Palette.ROW_LEILAO)

    _FG_GREEN = QBrush(QColor(Palette.LIQ_POSITIVE))
    _FG_RED = QBrush(QColor(Palette.LIQ_NEGATIVE))
    _FG_STRIKEOUT = QBrush(QColor(Palette.STRIKEOUT_COLOR))
    _FG_PRIMARY = QBrush(QColor(Palette.TEXT_PRIMARY))
    _FG_MUTED = QBrush(QColor(Palette.TEXT_MUTED))

    _CENTER_COLS = {
        "strike", "custo_sbth_display", "custo_box_display",
        "ganho_bruto_display", "ganho_liq_display",
        "rent_cdi_bruto_display", "rent_cdi_liq_display",
        "label_dias", "leilao_display", "liq_indicator",
        "liq_put_display", "liq_call_display", "of_compra_put", "of_venda_call",
        "qul_put", "qul_call", "money_display", "tipo_opcao", "taxa_aluguel",
        "label_detectado",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._oportunidades: list[OportunidadeMonitor] = []
        self._key_map: dict[int, int] = {}

    def rowCount(self, parent=None):
        return len(self._oportunidades)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or not (0 <= section < len(self.COLUMNS)):
            return None
            
        if role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][0]
            
        if role == Qt.ItemDataRole.ToolTipRole:
            tips = {
                "label_tipo": "Tipo de estratégia identificada (BOX, SBTH ou BOX+SBTH).",
                "ativo": "Código da ação objeto (ex: PETR4) que dá origem às opções.",
                "strike": "Preço de exercício das opções envolvidas na estrutura.",
                "ganho_bruto_display": "Ganho percentual BRUTO — sem descontar taxas B3 nem IR." + CUSTOS_DISCLOSURE,
                "ganho_liq_display": "Ganho percentual LÍQUIDO — com taxas B3 e IR descontados (valor que efetivamente sobra)." + CUSTOS_DISCLOSURE,
                "rent_cdi_bruto_display": "Rentabilidade BRUTA comparada à taxa CDI do período (sem descontos)." + CUSTOS_DISCLOSURE,
                "rent_cdi_liq_display": "Rentabilidade LÍQUIDA comparada à taxa CDI — B3 e IR descontados." + CUSTOS_DISCLOSURE,
                "label_dias": "Quantidade de dias corridos até a data de vencimento.",
                "vencimento": "Data de expiração das opções da montagem.",
                "liq_indicator": "Sinalizador de liquidez (✓: Ambos lados ok, ✗: Falta liquidez).",
                "leilao_display": "Indica se o ativo está em leilão (negociação suspensa temporariamente).",
                "custo_box_display": "Custo de montagem da perna de BOX (entrada de capital)." + CUSTOS_DISCLOSURE,
                "custo_sbth_display": "Custo de montagem da perna de SBTH (entrada de capital)." + CUSTOS_DISCLOSURE,
                "liq_put_display": "Liquidez em contratos da PUT (quantidade de ofertas de compra × lote padrão).",
                "liq_call_display": "Liquidez em contratos da CALL (quantidade de ofertas de venda × lote padrão).",
                "money_display": "Indica se as opções estão 'Dentro do Dinheiro' (P: Put, C: Call).",
                "of_compra_put": "Oferta de compra da PUT (bid) — maior preço que alguém paga.",
                "of_venda_call": "Oferta de venda da CALL (ask) — menor preço que alguém vende.",
                "qul_put": "Quantidade de contratos negociados da PUT no pregão (volume).",
                "qul_call": "Quantidade de contratos negociados da CALL no pregão (volume).",
                "tipo_opcao": "MOD — estilo da opção: 🇺🇸 = Americana (A) | 🇪🇺 = Europeia (E).",
                "cod_put": "Código do ativo da PUT na B3.",
                "cod_call": "Código do ativo da CALL na B3.",
                "taxa_aluguel": "Taxa de aluguel (BTC) da ação objeto — InvestSite.",
                "label_detectado": "Data e hora (Brasília) em que o monitor detectou a oportunidade pelo RTD (DD/MM/YYYY HH:MM:SS). Útil para correlacionar com o book.",
            }
            col_key = self.COLUMNS[section][1]
            base = tips.get(col_key, self.COLUMNS[section][0])
            if col_key in ("ganho_bruto_display", "ganho_liq_display",
                           "rent_cdi_bruto_display", "rent_cdi_liq_display",
                           "custo_box_display", "custo_sbth_display"):
                return base
            return base
            
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._oportunidades):
            return None

        opp = self._oportunidades[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_data(opp, col_key)

        if role == Qt.ItemDataRole.BackgroundRole:
            return self._background_data(opp, col_key)

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground_data(opp, col_key)

        if role == Qt.ItemDataRole.FontRole:
            return self._font_data(opp, col_key)

        if role == Qt.ItemDataRole.DecorationRole and col_key == "tipo_opcao":
            return flag_icon(opp.tipo_opcao)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in self._CENTER_COLS:
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def _display_data(self, opp: OportunidadeMonitor, col_key: str):
        if col_key == "label_tipo":
            return opp.label_tipo
        if col_key == "rent_cdi_bruto_display":
            return opp.rent_cdi_bruto_display
        if col_key == "rent_cdi_liq_display":
            return opp.rent_cdi_liq_display
        if col_key == "ganho_bruto_display":
            return opp.ganho_bruto_display
        if col_key == "ganho_liq_display":
            return opp.ganho_liq_display
        if col_key == "label_dias":
            return opp.label_dias
        if col_key == "strike":
            return "{:.2f}".format(opp.strike)
        if col_key == "custo_sbth_display":
            return opp.custo_sbth_display
        if col_key == "custo_box_display":
            return opp.custo_box_display
        if col_key == "leilao_display":
            return "\u26a0 LEILAO" if opp.em_leilao else ""
        if col_key == "liq_indicator":
            put_ok = opp.liq_put_x_lote >= 0
            call_ok = opp.liq_call_x_lote >= 0
            if put_ok and call_ok:
                return "\u2713"
            if not put_ok and not call_ok:
                return "\u2717"
            return "\u2713~"
        if col_key == "liq_put_display":
            return "{:.0f}".format(opp.liq_put_x_lote)
        if col_key == "liq_call_display":
            return "{:.0f}".format(opp.liq_call_x_lote)
        if col_key == "of_compra_put":
            return "{:.2f}".format(opp.of_compra_put) if opp.of_compra_put > 0 else "-"
        if col_key == "of_venda_call":
            return "{:.2f}".format(opp.of_venda_call) if opp.of_venda_call > 0 else "-"
        if col_key == "qul_put":
            return "{:.0f}".format(opp.qul_put) if opp.qul_put > 0 else "-"
        if col_key == "qul_call":
            return "{:.0f}".format(opp.qul_call) if opp.qul_call > 0 else "-"
        if col_key == "money_display":
            return opp.money_display
        if col_key == "taxa_aluguel":
            return "{:.2f}%".format(opp.taxa_aluguel)
        if col_key == "label_detectado":
            return opp.label_detectado
        if col_key == "tipo_opcao":
            return ""
        value = getattr(opp, col_key, None)
        if value is None:
            return ""
        
        # Formata datas no padrao brasileiro
        from datetime import date
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
            
        return str(value)

    def _background_data(self, opp: OportunidadeMonitor, col_key: str):
        if opp.em_leilao:
            return QBrush(self._BG_LEILAO)
        if not opp.viavel:
            return QBrush(self._BG_NOT_VIABLE)
        if opp.classificacao == "1BOX":
            return QBrush(self._BG_VIABLE_BOX)
        if opp.classificacao == "2SBTH":
            return QBrush(self._BG_VIABLE_SBTH)
        if opp.classificacao == "3BOXSBTH":
            return QBrush(self._BG_VIABLE_BOXSBTH)
        return None

    def _foreground_data(self, opp: OportunidadeMonitor, col_key: str):
        is_box = opp.classificacao in ("1BOX", "3BOXSBTH")
        is_sbth = opp.classificacao in ("2SBTH", "3BOXSBTH")

        if col_key == "leilao_display" and opp.em_leilao:
            return self._FG_RED

        if col_key == "liq_indicator":
            put_ok = opp.liq_put_x_lote >= 0
            call_ok = opp.liq_call_x_lote >= 0
            if put_ok and call_ok:
                return self._FG_GREEN
            if not put_ok and not call_ok:
                return self._FG_RED
            return QBrush(QColor(Palette.ORANGE))

        if col_key == "liq_put_display":
            return self._FG_RED if opp.liq_put_x_lote < 0 else self._FG_GREEN

        if col_key == "liq_call_display":
            return self._FG_RED if opp.liq_call_x_lote < 0 else self._FG_GREEN

        if col_key == "ganho_bruto_display":
            if opp.classificacao in ("1BOX", "3BOXSBTH") and opp.pct_ganho_box_bruto > 0:
                return self._FG_GREEN
            if opp.classificacao == "2SBTH" and opp.pct_ganho_sbth_bruto > 0:
                return self._FG_GREEN
            return self._FG_MUTED

        if col_key == "ganho_liq_display":
            if opp.classificacao in ("1BOX", "3BOXSBTH") and opp.pct_ganho_box_liquido > 0:
                return self._FG_GREEN
            if opp.classificacao == "2SBTH" and opp.pct_ganho_sbth_liquido > 0:
                return self._FG_GREEN
            return self._FG_MUTED

        if col_key == "label_tipo":
            if opp.classificacao == "1BOX":
                return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
            if opp.classificacao == "2SBTH":
                return QBrush(QColor(Palette.CYAN))
            if opp.classificacao == "3BOXSBTH":
                return QBrush(QColor(Palette.PURPLE))
            return self._FG_MUTED

        if col_key == "rent_cdi_bruto_display":
            if opp.pct_cdi_box_bruto > 0 or opp.pct_cdi_sbth_bruto > 0:
                return QBrush(QColor(Palette.YELLOW))
            return self._FG_MUTED

        if col_key == "rent_cdi_liq_display":
            if opp.pct_cdi_box_liquido > 0 or opp.pct_cdi_sbth_liquido > 0:
                return QBrush(QColor(Palette.YELLOW))
            return self._FG_MUTED

        if col_key == "custo_sbth_display" and not is_sbth and opp.custo_sbth > 0:
            return self._FG_STRIKEOUT
        if col_key == "custo_box_display" and not is_box and opp.custo_box > 0:
            return self._FG_STRIKEOUT

        if not opp.viavel and col_key not in ("leilao_display", "label_tipo", "liq_indicator"):
            return self._FG_MUTED

        return None

    def _font_data(self, opp: OportunidadeMonitor, col_key: str):
        is_box = opp.classificacao in ("1BOX", "3BOXSBTH")
        is_sbth = opp.classificacao in ("2SBTH", "3BOXSBTH")

        needs_strikethrough = (
            (col_key == "custo_sbth_display" and not is_sbth and opp.custo_sbth > 0)
            or (col_key == "custo_box_display" and not is_box and opp.custo_box > 0)
        )
        if needs_strikethrough:
            font = QFont()
            font.setStrikeOut(True)
            return font

        if col_key == "leilao_display" and opp.em_leilao:
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "label_tipo":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "ganho_bruto_display":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "ganho_liq_display":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "rent_cdi_bruto_display":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "rent_cdi_liq_display":
            font = QFont()
            font.setBold(True)
            return font

        if col_key == "liq_indicator":
            font = QFont()
            font.setBold(True)
            font.setPointSize(11)
            return font

        return None

    def _item_key(self, opp: OportunidadeMonitor) -> int:
        return opp.instrumento_id

    def atualizar(self, oportunidades: list[OportunidadeMonitor]):
        self.layoutAboutToBeChanged.emit()
        self._oportunidades = oportunidades
        self._key_map = {self._item_key(opp): i for i, opp in enumerate(oportunidades)}
        self.layoutChanged.emit()

    def get_oportunidade(self, row: int) -> OportunidadeMonitor | None:
        if 0 <= row < len(self._oportunidades):
            return self._oportunidades[row]
        return None
