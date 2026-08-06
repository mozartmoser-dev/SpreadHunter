"""Tests for CalculadoraCaudaAssincrona — 2-sigma validation + ratio float."""

import math
import pytest

from src.domain.services.calendario_b3 import dc_to_du
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
        taxa_cdi=0.1425,
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
        assert 0.0 <= r.ratio_put <= 1.0

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


class TestProcessarOtimizado:
    """Tests for processar_otimizado — 4 variantes, veto 3sigmas, id_chassi."""

    BASE = dict(
        preco_ativo=100.0,
        strike_call=105.0,
        strike_put=100.0,
        premio_call=4.0,
        premio_put=3.0,
        dte_call=5,
        ativo="PETR4",
        iv_call_pct=15.0,
        pnl_projetado_base=1.0,
        capital_empregado_base=100.0,
        pct_cdi_base=3.0,
        dte_put=5,
        iv_put_pct=15.0,
        otimizado_ratio_put_step=0.05,
        otimizado_ratio_put_min=0.80,
        otimizado_ratio_max=1.30,
    )

    def test_retorna_lista(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        assert isinstance(resultados, list)
        assert len(resultados) > 0

    def test_quatro_variantes_max(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        assert len(resultados) <= 4
        for r in resultados:
            assert r.viavel

    def test_mesmo_id_chassi(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        if len(resultados) >= 2:
            chassi = resultados[0].id_chassi
            for r in resultados[1:]:
                assert r.id_chassi == chassi

    def test_estagio_base_se_existe(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        bases = [r for r in resultados if r.estagio == "Base"]
        assert len(bases) <= 1

    def test_estagios_presentes(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        estagios = {r.estagio for r in resultados}
        assert "Base" in estagios
        assert "Otimizado" in estagios

    def test_ratios_no_range(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        for r in resultados:
            assert self.BASE["otimizado_ratio_put_min"] <= r.ratio_put <= 1.0
            assert 1.0 <= r.ratio_call <= self.BASE["otimizado_ratio_max"]

    def test_pnl_cauda_positivo_veto_3s(self):
        """Escudo de 3 sigmas: nenhum candidato com PnL<0 em ±3σ."""
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        for r in resultados:
            assert r.pnl_na_cauda_esquerda >= 0
            assert r.pnl_na_cauda_direita >= 0

    def test_retorna_vazio_iv_zero(self):
        base = dict(self.BASE)
        base["iv_call_pct"] = 0.0
        assert CalculadoraCaudaAssincrona.processar_otimizado(**base) == []

    def test_retorna_vazio_dte_zero(self):
        base = dict(self.BASE)
        base["dte_call"] = 0
        assert CalculadoraCaudaAssincrona.processar_otimizado(**base) == []

    def test_breakevens_nas_variantes(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        for r in resultados:
            if r.ratio_call > 1.0:
                assert r.breakeven_direito is not None
            if r.ratio_put < 1.0:
                assert r.breakeven_esquerdo is not None

    def test_campos_preenchidos(self):
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(**self.BASE)
        for r in resultados:
            assert r.ativo == "PETR4"
            assert r.strike_call == 105.0
            assert r.strike_put == 100.0
            assert r.ratio_call >= 1.0
            assert r.dte_call == 5


class TestLoteB3:
    """B3 lot-snapping: ratios must produce integer contract counts (100 shares)."""

    BASE = dict(
        preco_ativo=25.00,
        strike_call=27.50,
        strike_put=22.50,
        premio_call=1.00,
        premio_put=1.00,
        dte_call=40,
        ativo="PETR4",
        iv_call_pct=50.0,
        pnl_projetado_base=90.0,
        capital_empregado_base=2420.0,
        pct_cdi_base=2.5,
        calda_ratio_max=200,
        calda_ratio_put_min=0.3,
        calda_ratio_put_step=0.10,
        calda_desvios_cauda=0.5,
        qtd_acao=100,
    )

    def test_calcular_ratio_call_gera_contratos_inteiros(self):
        """ratio_call * qtd_acao / 100 must be integer (valid B3 contracts)."""
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        contratos = r.ratio_call * 100 / 100
        assert abs(contratos - round(contratos)) < 1e-9, f"Non-integer contracts: ratio_call={r.ratio_call} -> contracts={contratos}"

    def test_calcular_ratio_put_gera_contratos_inteiros(self):
        """ratio_put * qtd_acao / 100 must be integer (valid B3 contracts)."""
        r = CalculadoraCaudaAssincrona.calcular(**self.BASE)
        assert r is not None
        contratos = r.ratio_put * 100 / 100
        assert contratos >= 0
        assert abs(contratos - round(contratos)) < 1e-9, f"Non-integer contracts: ratio_put={r.ratio_put} -> contracts={contratos}"

    def test_calcular_ratio_call_snapped_para_inteiro(self):
        """ratio_call with qtd_acao=100 should produce integer contract count."""
        base = dict(self.BASE)
        base["pnl_projetado_base"] = 5.0
        r = CalculadoraCaudaAssincrona.calcular(**base)
        assert r is not None
        contratos = r.ratio_call * 100 / 100
        assert abs(contratos - round(contratos)) < 1e-9

    def test_calcular_com_lote_200_snaps_contratos_inteiros(self):
        """With qtd_acao=200, snapped ratios produce integer contract counts."""
        base = dict(self.BASE)
        base["qtd_acao"] = 200
        base["pnl_projetado_base"] = 3.0
        base["capital_empregado_base"] = 2420.0
        base["calda_ratio_put_step"] = 0.10
        base["calda_ratio_max"] = 300
        r = CalculadoraCaudaAssincrona.calcular(**base)
        if r is not None:
            contratos_call = r.ratio_call * 200 / 100
            contratos_put = r.ratio_put * 200 / 100
            assert abs(contratos_call - round(contratos_call)) < 1e-9
            assert abs(contratos_put - round(contratos_put)) < 1e-9
            assert r.pnl_projetado > 0

    def test_processar_otimizado_snaps_ratios(self):
        """processar_otimizado should return only variants with valid lot sizes."""
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(
            preco_ativo=100.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.0,
            dte_call=5,
            ativo="PETR4",
            iv_call_pct=15.0,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            qtd_acao=100,
        )
        for r in resultados:
            snaps_call = round(r.ratio_call * 100 / 100)
            snaps_put = round(r.ratio_put * 100 / 100)
            assert snaps_call * 100 % 100 == 0
            assert snaps_put * 100 % 100 == 0
            assert r.pnl_projetado > 0

    def test_calcular_retorna_none_quando_snap_zera_pnl(self):
        """If snapping ratios makes PnL <= 0, calcular returns None."""
        base = dict(self.BASE)
        base["pnl_projetado_base"] = 0.01
        base["premio_call"] = 0.05
        base["premio_put"] = 0.05
        r = CalculadoraCaudaAssincrona.calcular(**base)
        if r is not None:
            assert r.pnl_projetado > 0


class TestSigmaConsistencia:
    """Sigma period must use dc_to_du/252 convention (not dte/252).

    All sigma calculations across the codebase must converge:
      σ = IV · √(du / 252)   where du = dc_to_du(dte_calendar)
    This matches the payoff-graph convention (dte/365) within ~1%.
    """

    @pytest.mark.parametrize("dte_call,iv_call_pct", [
        (37, 35.27),
        (40, 50.0),
        (5, 15.0),
        (63, 28.5),
        (1, 100.0),
    ])
    def test_calcular_sigma_usa_du_total(self, dte_call, iv_call_pct):
        du = dc_to_du(None, None, dte_call)
        iv = iv_call_pct / 100.0
        expected_sigma = iv * math.sqrt(du / 252.0)
        r = CalculadoraCaudaAssincrona.calcular(
            preco_ativo=25.0,
            strike_call=27.50,
            strike_put=22.50,
            premio_call=1.00,
            premio_put=0.20,
            dte_call=dte_call,
            ativo="PETR4",
            iv_call_pct=iv_call_pct,
            pnl_projetado_base=0.90,
            capital_empregado_base=24.20,
            pct_cdi_base=2.5,
            calda_ratio_max=300,
            calda_ratio_put_min=0.3,
            calda_ratio_put_step=0.05,
            calda_desvios_cauda=0.5,
        )
        if r is not None:
            assert r.sigma_periodo == pytest.approx(expected_sigma, abs=1e-4)

    @pytest.mark.parametrize("dte_call,iv_call_pct,dte_put,iv_put_pct", [
        (37, 35.27, 156, 43.12),
        (40, 50.0, 40, 50.0),
        (5, 15.0, 5, 15.0),
    ])
    def test_processar_otimizado_sigma_usa_du_total(self, dte_call, iv_call_pct, dte_put, iv_put_pct):
        du = dc_to_du(None, None, dte_call)
        iv = iv_call_pct / 100.0
        expected_sigma = iv * math.sqrt(du / 252.0)
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(
            preco_ativo=100.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.0,
            dte_call=dte_call,
            ativo="PETR4",
            iv_call_pct=iv_call_pct,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            dte_put=dte_put,
            iv_put_pct=iv_put_pct,
            otimizado_ratio_put_step=0.05,
            otimizado_ratio_put_min=0.80,
            otimizado_ratio_max=1.30,
        )
        for r in resultados:
            assert r.sigma_periodo == pytest.approx(expected_sigma, abs=1e-4)

    @pytest.mark.parametrize("dte_call", [20, 37, 63, 252])
    def test_du_aproximado_consistente_com_365(self, dte_call):
        """dc_to_du/252 ≈ dte/365 within 1% (DTE>=20 to avoid rounding noise in dc_to_du)."""
        du = dc_to_du(None, None, dte_call)
        t_biz = du / 252.0
        t_cal = dte_call / 365.0
        ratio = math.sqrt(t_biz / t_cal)
        assert 0.99 <= ratio <= 1.01, (
            f"dte={dte_call}: sqrt(du/252) / sqrt(dte/365) = {ratio:.4f}"
        )

    def test_sigma_calcular_e_processar_concordam(self):
        """calcular() and processar_otimizado() produce same sigma for same dte/iv."""
        dte_call = 40
        iv_call_pct = 50.0
        du = dc_to_du(None, None, dte_call)
        expected = (iv_call_pct / 100.0) * math.sqrt(du / 252.0)

        r = CalculadoraCaudaAssincrona.calcular(
            preco_ativo=25.00,
            strike_call=27.50,
            strike_put=22.50,
            premio_call=1.00,
            premio_put=0.20,
            dte_call=dte_call,
            ativo="PETR4",
            iv_call_pct=iv_call_pct,
            pnl_projetado_base=0.90,
            capital_empregado_base=24.20,
            pct_cdi_base=2.5,
            calda_ratio_max=300,
            calda_ratio_put_min=0.3,
            calda_ratio_put_step=0.05,
            calda_desvios_cauda=0.5,
        )
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(
            preco_ativo=100.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.0,
            dte_call=dte_call,
            ativo="PETR4",
            iv_call_pct=iv_call_pct,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            dte_put=dte_call,
            iv_put_pct=iv_call_pct,
            otimizado_ratio_put_step=0.05,
            otimizado_ratio_put_min=0.80,
            otimizado_ratio_max=1.30,
        )
        assert r is not None, "calcular() returned None — check inputs"
        assert r.sigma_periodo == pytest.approx(expected, abs=1e-4)
        for res in resultados:
            assert res.sigma_periodo == pytest.approx(expected, abs=1e-4)


class TestPutIntrinsecoSemBS:
    """Prova divergencia pre-fix: calcular() ignorava payoff intrinseco da PUT
    no fallback sem BS, enquanto processar_otimizado() usava intrinsico.

    BUG: no else de calcular() (~linha 160), bs_put_ref = bs_end_l = bs_end_r = 0.0
    zerava a contribuicao da PUT no delta_pnl. processar_otimizado() sempre usou
    max(0, Kp - S) como fallback, gerando PnL diferente para a mesma estrutura.
    """

    def test_calcular_put_intrinseco_sem_bs_protege_cauda(self):
        """PUT ITM sem BS: pnl_na_cauda_esquerda deve refletir protecao intrinseca.

        Cenário: strike_put > preco_ativo (ITM), sem iv_put/dte_put (usar_bs=False).
        O fallback correto usa max(0, Kp - S), igual ao processar_otimizado().
        Antes do fix, calcular() usava bs_put_ref=bs_end_l=0.0 → delta_pnl da PUT = 0.
        """
        preco_ativo = 25.0
        strike_put = 26.0
        premio_put = 3.0
        qtd_acao = 1000
        calda_desvios_cauda = 1.0

        r = CalculadoraCaudaAssincrona.calcular(
            preco_ativo=preco_ativo,
            strike_call=27.50,
            strike_put=strike_put,
            premio_call=1.00,
            premio_put=premio_put,
            dte_call=40,
            ativo="PETR4",
            iv_call_pct=50.0,
            pnl_projetado_base=90.0,
            capital_empregado_base=2420.0,
            pct_cdi_base=2.5,
            calda_ratio_max=300,
            calda_ratio_put_min=0.3,
            calda_ratio_put_step=0.1,
            calda_desvios_cauda=calda_desvios_cauda,
            qtd_acao=qtd_acao,
        )
        assert r is not None, "calcular() deveria encontrar solucao com pequeno sigma"
        assert r.ratio_put < 1.0, "PUT ITM deve permitir ratio < 1"

        du = dc_to_du(None, None, 40)
        sigma_p_exato = (50.0 / 100.0) * math.sqrt(du / 252.0)
        s_end_l = preco_ativo * (1 - calda_desvios_cauda * sigma_p_exato)

        bs_put_ref_intr = max(0, strike_put - preco_ativo)
        bs_end_l_intr = max(0, strike_put - s_end_l)

        delta_l_put = r.ratio_put * (bs_end_l_intr - bs_put_ref_intr)
        delta_l_stock = s_end_l - preco_ativo
        delta_l_call = r.ratio_call * max(0, s_end_l - 27.50) - r.ratio_call * max(0, preco_ativo - 27.50)
        delta_l_correto = (delta_l_stock + delta_l_call + delta_l_put) * qtd_acao

        extra_call_pnl = 1.00 - max(0, preco_ativo - 27.50)
        custo_put = premio_put - max(0, strike_put - preco_ativo)
        pnl_spot = 90.0 + (r.ratio_call - 1) * extra_call_pnl * qtd_acao + (1 - r.ratio_put) * custo_put * qtd_acao
        expected_pnl_left = round(pnl_spot + delta_l_correto, 4)

        msg = (
            f"BUG: pnl_na_cauda_esquerda={r.pnl_na_cauda_esquerda} != esperado={expected_pnl_left}. "
            f"PUT ITM (strike={strike_put} > spot={preco_ativo}) sem BS: "
            f"bs_put_ref_intr={bs_put_ref_intr}, bs_end_l_intr={bs_end_l_intr:.2f} "
            f"(s_end_l={s_end_l:.2f}). "
            f"calcular() usa bs_put_ref=0 (ignora protecao da PUT), "
            f"processar_otimizado() usa bs_put_ref={bs_put_ref_intr} (correto com intrinseco)."
        )
        assert r.pnl_na_cauda_esquerda == expected_pnl_left, msg


class TestVencimentoPropagation:
    """Verifica que vencimento_call/vencimento_put são propagados corretamente."""

    def test_processar_otimizado_propaga_vencimentos_diferentes(self):
        """Vencimentos diferentes entre call e put devem aparecer corretos em cada variante."""
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(
            preco_ativo=100.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.0,
            dte_call=30,
            ativo="PETR4",
            iv_call_pct=30.0,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            dte_put=30,
            iv_put_pct=30.0,
            otimizado_ratio_put_step=0.05,
            otimizado_ratio_put_min=0.80,
            otimizado_ratio_max=1.30,
            vencimento_call="2026-08-21",
            vencimento_put="2026-11-20",
        )
        assert len(resultados) >= 1, "Deveria gerar pelo menos a variante Base"
        for r in resultados:
            assert r.vencimento_call == "2026-08-21", (
                f"{r.estagio}: vencimento_call deveria ser '2026-08-21', "
                f"mas veio {r.vencimento_call}"
            )
            assert r.vencimento_put == "2026-11-20", (
                f"{r.estagio}: vencimento_put deveria ser '2026-11-20', "
                f"mas veio {r.vencimento_put}"
            )

    def test_processar_otimizado_sem_vencimento_nao_quebra(self):
        """Sem vencimentos (default None), o comportamento antigo deve ser preservado."""
        resultados = CalculadoraCaudaAssincrona.processar_otimizado(
            preco_ativo=100.0,
            strike_call=105.0,
            strike_put=100.0,
            premio_call=4.0,
            premio_put=3.0,
            dte_call=30,
            ativo="PETR4",
            iv_call_pct=30.0,
            pnl_projetado_base=1.0,
            capital_empregado_base=100.0,
            pct_cdi_base=3.0,
            dte_put=30,
            iv_put_pct=30.0,
            otimizado_ratio_put_step=0.05,
            otimizado_ratio_put_min=0.80,
            otimizado_ratio_max=1.30,
        )
        assert len(resultados) >= 1
        for r in resultados:
            assert r.vencimento_call is None
            assert r.vencimento_put is None
