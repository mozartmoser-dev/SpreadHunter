from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame,
)
from PySide6.QtCore import Qt

from src.ui.desktop.theme import Palette

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_UTC_TZ = timezone.utc


def _fmt_ts(ts: float | None, tz=_TZ_BR) -> str:
    if ts is None:
        return "-"
    try:
        return datetime.fromtimestamp(ts, tz=tz).strftime("%H:%M:%S.%f")[:-3]
    except (ValueError, OSError):
        return "-"


def _idade(ts: float | None, agora: float) -> str:
    if ts is None:
        return "-"
    try:
        d = max(0.0, agora - ts)
    except (TypeError, ValueError):
        return "-"
    if d < 1.0:
        return f"{d*1000:.0f} ms"
    if d < 60.0:
        return f"{d:.1f} s"
    return f"{int(d//60)} min {int(d%60)} s"


def _fmt_detectado(dt) -> str:
    if dt is None:
        return "-"
    if not isinstance(dt, datetime):
        return str(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ_BR)
    return dt.astimezone(_TZ_BR).strftime("%H:%M:%S.%f")[:-3]


def _linhas_times(r, assinar_timestamp_openfast: bool | None = None) -> list[dict]:
    """Monta as linhas do painel a partir do DTO (lendo defensivamente via getattr).

    Tn e T0..T4 preservam os significados existentes no fluxo:
    - Tn  = último negócio / origem da cotação (TIMENEG com fallback TIME) -> ts_origem_ativo
    - T0  = última atualização de mercado (entrega do campo ASK)          -> ts_ativo_ask
    - T1  = entrada no pipeline (varredura do ciclo)                      -> ts_scan
    - T2  = preparação dos dados (entrega)                                -> ts_entrega_ativo
    - T3  = oportunidade calculada                                        -> detectado_em
    - T4  = resultado pronto                                              -> detectado_em

    Quando `assinar_timestamp_openfast` é False e não há ts_origem_ativo, o Tn
    mostra "N/D (param off)" em vez de "-", deixando claro que o dado não foi
    coletado por configuração (TIME/TIMENEG não assinado). Com valor True ou
    None (estado desconhecido), mantém o comportamento neutro "-".
    """
    agora = __import__("time").time()
    ts_origem = getattr(r, "ts_origem_ativo", None)
    ts_ask = getattr(r, "ts_ativo_ask", None)
    ts_bid = getattr(r, "ts_ativo_bid", None)
    ts_scan = getattr(r, "ts_scan", None)
    ts_entrega = getattr(r, "ts_entrega_ativo", None)
    detectado = getattr(r, "detectado_em", None)
    detectado_ts = None
    if isinstance(detectado, datetime):
        if detectado.tzinfo is None:
            detectado_ts = detectado.replace(tzinfo=_TZ_BR).timestamp()
        else:
            detectado_ts = detectado.timestamp()

    origem_off = assinar_timestamp_openfast is False and ts_origem is None
    hora_tn = "N/D (param off)" if origem_off else _fmt_ts(ts_origem)
    idade_tn = "-" if origem_off else _idade(ts_origem, agora)
    origem_rotulo = (
        "não coletado — assinar_timestamp_openfast=0 (param off)"
        if origem_off else "OpenFast TIMENEG (fallback TIME)"
    )

    return [
        {"marcador": "Tn", "significado": "Último negócio / origem da cotação (TIMENEG → TIME)",
         "hora": hora_tn, "idade": idade_tn, "origem": origem_rotulo},
        {"marcador": "T0", "significado": "Última atualização de mercado (entrega ASK)",
         "hora": _fmt_ts(ts_ask), "idade": _idade(ts_ask, agora),
         "origem": "get_ts_campo(ativo, ASK)"},
        {"marcador": "T0b", "significado": "Última atualização de mercado (entrega BID)",
         "hora": _fmt_ts(ts_bid), "idade": _idade(ts_bid, agora),
         "origem": "get_ts_campo(ativo, BID)"},
        {"marcador": "T1", "significado": "Entrada no pipeline (varredura do ciclo)",
         "hora": _fmt_ts(ts_scan), "idade": _idade(ts_scan, agora),
         "origem": "capturar_dados_mercado (Onda 1/2)"},
        {"marcador": "T2", "significado": "Preparação dos dados (entrega)",
         "hora": _fmt_ts(ts_entrega), "idade": _idade(ts_entrega, agora),
         "origem": "get_ts_campo(ativo, ASK)"},
        {"marcador": "T3", "significado": "Oportunidade calculada",
         "hora": _fmt_ts(detectado_ts), "idade": _idade(detectado_ts, agora),
         "origem": "detectado_em (use case)"},
        {"marcador": "T4", "significado": "Resultado pronto",
         "hora": _fmt_ts(detectado_ts), "idade": _idade(detectado_ts, agora),
         "origem": "detectado_em (use case)"},
        {"marcador": "Onda", "significado": "Onda de varredura",
         "hora": str(getattr(r, "onda", None)) if getattr(r, "onda", None) is not None else "-",
         "idade": "-", "origem": "capturar_dados_mercado"},
        {"marcador": "Feed", "significado": "Estado do feed",
         "hora": str(getattr(r, "feed_state", "") or "-"), "idade": "-",
         "origem": "provider"},
        {"marcador": "Detectado", "significado": "Detecção (datetime)",
         "hora": _fmt_detectado(detectado), "idade": "-", "origem": "detectado_em"},
    ]


class TimesDialog(QDialog):
    def __init__(self, r, strategy: str = "", parent=None,
                 assinar_timestamp_openfast: bool | None = None):
        super().__init__(parent)
        self.r = r
        self.strategy = strategy
        self._assinar_timestamp_openfast = assinar_timestamp_openfast
        self.setWindowTitle(f"Times — {strategy or 'Cotação'}")
        self.setMinimumSize(640, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        ativo = getattr(self.r, "ativo", "-")
        title = QLabel(f"<b>Timestamps da cotação</b> — {self.strategy or 'N/A'} | {ativo}")
        title.setStyleSheet(f"font-size: 12pt; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(["Marcador", "Significado", "Horário (BR)", "Idade", "Origem"])
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
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

        nota = QLabel(
            "Tn/T0 vêm da fonte em tempo real (não são persistidos). "
            "Se assinar_timestamp_openfast=0, o Tn mostra 'N/D (param off)' — o dado não é coletado "
            "por configuração (TIME/TIMENEG não assinado). "
            "T3/T4 compartilham detectado_em (não há registro separado de cálculo no fluxo atual)."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 8pt;")
        layout.addWidget(nota)

        self._preencher()

    def _preencher(self):
        linhas = _linhas_times(self.r, self._assinar_timestamp_openfast)
        self.tabela.setRowCount(len(linhas))
        for i, linha in enumerate(linhas):
            self.tabela.setItem(i, 0, QTableWidgetItem(linha["marcador"]))
            self.tabela.setItem(i, 1, QTableWidgetItem(linha["significado"]))
            self.tabela.setItem(i, 2, QTableWidgetItem(linha["hora"]))
            self.tabela.setItem(i, 3, QTableWidgetItem(linha["idade"]))
            self.tabela.setItem(i, 4, QTableWidgetItem(linha["origem"]))
            for col in range(5):
                item = self.tabela.item(i, col)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.tabela.resizeColumnsToContents()
        self.tabela.setColumnWidth(1, 360)
