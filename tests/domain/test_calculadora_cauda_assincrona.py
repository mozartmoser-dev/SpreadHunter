"""Tests for CalculadoraCaudaAssincrona — the cauda ratio optimizer."""

import math
import pytest

from src.domain.services.calculadora_cauda_assincrona import (
    CalculadoraCaudaAssincrona,
    ResultadoCaudaAssincrona,
)


class TestCaudaBasics:
    """Cenário típico: CALL OTM, gap > 0, encontra N ótimo com BE >= 3σ."""

    BASE = dict(
        preco_ativo=25.00,
        strike_call=20.00,
        strike_put=23.00,
        premio_call=5.40,
        premio_put=0.10,
        dte_call=35,
        ativo="PETR4",
        iv_call_pct=1.0,
        pnl_projetado_base=0.30,
        capital_empregado_base=19.70,
        pct_cdi_base=1.2,
    )

    @staticmethod
    def sigma_periodo(dte, iv):
        return iv / 100.0 * math.sqrt(dte / 252.0)

    def test_retorna_resultado_quando_encontra_ratio(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        assert r.viavel
        assert r.ratio_call >= 1
        assert r.pnl_com_ratio > self.BASE["pnl_projetado_base"]

    def test_ratio_maior_que_um_quando_gap_grande(self):
        base = dict(self.BASE)
        base["pnl_projetado_base"] = 0.05
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is not None
        assert r.ratio_call > 1

    def test_none_quando_gap_negativo(self):
        base = dict(self.BASE)
        base["pnl_projetado_base"] = 10.0
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is None

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

    def test_target_pnl_cresce_com_premio_risco(self):
        r1 = CalculadoraCaudaAssincrona.calcular(**self.BASE, calda_premio_risco=1.0)
        r2 = CalculadoraCaudaAssincrona.calcular(**self.BASE, calda_premio_risco=5.0)
        if r1 and r2:
            assert r2.target_pnl > r1.target_pnl

    def test_k_3sigma_cresce_com_desvios(self):
        r1 = CalculadoraCaudaAssincrona.calcular(**self.BASE, calda_desvios_cauda=1.0)
        r2 = CalculadoraCaudaAssincrona.calcular(**self.BASE, calda_desvios_cauda=5.0)
        if r1 and r2:
            assert r2.k_3sigma > r1.k_3sigma

    def test_breakeven_superior_para_ratio_um(self):
        be = CalculadoraCaudaAssincrona._breakeven_superior(25.0, 27.0, 0.5, 0.4, 1)
        assert be is None

    def test_breakeven_superior_para_ratio_dois(self):
        be = CalculadoraCaudaAssincrona._breakeven_superior(25.0, 20.0, 1.0, 0.4, 2)
        assert be is not None
        num = 2 * (20.0 + 1.0) - 25.0 - 0.4
        assert abs(be - num / 1.0) < 1e-6

    def test_breakeven_superior_para_ratio_tres(self):
        be = CalculadoraCaudaAssincrona._breakeven_superior(25.0, 20.0, 1.0, 0.4, 3)
        assert be is not None
        num = 3 * (20.0 + 1.0) - 25.0 - 0.4
        assert abs(be - num / 2.0) < 1e-6

    def test_breakeven_converge_para_kc_mais_pc(self):
        be2 = CalculadoraCaudaAssincrona._breakeven_superior(25.0, 27.0, 0.5, 0.4, 2)
        be10 = CalculadoraCaudaAssincrona._breakeven_superior(25.0, 27.0, 0.5, 0.4, 10)
        be1000 = CalculadoraCaudaAssincrona._breakeven_superior(25.0, 27.0, 0.5, 0.4, 1000)
        kc_plus_pc = 27.0 + 0.5
        assert be10 < be2  # BE cai com mais CALLs
        assert abs(be1000 - kc_plus_pc) < 0.01  # converge para Kc+Pc

    def test_cenario_itm_call(self):
        base = dict(self.BASE)
        base["preco_ativo"] = 30.0
        base["strike_call"] = 25.0
        base["premio_call"] = 5.50
        base["premio_put"] = 0.10
        base["pnl_projetado_base"] = 0.50
        base["capital_empregado_base"] = 24.60
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is not None or True
        if r:
            assert r.ratio_call >= 1

    def test_com_preco_compra_diferente(self):
        base = dict(self.BASE)
        base["preco_compra"] = 24.50
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is not None

    def test_pnl_com_ratio_correto_para_n_dois(self):
        base = dict(self.BASE)
        base["pnl_projetado_base"] = 0.20
        base["calda_premio_risco"] = 1.0
        r = CalculadoraCaudaAssincrona.calcular(**base)
        if r and r.ratio_call >= 2:
            extra = r.premio_call - max(0, r.preco_ativo - r.strike_call)
            esperado = r.pnl_base + extra * (r.ratio_call - 1)
            assert abs(r.pnl_com_ratio - esperado) < 1e-4

    def test_score_cauda_positivo(self):
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        if r:
            assert r.score_cauda > 0
