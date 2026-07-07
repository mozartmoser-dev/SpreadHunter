"""Calculadoras — diálogo unificado com abas Black-Scholes e CDI.

A aba B&S mantém a mesma lógica de `calculadora_dialog.py` (preço, IV, gregas,
sensibilidade ±2σ). A aba CDI mantém a lógica de `calculadora_cdi_dialog.py`
(quanto investir hoje para receber o strike no vencimento).

Ambos leem `taxa_cdi` de `ParametroRepository` (Banco -> fallback 0.1425),
eliminando os valores hardcoded 14.50/14.15 que ficavam fora de sincronia
com a tabela de parâmetros.

Reabre substituindo os antigos botões `btn_calc` (B&S) e `btn_cdi` (CDI).
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtWidgets import (
    QDialog,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QFormLayout,
    QFrame,
    QTextEdit,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt

from src.domain.services.calculadora_colar import CalculadoraColar
from src.domain.services.calendario_b3 import dc_to_du
from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.ui.desktop.theme import Palette


# ─── Constantes de UI ──────────────────────────────────────────────────────

_CDI_FALLBACK = 0.1425  # alinha com JSON default (config/parametros_default.json)


_LABEL_STYLE = f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;"
_INPUT_STYLE = """
    QLineEdit {
        background-color: #1e1e2f; color: #e0e0e0;
        border: 1px solid #2d2d44; border-radius: 4px;
        padding: 4px 8px; font-size: 10pt;
    }
    QLineEdit:focus { border: 1px solid #1abc9c; }
"""

_INPUT_STYLE_CDI = """
    QLineEdit {
        background-color: #2a2a2a; color: #e0e0e0;
        border: 1px solid #2d2d44; border-radius: 4px;
        padding: 4px 8px; font-size: 11pt; font-weight: bold;
    }
    QLineEdit:focus { border: 1px solid #f39c12; }
"""

_RESULT_STYLE = f"""
    QTextEdit {{
        background-color: #15152a; color: #e0e0e0;
        border: 1px solid {Palette.BORDER}; border-radius: 4px;
        font-family: Consolas, monospace; font-size: 9pt; padding: 8px;
    }}
"""


def _read_taxa_cdi(db_path) -> float:
    """Lê ParametroRepository.get_by_chave('taxa_cdi'); fallback = JSON default."""
    try:
        repo = ParametroRepository(db_path)
        p = repo.get_by_chave("taxa_cdi")
        if p is not None and p.valor is not None:
            return float(p.valor)
    except Exception:
        pass
    return _CDI_FALLBACK


def _brl(val: float, casas: int = 2) -> str:
    """Formata float no padrão BR: 1.234,56."""
    txt = f"{val:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return txt


# ─── Aba 1: Black-Scholes ──────────────────────────────────────────────────

class BlackScholesWidget(QWidget):
    def __init__(self, taxa_cdi_padrao: float, parent=None):
        super().__init__(parent)
        self._taxa_cdi_padrao = taxa_cdi_padrao
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title = QLabel("🧮 Calculadora Black-Scholes")
        title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        sub = QLabel(
            "Precificação de opções, cálculo de IV e sensibilidade ±2σ. "
            "A taxa anual vem do Banco de Dados (Parâmetros > Geral)."
        )
        sub.setStyleSheet(f"font-size: 9pt; color: {Palette.TEXT_MUTED};")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(8)

        def make_input(default: str = "", w: int = 140) -> QLineEdit:
            inp = QLineEdit(default)
            inp.setFixedWidth(w)
            inp.setStyleSheet(_INPUT_STYLE)
            inp.setAlignment(Qt.AlignCenter)
            return inp

        def styled_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(_LABEL_STYLE)
            return lbl

        self.inp_spot = make_input()
        form.addRow(styled_label("Preço Ativo (S):"), self.inp_spot)

        self.inp_strike = make_input()
        form.addRow(styled_label("Strike (K):"), self.inp_strike)

        self.inp_dias = make_input()
        form.addRow(styled_label("Dias p/ venc.:"), self.inp_dias)

        # Taxa vem do banco (default do JSON). Pré-preenche já como % a.a. BR.
        taxa_default = _brl(self._taxa_cdi_padrao * 100, 2)
        self.inp_taxa = make_input(taxa_default)
        form.addRow(styled_label("Taxa % anual (do BD):"), self.inp_taxa)

        self.inp_premio = make_input()
        form.addRow(styled_label("Prêmio (opcional):"), self.inp_premio)

        self.inp_iv = make_input()
        form.addRow(styled_label("IV % (opcional):"), self.inp_iv)

        # Tipo call/put
        tipo_layout = QHBoxLayout()
        tipo_layout.setSpacing(12)
        tipo_layout.addWidget(styled_label("Tipo:"))

        self.radio_call = QRadioButton("Call")
        self.radio_put = QRadioButton("Put")
        self.radio_call.setChecked(True)
        for rb in (self.radio_call, self.radio_put):
            rb.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 9pt;")
        self.grupo_tipo = QButtonGroup(self)
        self.grupo_tipo.addButton(self.radio_call)
        self.grupo_tipo.addButton(self.radio_put)
        tipo_layout.addWidget(self.radio_call)
        tipo_layout.addWidget(self.radio_put)
        tipo_layout.addStretch()
        form.addRow(QLabel(""), tipo_layout)

        layout.addLayout(form)

        btn_calcular = QPushButton("▶  Calcular")
        btn_calcular.setProperty("class", "primary")
        btn_calcular.setStyleSheet("""
            QPushButton {
                background-color: #1abc9c; color: #0d0d1a;
                border: none; border-radius: 4px;
                padding: 8px 24px; font-size: 10pt; font-weight: bold;
            }
            QPushButton:hover { background-color: #16a085; }
        """)
        btn_calcular.clicked.connect(self._calcular)
        btn_calcular.setFixedWidth(160)
        layout.addWidget(btn_calcular, alignment=Qt.AlignmentFlag.AlignCenter)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep2)

        self.resultado = QTextEdit()
        self.resultado.setReadOnly(True)
        self.resultado.setStyleSheet(_RESULT_STYLE)
        self.resultado.setMinimumHeight(180)
        layout.addWidget(self.resultado, stretch=1)

    def _calcular(self):
        try:
            S = float(self.inp_spot.text().replace(",", "."))
            K = float(self.inp_strike.text().replace(",", "."))
            dias = int(self.inp_dias.text())
            taxa_pct = float(self.inp_taxa.text().replace(",", "."))
            r = taxa_pct / 100.0
            tipo = "call" if self.radio_call.isChecked() else "put"
            T = dias / 365.0

            if T <= 0:
                self.resultado.setText("❌ Dias precisa ser > 0")
                return

            linhas = []
            linhas.append(f"Spot:     R$ {S:.2f}")
            linhas.append(f"Strike:   R$ {K:.2f}")
            linhas.append(f"DTE:      {dias}d ({T:.4f} anos)")
            linhas.append(f"Taxa:     {taxa_pct:.2f}% a.a.")
            linhas.append(f"Tipo:     {'CALL' if tipo == 'call' else 'PUT'}")
            linhas.append("")

            premio_text = self.inp_premio.text().strip().replace(",", ".")
            iv_text = self.inp_iv.text().strip().replace(",", ".")

            iv_pct: float | None = None
            if premio_text:
                premio = float(premio_text)
                iv_dec = CalculadoraColar.calcular_iv(S, K, T, r, premio, tipo)
                if iv_dec is not None:
                    linhas.append(f"✅ IV calculada: {iv_dec * 100:.2f}%")
                    iv_pct = iv_dec * 100
                else:
                    linhas.append("❌ IV não convergiu (verifique os dados)")

            if iv_text:
                iv_dec = float(iv_text) / 100.0
                if tipo == "call":
                    preco_bs = CalculadoraColar.black_scholes_call(S, K, T, r, iv_dec)
                else:
                    preco_bs = CalculadoraColar.black_scholes_put(S, K, T, r, iv_dec)
                linhas.append(f"BS price ({iv_text}% IV): R$ {preco_bs:.4f}")

            if premio_text and iv_pct is not None:
                bs_preco = (
                    CalculadoraColar.black_scholes_call(S, K, T, r, iv_pct / 100)
                    if tipo == "call"
                    else CalculadoraColar.black_scholes_put(S, K, T, r, iv_pct / 100)
                )
                intrinsic = max(S - K, 0) if tipo == "call" else max(K - S, 0)
                time_val = premio - intrinsic
                linhas.append(f"Valor intrínseco:  R$ {intrinsic:.4f}")
                if time_val >= 0:
                    linhas.append(f"Valor temporal:    R$ {time_val:.4f}")
                else:
                    linhas.append(f"❌ Prêmio < intrínseco: R$ {time_val:.4f}")

                for vol_label, vol_pct in (
                    ("IV-2σ", max(0.01, iv_pct - 20)),
                    ("IV-1σ", max(0.01, iv_pct - 10)),
                    ("IV", iv_pct),
                    ("IV+1σ", iv_pct + 10),
                    ("IV+2σ", iv_pct + 20),
                ):
                    vol_dec = vol_pct / 100.0
                    p = (
                        CalculadoraColar.black_scholes_call(S, K, T, r, vol_dec)
                        if tipo == "call"
                        else CalculadoraColar.black_scholes_put(S, K, T, r, vol_dec)
                    )
                    linhas.append(f"  {vol_label} ({vol_pct:.1f}%): R$ {p:.4f}")

            self.resultado.setText("\n".join(linhas))

        except ValueError as e:
            self.resultado.setText(f"❌ Erro: verifique os campos numéricos\n{str(e)}")
        except Exception as e:
            self.resultado.setText(f"❌ Erro inesperado: {str(e)}")


# ─── Aba 2: CDI ───────────────────────────────────────────────────────────

class CdiWidget(QWidget):
    def __init__(self, taxa_cdi_padrao: float, parent=None):
        super().__init__(parent)
        self._taxa_cdi_padrao = taxa_cdi_padrao
        self._setup_ui()
        self._calcular()  # pré-popula com valores default

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("📊  Calculadora CDI")
        title.setStyleSheet("font-size: 12pt; font-weight: bold; color: #66bb6a;")
        layout.addWidget(title)

        sub = QLabel(
            "Valor a investir hoje para receber o Strike no vencimento. "
            "A taxa anual vem do Banco de Dados (Parâmetros > Geral)."
        )
        sub.setStyleSheet(f"font-size: 9pt; color: {Palette.TEXT_MUTED};")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(8)

        # CDI Anual — pré-preenchido com o do banco (formato BR com vírgula)
        cdi_default = f"{self._taxa_cdi_padrao * 100:.2f}".replace(".", ",")
        self.ed_cdi = QLineEdit(cdi_default)
        self.ed_cdi.setStyleSheet(_INPUT_STYLE_CDI)
        self.ed_cdi.setAlignment(Qt.AlignCenter)
        form.addRow(QLabel("CDI Anual (%):"), self.ed_cdi)

        self.ed_strike = QLineEdit("1,60")
        self.ed_strike.setStyleSheet(_INPUT_STYLE_CDI)
        self.ed_strike.setAlignment(Qt.AlignCenter)
        form.addRow(QLabel("Strike (R$):"), self.ed_strike)

        default_date = (date.today() + timedelta(days=30)).strftime("%d/%m/%Y")
        self.ed_data = QLineEdit(default_date)
        self.ed_data.setStyleSheet(_INPUT_STYLE_CDI)
        self.ed_data.setAlignment(Qt.AlignCenter)
        form.addRow(QLabel("Vencimento (DD/MM/AAAA):"), self.ed_data)

        self.ed_pct = QLineEdit("100")
        self.ed_pct.setStyleSheet(_INPUT_STYLE_CDI)
        self.ed_pct.setAlignment(Qt.AlignCenter)
        form.addRow(QLabel("% do CDI:"), self.ed_pct)

        # Aplica _LABEL_STYLE aos labels da form (form.itemAt.label)
        for i in range(form.count()):
            it = form.itemAt(i, QFormLayout.LabelRole)
            if it is not None:
                w = it.widget()
                if isinstance(w, QLabel):
                    w.setStyleSheet(_LABEL_STYLE)

        layout.addLayout(form)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep2)

        res_frame = QFrame()
        res_frame.setStyleSheet("background-color: #1e2a1e; border-radius: 4px; padding: 8px;")
        res_layout = QFormLayout(res_frame)
        res_layout.setSpacing(6)

        self.lbl_dias = QLabel("—")
        self.lbl_dias.setStyleSheet("font-size: 11pt; font-weight: bold; color: #4fc3f7;")
        res_layout.addRow(QLabel("Dias até vencimento:"), self.lbl_dias)

        self.lbl_pct_periodo = QLabel("—")
        self.lbl_pct_periodo.setStyleSheet("font-size: 11pt; font-weight: bold; color: #66bb6a;")
        res_layout.addRow(QLabel("CDI do período:"), self.lbl_pct_periodo)

        self.lbl_investir = QLabel("—")
        self.lbl_investir.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ffa726;")
        res_layout.addRow(QLabel("INVESTIR HOJE (R$):"), self.lbl_investir)

        for i in range(res_layout.count()):
            it = res_layout.itemAt(i, QFormLayout.LabelRole)
            if it is not None:
                w = it.widget()
                if isinstance(w, QLabel):
                    w.setStyleSheet(_LABEL_STYLE)

        layout.addWidget(res_frame)

        # Auto-recalcula ao editar qualquer campo
        for ed in (self.ed_cdi, self.ed_strike, self.ed_data, self.ed_pct):
            ed.textChanged.connect(self._calcular)

        btn_close = QPushButton("Fechar")
        btn_close.setProperty("class", "primary")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #2d2d44; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 4px;
                padding: 4px 16px; font-size: 9pt;
            }
            QPushButton:hover { background-color: #3d3d55; }
        """)
        btn_close.clicked.connect(self._on_close_clicked)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_close_clicked(self):
        # Permite fechar o parent dialog (não a aba)
        parent = self.parent()
        while parent is not None and not isinstance(parent, QDialog):
            parent = parent.parent()
        if parent is not None:
            parent.accept()
        else:
            self.close()

    def _calcular(self, *_):
        try:
            cdi_ano = float(self.ed_cdi.text().replace(",", ".")) / 100
            strike = float(self.ed_strike.text().replace(",", "."))
            pct_cdi = float(self.ed_pct.text().replace(",", ".")) / 100

            partes = self.ed_data.text().strip().split("/")
            if len(partes) != 3:
                raise ValueError("Use DD/MM/AAAA")
            d, m, a = int(partes[0]), int(partes[1]), int(partes[2])
            if a < 100:
                a += 2000
            data_venc = date(a, m, d)

            hoje = date.today()
            dias = (data_venc - hoje).days
            if dias <= 0:
                raise ValueError("Vencimento no passado")

            cdi_p = (1 + cdi_ano * pct_cdi) ** (dias / 365) - 1
            investir = strike / (1 + cdi_p)

            self.lbl_dias.setText(f"{dias} dias corridos")
            self.lbl_pct_periodo.setText(f"{_brl(cdi_p * 100, 4)}%")
            self.lbl_investir.setText(f"R$ {_brl(investir, 3)}")
        except Exception as ex:
            self.lbl_dias.setText("—")
            self.lbl_pct_periodo.setText("—")
            self.lbl_investir.setText(str(ex))


# ─── Dialog unificado ──────────────────────────────────────────────────────

class CalculadorasDialog(QDialog):
    """Diálogo com abas B&S e CDI. Substitui btn_calc + btn_cdi."""

    def __init__(self, db_path=None, parent=None):
        super().__init__(parent, Qt.Window)
        self.db_path = db_path
        self.setWindowTitle("🧮 Calculadoras")
        self.setMinimumSize(720, 640)
        self._taxa_cdi_padrao = _read_taxa_cdi(db_path)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header com CDI atual do banco
        header = QHBoxLayout()
        title = QLabel("🧮 Calculadoras")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {Palette.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        cdi_lbl = QLabel(
            f"CDI/Selic atual: {_brl(self._taxa_cdi_padrao * 100, 2)}% a.a. (do BD)"
        )
        cdi_lbl.setStyleSheet(
            f"font-size: 9pt; color: {Palette.TEXT_MUTED}; padding: 4px 8px;"
        )
        header.addWidget(cdi_lbl)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(BlackScholesWidget(self._taxa_cdi_padrao, self), "⚖ Black-Scholes")
        self.tabs.addTab(CdiWidget(self._taxa_cdi_padrao, self), "📊 CDI")
        layout.addWidget(self.tabs, stretch=1)

        # Rodapé único com botão Fechar (cobre ambas as abas)
        rodape = QHBoxLayout()
        rodape.addStretch()
        self.btn_fechar = QPushButton("Fechar")
        self.btn_fechar.clicked.connect(self.accept)
        rodape.addWidget(self.btn_fechar)
        layout.addLayout(rodape)
