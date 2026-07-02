import json
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView,
    QMessageBox, QLabel, QHeaderView, QTextEdit, QTabWidget, QWidget, QFormLayout,
    QTableWidget, QTableWidgetItem, QGroupBox,
)
from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtGui import QFont, QColor, QBrush

from src.ui.desktop.theme import Palette


def plot_historico(parent, ativo: str, preco_atual: float = None,
                   strike_put: float = None, strike_call: float = None,
                   n_sessoes: int = 21):
    from PySide6.QtWidgets import QMessageBox
    import numpy as np
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient

    client = OpcoesNetClient()
    candles = client.get_stock_history_formatted(ativo)
    if not candles:
        QMessageBox.information(parent, "Gráfico",
                                f"Não foi possível obter histórico de {ativo}.")
        return

    import datetime as dt_module
    dates = []
    opens, highs, lows, closes = [], [], [], []
    volumes = []
    vol_hists, vol_impls = [], []
    for c in candles:
        d = c.get("date")
        if isinstance(d, str):
            dt = dt_module.datetime.strptime(d[:10], "%Y-%m-%d")
        else:
            continue
        dates.append(dt)
        opens.append(c.get("open"))
        highs.append(c.get("high"))
        lows.append(c.get("low"))
        closes.append(c.get("close"))
        volumes.append(c.get("volume"))
        vol_hists.append(c.get("vol_hist"))
        vol_impls.append(c.get("vol_impl"))

    has_vol = any(v is not None for v in vol_hists) or any(v is not None for v in vol_impls)

    BG = '#0d0d0d'; TEXT = '#c0c0c0'; WHITE = '#ffffff'
    GREEN = '#4caf50'; RED = '#ff3355'; BLUE = '#2196f3'
    ACCENT = '#ffc107'

    n_sub = 2 if has_vol else 1
    fig = Figure(figsize=(11, 6.5), facecolor=BG)
    heights = [3, 1] if n_sub == 2 else [3]
    gs = fig.add_gridspec(n_sub, 1, height_ratios=heights, hspace=0.08)

    ax1 = fig.add_subplot(gs[0], facecolor=BG)
    width = 0.6
    for i in range(len(dates)):
        color = GREEN if closes[i] >= opens[i] else RED
        ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=0.8, alpha=0.7)
        ax1.bar(dates[i], closes[i] - opens[i], width, bottom=opens[i], color=color, alpha=0.85)

    ax1.set_title(f"{ativo} — Histórico de Preços", color='#e0e0e0', fontsize=11, fontweight='bold')
    ax1.tick_params(colors=TEXT, labelsize=8)
    ax1.set_ylabel('Preço (R$)', color=TEXT, fontsize=9)
    for s in ax1.spines.values():
        s.set_color('#333')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
    ax1.tick_params(axis='x', colors=TEXT)
    ax1.set_xlim(dates[0], dates[-1])

    if dates:
        x0n = mdates.date2num(dates[0])
        x1n = mdates.date2num(dates[-1])
        span = x1n - x0n
        linhas = []
        if preco_atual is not None and preco_atual > 0:
            linhas.append((preco_atual, WHITE, WHITE, f'Ativo R${preco_atual:.2f}'))
        for strike, cor_linha, cor_box, rotulo in [
            (strike_put, RED, '#4caf50', 'C-PUT'),
            (strike_call, ACCENT, '#ff3355', 'V-CALL'),
        ]:
            if strike is not None and strike > 0:
                linhas.append((strike, cor_linha, cor_box, f'{rotulo} R${strike:.2f}'))
        linhas.sort(key=lambda x: x[0])
        n = len(linhas)
        proximas = any(abs(linhas[i][0] - linhas[i + 1][0]) < 1.5 for i in range(n - 1))
        for i, (y, cor_linha, cor_box, texto) in enumerate(linhas):
            pct = 0.85 - (i / (n - 1)) * 0.35 if (proximas and n > 1) else 0.7
            xc = x0n + pct * span
            gap = 0.06 * span
            if xc - gap > x0n:
                ax1.plot([x0n, xc - gap], [y, y], color=cor_linha, linewidth=1.2, linestyle='--', alpha=0.9, zorder=4)
            if xc + gap < x1n:
                ax1.plot([xc + gap, x1n], [y, y], color=cor_linha, linewidth=1.2, linestyle='--', alpha=0.9, zorder=4)
            cor_fundo = cor_box if cor_box != WHITE else '#0d0d0d'
            ax1.text(xc, y, texto, ha='center', va='center', color=WHITE, fontsize=8,
                     bbox=dict(boxstyle='round,pad=0.15', facecolor=cor_fundo, edgecolor=cor_linha, alpha=0.9))
    if strike_put is not None and strike_put > 0 and strike_call is not None and strike_call > 0:
        ax1.fill_between(dates, strike_put, strike_call, color='#42a5f5', alpha=0.04, zorder=1)

    hover_annot = ax1.annotate(
        '', xy=(0, 0), fontsize=7.5, color='#fff',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a1a', edgecolor=ACCENT, alpha=0.9),
        ha='center', va='center', visible=False, zorder=10,
    )
    hover_vline = ax1.axvline(0, color=ACCENT, linewidth=0.6, linestyle=':', alpha=0.3, visible=False, zorder=5)

    def _on_hover(event):
        if event.inaxes != ax1 or event.xdata is None:
            hover_annot.set_visible(False)
            hover_vline.set_visible(False)
            fig.canvas.draw_idle()
            return
        t = mdates.num2date(event.xdata).replace(tzinfo=None)
        idx = min(range(len(dates)), key=lambda i: abs((dates[i] - t).total_seconds()))
        d = dates[idx]
        hover_annot.xy = (mdates.date2num(d), highs[idx])
        hover_annot.set_text(
            f"{d.strftime('%d/%m/%Y')}  "
            f"O={opens[idx]:.2f} H={highs[idx]:.2f} L={lows[idx]:.2f} C={closes[idx]:.2f}"
            + (f"  Vol={volumes[idx]:,.0f}" if idx < len(volumes) and volumes[idx] is not None else "")
        )
        hover_annot.set_visible(True)
        hover_vline.set_xdata([mdates.date2num(d), mdates.date2num(d)])
        hover_vline.set_visible(True)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('motion_notify_event', _on_hover)

    if len(closes) > 10:
        from scipy.stats import norm
        prices_arr = np.array(closes)
        log_ret = np.diff(np.log(prices_arr))
        sigma_daily = np.std(log_ret)
        sigma_periodo = sigma_daily * np.sqrt(n_sessoes)
        spot = closes[-1]
        sigmas = [spot * (1 + i * sigma_periodo) for i in range(-3, 4) if i != 0]
        ylo = min(min(sigmas), prices_arr.min())
        yhi = max(max(sigmas), prices_arr.max())
        pad = (yhi - ylo) * 0.03
        ax1.set_ylim(ylo - pad, yhi + pad)
        for i in range(-3, 4):
            if i == 0: continue
            p = spot * (1 + i * sigma_periodo)
            ax1.axhline(p, color=ACCENT, linewidth=0.5, linestyle=':', alpha=0.25)
            ax1.text(dates[-1], p, f'{i}σ R${p:.2f}',
                     ha='right', va='center', color=ACCENT, fontsize=6.5, alpha=0.7,
                     bbox=dict(boxstyle='round,pad=0.15', facecolor='#1a1a1a', edgecolor='none', alpha=0.6))
        x_gauss = np.linspace(-3.5 * sigma_periodo, 3.5 * sigma_periodo, 300)
        y_gauss = norm.pdf(x_gauss, 0, sigma_periodo)
        ax_inset = ax1.inset_axes([0.02, 0.65, 0.18, 0.28], facecolor='#1a1a1a')
        ax_inset.plot(x_gauss, y_gauss, color=ACCENT, linewidth=1.2, alpha=0.8)
        ax_inset.fill_between(x_gauss, 0, y_gauss, color=ACCENT, alpha=0.1)
        ax_inset.axvline(0, color=TEXT, linewidth=0.5, linestyle='-', alpha=0.3)
        for strike, cor, letra in [(strike_put, '#4caf50', 'P'),
                                    (strike_call, '#ff3355', 'C')]:
            if strike is not None and strike > 0:
                desvio = (strike - spot) / spot / sigma_periodo
                ax_inset.axvline(desvio, color=cor, linewidth=1.5, linestyle='-', alpha=0.9)
                ax_inset.text(desvio, ax_inset.get_ylim()[1] * 0.9, letra,
                              ha='center', va='top', color=cor, fontsize=5.5,
                              bbox=dict(boxstyle='round,pad=0.1', facecolor='#1a1a1a', edgecolor=cor, alpha=0.5))
        for i in range(1, 4):
            for s in (-i * sigma_periodo, i * sigma_periodo):
                ax_inset.axvline(s, color=ACCENT, linewidth=0.4, linestyle=':', alpha=0.2)
        ax_inset.set_facecolor('#1a1a1a')
        ax_inset.tick_params(colors=TEXT, labelsize=5)
        for spine in ax_inset.spines.values():
            spine.set_color('#333')
        ax_inset.set_title(f'{n_sessoes} preg — strikes no Gauss', color=TEXT, fontsize=6)
        ax_inset.set_ylabel('dens.', color=TEXT, fontsize=5)

    if has_vol:
        ax2 = fig.add_subplot(gs[1], facecolor=BG)
        has_vol_data = any(v is not None for v in volumes)
        if has_vol_data:
            vol_max = max(v for v in volumes if v is not None) if any(v is not None for v in volumes) else 1
            vol_norm = [v / vol_max if v is not None else 0 for v in volumes]
            colors_vol = [GREEN if closes[i] >= opens[i] else RED for i in range(len(dates))]
            ax2.bar(dates, vol_norm, width=width, color=colors_vol, alpha=0.7)

        ax2_twin = ax2.twinx()
        has_hist = any(v is not None for v in vol_hists)
        has_impl = any(v is not None for v in vol_impls)
        if has_hist:
            hist_data = [(dates[i], vol_hists[i]) for i in range(len(vol_hists)) if vol_hists[i] is not None]
            if hist_data:
                h_dates, h_vals = zip(*hist_data)
                ax2_twin.plot(h_dates, h_vals, color=BLUE, linewidth=1.0, alpha=0.8, label='Vol. Hist.')
        if has_impl:
            impl_data = [(dates[i], vol_impls[i]) for i in range(len(vol_impls)) if vol_impls[i] is not None]
            if impl_data:
                i_dates, i_vals = zip(*impl_data)
                ax2_twin.plot(i_dates, i_vals, color=RED, linewidth=1.0, alpha=0.8, label='Vol. Impl.')
        ax2_twin.set_ylabel('Volatilidade', color=TEXT, fontsize=9)
        ax2_twin.tick_params(colors=TEXT, labelsize=7)
        ax2_twin.legend(loc='upper left', fontsize=7, labelcolor=TEXT, facecolor='#1a1a1a', edgecolor='#333')

        ax2.set_ylabel('Volume (norm.)', color=TEXT, fontsize=9)
        ax2.tick_params(colors=TEXT, labelsize=7)
        for s in ax2.spines.values():
            s.set_color('#333')
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

    fig.tight_layout(pad=1.5)

    dialog = QDialog(parent, Qt.Window)
    dialog.setWindowTitle(f"Gráfico — {ativo}")
    dialog.setMinimumSize(950, 580)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(8, 8, 8, 8)
    canvas = FigureCanvas(fig)
    layout.addWidget(canvas, stretch=1)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_fechar = QPushButton("Fechar")
    btn_fechar.setAutoDefault(False)
    btn_fechar.clicked.connect(dialog.close)
    btn_fechar.setProperty("class", "primary")
    btn_row.addWidget(btn_fechar)
    layout.addLayout(btn_row)
    dialog.exec_()


class HistoricoTableModel(QAbstractTableModel):
    COLUMNS = [
        ("Data/Hora", "created_at"),
        ("Ativo", "ativo"),
        ("Strike", "strike"),
        ("Operação", "operacao"),
        ("Dias", "dias"),
        ("Preço Ativo", "preco_ativo"),
        ("Custo", "custo"),
        ("Ganho %", "ganho"),
        ("Rent. vs CDI", "cdi_rent"),
    ]

    def __init__(self, items=None):
        super().__init__()
        self._items = items or []

    def rowCount(self, parent=None):
        return len(self._items)

    def columnCount(self, parent=None):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            if role == Qt.ItemDataRole.DisplayRole:
                return self.COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col_key = self.COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key == "created_at":
                dt_str = item["created_at"]
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    return dt.strftime("%d/%m/%Y %H:%M")
                except ValueError:
                    return dt_str
            if col_key == "strike":
                return "{:.2f}".format(item["strike"])
            if col_key == "preco_ativo":
                return "{:.2f}".format(item["preco_ativo"])
            if col_key == "custo":
                op = item["operacao"]
                val = item["custo_box"] if op in ("BOX", "BOXSBTH") else item["custo_sbth"]
                return "{:.4f}".format(val) if val is not None else "-"
            if col_key == "ganho":
                op = item["operacao"]
                val = item["pct_ganho_box"] if op in ("BOX", "BOXSBTH") else item["pct_ganho_sbth"]
                return "{:.2f}%".format(val * 100) if val is not None else "-"
            if col_key == "cdi_rent":
                op = item["operacao"]
                val = item["pct_cdi_box"] if op in ("BOX", "BOXSBTH") else item["pct_cdi_sbth"]
                return "{:.2f}x".format(val) if val is not None else "-"
            return str(item.get(col_key, ""))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("strike", "operacao", "dias", "preco_ativo", "custo", "ganho", "cdi_rent"):
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "ganho":
                op = item["operacao"]
                val = item["pct_ganho_box"] if op in ("BOX", "BOXSBTH") else item["pct_ganho_sbth"]
                if val and val > 0:
                    return QBrush(QColor(Palette.LIQ_POSITIVE))
            if col_key == "cdi_rent":
                return QBrush(QColor(Palette.YELLOW))
            if col_key == "operacao":
                op = item["operacao"]
                if op == "BOX":
                    return QBrush(QColor(Palette.ACCENT_BLUE_BRIGHT))
                elif op == "SBTH":
                    return QBrush(QColor(Palette.CYAN))
                return QBrush(QColor(Palette.PURPLE))
            return QBrush(QColor(Palette.TEXT_PRIMARY))

        return None

    def get_item(self, row: int) -> dict | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def atualizar(self, items):
        self.layoutAboutToBeChanged.emit()
        self._items = items
        self.layoutChanged.emit()


class HistoricoDialog(QDialog):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Histórico de Operações Registradas")
        self.setMinimumSize(950, 500)
        self._setup_ui()
        self.carregar_dados()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_title = QLabel("Histórico de Operações Registradas")
        lbl_title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: {}; padding: 4px 0;".format(Palette.TEXT_PRIMARY)
        )
        layout.addWidget(lbl_title)

        self.table_view = QTableView()
        self.model = HistoricoTableModel()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setFont(QFont("Consolas", 9))
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setDefaultSectionSize(26)
        self.table_view.verticalHeader().hide()
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table_view, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_detalhes = QPushButton("🔍 Ver Detalhes")
        self.btn_detalhes.setProperty("class", "primary")
        self.btn_detalhes.clicked.connect(self._on_detalhes_clicked)
        btn_layout.addWidget(self.btn_detalhes)

        self.btn_grafico = QPushButton("📊 Ver Gráfico")
        self.btn_grafico.setProperty("class", "primary")
        self.btn_grafico.clicked.connect(self._on_grafico_clicked)
        btn_layout.addWidget(self.btn_grafico)

        self.btn_excluir = QPushButton("🗑️ Excluir Registro")
        self.btn_excluir.setProperty("class", "danger")
        self.btn_excluir.clicked.connect(self._on_excluir_clicked)
        btn_layout.addWidget(self.btn_excluir)

        btn_layout.addStretch()

        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_fechar)

        layout.addLayout(btn_layout)

    def carregar_dados(self):
        from src.infrastructure.persistence.repositories.repositories import OportunidadeRepository
        repo = OportunidadeRepository(self.db_path)
        try:
            items = repo.get_historico_com_estrutura()
            self.model.atualizar(items)
        except Exception as e:
            QMessageBox.critical(self, "Erro", "Erro ao carregar histórico: " + str(e))

    def _get_item_selecionado(self) -> dict | None:
        selected = self.table_view.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma operação da tabela.")
            return None
        return self.model.get_item(selected[0].row())

    def _on_row_double_clicked(self, index):
        self._on_detalhes_clicked()

    def _on_detalhes_clicked(self):
        item = self._get_item_selecionado()
        if item:
            self._mostrar_detalhes(item)

    def _on_grafico_clicked(self):
        item = self._get_item_selecionado()
        if not item:
            return
        plot_historico(
            self,
            ativo=item["ativo"],
            preco_atual=item.get("preco_ativo"),
            strike_put=item.get("strike"),
            strike_call=None,
        )

    def _mostrar_detalhes(self, item):
        snapshot_raw = item.get("snapshot_mercado")
        if isinstance(snapshot_raw, str):
            try:
                snapshot = json.loads(snapshot_raw)
            except Exception:
                snapshot = {}
        else:
            snapshot = snapshot_raw or {}

        estruturas = item.get("estruturas", [])

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Detalhes do Registro - {item['ativo']} {item['strike']:.2f}")
        dlg.setMinimumSize(620, 520)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(12, 12, 12, 12)
        dlg_layout.setSpacing(8)

        lbl = QLabel(f"Registro — {item['ativo']} (Strike: {item['strike']:.2f})  |  {item.get('created_at', '')[:19]}")
        lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: {};".format(Palette.TEXT_PRIMARY))
        dlg_layout.addWidget(lbl)

        tabs = QTabWidget()
        dlg_layout.addWidget(tabs, stretch=1)

        # --- Tab 1: Snapshot ---
        tab_snap = QWidget()
        snap_layout = QVBoxLayout(tab_snap)
        snap_layout.setContentsMargins(4, 4, 4, 4)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Consolas", 10))
        txt.setStyleSheet("background-color: #0f0f1a; color: #00ffcc; border: 1px solid #2d2d44; border-radius: 4px;")

        lines = [
            f"Preço Ação: R$ {item['preco_ativo']:.2f}",
            f"Dias p/ Exercício: {item['dias']}",
            f"Estratégia: {item['operacao']}",
            f"Classificação: {item.get('classificacao', 'N/A')}",
            "",
            "=== Dados de Cotação de Opções ===",
        ]

        if snapshot:
            lines.extend([
                f"Opção Tipo: {snapshot.get('tipo_opcao', 'N/A')}",
                f"Compra Put: R$ {snapshot.get('of_compra_put', 0.0):.2f}",
                f"Venda Put: R$ {snapshot.get('of_venda_put', 0.0):.2f}",
                f"Compra Call: R$ {snapshot.get('of_compra_call', 0.0):.2f}",
                f"Venda Call: R$ {snapshot.get('of_venda_call', 0.0):.2f}",
                f"Qul Put: {snapshot.get('qul_put', 0.0):.0f}",
                f"Qul Call: {snapshot.get('qul_call', 0.0):.0f}",
                f"Liq Lote Put: {snapshot.get('liq_put_x_lote', 0.0):.0f}",
                f"Liq Lote Call: {snapshot.get('liq_call_x_lote', 0.0):.0f}",
                f"Moneyness Put: {snapshot.get('money_put', 0.0):.2f}",
                f"Moneyness Call: {snapshot.get('money_call', 0.0):.2f}",
                f"Leilão Ativo: {'Sim' if snapshot.get('em_leilao', False) else 'Não'}",
            ])
        else:
            lines.append("Nenhum dado de cotação adicional salvo.")

        # Add estrutura data from BD if available
        for est in estruturas:
            lines.extend([
                "",
                f"=== Estrutura: {est.get('tipo', 'N/A')} ===",
                f"Coeficiente Alvo: R$ {est.get('coefic_alvo', 0.0):.4f}",
                f"Coeficiente Mercado: R$ {est.get('coefic_mercado', 0.0):.4f}",
                f"Taxa de Ganho: {est.get('taxa_ganho', 0.0):.2f}%",
            ])
            if est.get("pernas"):
                lines.append(f"Pernas ({len(est['pernas'])}):")
                for p in est["pernas"]:
                    lado_label = "COMPRA" if p.get("lado") == "C" else "VENDA"
                    lines.append(f"  {p.get('codigo', '')} | {lado_label} | {p.get('quantidade', 0)}x | Prof. {p.get('profundidade', 0)}")

        txt.setPlainText("\n".join(lines))
        snap_layout.addWidget(txt)
        tabs.addTab(tab_snap, "Snapshot")

        # --- Tab 2: Pernas (tabela) ---
        tab_pernas = QWidget()
        pernas_layout = QVBoxLayout(tab_pernas)
        pernas_layout.setContentsMargins(8, 8, 8, 8)

        if estruturas:
            for i, est in enumerate(estruturas):
                gb = QGroupBox(f"Estrutura {i+1}: {est.get('tipo', 'N/A')}")
                gb_layout = QVBoxLayout(gb)

                params_layout = QFormLayout()
                for rotulo, chave, fmt in [
                    ("Coef. Alvo", "coefic_alvo", "R$ {:.4f}"),
                    ("Coef. Mercado", "coefic_mercado", "R$ {:.4f}"),
                    ("Taxa Ganho", "taxa_ganho", "{:.2f}%"),
                ]:
                    v = est.get(chave)
                    if v is not None:
                        lv = QLabel(fmt.format(v))
                        lv.setStyleSheet("color: {}; font-family: Consolas;".format(Palette.TEXT_PRIMARY))
                        params_layout.addRow(QLabel(rotulo + ":"), lv)
                gb_layout.addLayout(params_layout)

                if est.get("pernas"):
                    table = QTableWidget()
                    table.setColumnCount(5)
                    table.setHorizontalHeaderLabels(["Código", "Lado", "Qtd", "Prof.", "Ordem"])
                    table.setRowCount(len(est["pernas"]))
                    table.horizontalHeader().setStretchLastSection(True)
                    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
                    table.setSelectionBehavior(QAbstractItemView.SelectRows)
                    table.setFont(QFont("Consolas", 9))
                    table.verticalHeader().hide()

                    for j, p in enumerate(est["pernas"]):
                        lado_label = "Compra" if p.get("lado") == "C" else "Venda"
                        table.setItem(j, 0, QTableWidgetItem(p.get("codigo", "")))
                        table.setItem(j, 1, QTableWidgetItem(lado_label))
                        table.setItem(j, 2, QTableWidgetItem(str(p.get("quantidade", ""))))
                        table.setItem(j, 3, QTableWidgetItem(str(p.get("profundidade", ""))))
                        table.setItem(j, 4, QTableWidgetItem(str(p.get("ordem", ""))))
                        for col in range(4):
                            table.item(j, col).setTextAlignment(Qt.AlignCenter)

                    gb_layout.addWidget(table)
                else:
                    lbl_sem = QLabel("Nenhuma perna registrada.")
                    lbl_sem.setStyleSheet("color: {}; font-style: italic;".format(Palette.TEXT_MUTED))
                    gb_layout.addWidget(lbl_sem)

                pernas_layout.addWidget(gb)
        else:
            lbl_sem = QLabel("Nenhuma estrutura vinculada a esta operação.\n\n"
                             "Apenas operações exportadas via 'Registrar Operação' (basket)\n"
                             "possuem estruturas e pernas no banco.")
            lbl_sem.setStyleSheet("color: {}; font-style: italic;".format(Palette.TEXT_MUTED))
            pernas_layout.addWidget(lbl_sem)

        pernas_layout.addStretch()
        tabs.addTab(tab_pernas, "Pernas")

        # --- Tab 3: Parâmetros Técnicos ---
        tab_tec = QWidget()
        tec_layout = QVBoxLayout(tab_tec)
        tec_layout.setContentsMargins(8, 8, 8, 8)

        tec_form = QFormLayout()
        tec_form.setSpacing(6)

        campos_tecnicos = [
            ("pct_cdi_sbth_liquido", "CDI Líquido SBTH", "{:.2f}x"),
            ("pct_cdi_box_liquido",  "CDI Líquido BOX",  "{:.2f}x"),
            ("iv_put",   "IV Put",   "{:.1f}%"),
            ("iv_call",  "IV Call",  "{:.1f}%"),
            ("iv_rank",  "IV Rank",  "{:.2f}"),
            ("delta_total", "Delta Total", "{:.3f}"),
            ("theta_liquido", "Theta Líquido", "{:.2f}"),
            ("vega_liquido", "Vega Líquido", "{:.2f}"),
            ("risco_max", "Risco Máximo", "R$ {:.2f}"),
            ("pnl_projetado", "PnL Projetado", "R$ {:.2f}"),
            ("custo_b3", "Custo B3", "R$ {:.4f}"),
            ("pior_retorno", "Pior Retorno", "R$ {:.2f}"),
            ("melhor_retorno", "Melhor Retorno", "R$ {:.2f}"),
        ]

        adicionou = False
        for chave, rotulo, fmt in campos_tecnicos:
            val = snapshot.get(chave) if chave in snapshot else item.get(chave)
            if val is not None and val != 0.0:
                try:
                    texto = fmt.format(float(val))
                except Exception:
                    texto = str(val)
                lbl_val = QLabel(texto)
                lbl_val.setStyleSheet("color: {}; font-family: Consolas, monospace;".format(Palette.TEXT_PRIMARY))
                tec_form.addRow(QLabel(rotulo + ":"), lbl_val)
                adicionou = True

        if adicionou:
            tec_layout.addLayout(tec_form)
        else:
            lbl_sem = QLabel("Nenhum parâmetro técnico salvo para esta operação.\n\n"
                             "Parâmetros como IV, greeks e CDI líquido serão salvos\n"
                             "em operações registradas a partir desta versão.")
            lbl_sem.setStyleSheet("color: {}; font-style: italic;".format(Palette.TEXT_MUTED))
            tec_layout.addWidget(lbl_sem)

        tec_layout.addStretch()
        tabs.addTab(tab_tec, "Parâmetros Técnicos")

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dlg.accept)
        dlg_layout.addWidget(btn_fechar)

        dlg.exec_()

    def _on_excluir_clicked(self):
        item = self._get_item_selecionado()
        if not item:
            return

        confirm = QMessageBox.question(
            self, "Confirmação de Exclusão",
            f"Deseja realmente excluir a operação registrada de {item['ativo']} "
            f"(Strike: {item['strike']:.2f}) de {item['created_at']}?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            from src.infrastructure.persistence.repositories.repositories import OportunidadeRepository
            repo = OportunidadeRepository(self.db_path)
            try:
                if repo.delete_by_id(item["id"]):
                    QMessageBox.information(self, "Sucesso", "Operação excluída com sucesso.")
                    self.carregar_dados()
                else:
                    QMessageBox.warning(self, "Aviso", "A operação não pôde ser encontrada para exclusão.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", "Erro ao excluir operação: " + str(e))
