from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFormLayout, QLineEdit, QRadioButton, QButtonGroup, QFrame, QTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.domain.services.calculadora_colar import CalculadoraColar
from src.ui.desktop.theme import Palette
from src.domain.services.calendario_b3 import dc_to_du


class CalculadoraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("🧮 Calculadora de Opções")
        self.setMinimumSize(420, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🧮 Calculadora Black-Scholes")
        title.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {Palette.TEXT_PRIMARY};")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {Palette.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(8)
        label_style = f"color: {Palette.TEXT_SECONDARY}; font-size: 9pt; font-weight: bold;"
        input_style = """
            QLineEdit {
                background-color: #1e1e2f; color: #e0e0e0;
                border: 1px solid #2d2d44; border-radius: 4px;
                padding: 4px 8px; font-size: 10pt;
            }
            QLineEdit:focus { border-color: #1abc9c; }
        """

        def make_input(default="", w=120):
            inp = QLineEdit(default)
            inp.setFixedWidth(w)
            inp.setStyleSheet(input_style)
            return inp

        self.inp_spot = make_input()
        lbl = QLabel("Preço Ativo (S):")
        lbl.setStyleSheet(label_style)
        form.addRow(lbl, self.inp_spot)

        self.inp_strike = make_input()
        lbl = QLabel("Strike (K):")
        lbl.setStyleSheet(label_style)
        form.addRow(lbl, self.inp_strike)

        self.inp_dias = make_input()
        lbl = QLabel("Dias p/ venc.:")
        lbl.setStyleSheet(label_style)
        form.addRow(lbl, self.inp_dias)

        self.inp_taxa = make_input("14.50")
        lbl = QLabel("Taxa % anual:")
        lbl.setStyleSheet(label_style)
        form.addRow(lbl, self.inp_taxa)

        self.inp_premio = make_input()
        lbl = QLabel("Prêmio (opcional):")
        lbl.setStyleSheet(label_style)
        form.addRow(lbl, self.inp_premio)

        self.inp_iv = make_input()
        lbl = QLabel("IV % (opcional):")
        lbl.setStyleSheet(label_style)
        form.addRow(lbl, self.inp_iv)

        tipo_layout = QHBoxLayout()
        tipo_layout.setSpacing(12)
        lbl_tipo = QLabel("Tipo:")
        lbl_tipo.setStyleSheet(label_style)
        tipo_layout.addWidget(lbl_tipo)

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

        btn_calcular = QPushButton("Calcular")
        btn_calcular.setProperty("class", "primary")
        btn_calcular.setStyleSheet(f"""
            QPushButton {{
                background-color: #1abc9c; color: #0d0d1a;
                border: none; border-radius: 4px;
                padding: 8px 24px; font-size: 10pt; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #16a085; }}
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
        self.resultado.setStyleSheet(f"""
            QTextEdit {{
                background-color: #15152a; color: #e0e0e0;
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                font-family: Consolas, monospace; font-size: 9pt; padding: 8px;
            }}
        """)
        self.resultado.setMinimumHeight(160)
        layout.addWidget(self.resultado, stretch=1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setAutoDefault(False)
        btn_fechar.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d44; color: {Palette.TEXT_PRIMARY};
                border: 1px solid {Palette.BORDER}; border-radius: 4px;
                padding: 6px 14px; font-size: 9pt;
            }}
            QPushButton:hover {{ background-color: #3d3d55; }}
        """)
        btn_fechar.clicked.connect(self.close)
        layout.addWidget(btn_fechar, alignment=Qt.AlignmentFlag.AlignRight)

    def _calcular(self):
        try:
            S = float(self.inp_spot.text().replace(",", "."))
            K = float(self.inp_strike.text().replace(",", "."))
            dias = int(self.inp_dias.text())
            taxa_pct = float(self.inp_taxa.text().replace(",", "."))
            r = taxa_pct / 100.0
            tipo = 'call' if self.radio_call.isChecked() else 'put'
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

            if premio_text:
                premio = float(premio_text)
                iv_dec = CalculadoraColar.calcular_iv(S, K, T, r, premio, tipo)
                if iv_dec is not None:
                    linhas.append(f"✅ IV calculada: {iv_dec*100:.2f}%")
                    iv_pct = iv_dec * 100

                    du = dc_to_du(None, None, dias)
                    cdi_anual = 0.145
                    cdi_periodo = (1 + cdi_anual) ** (du / 252) - 1
                    if cdi_periodo > 0:
                        pmax = premio
                        pior = S - K if tipo == 'call' else K - S
                        if tipo == 'call':
                            pior = max(K - S, 0)
                        else:
                            pior = -max(K - S, 0)
                        linhas.append(f"CDI per.:  {cdi_periodo*100:.4f}%")
                else:
                    linhas.append("❌ IV não convergiu (verifique os dados)")
            else:
                iv_pct = None

            if iv_text:
                iv_dec = float(iv_text) / 100.0
                if tipo == 'call':
                    preco_bs = CalculadoraColar.black_scholes_call(S, K, T, r, iv_dec)
                else:
                    preco_bs = CalculadoraColar.black_scholes_put(S, K, T, r, iv_dec)
                linhas.append(f"BS price ({iv_text}% IV): R$ {preco_bs:.4f}")

            if premio_text and iv_pct is not None:
                bs_preco = CalculadoraColar.black_scholes_call(S, K, T, r, iv_pct/100) if tipo == 'call' else CalculadoraColar.black_scholes_put(S, K, T, r, iv_pct/100)
                intrinsic = max(S - K, 0) if tipo == 'call' else max(K - S, 0)
                time_val = premio - intrinsic
                linhas.append(f"Valor intrínseco:  R$ {intrinsic:.4f}")
                linhas.append(f"Valor temporal:    R$ {time_val:.4f}" if time_val >= 0 else f"❌ Prêmio < intrínseco: R$ {time_val:.4f}")

                for vol_label, vol_pct in [("IV-2σ", max(0.01, iv_pct - 20)), ("IV-1σ", max(0.01, iv_pct - 10)), ("IV", iv_pct), ("IV+1σ", iv_pct + 10), ("IV+2σ", iv_pct + 20)]:
                    vol_dec = vol_pct / 100.0
                    p = CalculadoraColar.black_scholes_call(S, K, T, r, vol_dec) if tipo == 'call' else CalculadoraColar.black_scholes_put(S, K, T, r, vol_dec)
                    linhas.append(f"  {vol_label} ({vol_pct:.1f}%): R$ {p:.4f}")

            self.resultado.setText("\n".join(linhas))

        except ValueError as e:
            self.resultado.setText(f"❌ Erro: verifique os campos numéricos\n{str(e)}")
        except Exception as e:
            self.resultado.setText(f"❌ Erro inesperado: {str(e)}")
