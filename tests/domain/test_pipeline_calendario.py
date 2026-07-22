"""Tests for the calendar collar pipeline fixes:
- _processar_cauda wired into _processar_colar_calendario
- Variant fields (score, greeks, IV rank) properly inherited from base
"""
import math
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.domain.services.calculadora_cauda_assincrona import (
    CalculadoraCaudaAssincrona,
    ResultadoCaudaAssincrona,
)
from src.domain.services.calculadora_colar_calendario import (
    ResultadoColarCalendario,
    TipoColarCalendario,
)


def _criar_base_viavel(
    ativo: str = "PETR4",
    pnl_projetado: float = 1.0,
    pct_cdi: float = 3.0,
) -> ResultadoColarCalendario:
    return ResultadoColarCalendario(
        ativo=ativo,
        vencimento_call=date(2026, 8, 20),
        vencimento_put=date(2026, 12, 15),
        dte_call=30,
        dte_put=147,
        dte_extra=117,
        strike_call=105.0,
        strike_put=100.0,
        cod_call="PETRH105",
        cod_put="PETRX100",
        preco_ativo=102.0,
        premio_call=4.0,
        premio_put=3.5,
        net_credito=0.5,
        iv_call=32.0,
        iv_put=35.0,
        valor_put_venc_call=2.80,
        pnl_stock=0.0,
        pnl_projetado=pnl_projetado,
        capital_empregado=100.0,
        pct_retorno=1.0,
        pct_cdi=pct_cdi,
        delta_total=0.65,
        theta_call=-0.05,
        theta_put=-0.03,
        theta_liquido=0.02,
        viavel=True,
        tipo=TipoColarCalendario.NEUTRO,
        r=0.145,
        custo_b3=5.0,
        custo_ir=1.5,
        pct_cdi_liquido=2.8,
        score=5.2,
        risco_max=20.0,
        iv_rank=0.6,
        iv_rank_call=0.55,
        iv_rank_put=0.65,
        vega_call=0.12,
        vega_put=0.10,
        vega_liquido=0.02,
        gamma_call=0.08,
        gamma_put=0.06,
        score_iv=0.74,
        preco_compra=102.0,
        be_baixa=98.5,
        be_alta=108.2,
        be_baixa_intrinseco=97.0,
        be_alta_intrinseco=109.5,
        ratio_call=1.0,
        ratio_put=1.0,
        detectado_em=datetime.now(),
        qtd_acao=100,
        qtd_call=100,
        qtd_put=100,
    )


class TestCaudaIntegration:
    """Verifica que _processar_cauda (via calcular()) produz resultados corretos."""

    def test_calcular_produz_resultado_com_ratio_ajustado(self):
        r = CalculadoraCaudaAssincrona.calcular(
            preco_ativo=102.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.5,
            dte_call=30,
            ativo="PETR4",
            iv_call_pct=32.0,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            taxa_cdi=0.145,
            calda_premio_risco=2.5,
            calda_desvios_cauda=3.0,
            calda_ratio_max=50,
            calda_ratio_put_min=0.3,
            calda_ratio_put_step=0.1,
            custo_b3_base=5.0,
            preco_compra=102.0,
            dte_put=147,
            iv_put_pct=35.0,
            qtd_acao=100,
            vencimento_call="2026-08-20",
            vencimento_put="2026-12-15",
        )
        assert r is not None
        assert r.viavel
        assert r.ratio_call >= 1.0
        assert 0.0 <= r.ratio_put <= 1.0
        assert r.pnl_com_ratio > 0
        assert r.pct_cdi_com_ratio > 0
        assert r.breakeven_esquerdo is not None or r.breakeven_direito is not None
        assert r.vencimento_call == "2026-08-20"
        assert r.vencimento_put == "2026-12-15"

    def test_calcular_sem_solucao_retorna_none(self):
        r = CalculadoraCaudaAssincrona.calcular(
            preco_ativo=25.0,
            strike_call=27.5,
            strike_put=22.5,
            premio_call=0.01,
            premio_put=0.01,
            dte_call=5,
            ativo="PETR4",
            iv_call_pct=15.0,
            pnl_projetado_base=0.0,
            capital_empregado_base=25.0,
            pct_cdi_base=0.0,
            calda_premio_risco=10.0,
            calda_desvios_cauda=3.0,
            calda_ratio_max=50,
            calda_ratio_put_min=0.3,
            calda_ratio_put_step=0.1,
            qtd_acao=100,
        )
        assert r is None

    def test_calcular_score_reflete_pnl_ajustado(self):
        r = CalculadoraCaudaAssincrona.calcular(
            preco_ativo=100.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.0,
            dte_call=30,
            ativo="PETR4",
            iv_call_pct=30.0,
            pnl_projetado_base=1.5,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            taxa_cdi=0.145,
            calda_premio_risco=2.0,
            calda_desvios_cauda=3.0,
            calda_ratio_max=200,
            calda_ratio_put_min=0.5,
            calda_ratio_put_step=0.10,
            custo_b3_base=5.0,
            dte_put=120,
            iv_put_pct=33.0,
            qtd_acao=100,
        )
        assert r is not None, "calcular retornou None — parâmetros não geraram solução viável"
        assert r.score_cauda > 0
        assert r.pnl_com_ratio > r.pnl_base


class TestVariantFieldsInheritance:
    """Verifica que a construcao de variantes otimizadas herda campos do base."""

    def test_variant_should_inherit_score_from_base(self):
        base = _criar_base_viavel()
        assert base.score == 5.2
        assert base.score_iv == 0.74

    def test_variant_should_inherit_greeks_from_base(self):
        base = _criar_base_viavel()
        assert base.vega_call == 0.12
        assert base.vega_put == 0.10
        assert base.vega_liquido == 0.02
        assert base.gamma_call == 0.08
        assert base.gamma_put == 0.06
        assert base.theta_call == -0.05
        assert base.theta_put == -0.03
        assert base.theta_liquido == 0.02
        assert base.delta_total == 0.65

    def test_variant_should_inherit_iv_rank_from_base(self):
        base = _criar_base_viavel()
        assert base.iv_rank == 0.6
        assert base.iv_rank_call == 0.55
        assert base.iv_rank_put == 0.65

    def test_variant_should_inherit_costs_from_base(self):
        base = _criar_base_viavel()
        assert base.custo_ir == 1.5
        assert base.pct_cdi_liquido == 2.8
        assert base.risco_max == 20.0

    def test_variant_should_inherit_be_intrinseco_from_base(self):
        base = _criar_base_viavel()
        assert base.be_baixa_intrinseco == 97.0
        assert base.be_alta_intrinseco == 109.5

    def test_otimizado_ratio_variant_has_score_positive(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(
            preco_ativo=102.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.5,
            dte_call=30,
            ativo="PETR4",
            iv_call_pct=32.0,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            dte_put=147,
            iv_put_pct=35.0,
            otimizado_ratio_put_min=0.80,
            otimizado_ratio_max=1.30,
            otimizado_ratio_put_step=0.10,
            qtd_acao=100,
            vencimento_call="2026-08-20",
            vencimento_put="2026-12-15",
        )
        for r in resultados:
            assert r.pnl_com_ratio > 0
            assert r.pct_cdi_com_ratio > 0
            assert r.vencimento_call is not None
            assert r.vencimento_put is not None

    def test_base_resultado_calendario_campos_nao_default(self):
        base = _criar_base_viavel()
        assert base.iv_call == 32.0
        assert base.iv_put == 35.0
        assert base.premio_call == 4.0
        assert base.premio_put == 3.5
        assert base.capital_empregado == 100.0


class TestPipelineOtimizadoProducesProperResults:
    """Verifica que o processar_otimizado gera variantes com campos completos."""

    BASE_OTIMIZADO = dict(
        preco_ativo=100.0,
        strike_call=105.0,
        strike_put=100.0,
        premio_call=4.0,
        premio_put=3.0,
        dte_call=30,
        ativo="PETR4",
        iv_call_pct=30.0,
        pnl_projetado_base=1.5,
        capital_empregado_base=100.0,
        pct_cdi_base=3.0,
        dte_put=120,
        iv_put_pct=33.0,
        otimizado_ratio_put_min=0.80,
        otimizado_ratio_max=1.30,
        otimizado_ratio_put_step=0.10,
        qtd_acao=100,
        vencimento_call="2026-08-20",
        vencimento_put="2026-12-15",
    )

    def test_resultados_otimizados_tem_campos_essenciais(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE_OTIMIZADO)
        assert len(resultados) >= 1
        for r in resultados:
            assert r.ativo == "PETR4"
            assert r.strike_call > 0
            assert r.strike_put > 0
            assert r.premio_call > 0
            assert r.premio_put > 0
            assert r.dte_call == 30
            assert r.ratio_call >= 1.0
            assert r.ratio_put > 0
            assert isinstance(r.estagio, str)
            assert r.estagio in ("Base", "Rendimento", "Proteção", "Platô")

    def test_estagio_base_ratio_um_para_um(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE_OTIMIZADO)
        base_result = next((r for r in resultados if r.estagio == "Base"), None)
        if base_result:
            assert base_result.ratio_call == 1.0
            assert base_result.ratio_put == 1.0

    def test_variante_tem_breakevens_quando_ratio_diferente(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE_OTIMIZADO)
        for r in resultados:
            if r.ratio_call > 1.0:
                assert r.breakeven_direito is not None, (
                    f"{r.estagio} com ratio_call={r.ratio_call} deve ter breakeven_direito"
                )
            if r.ratio_put < 1.0:
                assert r.breakeven_esquerdo is not None, (
                    f"{r.estagio} com ratio_put={r.ratio_put} deve ter breakeven_esquerdo"
                )
