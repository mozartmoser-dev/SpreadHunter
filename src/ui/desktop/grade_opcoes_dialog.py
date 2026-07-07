"""Grade de Opções — visualização estilo Profit Pro com calls à esquerda,
strike ao centro e puts à direita, agrupada por série (vencimento).

Botão "Atualizar" à esquerda do header dispara a importação via importflash.

Bandeirinhas desenhadas via QPixmap (sem dependências externas):
  - CALL tipo A (Americana) → 🇺🇸 EUA
  - CALL tipo E (Europeia)  → 🇪🇺 Europa
  - PUT  (sempre E)         → 🇧🇷 Brasil (diferencia visualmente da CALL E)
"""
from __future__ import annotations

import io
import contextlib
import math
import re
from datetime import date
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal, QPointF
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.domain.entities.instrumento_opcional import TipoOpcao
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
from src.ui.desktop.theme import Palette

if TYPE_CHECKING:
    from datetime import date as _date


# ── Bandeirinhas (geradas via QPainter, sem dependências externas) ───────

def _hex(h: str) -> QColor:
    return QColor(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def _clip_rounded(p: QPainter, w: int, h: int, r: int):
    """Ativa clip em retângulo arredondado w x h com raio r."""
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, r, r)
    p.setClipPath(path)


def _pixmap_br(size: int = 18) -> QPixmap:
    """Bandeirinha do Brasil — usada para PUT (Europeia, B3)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    _clip_rounded(p, size, size, 2)

    # Fundo verde
    p.fillRect(0, 0, size, size, _hex("#009C3B"))
    # Losango amarelo
    pts = [
        (size / 2, 1),
        (size - 1, size / 2),
        (size / 2, size - 1),
        (1, size / 2),
    ]
    p.setBrush(_hex("#FFDF00"))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    # Disco azul central
    p.setBrush(_hex("#002776"))
    p.drawEllipse(QPointF(size / 2, size / 2), size * 0.18, size * 0.18)
    # Faixa branca no disco (banda cruzada)
    p.setPen(QPen(_hex("#FFFFFF"), max(1, size * 0.04)))
    p.drawLine(QPointF(size * 0.32, size / 2), QPointF(size * 0.68, size / 2))
    p.end()
    return pm


def _pixmap_us(size: int = 18) -> QPixmap:
    """Bandeirinha dos EUA — usada para CALL tipo A (Americana)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    _clip_rounded(p, size, size, 2)

    # 13 listras vermelhas e brancas
    stripe_h = size / 13.0
    for i in range(13):
        color = _hex("#B22234") if i % 2 == 0 else _hex("#FFFFFF")
        p.fillRect(0, round(i * stripe_h), size, round(stripe_h) + 1, color)
    # Cantinho azul
    bl_w = size * 0.4
    bl_h = size * 0.54
    p.fillRect(0, 0, round(bl_w), round(bl_h), _hex("#3C3B6E"))
    # Estrelas (apenas pontos brancos)
    p.setBrush(_hex("#FFFFFF"))
    p.setPen(Qt.NoPen)
    rows, cols = 5, 6  # grade alternada
    for r in range(rows):
        for c in range(cols):
            x = (c + 0.5) * (bl_w / cols)
            y = (r + 0.5) * (bl_h / rows)
            rad = size * 0.035
            p.drawEllipse(QPointF(x, y), rad, rad)
    p.end()
    return pm


def _pixmap_eu(size: int = 18) -> QPixmap:
    """Bandeirinha da Europa — usada para CALL tipo E (Europeia)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    _clip_rounded(p, size, size, 2)

    # Fundo azul
    p.fillRect(0, 0, size, size, _hex("#003399"))
    # 12 estrelas douradas em anel (sentido horário, começa no topo)
    p.setBrush(_hex("#FFCC00"))
    p.setPen(Qt.NoPen)
    cx, cy = size / 2, size / 2
    radius = size * 0.34
    star_r = size * 0.06
    for i in range(12):
        ang = math.pi / 2.0 - 2 * math.pi * i / 12.0  # 1º quadrante clockwise
        sx = cx + radius * math.cos(ang)
        sy = cy - radius * math.sin(ang)
        p.drawEllipse(QPointF(sx, sy), star_r, star_r)
    p.end()
    return pm


_CACHE_FLAGS = {}


def _flag_icon(kind: str) -> QIcon:
    """kind = 'CALL_A' | 'CALL_E' | 'PUT'.

    Convenções de bandeirinha:
      - CALL tipo A (Americana) → 🇺🇸 EUA
      - CALL tipo E (Europeia)  → 🇪🇺 Europa (12 estrelas em anel)
      - PUT  (sempre E)         → 🇪🇺 Europa (mesma bandeira — PUTs B3 são europeias)

    A diferença visual entre CALL_E e PUT fica pela posição na grid (esquerda
    vs direita) e pela coluna "Tipo" ficar na coluna 2 (CALL) e coluna 5 (PUT).
    """
    if kind in _CACHE_FLAGS:
        return _CACHE_FLAGS[kind]
    if kind == "CALL_A":
        pm = _pixmap_us()
    else:  # CALL_E ou PUT — ambos europeus
        pm = _pixmap_eu()
    icon = QIcon(pm)
    _CACHE_FLAGS[kind] = icon
    return icon


_MESES_PT = {
    1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
    7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ",
}

_WEEK_RE = re.compile(r"W([1-9])")


def _dias_ate(vencimento: date) -> int:
    try:
        return max((vencimento - date.today()).days, 0)
    except Exception:
        return 0


def _label_serie(venc: date, codigos: list[str]) -> str:
    """Gera label amigável: 'SEMANA 2 — 10/07/2026' ou 'MENSAL — 21/08/2026'."""
    data_str = f"{venc.day:02d}/{venc.month:02d}/{venc.year}"
    semanas: set[int] = set()
    sem_count = 0
    for cod in codigos:
        m = _WEEK_RE.search(cod or "")
        if m:
            sem_count += 1
            semanas.add(int(m.group(1)))
    # Se a maioria dos códigos tem sufixo Wn e todos apontam para a mesma semana
    if sem_count > 0 and len(semanas) == 1:
        return f"SEMANA {next(iter(semanas))} — {data_str}"
    # Caso contrário (sem sufixo, mistura de W1..W5, etc.) → MENSAL
    return f"MENSAL — {data_str}"


def _fmt_strike(strike: float | None) -> str:
    if strike is None:
        return "—"
    try:
        return f"{strike:.2f}".replace(".", ",")
    except Exception:
        return "—"


class _ImportThread(QThread):
    """Roda importflash.main() capturando stdout/stderr linha a linha."""

    finished = Signal(int)
    progress = Signal(str)

    def run(self):
        class _LineCapture(io.StringIO):
            def __init__(self, sig_target):
                super().__init__()
                self._buf = io.StringIO()
                self._partial = ""
                self._sig_target = sig_target

            def write(self, s):
                self._buf.write(s)
                self._partial += s
                while "\n" in self._partial:
                    idx = self._partial.index("\n")
                    line = self._partial[:idx]
                    self._partial = self._partial[idx + 1:]
                    if line:
                        self._sig_target.emit(line)

            def flush(self):
                pass

            def getvalue(self):
                return self._buf.getvalue()

        captura = _LineCapture(self.progress)
        with contextlib.redirect_stdout(captura), contextlib.redirect_stderr(captura):
            try:
                from scripts.validar_opcoes.importflash import main
                rc = main()
            except Exception as e:
                print(f"ERRO: {e}")
                import traceback
                traceback.print_exc()
                rc = 1
        output = captura.getvalue()
        if output:
            print(output, end="", flush=True)
        self.finished.emit(rc if rc is not None else 1)


class GradeOpcoesDialog(QDialog):
    """Diálogo visualizador da grade de opções estilo plataforma Profit."""

    def __init__(self, db_path, parent=None, on_import_concluido=None):
        super().__init__(parent)
        self.db_path = db_path
        self._on_import_concluido = on_import_concluido
        self._import_thread = None
        self.setWindowTitle("Grade de Opções")
        self.setMinimumSize(1100, 600)
        self._setup_ui()
        self.carregar_dados()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- Header com botão Atualizar à ESQUERDA (logo após o título) ---
        header = QHBoxLayout()
        header.setSpacing(12)

        lbl_title = QLabel("Grade de Opções")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(
                Palette.TEXT_PRIMARY
            )
        )
        header.addWidget(lbl_title)

        self.btn_atualizar = QPushButton("\u21bb  Atualizar")
        self.btn_atualizar.setProperty("class", "primary")
        self.btn_atualizar.setToolTip(
            "Importar/refrescar instrumentos do opcoes.net.br (via API OptionsChain)"
        )
        self.btn_atualizar.clicked.connect(self._atualizar_base)
        header.addWidget(self.btn_atualizar)

        header.addStretch()

        lbl_ativo = QLabel("Ativo:")
        lbl_ativo.setStyleSheet(
            "color: {}; font-size: 9pt; font-weight: bold;".format(Palette.TEXT_MUTED)
        )
        header.addWidget(lbl_ativo)

        self.cmb_ativo = QComboBox()
        self.cmb_ativo.setMinimumWidth(140)
        self.cmb_ativo.currentIndexChanged.connect(self._repopular_serie)
        header.addWidget(self.cmb_ativo)

        self.btn_listar = QPushButton("Listar")
        self.btn_listar.setToolTip("Repopular grade do ativo selecionado")
        self.btn_listar.clicked.connect(self._repopular_serie)
        header.addWidget(self.btn_listar)

        layout.addLayout(header)

        # --- Status line + progress bar ---
        self.lbl_status = QLabel("0 séries — 0 opções")
        self.lbl_status.setStyleSheet(
            "color: {}; font-size: 9pt;".format(Palette.TEXT_MUTED)
        )
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e2f; border: 1px solid #2d2d44;
                border-radius: 4px; height: 18px; text-align: center; color: #e0e0e0;
            }
            QProgressBar::chunk { background-color: #1abc9c; border-radius: 4px; }
        """)
        layout.addWidget(self.progress_bar)

        # --- Tree principal ---
        # Colunas: 0=Série, 1=CALL cod, 2=CALL tipo, 3=Strike (centro), 4=PUT cod, 5=PUT tipo
        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels([
            "Série",
            "CALL",
            "Tipo",
            "Strike",
            "PUT",
            "Tipo",
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setIndentation(20)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a2e; alternate-background-color: #1e1e34;
                color: #d0d0e0; gridline-color: #2a2a3e;
                border: 1px solid #2d2d44; border-radius: 4px;
                font-family: "JetBrains Mono", "Consolas", "Courier New", monospace;
                font-size: 9pt; outline: none;
            }
            QTreeWidget::item { padding: 4px 8px; }
            QTreeWidget::item:selected { background-color: #2d4a7a; color: #ffffff; }
            QHeaderView::section {
                background-color: #0f0f23; color: #a0a0c0; padding: 8px 10px;
                font-weight: bold; font-size: 8.5pt;
                font-family: "Segoe UI", sans-serif;
                border: none; border-right: 1px solid #1a1a2e;
                border-bottom: 1px solid #2d2d44;
            }
        """)

        header_view = self.tree.header()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.resizeSection(0, 280)  # Série
        header_view.resizeSection(1, 160)  # CALL cod
        header_view.resizeSection(2, 60)   # CALL tipo
        header_view.resizeSection(3, 120)   # Strike (centro)
        header_view.resizeSection(4, 60)   # PUT tipo
        header_view.setSectionResizeMode(5, QHeaderView.Stretch)

        layout.addWidget(self.tree, stretch=1)

        # --- Rodapé ---
        rodape = QHBoxLayout()
        rodape.addStretch()
        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        rodape.addWidget(self.btn_fechar)
        layout.addLayout(rodape)

    # ---------------------------------------------------------- Carregamento

    def carregar_dados(self):
        """Recarrega a lista de ativos do banco e popula o combo."""
        repo = InstrumentoRepository(self.db_path)
        instrumentos = repo.get_all()
        ativos = sorted({i.ativo for i in instrumentos})
        self.cmb_ativo.blockSignals(True)
        self.cmb_ativo.clear()
        self.cmb_ativo.addItem("TODAS", "")
        for a in ativos:
            self.cmb_ativo.addItem(a, a)
        self.cmb_ativo.blockSignals(False)
        # Default: TODAS
        self.cmb_ativo.setCurrentIndex(0)
        self._repopular_serie()

        # Mensagem inicial amigável
        if not ativos:
            self.lbl_status.setText(
                "Banco vazio — clique em 🔄 Atualizar para importar do opcoes.net.br"
            )

    def _repopular_serie(self, *_):
        ativo_filtro = self.cmb_ativo.currentData()
        if ativo_filtro is None:
            # Pode vir do currentText() em alguns casos
            ativo_filtro = ""

        repo = InstrumentoRepository(self.db_path)
        if ativo_filtro and ativo_filtro != "TODAS":
            insts = repo.get_by_ativo(ativo_filtro)
            titulo_ativo = f" — {ativo_filtro}"
        else:
            insts = repo.get_all()

        insts = [i for i in insts if i.vencimento >= date.today()]
        insts.sort(key=lambda x: (x.vencimento, x.ativo, x.strike or 0.0))

        # Agrupar por vencimento
        series: dict[date, list] = {}
        for i in insts:
            series.setdefault(i.vencimento, []).append(i)

        self.tree.clear()
        total_ops = 0
        root_items = []
        for venc, lista in series.items():
            dias = _dias_ate(venc)
            # Pegar códigos da série para detectar W1..W5
            codigos = [i.cod_put or "" for i in lista] + [i.cod_call or "" for i in lista]
            label = _label_serie(venc, codigos)

            if ativo_filtro and ativo_filtro != "TODAS":
                titulo = f"{label}    |    {dias} dia(s)"
            else:
                # modo TODAS: agrupar também por ativo dentro da série
                ativos_set = sorted({i.ativo for i in lista})
                titulo = f"{label}    |    {dias} dia(s)    |    {len(ativos_set)} ativo(s)"

            parent = QTreeWidgetItem(self.tree, [
                titulo, "", "", "", "", "",
            ])
            parent.setExpanded(False)

            fonte_serie = QFont("Segoe UI", 9)
            fonte_serie.setBold(True)
            parent.setFont(0, fonte_serie)
            cor_serie = QColor(Palette.ACCENT_BLUE_BRIGHT)
            for col in range(6):
                parent.setForeground(col, cor_serie)
            parent.setBackground(0, QColor("#0f3460"))

            if ativo_filtro and ativo_filtro != "TODAS":
                # Modo único ativo: lista diretamente os strikes
                for inst in lista:
                    row = self._criar_linha(inst)
                    parent.addChild(row)
                    total_ops += 1
            else:
                # Modo TODAS: sub-grupo por ativo
                por_ativo: dict[str, list] = {}
                for inst in lista:
                    por_ativo.setdefault(inst.ativo, []).append(inst)
                for atv, lst in sorted(por_ativo.items()):
                    sub = QTreeWidgetItem(parent, [
                        f"   ▸ {atv}    ({len(lst)} strikes)", "", "", "", "", "",
                    ])
                    fonte_sub = QFont("Segoe UI", 8)
                    fonte_sub.setBold(True)
                    sub.setFont(0, fonte_sub)
                    sub.setForeground(0, QColor("#c0a060"))
                    sub.setBackground(0, QColor("#2a2418"))
                    sub.setExpanded(False)
                    for inst in lst:
                        row = self._criar_linha(inst)
                        sub.addChild(row)
                        total_ops += 1

            parent.setText(
                0,
                titulo,
            )

            root_items.append(parent)

        # Auto-expande o primeira série e seu primeiro ativo (modo TODAS)
        if root_items:
            root_items[0].setExpanded(True)
            for i in range(root_items[0].childCount()):
                if root_items[0].child(i).text(0).startswith("   ▸"):
                    root_items[0].child(i).setExpanded(True)
                    break

        if ativo_filtro and ativo_filtro != "TODAS":
            rotulo = f"{len(series)} série(s) — {total_ops} opções para {ativo_filtro}"
        else:
            rotulo = (
                f"{len(series)} série(s) — {total_ops} opções — "
                f"{len({i.ativo for i in insts})} ativo(s)"
            )
        ult = self._ultima_importacao(insts)
        if ult is not None:
            ult_str = ult.strftime("%d/%m/%Y %H:%M")
            rotulo = f"{rotulo}    |    Última importação: {ult_str}"
        self.lbl_status.setText(rotulo)

    def _ultima_importacao(self, insts):
        """Retorna o created_at mais recente entre os instrumentos."""
        if not insts:
            return None
        maiores = [i.created_at for i in insts if i.created_at is not None]
        if not maiores:
            return None
        return max(maiores)

    def _criar_linha(self, inst) -> QTreeWidgetItem:
        """Cria um nó de strike com layout CALL | CALL tipo | Strike | PUT | PUT tipo.

        Colunas:
          0 = (vazio)
          1 = código CALL
          2 = bandeira CALL (🇺🇸 A / 🇪🇺 E)
          3 = strike central
          4 = código PUT
          5 = bandeira PUT (sempre 🇧🇷 — diferencia da CALL Europeia)
        """
        strike_str = _fmt_strike(inst.strike)
        flag_call_key = "CALL_A" if inst.tipo_opcao == TipoOpcao.AMERICANA else "CALL_E"
        flag_put_key = "PUT"

        row = QTreeWidgetItem([
            "",
            inst.cod_call or "—",
            "",  # ícone via QTreeWidgetItem.setIcon
            strike_str,
            inst.cod_put or "—",
            "",  # ícone via QTreeWidgetItem.setIcon
        ])
        for col in [1, 2, 3, 4, 5]:
            row.setTextAlignment(col, Qt.AlignCenter)

        # Bandeirinhas (ícones) — tamanho consistente
        from PySide6.QtCore import QSize as _QSize
        row.setIcon(2, _flag_icon(flag_call_key))
        row.setIcon(5, _flag_icon(flag_put_key))
        row.setSizeHint(2, _QSize(22, 20))
        row.setSizeHint(5, _QSize(22, 20))

        # Strike (centro) destacada
        row.setForeground(3, QColor(Palette.YELLOW))
        fonte_strike = QFont("JetBrains Mono", 10)
        fonte_strike.setBold(True)
        row.setFont(3, fonte_strike)
        row.setBackground(3, QColor("#1a2e3a"))
        # Cores de CALL (ciano, esquerda) e PUT (laranja, direita)
        if inst.cod_call:
            row.setForeground(1, QColor(Palette.CYAN))
        else:
            row.setForeground(1, QColor(Palette.TEXT_MUTED))
        if inst.cod_put:
            row.setForeground(4, QColor(Palette.ORANGE))
        else:
            row.setForeground(4, QColor(Palette.TEXT_MUTED))
        return row

    # ---------------------------------------------------------- Importação

    def _atualizar_base(self):
        """Botão Atualizar: abre blacklist dialog e dispara importação."""
        from src.ui.desktop.blacklist_import_dialog import BlacklistImportDialog
        dlg = BlacklistImportDialog(self.db_path, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        if self._import_thread and self._import_thread.isRunning():
            QMessageBox.warning(self, "Importação", "Já existe importação em andamento.")
            return

        self.btn_atualizar.setEnabled(False)
        self.btn_atualizar.setText("\u23f3  Importando...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.lbl_status.setText("Importando dados do opcoes.net.br...")
        self.lbl_status.setStyleSheet(
            "color: {}; font-weight: bold;".format(Palette.YELLOW)
        )

        self._import_thread = _ImportThread()
        self._import_thread.finished.connect(self._on_import_finished)
        self._import_thread.progress.connect(self._on_import_progress)
        self._import_thread.start()

    def _on_import_progress(self, msg: str):
        self.lbl_status.setText(f"Import: {msg[:140]}")

    def _on_import_finished(self, exit_code: int):
        self.btn_atualizar.setEnabled(True)
        self.btn_atualizar.setText("\u21bb  Atualizar")
        self.progress_bar.setVisible(False)
        if exit_code == 0:
            self.lbl_status.setText("Importação concluída com sucesso!")
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.GREEN)
            )
            self.carregar_dados()
            if self._on_import_concluido:
                self._on_import_concluido(exit_code)
            QMessageBox.information(self, "Importação", "Importação concluída com sucesso!")
        else:
            self.lbl_status.setText(f"Importação falhou (código {exit_code})")
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold;".format(Palette.RED)
            )
            QMessageBox.critical(self, "Importação", f"Importação falhou (código {exit_code}).")

    def closeEvent(self, event):
        if self._import_thread and self._import_thread.isRunning():
            self._import_thread.quit()
            self._import_thread.wait(2000)
        super().closeEvent(event)
