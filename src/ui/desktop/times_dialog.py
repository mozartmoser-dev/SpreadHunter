from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame,
)
from PySide6.QtGui import QColor, QFontMetrics
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


def _diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def _fmt_dur(d: float | None) -> str:
    if d is None:
        return "-"
    try:
        sinal = "-" if d < 0 else ""
        a = abs(d)
    except (TypeError, ValueError):
        return "-"
    if a < 1.0:
        return f"{sinal}{a*1000:.0f} ms"
    if a < 60.0:
        return f"{sinal}{a:.1f} s"
    return f"{sinal}{int(a//60)} min {int(a%60)} s"


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

    Apresentação organizada em blocos com linhas de título; os valores, idades e
    cálculos são exatamente os mesmos do fluxo (nada é recalculado ou alterado):

    RECEBIMENTO NO PC
    - T0   = recebimento do último ASK pelo feed                       -> ts_ativo_ask
    - T0b  = recebimento do último BID pelo feed                       -> ts_ativo_bid

    MENSAGEM OPENFAST
    - TIME          = horário da mensagem enviada pelo OpenFast        -> ts_time_ativo
    - TIME → T0     = atraso de entrega (T0 − TIME)                    -> _diff(ts_ativo_ask, ts_time_ativo)
    - (Idade TIME   = coluna "Idade" da linha TIME, agora − ts_time_ativo)

    ÚLTIMO NEGÓCIO
    - Tn                = horário da cotação (TIME → TIMENEG)          -> ts_origem_ativo
    - TIME → TIMENEG    = diferença entre a mensagem e o último negócio -> _diff(ts_time_ativo, ts_timeng_ativo)
    - (Idade Tn         = coluna "Idade" da linha Tn, agora − ts_origem_ativo)

    PROCESSAMENTO
    - T1 = entrada no pipeline (varredura do ciclo)                    -> ts_scan
    - T2 = preparação dos dados — não produzido neste fluxo            -> ts_entrega_ativo (nunca atribuído)
    - T3 = oportunidade calculada                                      -> detectado_em
    - T4 = resultado pronto                                            -> detectado_em

    STATUS
    - Onda/Feed = fase da carga (1 rápida/básica | 2 completa) e estado da conexão

    Quando `assinar_timestamp_openfast` é False e não há ts_origem_ativo, o Tn
    mostra "N/D (param off)" em vez de "-", deixando claro que o dado não foi
    coletado por configuração (TIME/TIMENEG não assinado). Com valor True ou
    None (estado desconhecido), mantém o comportamento neutro "-".
    """
    agora = __import__("time").time()
    ts_origem = getattr(r, "ts_origem_ativo", None)
    ts_time = getattr(r, "ts_time_ativo", None)
    ts_timeng = getattr(r, "ts_timeng_ativo", None)
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
    time_off = assinar_timestamp_openfast is False and ts_time is None
    hora_tn = "N/D (param off)" if origem_off else _fmt_ts(ts_origem)
    idade_tn = "-" if origem_off else _idade(ts_origem, agora)
    origem_rotulo = (
        "não coletado — assinar_timestamp_openfast=0 (param off)"
        if origem_off else "OpenFast TIME (fallback TIMENEG)"
    )

    return [
        {"tipo": "bloco", "marcador": "RECEBIMENTO NO PC",
         "significado": "", "hora": "", "idade": "", "origem": ""},
        {"marcador": "T0", "significado": "Recebimento do último ASK pelo feed",
         "hora": _fmt_ts(ts_ask), "idade": _idade(ts_ask, agora),
         "origem": "get_ts_campo(ativo, ASK)"},
        {"marcador": "T0b", "significado": "Recebimento do último BID pelo feed",
         "hora": _fmt_ts(ts_bid), "idade": _idade(ts_bid, agora),
         "origem": "get_ts_campo(ativo, BID)"},
        {"tipo": "bloco", "marcador": "MENSAGEM OPENFAST",
         "significado": "", "hora": "", "idade": "", "origem": ""},
        {"marcador": "TIME", "significado": "Horário da mensagem enviada pelo OpenFast",
         "hora": ("N/D (param off)" if time_off else _fmt_ts(ts_time)),
         "idade": "-" if time_off else _idade(ts_time, agora),
         "origem": "OpenFast TIME"},
        {"marcador": "TIME → T0", "significado": "Tempo entre a mensagem e seu recebimento no PC",
         "hora": "-", "idade": _fmt_dur(_diff(ts_ask, ts_time)),
         "origem": "T0 (entrega ASK) − TIME (mensagem)"},
        {"tipo": "bloco", "marcador": "ÚLTIMO NEGÓCIO",
         "significado": "", "hora": "", "idade": "", "origem": ""},
        {"marcador": "Tn", "significado": "Horário da cotação (TIME → TIMENEG)",
         "hora": hora_tn, "idade": idade_tn, "origem": origem_rotulo},
        {"marcador": "TIME → TIMENEG", "significado": "Diferença entre a mensagem e o último negócio",
         "hora": "-", "idade": _fmt_dur(_diff(ts_time, ts_timeng)),
         "origem": "TIME (mensagem) − TIMENEG (último negócio)"},
        {"tipo": "bloco", "marcador": "PROCESSAMENTO",
         "significado": "", "hora": "", "idade": "", "origem": ""},
        {"marcador": "T1", "significado": "Entrada no pipeline (varredura do ciclo)",
         "hora": _fmt_ts(ts_scan), "idade": _idade(ts_scan, agora),
         "origem": "capturar_dados_mercado (Onda 1/2)"},
        {"marcador": "T2", "significado": "Preparação dos dados (não produzido neste fluxo)",
         "hora": _fmt_ts(ts_entrega), "idade": _idade(ts_entrega, agora),
         "origem": "não preenchido — ts_entrega_ativo nunca é atribuído"},
        {"marcador": "T3", "significado": "Oportunidade calculada",
         "hora": _fmt_ts(detectado_ts), "idade": _idade(detectado_ts, agora),
         "origem": "detectado_em (use case)"},
        {"marcador": "T4", "significado": "Resultado pronto",
         "hora": _fmt_ts(detectado_ts), "idade": _idade(detectado_ts, agora),
         "origem": "detectado_em (use case)"},
        {"tipo": "bloco", "marcador": "STATUS",
         "significado": "", "hora": "", "idade": "", "origem": ""},
        {"marcador": "Onda", "significado": "Onda de varredura (1 = rápida/básica | 2 = completa)",
         "hora": str(getattr(r, "onda", None)) if getattr(r, "onda", None) is not None else "-",
         "idade": "-", "origem": "capturar_dados_mercado"},
        {"marcador": "Feed", "significado": "Estado da conexão do feed (Conectado / Desconectado)",
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
        self.setMinimumSize(700, 560)
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
        self.tabela.setHorizontalHeaderLabels(["Marcador", "Significado", "Horário/Valor (BR)", "Idade", "Origem"])
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setWordWrap(True)
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
            "TIME = horário da mensagem enviada pelo OpenFast; TIMENEG = horário do último negócio. "
            "TIME→T0 mede o tempo entre a mensagem e seu recebimento no PC; TIME→TIMENEG, a diferença "
            "entre a mensagem e o último negócio. "
            "Se assinar_timestamp_openfast=0, Tn e TIME mostram 'N/D (param off)' — o dado não é coletado "
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
            if linha.get("tipo") == "bloco":
                item = QTableWidgetItem(linha["marcador"])
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(QColor("#8f9bbf"))
                f = item.font()
                f.setBold(True)
                f.setPointSizeF(8.5)
                item.setFont(f)
                self.tabela.setItem(i, 0, item)
                self.tabela.setSpan(i, 0, 1, 5)
                continue
            self.tabela.setItem(i, 0, QTableWidgetItem(linha["marcador"]))
            self.tabela.setItem(i, 1, QTableWidgetItem(linha["significado"]))
            self.tabela.setItem(i, 2, QTableWidgetItem(linha["hora"]))
            self.tabela.setItem(i, 3, QTableWidgetItem(linha["idade"]))
            item_origem = QTableWidgetItem(linha["origem"])
            self.tabela.setItem(i, 4, item_origem)
            for col in range(5):
                item = self.tabela.item(i, col)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.tabela.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        fm = self.tabela.fontMetrics()
        hfm = QFontMetrics(self.tabela.horizontalHeader().font())
        pad = 20
        largura = [0] * 5
        origem_normal = 0
        for linha in linhas:
            if linha.get("tipo") == "bloco":
                largura[0] = max(largura[0], fm.horizontalAdvance(linha["marcador"]))
                continue
            textos = [linha["marcador"], linha["significado"], linha["hora"],
                      linha["idade"], linha["origem"]]
            for col, texto in enumerate(textos):
                largura[col] = max(largura[col], fm.horizontalAdvance(texto))
            if not linha["origem"].startswith("não coletado"):
                origem_normal = max(origem_normal, fm.horizontalAdvance(linha["origem"]))
        for col, texto in enumerate(
                ["Marcador", "Significado", "Horário/Valor (BR)", "Idade", "Origem"]):
            largura[col] = max(largura[col], hfm.horizontalAdvance(texto))
        self.tabela.setColumnWidth(0, int(largura[0]) + pad)
        self.tabela.setColumnWidth(2, int(largura[2]) + pad)
        self.tabela.setColumnWidth(3, int(largura[3]) + pad)
        self.tabela.setColumnWidth(4, min(int(largura[4]) + pad, int(origem_normal) + pad + 20))
        largura_min = (
            self.tabela.columnWidth(0)
            + int(largura[1]) + pad
            + self.tabela.columnWidth(2)
            + self.tabela.columnWidth(3)
            + self.tabela.columnWidth(4)
            + 64
        )
        self.setMinimumWidth(largura_min)
        altura_conteudo = (
            self.tabela.horizontalHeader().height()
            + sum(self.tabela.rowHeight(i) for i in range(self.tabela.rowCount()))
        )
        self.resize(largura_min, max(self.height(), altura_conteudo + 170))
