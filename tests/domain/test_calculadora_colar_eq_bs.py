"""Regressão: Black-Scholes unificada da CalculadoraColar.

Antes havia duas implementações separadas (black_scholes_call/put na
CalculadoraColar e black_scholes(option_type) na CalculadoraColarCalendario).
A partir de 2026-08-10 as funções da CalculadoraColar delegam para o método
único do Calendário. Este teste prova que o comportamento numérico NÃO mudou:
compara golden values capturados da implementação antiga em um grid amostral
e no cenário real PETR4/028ac46c.
"""

import numpy as np
import pytest

from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_colar import CalculadoraColar
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario


# ─────────────────────────────────────────────────────────────
# Cenário real PETR4/028ac46c (mesmos parâmetros do TestChassiReal028ac46c)
# preco_ativo=40.64, strike_call=40.36, strike_put=38.00, dte_call=37
# taxa_cdi = 0.1425 (default do sistema) → r = ln(1 + cdi), T = du/252
# ─────────────────────────────────────────────────────────────
S_REAL = 40.64
KC_REAL = 40.36
KP_REAL = 38.00
T_REAL = dc_to_du(None, None, 37) / 252.0
R_REAL = float(np.log(1 + 0.1425))

# Golden values capturados da implementação antiga (pré-unificação)
GOLDEN_REAL = [  # (sigma, call, put) para ativo PETR4/028ac46c
    (0.05, 0.8612224994104238, 2.7322049608238667e-08),
    (0.20, 1.49901579950264, 0.12429843762380122),
    (0.20020117598836906, 1.5, 0.12475375732870919),
    (0.40, 2.5023974896143457, 0.8047368422677685),
]

# Golden values grid amostral da varredura de 20.000 pontos
GOLDEN_GRID = [  # (S, K, T, r, sigma) → (call, put)
    ((100, 100, 1.0, 0.05, 0.20), (10.450583572185565, 5.573526022256971)),
    ((110, 100, 1.0, 0.05, 0.20), (17.66295374059044, 2.785896190661841)),
    ((90, 100, 1.0, 0.05, 0.20), (5.091222078817552, 10.214164528888958)),
    ((50, 55, 0.25, 0.12, 0.45), (3.1353140164298985, 6.509818361597844)),
    ((55, 50, 0.25, 0.12, 0.45), (8.57219907320573, 2.094475750631135)),
    ((174.4, 160.0, 0.5, 0.10, 0.30), (27.628382003067756, 5.425089923181986)),
    ((25.7, 26.5, 0.079, 0.133, 0.65), (1.639505407834113, 2.1625275590859196)),
    ((13.52, 13.3, 0.039, 0.13, 0.55), (0.7342414252751199, 0.4469810743413909)),
    ((40.64, 40.36, 0.1031746, 0.1332188, 0.20), (1.4990156637129637, 0.6680706679637947)),
    ((40.64, 38.0, 0.1031746, 0.1332188, 0.20), (3.2830276343176905, 0.12429845100578474)),
]


class TestBlackScholesUmicaColar:
    """Prova que a unificação numérica da BS não alterou a CalculadoraColar."""

    @pytest.mark.parametrize("sigma, call_gold, put_gold", GOLDEN_REAL)
    def test_cenario_real_petr4_028ac46c(self, sigma, call_gold, put_gold):
        call = CalculadoraColar.black_scholes_call(S_REAL, KC_REAL, T_REAL, R_REAL, sigma)
        put = CalculadoraColar.black_scholes_put(S_REAL, KP_REAL, T_REAL, R_REAL, sigma)
        assert call == pytest.approx(call_gold, rel=1e-9)
        assert put == pytest.approx(put_gold, rel=1e-9)

    @pytest.mark.parametrize("params, esperado", GOLDEN_GRID)
    def test_grid_amostral(self, params, esperado):
        S, K, T, r, sigma = params
        call = CalculadoraColar.black_scholes_call(S, K, T, r, sigma)
        put = CalculadoraColar.black_scholes_put(S, K, T, r, sigma)
        assert call == pytest.approx(esperado[0], rel=1e-9)
        assert put == pytest.approx(esperado[1], rel=1e-9)

    def test_paridade_call_put(self):
        S, K, T, r, sigma = 100, 110, 0.5, 0.10, 0.30
        call = CalculadoraColar.black_scholes_call(S, K, T, r, sigma)
        put = CalculadoraColar.black_scholes_put(S, K, T, r, sigma)
        assert abs(call - put - (S - K * np.exp(-r * T))) < 1e-9

    def test_equivalencia_com_calendario(self):
        """black_scholes_call/put == black_scholes(option_type) do Calendário."""
        S, K, T, r, sigma = 40.64, 40.36, T_REAL, R_REAL, 0.20
        assert CalculadoraColar.black_scholes_call(S, K, T, r, sigma) == pytest.approx(
            CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, 'call'), rel=1e-12
        )
        assert CalculadoraColar.black_scholes_put(S, K, T, r, sigma) == pytest.approx(
            CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, 'put'), rel=1e-12
        )

    def test_calcular_iv_mantido(self):
        """calcular_iv continua retornando o mesmo IV do prêmio real (sem IV calc)."""
        iv_call = CalculadoraColar.calcular_iv(S_REAL, KC_REAL, T_REAL, R_REAL, 1.50, 'call')
        iv_put = CalculadoraColar.calcular_iv(S_REAL, KP_REAL, T_REAL, R_REAL, 0.80, 'put')
        assert iv_call == pytest.approx(0.20020117598836906, rel=1e-9)
        assert iv_put == pytest.approx(0.39884210940479453, rel=1e-9)

    def test_preco_bs_iguala_premio_de_entrada(self):
        """Voltando o preço BS do IV recuperado obtém-se o prêmio original."""
        iv_call = CalculadoraColar.calcular_iv(S_REAL, KC_REAL, T_REAL, R_REAL, 1.50, 'call')
        preco_bs = CalculadoraColar.black_scholes_call(S_REAL, KC_REAL, T_REAL, R_REAL, iv_call)
        assert preco_bs == pytest.approx(1.50, rel=1e-9)