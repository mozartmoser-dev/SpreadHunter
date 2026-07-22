import json
import os
import sys
from pathlib import Path
import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario
from src.domain.services.calendario_b3 import dc_to_du
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="Simulador de Collar Calendario", layout="wide"
)

st.title("Simulador & Laboratorio de Collar Calendario")
st.markdown(
    "Altere as variaveis no painel para simular o comportamento das **Gregas Liquidas** "
    "e a **curva de PnL combinado** frente ao tempo, volatilidade e movimento do ativo."
)

PROJETO_ROOT = Path(__file__).resolve().parent.parent
ARQUIVO_INTEGRACAO = str(PROJETO_ROOT / "cenario_atual.json")

if os.path.exists(ARQUIVO_INTEGRACAO):
    try:
        with open(ARQUIVO_INTEGRACAO, "r") as f:
            dados_env = json.load(f)
        st.toast("Dados do cenario carregados via sistema principal!")
    except Exception:
        dados_env = {}
else:
    dados_env = {}

ticker_in = dados_env.get("ativo", "PETR4")
S0_in = float(dados_env.get("preco_spot", 38.50))

K_call_in = float(dados_env.get("strike_call", 40.00))
dte_call_in = int(dados_env.get("dte_call", 18))
iv_call_in = float(dados_env.get("iv_call", 0.28))

K_put_in = float(dados_env.get("strike_put", 37.00))
dte_put_in = int(dados_env.get("dte_put", 42))
iv_put_in = float(dados_env.get("iv_put", 0.31))

r_in = float(dados_env.get("taxa_cdi", 0.145))

st.sidebar.header("Controles do Mercado")

ticker = st.sidebar.text_input("Ativo / Ticker", value=ticker_in)
S = st.sidebar.number_input(
    "Preco Atual do Ativo (S)", value=S0_in, step=0.10, format="%.2f"
)

st.sidebar.divider()
st.sidebar.header("Pernas da Estrutura")

col_c1, col_c2 = st.sidebar.columns(2)
with col_c1:
    K_call = st.number_input(
        "Strike CALL", value=K_call_in, step=0.50, format="%.2f"
    )
    dte_call_orig = st.number_input(
        "DTE CALL (Curta)", value=dte_call_in, step=1
    )
    iv_call_base = (
        st.number_input(
            "IV CALL (%)", value=iv_call_in * 100.0, step=1.0, format="%.1f"
        )
        / 100.0
    )

with col_c2:
    K_put = st.number_input(
        "Strike PUT", value=K_put_in, step=0.50, format="%.2f"
    )
    dte_put_orig = st.number_input(
        "DTE PUT (Longa)", value=dte_put_in, step=1
    )
    iv_put_base = (
        st.number_input(
            "IV PUT (%)", value=iv_put_in * 100.0, step=1.0, format="%.1f"
        )
        / 100.0
    )

st.sidebar.divider()
st.sidebar.header("Simulacao 'E Se...'")

dias_passados = st.sidebar.slider(
    "Dias Decorridos (Avanco no Tempo)",
    0,
    int(dte_call_orig),
    0,
    help="Simula o efeito do tempo no PnL e nas gregas ate o vencimento da CALL curta.",
)

mult_iv = (
    st.sidebar.slider(
        "Choque de Volatilidade (Multiplicador %)",
        50,
        200,
        100,
        step=5,
        help="100% = Volatilidade Implicita Mantida.",
    )
    / 100.0
)

r_input = (
    st.sidebar.number_input("Taxa CDI Anual (%)", value=r_in * 100.0, step=0.25)
    / 100.0
)

r_cont = np.log(1.0 + r_input)

dte_call = max(dte_call_orig - dias_passados, 1)
dte_put = max(dte_put_orig - dias_passados, 1)

T_call = dc_to_du(None, None, dte_call) / 252.0
T_put = dc_to_du(None, None, dte_put) / 252.0

iv_c = iv_call_base * mult_iv
iv_p = iv_put_base * mult_iv


def bs_gregas(S_val, K, T, r, iv, tipo="call"):
    if T <= 1e-5:
        if tipo == "call":
            val = max(S_val - K, 0.0)
            delta = 1.0 if S_val > K else 0.0
        else:
            val = max(K - S_val, 0.0)
            delta = -1.0 if S_val < K else 0.0
        return val, delta, 0.0, 0.0, 0.0

    preco = CalculadoraColarCalendario.black_scholes(S_val, K, T, r, iv, tipo)
    delta = CalculadoraColarCalendario.bs_delta(S_val, K, T, r, iv, tipo)
    gamma = CalculadoraColarCalendario.bs_gamma(S_val, K, T, r, iv)
    vega = CalculadoraColarCalendario.bs_vega(S_val, K, T, r, iv)

    sqrt_T = np.sqrt(T)
    d1 = (np.log(S_val / K) + (r + 0.5 * iv ** 2) * T) / (iv * sqrt_T)
    d2 = d1 - iv * sqrt_T
    pdf_d1 = norm.pdf(d1)
    if tipo == "call":
        theta_anual = - (S_val * pdf_d1 * iv) / (2 * sqrt_T) - r * K * np.exp(-r * T) * norm.cdf(d2)
    else:
        theta_anual = - (S_val * pdf_d1 * iv) / (2 * sqrt_T) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    theta_diario = theta_anual / 252.0

    return preco, delta, gamma, vega, theta_diario


p_call, d_call, g_call, v_call, t_call = bs_gregas(
    S, K_call, T_call, r_cont, iv_c, "call"
)
p_put, d_put, g_put, v_put, t_put = bs_gregas(
    S, K_put, T_put, r_cont, iv_p, "put"
)

delta_liq = 1.0 - d_call + d_put
gamma_liq = -g_call + g_put
vega_liq = -v_call + v_put
theta_liq = -t_call + t_put

st.subheader(f"Gregas Liquidas - {ticker}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Delta Liquido",
        value=f"{delta_liq:.3f}",
        delta=f"Exposicao: {delta_liq*100:.1f}%",
    )

with col2:
    st.metric(
        label="Gamma Liquido",
        value=f"{gamma_liq:.4f}",
        delta="Aceleracao total",
    )

with col3:
    st.metric(
        label="Vega Liquido",
        value=f"R$ {vega_liq:.3f}",
        delta="Por +1% de IV",
    )

with col4:
    st.metric(
        label="Theta Liquido (Dia)",
        value=f"R$ {theta_liq:.3f}",
        delta="Ganho/Perda diaria",
        delta_color="normal" if theta_liq >= 0 else "inverse",
    )

st.divider()

col_graf, col_info = st.columns([2.5, 1])

with col_graf:
    st.subheader("Curva de Payoff Combinada no Vencimento da CALL Curta")

    precos_grid = np.linspace(S * 0.7, S * 1.3, 200)

    T_call_0 = dc_to_du(None, None, dte_call_orig) / 252.0
    T_put_0 = dc_to_du(None, None, dte_put_orig) / 252.0

    p_call_0, _, _, _, _ = bs_gregas(
        S, K_call, T_call_0, r_cont, iv_call_base, "call"
    )
    p_put_0, _, _, _, _ = bs_gregas(
        S, K_put, T_put_0, r_cont, iv_put_base, "put"
    )
    custo_montagem = S - p_call_0 + p_put_0

    pnl_grid = []
    dte_restante = max(dte_put_orig - dte_call_orig, 1)
    t_put_restante = dc_to_du(None, None, dte_restante) / 252.0

    for p_x in precos_grid:
        payoff_acao = p_x
        payoff_call = -max(p_x - K_call, 0.0)
        p_put_res, _, _, _, _ = bs_gregas(
            p_x, K_put, t_put_restante, r_cont, iv_p, "put"
        )
        pnl_pos = (payoff_acao + payoff_call + p_put_res) - custo_montagem
        pnl_grid.append(pnl_pos)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=precos_grid,
            y=pnl_grid,
            mode="lines",
            name="PnL no Venc. Curto",
            line=dict(color="#00E5FF", width=3),
        )
    )

    fig.add_hline(y=0, line_dash="dash", line_color="#888888")

    fig.add_vline(
        x=S,
        line_dash="solid",
        line_color="#FFFFFF",
        annotation_text=f"Spot: R$ {S:.2f}",
    )

    sigma_pct = iv_c * np.sqrt(T_call)
    drift = (r_cont - 0.5 * iv_c ** 2) * T_call

    cores_sigma = ["#FFEB3B", "#FF9800", "#F44336"]
    for i in range(1, 4):
        s_up = S * np.exp(drift + i * sigma_pct)
        s_dn = S * np.exp(drift - i * sigma_pct)

        fig.add_vline(
            x=s_up,
            line_dash="dot",
            line_color=cores_sigma[i - 1],
            annotation_text=f"+{i}s ({s_up:.2f})",
        )
        fig.add_vline(
            x=s_dn,
            line_dash="dot",
            line_color=cores_sigma[i - 1],
            annotation_text=f"-{i}s ({s_dn:.2f})",
        )

    fig.update_layout(
        template="plotly_dark",
        height=450,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Preco do Ativo no Vencimento Curto (R$)",
        yaxis_title="Lucro / Prejuizo Liquido por Acao (R$)",
    )

    st.plotly_chart(fig, use_container_width=True)

with col_info:
    st.subheader("Resumo do Cenario")
    st.info(
        f"**Ativo:** {ticker}\n\n"
        f"**Custo Estimado Montagem:** R$ {custo_montagem:.2f}\n\n"
        f"**CALL Vendida:** K=R$ {K_call:.2f} | DTE Restante: {int(dte_call)}d\n\n"
        f"**PUT Comprada:** K=R$ {K_put:.2f} | DTE Restante: {int(dte_put)}d\n\n"
        f"**Desvio 1s (Lognormal):** R$ {S * np.exp(drift - sigma_pct):.2f}"
        f" a R$ {S * np.exp(drift + sigma_pct):.2f}\n\n"
        f"**Desvio 2s (Lognormal):** R$ {S * np.exp(drift - 2*sigma_pct):.2f}"
        f" a R$ {S * np.exp(drift + 2*sigma_pct):.2f}"
    )
