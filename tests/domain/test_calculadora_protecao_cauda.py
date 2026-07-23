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
        # K=48.00 ask=0.02, estagio Proteção ativa razao_convexidade_max=1.5
        # qtd = round((0.2*1.5)*1000/100)*100 = 300, custo = 300*0.02 = 6.00
        assert r.custo_protecao_call == 6.00
        # K=33.00 ask=0.20, razao=1.5 → qtd=300, custo = 300*0.20 = 60.00
        assert r.custo_protecao_put == 60.00

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


# ═══════════════════════════════════════════════════════════════
# Mudança 1 — limite_protecao_pct por variante (estagio)
# ═══════════════════════════════════════════════════════════════

class TestLimitePorEstagio:
    RESULT = _chassi(
        ratio_call=1.25, ratio_put=1.0,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    STRIKE_CARO = {"strike": 48.00, "premio_ask": 15.0, "vol_ask": 500, "vol_bid": 400}

    def test_rendimento_usa_limite_proprio_nao_global(self):
        """Rendimento usa limite_protecao_pct_rendimento (0.20), não o global (0.35)."""
        r = _chassi(
            ratio_call=1.25, ratio_put=1.0,
            pnl_com_ratio=1700.0, pnl_base=1386.23,
            sigma_periodo=0.085, preco_ativo=40.64,
            estagio="Rendimento",
        )
        # ganho_extra = 313.77, budget global = 313.77*0.35 = 109.82, budget Rendimento = 313.77*0.20 = 62.75
        # strike caro: custo = 15*200 = 3000 (excede ambos → inviavel em qualquer caso)
        # Vamos testar com strike que cabe no global mas NÃO no Rendimento
        strike_limite = {"strike": 48.00, "premio_ask": 0.40, "vol_ask": 500, "vol_bid": 400}
        # custo global: 0.40*200=80 <= 109.82 → viavel
        # custo Rendimento: 80 > 62.75 → inviavel
        prot = CalculadoraProtecaoCauda.avaliar(
            r, strikes_call_candidatos=[strike_limite], qtd_acao=1000,
            limite_protecao_pct=0.35,
            limite_protecao_pct_rendimento=0.20,
        )
        assert prot is not None
        assert not prot.viavel_call
        assert prot.custo_protecao_call == 0.0

    def test_protecao_usa_limite_proprio_nao_global(self):
        """Proteção usa limite_protecao_pct_protecao (0.70), não o global (0.35)."""
        r = _chassi(
            ratio_call=1.25, ratio_put=1.0,
            pnl_com_ratio=1386.73, pnl_base=1386.23,
            sigma_periodo=0.085, preco_ativo=40.64,
            estagio="Proteção",
        )
        # ganho_extra = 0.50, budget global = 0.50*0.35 = 0.175, budget Protecao = 0.50*0.70 = 0.35
        # ask=0.002, qtd=100 (qtd_acao=100, naked_frac=0.25 → lote=100), custo=0.20
        # global: 0.20 > 0.175 → inviavel | Protecao: 0.20 <= 0.35 → viavel
        strike_barato = {"strike": 48.00, "premio_ask": 0.002, "vol_ask": 500, "vol_bid": 400}
        prot = CalculadoraProtecaoCauda.avaliar(
            r, strikes_call_candidatos=[strike_barato], qtd_acao=100,
            limite_protecao_pct=0.35,
            limite_protecao_pct_protecao=0.70,
            calda_preco_min_opcao=0.001,
        )
        assert prot is not None
        assert prot.viavel_call
        assert prot.custo_protecao_call > 0

    def test_base_usa_fallback_global(self):
        """Base não está no mapa → usa limite_protecao_pct global."""
        r = _chassi(
            ratio_call=1.25, ratio_put=1.0,
            pnl_com_ratio=1700.0, pnl_base=1386.23,
            sigma_periodo=0.085, preco_ativo=40.64,
            estagio="Base",
        )
        # Base nem chega a avaliar proteção (ratio_put=1.0, naked_put_gap=0),
        # mas se tivesse naked em ambos os lados, usaria o global.
        strike_ok = {"strike": 48.00, "premio_ask": 0.02, "vol_ask": 500, "vol_bid": 400}
        # ganho_extra = 313.77, budget = 313.77*0.35 = 109.82, custo = 4.0 → viavel
        prot = CalculadoraProtecaoCauda.avaliar(
            r, strikes_call_candidatos=[strike_ok], qtd_acao=1000,
            limite_protecao_pct=0.35,
        )
        assert prot is not None
        assert prot.viavel_call


# ═══════════════════════════════════════════════════════════════
# Mudança 2 — razão de convexidade
# ═══════════════════════════════════════════════════════════════

class TestRazaoConvexidade:
    def test_razao_convexidade_so_ativa_em_protecao(self):
        """Em Rendimento, razão fica em 1.0 mesmo com razao_convexidade_max=3.0."""
        r = _chassi(
            ratio_call=1.25, ratio_put=1.0,
            pnl_com_ratio=1700.0, pnl_base=1386.23,
            sigma_periodo=0.085, preco_ativo=40.64,
            estagio="Rendimento",
        )
        strike = {"strike": 48.00, "premio_ask": 0.02, "vol_ask": 500, "vol_bid": 400}
        prot = CalculadoraProtecaoCauda.avaliar(
            r, strikes_call_candidatos=[strike], qtd_acao=1000,
            razao_convexidade_max=3.0,
        )
        assert prot is not None
        assert prot.razao_convexidade_call == 1.0
        # naked_frac=0.25, qtd_acao=1000 → int(250/100+0.5)*100 = 300
        assert prot.qtd_protecao_call == 300

    def test_razao_convexidade_ativa_em_protecao(self):
        """Em Proteção, razao_convexidade_call > 1.0."""
        r = _chassi(
            ratio_call=1.25, ratio_put=1.0,
            pnl_com_ratio=1700.0, pnl_base=1386.23,
            sigma_periodo=0.085, preco_ativo=40.64,
            estagio="Proteção",
        )
        strike = {"strike": 48.00, "premio_ask": 0.02, "vol_ask": 500, "vol_bid": 400}
        prot = CalculadoraProtecaoCauda.avaliar(
            r, strikes_call_candidatos=[strike], qtd_acao=1000,
            razao_convexidade_max=1.5,
        )
        assert prot is not None
        assert prot.razao_convexidade_call == 1.5

    def test_razao_convexidade_escolhe_maior_que_cabe_no_orcamento(self):
        """Se razao=2.0 não cabe mas 1.5 cabe, escolhe 1.5."""
        r = _chassi(
            ratio_call=1.25, ratio_put=1.0,
            pnl_com_ratio=1386.30, pnl_base=1386.23,
            sigma_periodo=0.085, preco_ativo=40.64,
            estagio="Proteção",
        )
        # ganho_extra = 0.07, budget = 0.07*0.70 = 0.049
        # strike barato: ask=0.0002
        # razao=1.0 → qtd=200, custo=0.04 <= 0.049 → cabe
        # razao=1.1 → qtd=round((0.25*1.1)*1000/100)*100 = round(2.75)*100 = 300, custo=0.06 > 0.049 → NÃO cabe
        # razao=1.0 é a maior que cabe
        strike_barato = {"strike": 48.00, "premio_ask": 0.0002, "vol_ask": 500, "vol_bid": 400}
        prot = CalculadoraProtecaoCauda.avaliar(
            r, strikes_call_candidatos=[strike_barato], qtd_acao=1000,
            razao_convexidade_max=2.0,
            limite_protecao_pct_protecao=0.70,
        )
        assert prot is not None
        assert prot.razao_convexidade_call == 1.0

    def test_default_razao_convexidade_no_resultado(self):
        """ResultadoProtecaoCauda default tem razao_convexidade = 1.0."""
        p = ResultadoProtecaoCauda(
            id_chassi="test", ativo="X", lado_protegido="nenhum",
            naked_call_frac=0.0, naked_put_gap=0.0,
            strike_protecao_call=None, strike_protecao_put=None,
            premio_ask_call=None, premio_ask_put=None,
            qtd_protecao_call=0, qtd_protecao_put=0,
            custo_protecao_call=0.0, custo_protecao_put=0.0,
            custo_protecao_total=0.0,
            pnl_sem_protecao=0.0, pnl_liquido_pos_protecao=0.0,
            viavel_call=False, viavel_put=False, viavel=False,
        )
        assert p.razao_convexidade_call == 1.0
        assert p.razao_convexidade_put == 1.0


# ═══════════════════════════════════════════════════════════════
# Mudança 3 — seleção de strike por eficiência
# ═══════════════════════════════════════════════════════════════

class TestSelecaoPorEficiencia:
    RESULT = _chassi(
        ratio_call=1.25, ratio_put=1.0,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )
    # s_target_call = 40.64*(1+2*0.085) = 47.5488
    # s_eficiencia_call = 40.64*(1+2*1.5*0.085) = 40.64*(1+0.255) = 50.9952
    # Strikes >= 47.55: K=48, K=52
    # K=48: perda_evitada = max(0, 50.995-48)*200 = 2.995*200 = 599, custo = 0.02*200 = 4, eff=149.75
    # K=52: perda_evitada = max(0, 50.995-52)*200 = 0, eff=0
    # O mais eficiente é K=48

    STRIKES_DOIS = [
        {"strike": 48.00, "premio_ask": 0.02, "vol_ask": 500, "vol_bid": 400},
        {"strike": 52.00, "premio_ask": 0.01, "vol_ask": 500, "vol_bid": 400},
    ]

    def test_escolhe_mais_eficiente_nao_mais_proximo(self):
        """K=48 é o mais eficiente, K=52 é o mais distante do target mas seria mais próximo via min(abs)."""
        prot = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=self.STRIKES_DOIS, qtd_acao=1000,
        )
        assert prot is not None
        assert prot.viavel_call
        assert prot.strike_protecao_call == 48.00

    def test_dois_strikes_onde_mais_proximo_nao_eh_mais_eficiente(self):
        """K=48.00 é mais próximo de s_target=47.55 que K=49.00.
        K=49.00 ask=0.01: perda=max(0, 50.995-49)*200=399, custo=2, eff=199.5
        K=48.00 ask=0.02: perda=max(0, 50.995-48)*200=599, custo=4, eff=149.75
        O mais eficiente (K=49.00) deve ser escolhido mesmo sendo o mais distante do target."""
        strikes = [
            {"strike": 48.00, "premio_ask": 0.02, "vol_ask": 500, "vol_bid": 400},
            {"strike": 49.00, "premio_ask": 0.01, "vol_ask": 500, "vol_bid": 400},
        ]
        prot = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=strikes, qtd_acao=1000,
        )
        assert prot is not None
        assert prot.viavel_call
        # K=49.00 tem eficiencia maior (199.5 vs 149.75) → deve ser escolhido
        assert prot.strike_protecao_call == 49.00


# ═══════════════════════════════════════════════════════════════
# Mudança 3 — filtro de spread
# ═══════════════════════════════════════════════════════════════

class TestFiltroSpread:
    RESULT = _chassi(
        ratio_call=1.25, ratio_put=1.0,
        pnl_com_ratio=1700.0, pnl_base=1386.23,
        sigma_periodo=0.085, preco_ativo=40.64,
    )

    def test_spread_largo_descarta_candidato_liquido(self):
        """Strike com volume suficiente mas spread > 20% é descartado."""
        # ask=0.10, bid=0.05 → spread = (0.10-0.05)/0.10 = 0.50 = 50% > 20%
        strike_spread_largo = {
            "strike": 48.00, "premio_ask": 0.10, "premio_bid": 0.05,
            "vol_ask": 500, "vol_bid": 400,
        }
        prot = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[strike_spread_largo], qtd_acao=1000,
            spread_maximo_pct=0.20,
        )
        assert prot is not None
        assert not prot.viavel_call
        assert prot.strike_protecao_call is None

    def test_spread_aceitavel_aprova(self):
        """Strike com spread dentro do limite é aceito."""
        # ask=0.10, bid=0.09 → spread = 0.01/0.10 = 10% <= 20%
        strike_spread_ok = {
            "strike": 48.00, "premio_ask": 0.10, "premio_bid": 0.09,
            "vol_ask": 500, "vol_bid": 400,
        }
        prot = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[strike_spread_ok], qtd_acao=1000,
            spread_maximo_pct=0.20,
        )
        assert prot is not None
        assert prot.viavel_call

    def test_sem_premio_bid_ignora_filtro_spread(self):
        """Se premio_bid não existe no dict, spread filter não barra (compatibilidade)."""
        strike_sem_bid = {
            "strike": 48.00, "premio_ask": 0.02,
            "vol_ask": 500, "vol_bid": 400,
        }
        prot = CalculadoraProtecaoCauda.avaliar(
            self.RESULT, strikes_call_candidatos=[strike_sem_bid], qtd_acao=1000,
            spread_maximo_pct=0.01,
        )
        assert prot is not None
        assert prot.viavel_call
