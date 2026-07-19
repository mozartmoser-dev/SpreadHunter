"""Tests for CalculadoraProtecaoCauda — BWB protection layer over ratio-optimized collar."""

import pytest

from src.domain.services.calculadora_cauda_assincrona import ResultadoCaudaAssincrona
from src.domain.services.calculadora_protecao_cauda import (
    CalculadoraProtecaoCauda,
    ResultadoProtecaoCauda,
)


def _chassi(**kwargs) -> ResultadoCaudaAssincrona:
    defaults = dict(
        ativo="PETR4", strike_call=40.36, strike_put=38.00, dte_call=37,
        preco_ativo=40.64, premio_call=1.50, premio_put=0.80, iv_call=35.0,
        pnl_base=1386.23, pnl_projetado=1386.23, capital_base=41520.0,
        pct_cdi_base=2.37, target_pnl=0.0, gap=0.0, sigma_periodo=0.085,
        k_3sigma=47.50, ratio_call=1.0, ratio_put=1.0,
        pnl_com_ratio=1386.23, pct_cdi_com_ratio=2.37,
        pnl_na_cauda_esquerda=800.0, pnl_na_cauda_direita=950.0,
        range_ok=True, breakeven_esquerdo=35.0, breakeven_direito=45.0,
        viavel=True, estagio="Base", id_chassi="test_chassi",
        custo_b3_base=0.0, score_cauda=2.5,
    )
    defaults.update(kwargs)
    return ResultadoCaudaAssincrona(**defaults)


# ── Strikes candidatos que PASSAM nos filtros e na direção ──
# s_target_call = 40.64 * (1 + 2 * 0.085) = 47.55  → strikes >= 47.55
# s_target_put  = 40.64 * (1 - 2 * 0.085) = 33.73  → strikes <= 33.73

STRIKES_CALL = [
    {"strike": 41.00, "premio_bid": 0.30, "premio_ask": 0.35, "cab": 120, "voc": 500, "vov": 450},
    {"strike": 42.00, "premio_bid": 0.18, "premio_ask": 0.22, "cab": 80, "voc": 300, "vov": 280},
    {"strike": 43.00, "premio_bid": 0.10, "premio_ask": 0.13, "cab": 50, "voc": 200, "vov": 180},
    {"strike": 44.00, "premio_bid": 0.05, "premio_ask": 0.07, "cab": 20, "voc": 100, "vov": 90},
    {"strike": 45.00, "premio_bid": 0.02, "premio_ask": 0.03, "cab": 5, "voc": 50, "vov": 40},
    {"strike": 48.00, "premio_bid": 0.01, "premio_ask": 0.02, "cab": 10, "voc": 80, "vov": 70},
]

STRIKES_PUT = [
    {"strike": 33.00, "premio_bid": 0.15, "premio_ask": 0.20, "cab": 40, "voc": 200, "vov": 180},
    {"strike": 34.00, "premio_bid": 0.03, "premio_ask": 0.04, "cab": 10, "voc": 50, "vov": 40},
    {"strike": 35.00, "premio_bid": 0.06, "premio_ask": 0.08, "cab": 30, "voc": 120, "vov": 100},
    {"strike": 36.00, "premio_bid": 0.12, "premio_ask": 0.15, "cab": 60, "voc": 250, "vov": 230},
    {"strike": 37.00, "premio_bid": 0.25, "premio_ask": 0.30, "cab": 100, "voc": 400, "vov": 380},
]


class TestExposicaoNula:
    """Caso (a): sem naked exposure → retorna None."""

    def test_ratio_um_retorna_none(self):
        r = _chassi(ratio_call=1.0, ratio_put=1.0)
        assert CalculadoraProtecaoCauda.avaliar(r, strikes_call_candidatos=STRIKES_CALL) is None

    def test_naked_frac_abaixo_piso_retorna_none(self):
        r = _chassi(ratio_call=1.01, ratio_put=0.99)
        assert CalculadoraProtecaoCauda.avaliar(r, strikes_call_candidatos=STRIKES_CALL) is None


class TestApenasCall:
    """Caso (b): só naked_call_frac > piso."""

    RESULT = _chassi(
        id_chassi="call_only",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1600.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_retorna_resultado(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert r is not None
        assert r.lado_protegido == "call"

    def test_naked_call_frac_correto(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert r.naked_call_frac == pytest.approx(0.20)

    def test_strike_escolhido_mais_proximo_acima_de_s_target(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000, n_sigma=2.0,
        )
        # s_target = 40.64 * (1 + 2*0.085) = 47.55
        # strikes >= 47.55: 48.00 é o único
        assert r.strike_protecao_call == 48.00

    def test_qtd_lote_b3(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert r.qtd_protecao_call == 200

    def test_custo_premio_ask(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert r.custo_protecao_call == 4.00  # 200 * 0.02

    def test_pnl_liquido_menor_que_sem_protecao(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert r.pnl_liquido_pos_protecao < r.pnl_sem_protecao

    def test_put_lado_zerado(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert r.qtd_protecao_put == 0
        assert r.custo_protecao_put == 0.0
        assert not r.viavel_put
        assert r.strike_protecao_put is None
        assert r.premio_ask_put is None


class TestApenasPut:
    """Caso (c): só naked_put_gap > piso."""

    RESULT = _chassi(
        id_chassi="put_only",
        ratio_call=1.0, ratio_put=0.80,
        pnl_com_ratio=1550.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_retorna_resultado_com_lado_put(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r is not None
        assert r.lado_protegido == "put"

    def test_naked_put_gap_correto(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.naked_put_gap == pytest.approx(0.20)

    def test_strike_escolhido_mais_proximo_abaixo_de_s_target(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000, n_sigma=2.0,
        )
        # s_target = 40.64 * (1 - 2*0.085) = 33.73
        # strikes <= 33.73: 33.00 é o único
        assert r.strike_protecao_put == 33.00

    def test_qtd_lote_b3(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.qtd_protecao_put == 200

    def test_custo_premio_ask(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.custo_protecao_put == 40.00  # 200 * 0.20

    def test_call_lado_zerado(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.qtd_protecao_call == 0
        assert r.custo_protecao_call == 0.0
        assert not r.viavel_call
        assert r.strike_protecao_call is None
        assert r.premio_ask_call is None


class TestAmbosLados:
    """Caso (d): ambos os lados com exposição."""

    RESULT = _chassi(
        id_chassi="ambos",
        ratio_call=1.20, ratio_put=0.80,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_retorna_ambos(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        assert r is not None
        assert r.lado_protegido == "ambos"

    def test_ambos_com_custo_positivo(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        assert r.custo_protecao_call > 0
        assert r.custo_protecao_put > 0
        assert r.custo_protecao_total > 0

    def test_pnl_liquido_reduzido(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        assert r.pnl_liquido_pos_protecao < r.pnl_sem_protecao

    def test_viavel_ambos_com_ganho_suficiente(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        # ganho_extra = 1700 - 1386.23 = 313.77, limite=0.35 → max_custo ≈ 109.82
        # CALL: strike=48.00, premio_ask=0.02, qtd=200 → custo_call=4.00
        # PUT:  strike=33.00, premio_ask=0.20, qtd=200 → custo_put=40.00
        # total=44.00 < 109.82 → viavel
        assert r.viavel
        assert r.viavel_call
        assert r.viavel_put


class TestSemLiquidez:
    """Caso (e): strikes candidatos sem CAB nem preço → strike=None, custo=0, viavel=False."""

    STRIKES_SEM_BOOK = [
        {"strike": 48.00, "premio_bid": 0.0, "premio_ask": 0.0, "cab": 0, "voc": 0, "vov": 0},
    ]

    RESULT = _chassi(
        id_chassi="sem_book",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_sem_liquidez_retorna_none_no_lado(self):
        """Nenhum strike passa CAB>=1 nem premio_ask>=0.01 → viavel_call=False, tudo zerado."""
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=self.STRIKES_SEM_BOOK,
            qtd_acao=1000,
        )
        assert r is not None
        assert r.strike_protecao_call is None
        assert r.premio_ask_call is None
        assert r.qtd_protecao_call == 0
        assert r.custo_protecao_call == 0.0
        assert not r.viavel_call
        assert r.lado_protegido == "nenhum"

    def test_custo_zero_quando_inviavel(self):
        """Quando viavel_call=False, custo deve ser 0.0, nunca o valor calculado."""
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=self.STRIKES_SEM_BOOK,
            qtd_acao=1000,
        )
        assert r.custo_protecao_call == 0.0


class TestLimiteCusto:
    """Caso (f): custo da proteção excede o limite → viavel=False, custo=0."""

    RESULT = _chassi(
        id_chassi="custo_alto",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1400.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_viavel_false_quando_custo_excede_limite(self):
        strikes_caros = [
            {"strike": 48.00, "premio_bid": 10.0, "premio_ask": 15.0, "cab": 100, "voc": 50, "vov": 50},
        ]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=strikes_caros,
            qtd_acao=1000,
            limite_protecao_pct=0.35,
        )
        # ganho_extra = 1400 - 1386.23 = 13.77
        # max_custo = 13.77 * 0.35 = 4.82
        # custo = 15.0 * 200 = 3000 >> 4.82 → viavel=False
        assert r is not None
        assert not r.viavel_call

    def test_custo_zero_quando_excede_limite(self):
        """Custo só é > 0 quando viavel=True. Se inviável, custo=0."""
        strikes_caros = [
            {"strike": 48.00, "premio_bid": 10.0, "premio_ask": 15.0, "cab": 100, "voc": 50, "vov": 50},
        ]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=strikes_caros,
            qtd_acao=1000,
        )
        assert r.custo_protecao_call == 0.0


class TestParametros:
    """Testa diferentes combinações de parâmetros."""

    RESULT = _chassi(
        id_chassi="params",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1600.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_limite_protecao_baixo_torna_inviavel(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            qtd_acao=1000,
            limite_protecao_pct=0.001,
        )
        # max_custo = 213.77 * 0.001 = 0.21
        # custo = 0.02 * 200 = 4.00 > 0.21 → inviavel
        assert r is not None
        assert not r.viavel_call
        assert r.custo_protecao_call == 0.0

    def test_limite_protecao_alto_torna_viavel(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            qtd_acao=1000,
            limite_protecao_pct=0.99,
        )
        assert r is not None
        assert r.viavel_call
        assert r.custo_protecao_call > 0

    def test_cab_minimo_exigente_exclui_strike(self):
        """Strike com CAB abaixo do mínimo não passa filtro → strike=None, custo=0, viavel=False."""
        strikes_cab_baixo = [
            {"strike": 48.00, "premio_bid": 0.01, "premio_ask": 0.02, "cab": 1, "voc": 50, "vov": 40},
        ]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=strikes_cab_baixo,
            qtd_acao=1000,
            cab_minimo=10,
        )
        assert r is not None
        assert r.strike_protecao_call is None
        assert r.custo_protecao_call == 0.0
        assert not r.viavel_call

    def test_qtd_acao_diferente_escala_proporcional(self):
        r200 = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=200,
        )
        r1000 = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert 0 < r200.qtd_protecao_call < r1000.qtd_protecao_call
        assert r200.custo_protecao_call < r1000.custo_protecao_call


class TestChassiReal028ac46c:
    """Caso baseado no chassi real 028ac46c (PETR4)."""

    RESULT = _chassi(
        id_chassi="028ac46c",
        ativo="PETR4", preco_ativo=40.64, strike_call=40.36, strike_put=38.00,
        premio_call=1.50, premio_put=0.80,
        ratio_call=1.20, ratio_put=0.80,
        pnl_base=1386.23, pnl_com_ratio=1710.0,
        sigma_periodo=0.085, capital_base=41520.0,
        estagio="Proteção",
    )

    def test_naked_exposicoes_corretas(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        assert r.naked_call_frac == pytest.approx(0.20)
        assert r.naked_put_gap == pytest.approx(0.20)
        assert r.lado_protegido == "ambos"

    def test_contratos_inteiros_b3(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        assert r.qtd_protecao_call % 100 == 0
        assert r.qtd_protecao_put % 100 == 0

    def test_custo_usando_ask(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        # CALL: strike=48.00, ask=0.02, qtd=200 → 4.00
        # PUT:  strike=33.00, ask=0.20, qtd=200 → 40.00
        assert r.custo_protecao_call == 4.00
        assert r.custo_protecao_put == 40.00

    def test_ganho_extra_supera_custo(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT,
            strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT,
            qtd_acao=1000,
        )
        # ganho_extra ≈ 323.77, limite=0.35 → max_custo ≈ 113.32
        # custo total = 44.00 < 113.32 → viavel
        assert r.viavel
        assert r.pnl_liquido_pos_protecao > 0
