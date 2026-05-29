from datetime import date
import math
import pytest

from src.domain.services.calculadora_colar_calendario import (
    CalculadoraColarCalendario,
    ResultadoColarCalendario,
    TipoColarCalendario,
)


class TestBlackScholes:
    def test_call_atm(self):
        v = CalculadoraColarCalendario.black_scholes(100, 100, 1, 0.05, 0.2, 'call')
        assert v > 0

    def test_put_atm(self):
        v = CalculadoraColarCalendario.black_scholes(100, 100, 1, 0.05, 0.2, 'put')
        assert v > 0

    def test_call_itm(self):
        v = CalculadoraColarCalendario.black_scholes(110, 100, 1, 0.05, 0.2, 'call')
        atm = CalculadoraColarCalendario.black_scholes(100, 100, 1, 0.05, 0.2, 'call')
        assert v > atm

    def test_call_otm(self):
        v = CalculadoraColarCalendario.black_scholes(90, 100, 1, 0.05, 0.2, 'call')
        atm = CalculadoraColarCalendario.black_scholes(100, 100, 1, 0.05, 0.2, 'call')
        assert v < atm

    def test_zero_sigma(self):
        v = CalculadoraColarCalendario.black_scholes(100, 100, 1, 0.05, 0, 'call')
        assert v == 0.0

    def test_zero_t(self):
        v = CalculadoraColarCalendario.black_scholes(100, 100, 0, 0.05, 0.2, 'call')
        assert v == 0.0

    def test_call_put_parity(self):
        S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2
        call = CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, 'call')
        put = CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, 'put')
        assert abs(call - put - (S - K * math.exp(-r * T))) < 1e-6


class TestBsTheta:
    def test_theta_call_negativo(self):
        t = CalculadoraColarCalendario.bs_theta(100, 100, 1, 0.05, 0.2, 'call')
        assert t < 0

    def test_theta_put_negativo(self):
        t = CalculadoraColarCalendario.bs_theta(100, 100, 1, 0.05, 0.2, 'put')
        assert t < 0

    def test_zero_sigma(self):
        t = CalculadoraColarCalendario.bs_theta(100, 100, 1, 0.05, 0, 'call')
        assert t == 0.0

    def test_zero_t(self):
        t = CalculadoraColarCalendario.bs_theta(100, 100, 0, 0.05, 0.2, 'call')
        assert t == 0.0


class TestImpliedVolatility:
    def test_known_price(self):
        S, K, T, r = 100, 100, 1, 0.05
        price = CalculadoraColarCalendario.black_scholes(S, K, T, r, 0.25, 'call')
        iv = CalculadoraColarCalendario.implied_volatility(S, K, T, r, price, 'call')
        assert iv is not None
        assert abs(iv - 0.25) < 1e-3

    def test_zero_price(self):
        iv = CalculadoraColarCalendario.implied_volatility(100, 100, 1, 0.05, 0, 'call')
        assert iv is None

    def test_zero_t(self):
        iv = CalculadoraColarCalendario.implied_volatility(100, 100, 0, 0.05, 5, 'call')
        assert iv is None

    def test_otm_call_return_iv(self):
        iv = CalculadoraColarCalendario.implied_volatility(90, 100, 0.5, 0.1325, 0.5, 'call')
        assert iv is not None
        assert iv > 0


class TestCalcularCdiPeriodo:
    def test_um_ano_b3(self):
        cdi = 0.145
        calc = CalculadoraColarCalendario(taxa_cdi=cdi)
        assert calc.calcular_cdi_periodo(252) == pytest.approx(cdi, rel=1e-3)

    def test_zero_dias(self):
        calc = CalculadoraColarCalendario(taxa_cdi=0.145)
        assert calc.calcular_cdi_periodo(0) == 0.0

    def test_negativo(self):
        calc = CalculadoraColarCalendario(taxa_cdi=0.145)
        assert calc.calcular_cdi_periodo(-10) == 0.0

    def test_metade_ano_b3(self):
        calc = CalculadoraColarCalendario(taxa_cdi=0.145)
        v = calc.calcular_cdi_periodo(126)
        assert 0 < v < 0.145


class TestClassificarTipo:
    def test_alta(self):
        calc = CalculadoraColarCalendario()
        t = calc.classificar_tipo(10, 20, 15)
        assert t == TipoColarCalendario.ALTA

    def test_baixa(self):
        calc = CalculadoraColarCalendario()
        t = calc.classificar_tipo(25, 20, 15)
        assert t == TipoColarCalendario.BAIXA

    def test_neutro(self):
        calc = CalculadoraColarCalendario()
        t = calc.classificar_tipo(17.5, 20, 15)
        assert t == TipoColarCalendario.NEUTRO

    def test_na_fronteira(self):
        calc = CalculadoraColarCalendario()
        t = calc.classificar_tipo(17.5, 20, 15)
        assert t == TipoColarCalendario.NEUTRO

    def test_zero_spread(self):
        calc = CalculadoraColarCalendario()
        t = calc.classificar_tipo(50, 50, 50)
        assert t == TipoColarCalendario.NEUTRO


class TestCalcular:
    def test_happy_path(self):
        calc = CalculadoraColarCalendario(taxa_cdi=0.145, premio_risco=1.0)
        r = calc.calcular(
            preco_ativo=50,
            strike_call=55,
            strike_put=45,
            premio_call=3.0,
            premio_put=2.0,
            cod_call="CL1",
            cod_put="PT1",
            dte_call=30,
            dte_put=60,
            ativo="TEST4",
            vencimento_call=date(2026, 6, 27),
            vencimento_put=date(2026, 7, 27),
        )
        assert r is not None
        assert r.ativo == "TEST4"
        assert bool(r.viavel) is True
        assert r.dte_call == 30
        assert r.dte_put == 60
        assert r.dte_extra == 30
        assert r.pnl_projetado > 0
        assert r.capital_empregado > 0
        assert r.pct_cdi > 0

    def test_preco_ativo_zero(self):
        calc = CalculadoraColarCalendario()
        assert calc.calcular(0, 55, 45, 3, 2, "C", "P", 30, 60, "T",
                             date(2026, 6, 27), date(2026, 7, 27)) is None

    def test_premio_zero(self):
        calc = CalculadoraColarCalendario()
        assert calc.calcular(50, 55, 45, 0, 2, "C", "P", 30, 60, "T",
                             date(2026, 6, 27), date(2026, 7, 27)) is None

    def test_dte_zero(self):
        calc = CalculadoraColarCalendario()
        assert calc.calcular(50, 55, 45, 3, 2, "C", "P", 0, 60, "T",
                             date(2026, 6, 27), date(2026, 7, 27)) is None

    def test_pnl_negativo_retorna_none(self):
        calc = CalculadoraColarCalendario()
        assert calc.calcular(50, 55, 45, 0.1, 0.1, "C", "P", 365, 365,
                             "T", date(2026, 6, 27), date(2026, 7, 27)) is None

    def test_viabilidade_por_premio_risco(self):
        calc_alto = CalculadoraColarCalendario(taxa_cdi=0.145, premio_risco=100)
        r = calc_alto.calcular(50, 55, 45, 3, 2, "C", "P", 30, 60, "T",
                               date(2026, 6, 27), date(2026, 7, 27))
        assert r is not None
        assert bool(r.viavel) is False


class TestCalcularPvDividendos:
    def test_sem_dividendos_retorna_preco_original(self):
        S = CalculadoraColarCalendario.calcular_preco_ajustado_dividendos([], 100, 0.13, 365)
        assert S == 100.0

    def test_dividendo_futuro_reduz_preco(self):
        hoje = date.today()
        data_ex = date(hoje.year + 1, 1, 1)
        S = CalculadoraColarCalendario.calcular_preco_ajustado_dividendos(
            [(data_ex, 5.0)], 100, 0.13, 365
        )
        assert S < 100.0
        assert S > 94.0

    def test_dividendo_passado_ignorado(self):
        hoje = date.today()
        data_ex = date(hoje.year - 1, 1, 1)
        S = CalculadoraColarCalendario.calcular_preco_ajustado_dividendos(
            [(data_ex, 5.0)], 100, 0.13, 365
        )
        assert S == 100.0

    def test_dividendo_fora_do_dte_max_ignorado(self):
        hoje = date.today()
        data_ex = date(hoje.year + 2, 1, 1)
        S = CalculadoraColarCalendario.calcular_preco_ajustado_dividendos(
            [(data_ex, 5.0)], 100, 0.13, 30
        )
        assert S == 100.0

    def test_multiplos_dividendos(self):
        hoje = date.today()
        d1 = date(hoje.year, hoje.month + 1, 1) if hoje.month < 12 else date(hoje.year + 1, 1, 1)
        d2 = date(hoje.year, hoje.month + 4, 1) if hoje.month < 9 else date(hoje.year + 1, 4, 1)
        S = CalculadoraColarCalendario.calcular_preco_ajustado_dividendos(
            [(d1, 2.0), (d2, 2.0)], 100, 0.13, 365
        )
        assert S < 98.0
        assert S > 95.0

    def test_zero_r_usado_corretamente(self):
        hoje = date.today()
        data_ex = date(hoje.year + 1, 1, 1)
        S = CalculadoraColarCalendario.calcular_preco_ajustado_dividendos(
            [(data_ex, 5.0)], 100, 0.0, 365
        )
        assert S == pytest.approx(95.0)

    def test_com_dividendos_calcular_retorna_resultado(self):
        calc = CalculadoraColarCalendario(taxa_cdi=0.145, premio_risco=1.0)
        hoje = date.today()
        data_ex = date(hoje.year, hoje.month + 2, 1) if hoje.month < 10 else date(hoje.year + 1, 2, 1)
        divs = [(data_ex, 1.5)]
        r = calc.calcular(
            preco_ativo=50,
            strike_call=55,
            strike_put=45,
            premio_call=3.0,
            premio_put=2.0,
            cod_call="CL1",
            cod_put="PT1",
            dte_call=30,
            dte_put=60,
            ativo="TEST4",
            vencimento_call=date(2026, 6, 27),
            vencimento_put=date(2026, 7, 27),
            dividendos=divs,
        )
        assert r is not None
        assert isinstance(r, ResultadoColarCalendario)
        assert r.iv_call > 0


class TestGerarExplicacao:
    def test_gera_html(self):
        calc = CalculadoraColarCalendario(taxa_cdi=0.145, premio_risco=1.0)
        r = calc.calcular(50, 55, 45, 3, 2, "C", "P", 30, 60, "T",
                          date(2026, 6, 27), date(2026, 7, 27))
        assert r is not None
        html = CalculadoraColarCalendario.gerar_explicacao(r)
        assert "<h3>" in html
        assert r.ativo in html
        assert "CDI" in html
