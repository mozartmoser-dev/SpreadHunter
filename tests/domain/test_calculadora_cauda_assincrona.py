"""Tests for CalculadoraCaudaAssincrona — 2-sigma validation + ratio float."""

import math
import pytest

from src.domain.services.calculadora_cauda_assincrona import (
    CalculadoraCaudaAssincrona,
    ResultadoCaudaAssincrona,
)


class TestCaudaBasics:
    """Cenario tipico com parametros que passam na validacao 2-nivel."""

    BASE = dict(
        preco_ativo=25.00,
        strike_call=27.50,
        strike_put=22.50,
        premio_call=1.00,
        premio_put=0.20,
        dte_call=40,
        ativo="PETR4",
        iv_call_pct=50.0,
        pnl_projetado_base=0.90,
        capital_empregado_base=24.20,
        pct_cdi_base=2.5,
        calda_ratio_max=300,
        calda_ratio_put_min=0.3,
        calda_ratio_put_step=0.05,
        calda_desvios_cauda=0.5,
    )

    def test_ratio_call_float(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        assert isinstance(r.ratio_call, float)
        assert r.ratio_call >= 1.0

    def test_ratio_put_entre_min_e_um(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        assert 0.3 <= r.ratio_put <= 1.0

    def test_range_ok_zero_nivel(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        assert r.range_ok
        assert r.pnl_na_cauda_esquerda > 0
        assert r.pnl_na_cauda_direita > 0

    def test_breakevens_presentes(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        if r.ratio_call > 1.0:
            assert r.breakeven_direito is not None
        if r.ratio_put < 1.0:
            assert r.breakeven_esquerdo is not None

    def test_none_quando_iv_zero(self):
        base = dict(self.BASE)
        base["iv_call_pct"] = 0.0
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is None

    def test_none_quando_dte_zero(self):
        base = dict(self.BASE)
        base["dte_call"] = 0
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is None

    def test_n_otimo_maior_que_1_quando_gap_grande(self):
        base = dict(self.BASE)
        base["pnl_projetado_base"] = 0.01
        base["calda_premio_risco"] = 1.0
        base["calda_ratio_max"] = 500
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is not None
        assert r.ratio_call > 1.0

    def test_breakeven_direito_para_ratio_um(self):
        be = CalculadoraCaudaAssincrona._breakeven_direito(25.0, 27.0, 0.5, 0.4, 1, 1.0)
        assert be is None

    def test_breakeven_direito_para_ratio_dois(self):
        be = CalculadoraCaudaAssincrona._breakeven_direito(25.0, 20.0, 1.0, 0.4, 2, 1.0)
        assert be is not None
        num = 2 * (20.0 + 1.0) - 25.0 - 0.4
        assert abs(be - num / 1.0) < 1e-6

    def test_breakeven_direito_converge(self):
        be2 = CalculadoraCaudaAssincrona._breakeven_direito(25.0, 27.0, 0.5, 0.4, 2, 1.0)
        be10 = CalculadoraCaudaAssincrona._breakeven_direito(25.0, 27.0, 0.5, 0.4, 10, 1.0)
        be1000 = CalculadoraCaudaAssincrona._breakeven_direito(25.0, 27.0, 0.5, 0.4, 1000, 1.0)
        kc_plus_pc = 27.0 + 0.5
        assert be10 < be2
        assert abs(be1000 - kc_plus_pc) < 0.01

    def test_breakeven_esquerdo_para_m_menor_que_1(self):
        be = CalculadoraCaudaAssincrona._breakeven_esquerdo(25.0, 22.5, 1.0, 0.2, 1, 0.3)
        assert be is not None

    def test_pnl_positivo(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        if r:
            assert r.pnl_com_ratio > 0

    def test_score_positivo(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        if r:
            assert r.score_cauda > 0
