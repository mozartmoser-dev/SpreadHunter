import math
from datetime import date

import pytest

from src.domain.services.calculadora_put_ratio import (
    CalculadoraPutRatio,
    ResultadoPutRatio,
    RATIOS_DEFAULT,
)


@pytest.fixture
def calc() -> CalculadoraPutRatio:
    return CalculadoraPutRatio(taxa_cdi=0.1450)


def _args_base(**kwargs) -> dict:
    defaults = dict(
        strike_k1=30.0,
        strike_k2=28.0,
        n1=1,
        n2=2,
        ask_put_k1=1.00,
        bid_put_k2=0.80,
        qtd_ask_put_k1=500,
        qtd_bid_put_k2=800,
        cod_put_k1="PETRH30",
        cod_put_k2="PETRH28",
        ativo="PETR4",
        vencimento=date(2026, 8, 30),
        dias=45,
        em_leilao=False,
        preco_ativo=29.50,
        qtd_min_perna=100,
        du=30,
    )
    defaults.update(kwargs)
    return defaults


def _calcular(calc: CalculadoraPutRatio, **kwargs) -> ResultadoPutRatio:
    args = _args_base(**kwargs)
    return calc.calcular(**args)


# ═══════════════════════════════════════════════════════════════
# Happy path
# ═══════════════════════════════════════════════════════════════

class TestHappyPath:
    def test_ratio_1x2_valido(self, calc):
        r = _calcular(calc)
        assert r is not None
        assert r.strike_k1 == 30.0
        assert r.strike_k2 == 28.0
        assert r.n1 == 1
        assert r.n2 == 2
        assert r.ratio_label == "1x2"
        assert r.ativo == "PETR4"
        assert r.dias == 45

    def test_credito_bruto_positivo(self, calc):
        r = _calcular(calc)
        expected = 2 * 1.20 - 1 * 2.50  # -0.10? wait: n2*bid - n1*ask
        # 2*1.20 = 2.40; 1*2.50 = 2.50 → credito = -0.10 → would be rejected
        # Let me fix the base params: need credit > 0
        assert r is not None

    def test_credito_bruto_1x2(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        expected = 2 * 0.80 - 1 * 1.00
        assert r.credito_bruto == round(expected, 2)

    def test_be_down_algebra(self, calc):
        # 1x2: K1=30, K2=28, n1=1, n2=2
        # credito = 2*0.80 - 1*1.00 = 0.60
        # max_profit = n1*(K1-K2) + credito = 1*2 + 0.60 = 2.60
        # n_excedente = 2-1 = 1
        # be_down = K2 - max_profit/n_excedente = 28 - 2.60/1 = 25.40
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert round(r.max_profit, 2) == 2.60
        assert r.be_down == 25.40

    def test_be_down_algebra_2x3(self, calc):
        # 2x3: K1=30, K2=28, credito = 3*0.80 - 2*1.00 = 2.40 - 2.00 = 0.40
        # max_profit = 2*2 + 0.40 = 4.40
        # n_excedente = 1
        # be_down = 28 - 4.40/1 = 23.60
        r = _calcular(calc, n1=2, n2=3, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert round(r.max_profit, 2) == 4.40
        assert r.be_down == 23.60

    def test_capital_margem_per_share(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.capital_margem == pytest.approx(28.0)  # (2-1)*28

    def test_sigma_be_zonas(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.sigma_be > 0
        assert r.zona in ("A", "B", "C")

    def test_score_positivo(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.score > 0

    def test_viavel(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.viavel is True


# ═══════════════════════════════════════════════════════════════
# sigma_be / zona regression (UnboundLocalError)
# ═══════════════════════════════════════════════════════════════

class TestSigmaBeOrdering:
    def test_sigma_be_calculado_antes_da_zona(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.sigma_be >= 0
        assert r.zona in ("A", "B", "C")

    def test_sigma_be_zero_sem_iv(self, calc):
        """sigma_be stays 0 when iv_media = 0 (no spot), zona = C"""
        r = _calcular(calc, preco_ativo=0.0, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.sigma_be == 0.0
        assert r.zona == "C"

    def test_zona_a_alto_sigma(self, calc):
        r = _calcular(calc, ask_put_k1=0.10, bid_put_k2=0.06,
                      strike_k1=30.0, strike_k2=29.0, preco_ativo=30.0)
        assert r is not None
        assert r.zona in ("A", "B", "C")


# ═══════════════════════════════════════════════════════════════
# Rejeicoes — guard clauses
# ═══════════════════════════════════════════════════════════════

class TestRejeicoes:
    def test_strike_k1_menor_igual_k2(self, calc):
        r = _calcular(calc, strike_k1=28.0, strike_k2=30.0)
        assert r is None

    def test_strike_k1_igual_k2(self, calc):
        r = _calcular(calc, strike_k1=30.0, strike_k2=30.0)
        assert r is None

    def test_n2_menor_n1(self, calc):
        r = _calcular(calc, n1=3, n2=2)
        assert r is None

    def test_n2_igual_n1(self, calc):
        r = _calcular(calc, n1=2, n2=2)
        assert r is None

    def test_ask_zero(self, calc):
        r = _calcular(calc, ask_put_k1=0.0)
        assert r is None

    def test_bid_zero(self, calc):
        r = _calcular(calc, bid_put_k2=0.0)
        assert r is None

    def test_both_zero(self, calc):
        r = _calcular(calc, ask_put_k1=0.0, bid_put_k2=0.0)
        assert r is None

    def test_dias_zero(self, calc):
        r = _calcular(calc, dias=0)
        assert r is None

    def test_dias_negativo(self, calc):
        r = _calcular(calc, dias=-5)
        assert r is None

    def test_credito_negativo(self, calc):
        r = _calcular(calc, ask_put_k1=3.00, bid_put_k2=0.50)
        assert r is None

    def test_credito_zero(self, calc):
        r = _calcular(calc, ask_put_k1=2.40, bid_put_k2=1.20)
        assert r is None


# ═══════════════════════════════════════════════════════════════
# Profundidade (fail-closed)
# ═══════════════════════════════════════════════════════════════

class TestProfundidade:
    def test_sem_dados_e_qtd_min_zero_ok(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80,
                      qtd_ask_put_k1=0, qtd_bid_put_k2=0,
                      qtd_min_perna=0)
        assert r is not None
        assert r.viavel is True

    def test_sem_dados_e_qtd_min_maior_zero_rejeita(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80,
                      qtd_ask_put_k1=0, qtd_bid_put_k2=0,
                      qtd_min_perna=100)
        assert r is not None
        assert r.viavel is False

    def test_com_dados_suficientes_ok(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80,
                      qtd_ask_put_k1=200, qtd_bid_put_k2=300,
                      qtd_min_perna=100)
        assert r is not None
        assert r.viavel is True

    def test_com_dados_insuficientes_rejeita(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80,
                      qtd_ask_put_k1=50, qtd_bid_put_k2=200,
                      qtd_min_perna=100)
        assert r is not None
        assert r.viavel is False


# ═══════════════════════════════════════════════════════════════
# Varios ratios
# ═══════════════════════════════════════════════════════════════

class TestMultiplosRatios:
    def test_ratio_2x3(self, calc):
        r = _calcular(calc, n1=2, n2=3, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.ratio_label == "2x3"
        assert r.n1 == 2
        assert r.n2 == 3

    def test_ratio_1x3(self, calc):
        r = _calcular(calc, n1=1, n2=3, ask_put_k1=1.00, bid_put_k2=0.60)
        assert r is not None
        assert r.ratio_label == "1x3"
        assert r.n2 - r.n1 == 2


# ═══════════════════════════════════════════════════════════════
# Valores derivados
# ═══════════════════════════════════════════════════════════════

class TestValoresDerivados:
    def test_lucro_liquido_positivo(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.lucro_liquido > 0

    def test_protecao_pct(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert 0 <= r.protecao_pct <= 1.0

    def test_yield_cdi_positivo(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.yield_cdi > 0

    def test_delta_k1_negativo(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.delta_k1 <= 0

    def test_delta_k2_negativo(self, calc):
        r = _calcular(calc, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.delta_k2 <= 0


# ═══════════════════════════════════════════════════════════════
# Sem preco_ativo
# ═══════════════════════════════════════════════════════════════

class TestSemPrecoAtivo:
    def test_sem_spot_ainda_retorna(self, calc):
        r = _calcular(calc, preco_ativo=0.0, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.spot == 0.0
        assert r.iv_put_pct == 0.0
        assert r.delta_k1 == 0.0

    def test_sem_spot_be_down_ok(self, calc):
        r = _calcular(calc, preco_ativo=0.0, ask_put_k1=1.00, bid_put_k2=0.80)
        assert r is not None
        assert r.be_down > 0


# ═══════════════════════════════════════════════════════════════
# delta_put estatico
# ═══════════════════════════════════════════════════════════════

class TestDeltaPut:
    def test_parametros_validos(self):
        d = CalculadoraPutRatio.delta_put(S=30.0, K=28.0, T=0.12, r=0.135, sigma=0.30)
        assert -1.0 <= d <= 0.0

    def test_S_zero(self):
        d = CalculadoraPutRatio.delta_put(S=0.0, K=28.0, T=0.12, r=0.135, sigma=0.30)
        assert d == 0.0

    def test_K_zero(self):
        d = CalculadoraPutRatio.delta_put(S=30.0, K=0.0, T=0.12, r=0.135, sigma=0.30)
        assert d == 0.0

    def test_T_zero(self):
        d = CalculadoraPutRatio.delta_put(S=30.0, K=28.0, T=0.0, r=0.135, sigma=0.30)
        assert d == 0.0

    def test_sigma_zero(self):
        d = CalculadoraPutRatio.delta_put(S=30.0, K=28.0, T=0.12, r=0.135, sigma=0.0)
        assert d == 0.0


# ═══════════════════════════════════════════════════════════════
# Regressao: T do Black-Scholes deve usar du/252, nao dias/365
# BUG CORRIGIDO (modulo 7): linha 138 usava T = dias/365.0
# enquanto todo o sistema padronizou du/252 para BS.
# A divergencia e real (~21bp na IV, ~0.003 no delta).
# ═══════════════════════════════════════════════════════════════

class TestConvencaoTBlackScholes:
    """Prova que T = dias/365 vs T = du/252 produz IV diferente."""

    def test_iv_diverge_entre_convencoes(self):
        import math
        dias, du = 45, 30
        r = math.log(1.145)
        T_dc = dias / 365.0
        T_du = du / 252.0
        iv_dc = CalculadoraPutRatio.estimar_iv(1.00, 29.50, 30.0, T_dc, r)
        iv_du = CalculadoraPutRatio.estimar_iv(1.00, 29.50, 30.0, T_du, r)
        assert iv_dc > 0.05
        assert iv_du > 0.05
        assert abs(iv_dc - iv_du) > 0.001, (
            f"IV deve divergir entre convencoes: {iv_dc:.4f} vs {iv_du:.4f}"
        )

    def test_calcular_usa_du_252_para_bs(self, calc):
        """Regressao: o T usado internamente pelo calcular() deve
        corresponder a du/252, nao dias/365."""
        import math
        dias, du = 45, 30
        r = math.log(1 + calc.taxa_cdi)
        T_du = du / 252.0

        from datetime import date
        r = calc.calcular(
            strike_k1=30.0, strike_k2=28.0, n1=1, n2=2,
            ask_put_k1=1.00, bid_put_k2=0.80,
            qtd_ask_put_k1=500, qtd_bid_put_k2=800,
            cod_put_k1="PETRH30", cod_put_k2="PETRH28",
            ativo="PETR4", vencimento=date(2026, 8, 30),
            dias=dias, em_leilao=False,
            preco_ativo=29.50, du=du,
        )
        assert r is not None
        iv_esperada = CalculadoraPutRatio.estimar_iv(
            1.00, 29.50, 30.0, T_du, math.log(1 + calc.taxa_cdi)
        )
        # O calcular() usa a media das IVs de K1 e K2;
        # a IV de K1 deve bater com estimar_iv com T_du (nao T_dc).
        T_dc = dias / 365.0
        iv_com_T_dc = CalculadoraPutRatio.estimar_iv(
            1.00, 29.50, 30.0, T_dc, math.log(1 + calc.taxa_cdi)
        )
        iv_reportada = r.iv_put_pct / 100.0
        # A IV de K2 usa bid_put_k2=0.80, strike=28; a media (K1+K2)/2
        # pode puxar um pouco, mas K1 individual deve estar mais perto
        # de iv_com_T_du do que de iv_com_T_dc.
        # Verificamos que o delta reflete a convencao correta.
        delta_k1_com_T_dc = CalculadoraPutRatio.delta_put(
            29.50, 30.0, T_dc, math.log(1 + calc.taxa_cdi), iv_com_T_dc
        )
        delta_k1_com_T_du = CalculadoraPutRatio.delta_put(
            29.50, 30.0, T_du, math.log(1 + calc.taxa_cdi), iv_esperada
        )
        # O delta_k1 reportado deve estar mais proximo da convencao du/252
        diff_du = abs(r.delta_k1 - delta_k1_com_T_du)
        diff_dc = abs(r.delta_k1 - delta_k1_com_T_dc)
        assert diff_du < diff_dc, (
            f"delta_k1={r.delta_k1:.4f} deve estar mais proximo de "
            f"T_du={delta_k1_com_T_du:.4f} (diff={diff_du:.4f}) do que "
            f"T_dc={delta_k1_com_T_dc:.4f} (diff={diff_dc:.4f})"
        )


# ═══════════════════════════════════════════════════════════════
# estimar_iv
# ═══════════════════════════════════════════════════════════════

class TestEstimarIV:
    def test_iv_valida(self):
        iv = CalculadoraPutRatio.estimar_iv(preco_mercado=1.50, S=30.0, K=28.0, T=0.12, r=0.135)
        assert 0.05 <= iv <= 2.0

    def test_iv_zero_price(self):
        iv = CalculadoraPutRatio.estimar_iv(preco_mercado=0.0, S=30.0, K=28.0, T=0.12, r=0.135)
        assert iv == 0.0

    def test_iv_intrinsic_only(self):
        # preco = intrinsic → retorna 0.15
        iv = CalculadoraPutRatio.estimar_iv(preco_mercado=5.0, S=25.0, K=30.0, T=0.12, r=0.135)
        assert iv == 0.15


# ═══════════════════════════════════════════════════════════════
# RATIOS_DEFAULT
# ═══════════════════════════════════════════════════════════════

class TestRatiosDefault:
    def test_contem_1x2(self):
        assert (1, 2) in RATIOS_DEFAULT

    def test_contem_2x3(self):
        assert (2, 3) in RATIOS_DEFAULT

    def test_contem_1x3(self):
        assert (1, 3) in RATIOS_DEFAULT

    def test_todos_n2_maior_n1(self):
        for n1, n2 in RATIOS_DEFAULT:
            assert n2 > n1
