"""Equivalência OO (escalar) × VEC (vetorizado) — Fase 4.

Compara campo-a-campo as saídas de:
  - MonitorVendidasUseCase          x VetorMonitorVendidasUseCase          (BOX/SBTH vendido)
  - MonitorVendaCobertaUseCase      x VetorMonitorVendaCobertaUseCase      (TAXA / Venda Coberta)
  - varrer_comprada                                                 (TAXA_COMPRADA)

Cenário sintético determinístico (~160 chaves) cobrindo perfis: BOX-only, SBTH-only,
ambos, nenhum; viável/não-viável; leilão; boca ausente/zero/negativa; strike inválido;
inst ausente/vencido; DTE fora da janela; sem chave composta; passthrough ts/onda.
"""

import math
from dataclasses import fields
from datetime import date, timedelta

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.entities.taxa_aluguel import TaxaAluguel
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    TaxaAluguelRepository,
)
from src.application.use_cases.monitor_vendidas import MonitorVendidasUseCase
from src.application.use_cases.monitor_venda_coberta import MonitorVendaCobertaUseCase
from src.application.use_cases.experimental.vetor_monitor_vendidas import VetorMonitorVendidasUseCase
from src.application.use_cases.experimental.vetor_monitor_venda_coberta import VetorMonitorVendaCobertaUseCase

import pytest


PRECOS = {
    "PETR4": 30.0, "VALE3": 65.0, "ITUB4": 32.0, "BBDC4": 14.0, "ABEV3": 13.0,
    "WEGE3": 42.0, "MGLU3": 11.0, "GGBR4": 20.0, "RENT3": 52.0, "BOVA11": 125.0,
}


def _r(v):
    return float(round(v, 2))


def montar_cenario():
    """Retorna (instrumentos, dados_mercado) — determinístico."""
    hoje = date.today()
    insts: list[InstrumentoOpcional] = []
    mercado: dict[str, dict] = {}
    contador: dict[str, int] = {}

    def regista(ativo, dte, entry, salvar=True):
        cod_put = f"{ativo}T{contador.get(ativo, 0)}"
        cod_call = f"{ativo}C{contador.get(ativo, 0)}"
        contador[ativo] = contador.get(ativo, 0) + 1
        mercado[f"{ativo}|{cod_put}"] = entry
        if salvar:
            insts.append(InstrumentoOpcional(
                ativo=ativo, cod_put=cod_put, cod_call=cod_call,
                vencimento=hoje + timedelta(days=dte), tipo_opcao=TipoOpcao.AMERICANA,
            ))

    for ativo, P in PRECOS.items():
        # ---- vendidas: BOX-only (SBTH falha: strike <= bid_ativo*1.2)
        regista(ativo, 20, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.05),
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 5000.0, "voc_call_boca": 5000.0,
            "qul_put": 1234.6, "qul_call": 555.5, "onda": 1,
        })
        # inviável (prêmio marginal)
        regista(ativo, 20, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.004),
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.035), "of_venda_put": _r(P * 0.05),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 5000.0, "voc_call_boca": 5000.0,
        })
        # leilão
        regista(ativo, 31, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.05),
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 5000.0, "voc_call_boca": 5000.0, "em_leilao": True,
        })
        # boca=0 sem fallback → liq falha (não-viável, cond mantida)
        regista(ativo, 45, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.02),
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.08), "of_venda_put": _r(P * 0.10),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 0.0, "voc_call_boca": 0.0,
        })
        # boca negativa (truthy → usa -5)
        regista(ativo, 10, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.06),
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": -5.0, "voc_call_boca": -5.0,
        })
        # SBTH-only (receb_box <= strike)
        regista(ativo, 31, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.20),
            "of_compra_ativo": _r(P * 0.80), "of_venda_ativo": _r(P * 0.82),
            "of_compra_put": _r(P * 0.45), "of_venda_put": _r(P * 0.50),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.20),
            "vov_put_boca": 8000.0, "voc_call_boca": 8000.0,
            "qul_put": 800.0, "qul_call": 900.0,
            "ts_ativo_ask": 1234567890.0, "ts_ativo_bid": 1234567889.0,
        })
        # BOX + SBTH (ambos)
        regista(ativo, 10, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.20),
            "of_compra_ativo": _r(P * 0.80), "of_venda_ativo": _r(P * 0.82),
            "of_compra_put": _r(P * 0.45), "of_venda_put": _r(P * 0.50),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 8000.0, "voc_call_boca": 8000.0,
        })
        # condição falsa (strike distante)
        regista(ativo, 20, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 2.0),
            "of_compra_ativo": _r(P * 0.80), "of_venda_ativo": _r(P * 0.82),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.05),
            "vov_put_boca": 5000.0, "voc_call_boca": 5000.0,
        })
        # strike invalidado na fase de quebra (zero / negativo)
        regista(ativo, 20, {
            "preco_ativo": _r(P), "strike_rtd": 0.0,
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
        })
        regista(ativo, 20, {
            "preco_ativo": _r(P), "strike_rtd": -3.0,
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
        })
        # DTE fora da janela do perf (5 < perf_dias_minimos)
        regista(ativo, 5, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.05),
            "of_compra_ativo": _r(P * 0.99), "of_venda_ativo": _r(P * 1.01),
            "of_compra_put": _r(P * 0.10), "of_venda_put": _r(P * 0.12),
            "of_compra_call": _r(P * 0.02), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 5000.0, "voc_call_boca": 5000.0,
        })

        # ---- coberta (varrer): notação só precisa de of_compra_ativo/of_venda_call/voc_call
        regista(ativo, 20, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.90),
            "of_compra_ativo": _r(P * 0.95), "of_venda_ativo": _r(P * 0.97),
            "of_compra_call": _r(P * 0.50), "of_venda_call": _r(P * 0.02),
            "vov_put_boca": 0.0, "voc_call_boca": 4000.0, "qul_call": 7.0,
            "onda": 3,
        })
        # falha: strike >= preco_ativo
        regista(ativo, 11, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 1.02),
            "of_compra_ativo": _r(P * 0.95), "of_venda_ativo": _r(P * 0.97),
            "of_compra_call": _r(P * 0.50), "of_venda_call": _r(P * 0.02),
            "voc_call_boca": 4000.0,
        })
        # falha: recebimento <= strike
        regista(ativo, 11, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.90),
            "of_compra_ativo": _r(P * 0.85), "of_venda_ativo": _r(P * 0.87),
            "of_compra_call": _r(P * 0.50), "of_venda_call": _r(P * 0.05),
            "voc_call_boca": 4000.0,
        })
        # leilão + baixa liquidez (voc < lote 100)
        regista(ativo, 30, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.60),
            "of_compra_ativo": _r(P * 0.65), "of_venda_ativo": _r(P * 0.67),
            "of_compra_call": _r(P * 0.40), "of_venda_call": _r(P * 0.02),
            "voc_call_boca": 50.0, "em_leilao": True,
        })
        # DTE 31 > 30 → fora da janela da coberta
        regista(ativo, 31, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.90),
            "of_compra_ativo": _r(P * 0.95), "of_venda_ativo": _r(P * 0.97),
            "of_compra_call": _r(P * 0.50), "of_venda_call": _r(P * 0.02),
            "voc_call_boca": 4000.0,
        })

        # ---- comprada: strike <= 0.2*preco, custo_montagem=ask_ativo-bid_call
        regista(ativo, 9, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.10),
            "of_compra_ativo": _r(P * 0.98), "of_venda_ativo": _r(P * 1.001),
            "of_compra_call": _r(P * 0.99), "of_venda_call": _r(P * 1.01),
            "voc_call_boca": 500.0, "qul_call": 3.0, "ts_scan": 1234567000.0,
        })
        # falha: strike > 0.2*preco
        regista(ativo, 7, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.30),
            "of_compra_ativo": _r(P * 0.98), "of_venda_ativo": _r(P * 1.001),
            "of_compra_call": _r(P * 0.99), "of_venda_call": _r(P * 1.01),
            "voc_call_boca": 500.0,
        })
        # falha: custo_montagem <= 0 (bid_call >= ask_ativo)
        regista(ativo, 7, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.10),
            "of_compra_ativo": _r(P * 0.98), "of_venda_ativo": _r(P * 1.001),
            "of_compra_call": _r(P * 1.05), "of_venda_call": _r(P * 1.08),
            "voc_call_boca": 500.0,
        })
        # falha: strike <= custo_montagem
        regista(ativo, 5, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.005),
            "of_compra_ativo": _r(P * 0.98), "of_venda_ativo": _r(P * 1.001),
            "of_compra_call": _r(P * 0.99), "of_venda_call": _r(P * 1.01),
            "voc_call_boca": 500.0,
        })
        # leilão + DTE 11 > 10 → comprada fora da janela
        regista(ativo, 11, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.10),
            "of_compra_ativo": _r(P * 0.98), "of_venda_ativo": _r(P * 1.001),
            "of_compra_call": _r(P * 0.99), "of_venda_call": _r(P * 1.01),
            "voc_call_boca": 500.0, "em_leilao": True,
        })
        # DTE 5 na borda (permitida na comprada)
        regista(ativo, 5, {
            "preco_ativo": _r(P), "strike_rtd": _r(P * 0.12),
            "of_compra_ativo": _r(P * 0.98), "of_venda_ativo": _r(P * 1.001),
            "of_compra_call": _r(P * 0.99), "of_venda_call": _r(P * 1.01),
            "voc_call_boca": 300.0,
        })

    # chaves sem suporte: sem "|", inst ausente, inst vencido, chaves_parsed vazia
    mercado["BOVA11"] = {"preco_ativo": 125.0, "strike_rtd": 120.0,
                         "of_compra_ativo": 120.0, "of_venda_ativo": 126.0}
    mercado["ZZZZ|SEMINST"] = {"preco_ativo": 10.0, "strike_rtd": 10.0,
                               "of_compra_ativo": 9.0, "of_venda_ativo": 11.0}
    insts.append(InstrumentoOpcional(
        ativo="VENCIDO", cod_put="VENCIDOT0", cod_call="VENCIDOC0",
        vencimento=hoje - timedelta(days=1), tipo_opcao=TipoOpcao.AMERICANA))
    mercado["VENCIDO|VENCIDOT0"] = {"preco_ativo": 5.0, "strike_rtd": 5.0,
                                    "of_compra_ativo": 5.0, "of_venda_ativo": 5.0}
    # chaves_parsed (lista ordenada) contém chave sem "|" — vetor deve segui-la igual à OO
    mercado["SEM|"] = {"preco_ativo": 1.0, "strike_rtd": 1.0,
                       "of_compra_ativo": 1.0, "of_venda_ativo": 1.0}

    return insts, mercado


def _agrupar(dto):
    return (dto.ativo, dto.strike, dto.vencimento, dto.cod_put, dto.cod_call, dto.classificacao)


def _comparar_dto(a, b):
    """Compara todos os campos do DTO; detectado_em com tolerância de 5s."""
    assert type(a) is type(b)
    for camp in fields(a):
        va, vb = getattr(a, camp.name), getattr(b, camp.name)
        if camp.name == "detectado_em":
            assert va is not None and vb is not None
            assert abs((va - vb).total_seconds()) <= 5.0, (camp.name, va, vb)
            continue
        if isinstance(va, float) or isinstance(vb, float):
            assert math.isclose(float(va), float(vb), rel_tol=1e-9, abs_tol=1e-9), \
                (camp.name, va, vb)
        else:
            assert va == vb, (camp.name, va, vb)


def _comparar_listas(oos, vets):
    assert len(oos) == len(vets), (len(oos), len(vets))
    for oo, vet in zip(oos, vets):
        assert _agrupar(oo) == _agrupar(vet), (_agrupar(oo), _agrupar(vet))
        _comparar_dto(oo, vet)


@pytest.fixture
def cenario(db_path):
    insts, mercado = montar_cenario()
    conn = init_db(db_path)
    conn.close()
    ParametroRepository(db_path).seed_defaults()
    repo = InstrumentoRepository(db_path)
    repo.save_batch(insts)
    taxa_repo = TaxaAluguelRepository(db_path)
    taxa_repo.save(TaxaAluguel(
        ativo="PETR4", data=date.today(), taxa_atual=0.5, taxa_7d=0.5, taxa_28d=0.6))
    taxa_repo.save(TaxaAluguel(
        ativo="VALE3", data=date.today(), taxa_atual=0.0, taxa_7d=0.0, taxa_28d=0.0))
    inst_map = repo.get_all_mapped()
    return mercado, inst_map


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_eq.db"


class TestEquivalenciaBoxSbthVendido:
    @pytest.mark.parametrize("chaves_parsed", [None])
    def test_equivalencia_vendidas(self, cenario, db_path, chaves_parsed):
        mercado, inst_map = cenario
        oo = MonitorVendidasUseCase(db_path).varrer(
            mercado, inst_map=inst_map, chaves_parsed=chaves_parsed)
        vet = VetorMonitorVendidasUseCase(db_path).varrer(
            mercado, inst_map=inst_map, chaves_parsed=chaves_parsed)
        _comparar_listas(oo, vet)
        assert len(oo) > 0  # cenario de fato gera oportunidades
        assert any(r.classificacao == "BOX_VENDIDO" for r in oo)
        assert any(r.classificacao == "SBTH_VENDIDA" for r in oo)

    def test_equivalencia_vendidas_chaves_parsed(self, cenario, db_path):
        mercado, inst_map = cenario
        chaves_parsed = list(mercado.keys())
        chaves_parsed.reverse()  # ordem invertida do snapshot default
        oo = MonitorVendidasUseCase(db_path).varrer(
            mercado, inst_map=inst_map, chaves=chaves_parsed, chaves_parsed=chaves_parsed)
        vet = VetorMonitorVendidasUseCase(db_path).varrer(
            mercado, inst_map=inst_map, chaves=chaves_parsed, chaves_parsed=chaves_parsed)
        _comparar_listas(oo, vet)

    def test_pipeline_tracker_equivalencia(self, cenario, db_path):
        mercado, inst_map = cenario
        tracker_oo = PipelineTracker()
        tracker_vet = PipelineTracker()
        oo = MonitorVendidasUseCase(db_path).varrer(
            mercado, inst_map=inst_map, pipeline_tracker=tracker_oo)
        vet = VetorMonitorVendidasUseCase(db_path).varrer(
            mercado, inst_map=inst_map, pipeline_tracker=tracker_vet)
        assert tracker_oo.nome_estrategia == tracker_vet.nome_estrategia
        assert len(tracker_oo.stages) == len(tracker_vet.stages)
        for s_oo, s_vet in zip(tracker_oo.stages, tracker_vet.stages):
            assert (s_oo.nome, s_oo.entrada, s_oo.saida, s_oo.rejeitados, s_oo.motivo) == \
                   (s_vet.nome, s_vet.entrada, s_vet.saida, s_vet.rejeitados, s_vet.motivo)
        assert len(oo) == len(vet)


class TestEquivalenciaVendaCoberta:
    def test_equivalencia_varrer(self, cenario, db_path):
        mercado, inst_map = cenario
        oo = MonitorVendaCobertaUseCase(db_path).varrer(mercado, inst_map=inst_map)
        vet = VetorMonitorVendaCobertaUseCase(db_path).varrer(mercado, inst_map=inst_map)
        _comparar_listas(oo, vet)
        assert all(r.classificacao == "VENDA_COBERTA" for r in oo + vet)

    def test_equivalencia_varrer_comprada(self, cenario, db_path):
        mercado, inst_map = cenario
        oo = MonitorVendaCobertaUseCase(db_path).varrer_comprada(mercado, inst_map=inst_map)
        vet = VetorMonitorVendaCobertaUseCase(db_path).varrer_comprada(mercado, inst_map=inst_map)
        _comparar_listas(oo, vet)
        assert all(r.classificacao == "TAXA_COMPRADA" for r in oo + vet)

    def test_pipeline_tracker_equivalencia(self, cenario, db_path):
        mercado, inst_map = cenario
        tracker_oo = PipelineTracker()
        tracker_vet = PipelineTracker()
        oo = MonitorVendaCobertaUseCase(db_path).varrer(
            mercado, inst_map=inst_map, pipeline_tracker=tracker_oo)
        vet = VetorMonitorVendaCobertaUseCase(db_path).varrer(
            mercado, inst_map=inst_map, pipeline_tracker=tracker_vet)
        assert tracker_oo.nome_estrategia == tracker_vet.nome_estrategia
        assert len(tracker_oo.stages) == len(tracker_vet.stages)
        for s_oo, s_vet in zip(tracker_oo.stages, tracker_vet.stages):
            assert (s_oo.nome, s_oo.entrada, s_oo.saida, s_oo.rejeitados, s_oo.motivo) == \
                   (s_vet.nome, s_vet.entrada, s_vet.saida, s_vet.rejeitados, s_vet.motivo)

    def test_agregado_worker_coberta(self, cenario, db_path):
        """Emula a agregação do worker (varrer + comprada + sort) nos dois lados."""
        mercado, inst_map = cenario
        oo_uc = MonitorVendaCobertaUseCase(db_path)
        vet_uc = VetorMonitorVendaCobertaUseCase(db_path)
        chave_sort = lambda o: (not o.viavel, -o.pct_cdi)
        oo = sorted(oo_uc.varrer(mercado, inst_map=inst_map) +
                    oo_uc.varrer_comprada(mercado, inst_map=inst_map), key=chave_sort)
        vet = sorted(vet_uc.varrer(mercado, inst_map=inst_map) +
                     vet_uc.varrer_comprada(mercado, inst_map=inst_map), key=chave_sort)
        _comparar_listas(oo, vet)


class TestCoberturaDeFalhasNaEquivalencia:
    def test_isolamento_ordem(self, cenario, db_path):
        """Rodando OO → VEC → OO, a segunda passada OO deve ser idêntica à primeira."""
        mercado, inst_map = cenario
        oo_uc = MonitorVendidasUseCase(db_path)
        a1 = oo_uc.varrer(mercado, inst_map=inst_map)
        VetorMonitorVendidasUseCase(db_path).varrer(mercado, inst_map=inst_map)
        a2 = oo_uc.varrer(mercado, inst_map=inst_map)
        assert len(a1) == len(a2)
        for x, y in zip(a1, a2):
            assert _agrupar(x) == _agrupar(y)
            assert x.pct_cdi == y.pct_cdi
            assert x.viavel == y.viavel

    def test_ordem_viaveis_primeiro_e_boca(self, cenario, db_path):
        """Ordenação (não-viavel por último) e fallback de boca: valor > 1 se houver viável."""
        mercado, inst_map = cenario
        oo = MonitorVendidasUseCase(db_path).varrer(mercado, inst_map=inst_map)
        vet = VetorMonitorVendidasUseCase(db_path).varrer(mercado, inst_map=inst_map)
        if any(r.viavel for r in oo):
            assert next((r for r in oo if r.viavel), None) is oo[0]
        _comparar_listas(oo, vet)

    def test_boca_negativa_nao_estoura(self, cenario, db_path):
        """vov/voc boca negativa → liq negativo, viavel=False, sem exceção."""
        mercado, inst_map = cenario
        oo = MonitorVendidasUseCase(db_path).varrer(mercado, inst_map=inst_map)
        vet = VetorMonitorVendidasUseCase(db_path).varrer(mercado, inst_map=inst_map)
        neg = [r for r in oo if r.liq_put_x_lote < 0]
        assert neg  # boca negativa e boca=0 geram liq negativo
        for r in neg:
            assert r.viavel is False
        _comparar_listas(oo, vet)