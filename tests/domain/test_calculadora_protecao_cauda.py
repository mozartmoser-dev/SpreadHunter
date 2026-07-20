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
#
# Formato do dict: {strike, premio_ask, vol_ask, vol_bid}
# vol_ask/vob_bid = volume diario. min(vol_ask, vol_bid) >= max(cab_minimo, qtd_lote * fator)
# Para fator=0.2 e qtd_lote=200: limiar = max(1, 200*0.2) = 40

STRIKES_CALL = [
    {"strike": 41.00, "premio_ask": 0.35, "vol_ask": 450, "vol_bid": 500},
    {"strike": 42.00, "premio_ask": 0.22, "vol_ask": 280, "vol_bid": 300},
    {"strike": 43.00, "premio_ask": 0.13, "vol_ask": 180, "vol_bid": 200},
    {"strike": 44.00, "premio_ask": 0.07, "vol_ask":  90, "vol_bid": 100},
    {"strike": 45.00, "premio_ask": 0.03, "vol_ask":  40, "vol_bid":  50},
    {"strike": 48.00, "premio_ask": 0.02, "vol_ask":  70, "vol_bid":  80},
]

STRIKES_PUT = [
    {"strike": 33.00, "premio_ask": 0.20, "vol_ask": 180, "vol_bid": 200},
    {"strike": 34.00, "premio_ask": 0.04, "vol_ask":  40, "vol_bid":  50},
    {"strike": 35.00, "premio_ask": 0.08, "vol_ask": 100, "vol_bid": 120},
    {"strike": 36.00, "premio_ask": 0.15, "vol_ask": 230, "vol_bid": 250},
    {"strike": 37.00, "premio_ask": 0.30, "vol_ask": 380, "vol_bid": 400},
]


# ═══════════════════════════════════════════════════════════════
# Exposição nula
# ═══════════════════════════════════════════════════════════════

class TestExposicaoNula:
    def test_ratio_um_retorna_none(self):
        r = _chassi(ratio_call=1.0, ratio_put=1.0)
        assert CalculadoraProtecaoCauda.avaliar(r, strikes_call_candidatos=STRIKES_CALL) is None

    def test_naked_frac_abaixo_piso_retorna_none(self):
        r = _chassi(ratio_call=1.01, ratio_put=0.99)
        assert CalculadoraProtecaoCauda.avaliar(r, strikes_call_candidatos=STRIKES_CALL) is None


# ═══════════════════════════════════════════════════════════════
# Apenas call
# ═══════════════════════════════════════════════════════════════

class TestApenasCall:
    RESULT = _chassi(
        id_chassi="call_only",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1600.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_retorna_resultado(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000)
        assert r is not None
        assert r.lado_protegido == "call"

    def test_naked_call_frac_correto(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000)
        assert r.naked_call_frac == pytest.approx(0.20)

    def test_strike_escolhido_mais_proximo_acima_de_s_target(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000, n_sigma=2.0)
        assert r.strike_protecao_call == 48.00

    def test_qtd_lote_b3(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000)
        assert r.qtd_protecao_call == 200

    def test_custo_premio_ask(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000)
        assert r.custo_protecao_call == 4.00  # 200 * 0.02

    def test_pnl_liquido_menor_que_sem_protecao(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000)
        assert r.pnl_liquido_pos_protecao < r.pnl_sem_protecao

    def test_put_lado_zerado(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000)
        assert r.qtd_protecao_put == 0
        assert r.custo_protecao_put == 0.0
        assert not r.viavel_put
        assert r.strike_protecao_put is None
        assert r.premio_ask_put is None


# ═══════════════════════════════════════════════════════════════
# Apenas put
# ═══════════════════════════════════════════════════════════════

class TestApenasPut:
    RESULT = _chassi(
        id_chassi="put_only",
        ratio_call=1.0, ratio_put=0.80,
        pnl_com_ratio=1550.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_retorna_resultado_com_lado_put(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000)
        assert r is not None
        assert r.lado_protegido == "put"

    def test_naked_put_gap_correto(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000)
        assert r.naked_put_gap == pytest.approx(0.20)

    def test_strike_escolhido_mais_proximo_abaixo_de_s_target(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000, n_sigma=2.0)
        assert r.strike_protecao_put == 33.00

    def test_qtd_lote_b3(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000)
        assert r.qtd_protecao_put == 200

    def test_custo_premio_ask(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000)
        assert r.custo_protecao_put == 40.00  # 200 * 0.20

    def test_call_lado_zerado(self):
        r = CalculadoraProtecaoCauda.avaliar(self.RESULT, strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000)
        assert r.qtd_protecao_call == 0
        assert r.custo_protecao_call == 0.0
        assert not r.viavel_call
        assert r.strike_protecao_call is None
        assert r.premio_ask_call is None


# ═══════════════════════════════════════════════════════════════
# Ambos os lados
# ═══════════════════════════════════════════════════════════════

class TestAmbosLados:
    RESULT = _chassi(
        id_chassi="ambos",
        ratio_call=1.20, ratio_put=0.80,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_retorna_ambos(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r is not None
        assert r.lado_protegido == "ambos"

    def test_ambos_com_custo_positivo(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.custo_protecao_call > 0
        assert r.custo_protecao_put > 0
        assert r.custo_protecao_total > 0

    def test_pnl_liquido_reduzido(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.pnl_liquido_pos_protecao < r.pnl_sem_protecao

    def test_viavel_ambos_com_ganho_suficiente(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.viavel
        assert r.viavel_call
        assert r.viavel_put


# ═══════════════════════════════════════════════════════════════
# Sem liquidez — 3 cenários exigidos
# ═══════════════════════════════════════════════════════════════

class TestSemLiquidez:
    """Cenários (a)(b)(c): volume insuficiente ou unidirecional reprova."""

    RESULT = _chassi(
        id_chassi="sem_book",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_volume_so_um_lado_reprova(self):
        """(a) volume suficiente só de um lado → viavel_call=False."""
        strikes = [{"strike": 48.00, "premio_ask": 0.02, "vol_ask": 500, "vol_bid": 0}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes, qtd_acao=1000,
            fator_seguranca_liquidez=0.2,
        )
        assert r.strike_protecao_call is None
        assert not r.viavel_call

    def test_volume_dois_lados_mas_insuficiente_reprova(self):
        """(b) volume nos dois lados, mas min < qtd_lote * fator → viavel=False."""
        strikes = [{"strike": 48.00, "premio_ask": 0.02, "vol_ask": 10, "vol_bid": 10}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes, qtd_acao=1000,
            fator_seguranca_liquidez=0.2,
        )
        # qtd_lote = 200, limiar = max(1, 200*0.2) = 40
        # min(10,10) = 10 < 40 → reprova
        assert r.strike_protecao_call is None
        assert not r.viavel_call

    def test_volume_dois_lados_suficiente_aprova(self):
        """(c) volume nos dois lados >= qtd_lote * fator → viavel_call=True."""
        strikes = [{"strike": 48.00, "premio_ask": 0.02, "vol_ask": 80, "vol_bid": 80}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes, qtd_acao=1000,
            fator_seguranca_liquidez=0.2,
        )
        # min(80,80) = 80 >= 40 → aprova
        assert r.viavel_call
        assert r.custo_protecao_call == 4.00

    def test_strike_com_volume_zerado_retorna_none_no_lado(self):
        """Nenhum strike tem volume → viavel_call=False, tudo zerado."""
        strikes = [{"strike": 48.00, "premio_ask": 0.00, "vol_ask": 0, "vol_bid": 0}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes, qtd_acao=1000,
        )
        assert r.strike_protecao_call is None
        assert r.custo_protecao_call == 0.0
        assert not r.viavel_call
        assert r.lado_protegido == "nenhum"

    def test_custo_zero_quando_inviavel(self):
        strikes = [{"strike": 48.00, "premio_ask": 0.00, "vol_ask": 0, "vol_bid": 0}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes, qtd_acao=1000,
        )
        assert r.custo_protecao_call == 0.0


# ═══════════════════════════════════════════════════════════════
# Custo excede limite
# ═══════════════════════════════════════════════════════════════

class TestLimiteCusto:
    RESULT = _chassi(
        id_chassi="custo_alto",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1400.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_viavel_false_quando_custo_excede_limite(self):
        strikes_caros = [{"strike": 48.00, "premio_ask": 15.0, "vol_ask": 100, "vol_bid": 100}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes_caros,
            qtd_acao=1000, limite_protecao_pct=0.35,
        )
        assert r is not None
        assert not r.viavel_call

    def test_custo_zero_quando_excede_limite(self):
        strikes_caros = [{"strike": 48.00, "premio_ask": 15.0, "vol_ask": 100, "vol_bid": 100}]
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes_caros, qtd_acao=1000,
        )
        assert r.custo_protecao_call == 0.0


# ═══════════════════════════════════════════════════════════════
# Parâmetros — limite_protecao_pct, cab_minimo, fator_seguranca_liquidez
# ═══════════════════════════════════════════════════════════════

class TestParametros:
    RESULT = _chassi(
        id_chassi="params",
        ratio_call=1.20, ratio_put=1.0,
        pnl_com_ratio=1600.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_limite_protecao_baixo_torna_inviavel(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
            limite_protecao_pct=0.001,
        )
        assert r is not None
        assert not r.viavel_call
        assert r.custo_protecao_call == 0.0

    def test_limite_protecao_alto_torna_viavel(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
            limite_protecao_pct=0.99,
        )
        assert r is not None
        assert r.viavel_call
        assert r.custo_protecao_call > 0

    def test_cab_minimo_alto_exclui_por_volume_insuficiente(self):
        """cab_minimo=100 > min(vol_ask,vol_bid) de todos os strikes → viavel=False."""
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
            cab_minimo=500,
        )
        assert r is not None
        assert r.strike_protecao_call is None
        assert r.custo_protecao_call == 0.0
        assert not r.viavel_call

    def test_cab_minimo_baixo_permite_strike(self):
        """cab_minimo=1 permite strikes com volume >= max(1, qtd_lote*fator)."""
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
            cab_minimo=1,
        )
        assert r.viavel_call
        assert r.custo_protecao_call > 0

    def test_fator_seguranca_exigente_exclui_por_tamanho_ordem(self):
        """fator=2.0 → limiar = max(1, 200*2.0) = 400 → nenhum strike tem min>=400 → reprova."""
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
            fator_seguranca_liquidez=2.0,
        )
        assert r is not None
        assert r.strike_protecao_call is None
        assert not r.viavel_call

    def test_fator_seguranca_baixo_permite(self):
        """fator=0.01 → limiar = max(1, 200*0.01) = max(1,2) = 1 → passa."""
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
            fator_seguranca_liquidez=0.01,
        )
        assert r.viavel_call

    def test_qtd_acao_diferente_escala_proporcional(self):
        r200 = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=200,
        )
        r1000 = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL, qtd_acao=1000,
        )
        assert 0 < r200.qtd_protecao_call < r1000.qtd_protecao_call
        assert r200.custo_protecao_call < r1000.custo_protecao_call


# ═══════════════════════════════════════════════════════════════
# Chassi real 028ac46c (PETR4)
# ═══════════════════════════════════════════════════════════════

class TestChassiReal028ac46c:
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
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.naked_call_frac == pytest.approx(0.20)
        assert r.naked_put_gap == pytest.approx(0.20)
        assert r.lado_protegido == "ambos"

    def test_contratos_inteiros_b3(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.qtd_protecao_call % 100 == 0
        assert r.qtd_protecao_put % 100 == 0

    def test_custo_usando_ask(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.custo_protecao_call == 4.00
        assert r.custo_protecao_put == 40.00

    def test_ganho_extra_supera_custo(self):
        r = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=STRIKES_CALL,
            strikes_put_candidatos=STRIKES_PUT, qtd_acao=1000,
        )
        assert r.viavel
        assert r.pnl_liquido_pos_protecao > 0


class TestDiagnosticLogs:
    """Verifica as 4 mensagens de log DEBUG de _avaliar_lado em cada ponto de rejeição."""

    RESULT = _chassi(
        ratio_call=1.25, ratio_put=1.0,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        pnl_projetado=1700.0,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    STRIKE_OK = {"strike": 46.00, "premio_ask": 0.15, "vol_ask": 500, "vol_bid": 400}
    STRIKE_SEM_LIQ = {"strike": 46.00, "premio_ask": 0.15, "vol_ask": 0, "vol_bid": 0}
    STRIKE_LADO_ERRADO = {"strike": 38.00, "premio_ask": 0.15, "vol_ask": 500, "vol_bid": 400}
    STRIKE_CARO = {"strike": 48.00, "premio_ask": 50.00, "vol_ask": 500, "vol_bid": 400}

    def test_log_zero_strikes_na_entrada(self, caplog):
        """Lista vazia → '0 strikes na entrada'."""
        caplog.set_level("DEBUG")
        CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[], qtd_acao=1000,
        )
        assert "0 strikes na entrada" in caplog.text

    def test_log_zero_pos_liquidez(self, caplog):
        """Candidato sem liquidez → '0 passaram liquidez'."""
        caplog.set_level("DEBUG")
        CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[self.STRIKE_SEM_LIQ], qtd_acao=1000,
        )
        assert "0 passaram liquidez" in caplog.text

    def test_log_zero_pos_direcao(self, caplog):
        """Candidato com liquidez mas strike do lado errado → '0 passaram direcao'."""
        caplog.set_level("DEBUG")
        CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[self.STRIKE_LADO_ERRADO], qtd_acao=1000,
        )
        assert "0 passaram direcao" in caplog.text

    def test_log_reprovado_por_custo(self, caplog):
        """Candidato válido mas custo acima do limite → 'reprovado'."""
        caplog.set_level("DEBUG")
        CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[self.STRIKE_CARO], qtd_acao=1000,
        )
        assert "reprovado" in caplog.text
