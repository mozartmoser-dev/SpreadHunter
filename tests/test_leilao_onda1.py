"""Leilao por perna na Onda 1 + label per-perna no DTO.

A Onda 1 de ``MercadoDataProvider`` hardcoda ``em_leilao=False`` (2 pontos:
criacao da entry e post-loop), mesmo lendo ``status_put/status_call/status_ativo``.
A Onda 2 ja deriva ``em_leilao`` dos 3 status. Este arquivo prova o furo na Onda 1
e cobre o novo ``OportunidadeMonitor.leilao_label`` (Leilao Ativo/PUT/CALL per-perna).

Fonte de status (OpenFast ST) confirmada entregue via sonda em 19/08/2026.
"""

import time
from datetime import date, timedelta

import pytest

from src.application.dtos.dtos import OportunidadeMonitor
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider


class FakePush:
    """Emula OpenFast: push change-driven; refresh() devolve {cod|campo: valor}."""

    disponivel = True
    suporta_push = True
    suporta_cab_skip = False
    is_stale_campo = None
    stale_campo_s = 15.0

    def __init__(self):
        self._cache = {}
        self._status = {}
        self._mudancas = {}

    def set_campo(self, codigo, campo, valor):
        self._cache[(codigo, campo)] = valor

    def set_mudancas(self, mudancas):
        self._mudancas = dict(mudancas)

    def set_status(self, codigo, status):
        self._status[codigo] = status

    def registrar_topico(self, codigo, campo):
        return 0

    def registrar_lista(self, registros):
        return len(registros)

    def registrar_status(self, codigo):
        return 0

    def ler_campo_cache(self, codigo, campo, allow_stale=False):
        return self._cache.get((codigo, campo))

    def ler_campos(self, codigo, *campos, allow_stale=False):
        return {c: self._cache.get((codigo, c)) for c in campos}

    def ler_status_cache(self, codigo):
        return self._status.get(codigo, "aberto")

    def forcar_leitura(self, codigo, campo):
        return self._cache.get((codigo, campo))

    def refresh(self, timeout_ms=0):
        return self._mudancas

    def desconectar(self):
        self._cache.clear()

    def reconectar(self):
        return True

    def invalidar_cache(self, codigo, campo):
        self._cache.pop((codigo, campo), None)

    def get_ts_campo(self, codigo, campo):
        return time.time()


def _set_book_completo(source, inst, key):
    ativo, cod_put = key.split("|", 1)
    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    for cod, ask, bid in [(cod_put, 4.40, 4.30), (inst.cod_call, 0.05, 0.04)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    source.set_campo(cod_put, FieldName.VOL_ASK, 5000.0)
    source.set_campo(cod_put, FieldName.QTD_LAST, 3000.0)
    source.set_campo(inst.cod_call, FieldName.VOL_BID, 5000.0)
    source.set_campo(inst.cod_call, FieldName.QTD_LAST, 3000.0)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, 150.0)
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, 150.0)
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    source.set_status(ativo, "aberto")
    source.set_status(cod_put, "aberto")
    source.set_status(inst.cod_call, "aberto")


def _make_db(tmp_path):
    db_path = tmp_path / "leilao_onda1.db"
    conn = init_db(db_path)
    conn.close()
    ParametroRepository(db_path).seed_defaults()
    repo = InstrumentoRepository(db_path)
    repo.invalidate_cache()
    repo.save(InstrumentoOpcional(
        ativo="PETR4",
        cod_put="PETRG180",
        cod_call="PETRH180",
        vencimento=date.today() + timedelta(days=20),
        tipo_opcao=TipoOpcao.AMERICANA,
        strike=18.00,
    ))
    return db_path


def _setup(db_path, source, key, onda2=False):
    provider = MercadoDataProvider(db_path, source)
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    ativo, cod_put = key.split("|", 1)
    provider._ativos_registrados = {ativo}
    provider._chaves_registradas = {key}
    provider._chaves_com_book = {key}
    if onda2:
        provider._chaves_detalhes_completos = {key}
    return provider


def _opp(status_put="aberto", status_call="aberto", status_ativo="aberto"):
    return OportunidadeMonitor(
        instrumento_id=1,
        ativo="PETR4",
        strike=18.0,
        vencimento=date.today() + timedelta(days=20),
        dias=20,
        cod_put="PETRG180",
        cod_call="PETRH180",
        tipo_opcao="A",
        status_put=status_put,
        status_call=status_call,
        status_ativo=status_ativo,
    )


@pytest.fixture
def env_onda1(tmp_path):
    db_path = _make_db(tmp_path)
    source = FakePush()
    key = "PETR4|PETRG180"
    provider = _setup(db_path, source, key, onda2=False)
    return db_path, source, provider, key


@pytest.fixture
def env_onda2(tmp_path):
    db_path = _make_db(tmp_path)
    source = FakePush()
    key = "PETR4|PETRG180"
    provider = _setup(db_path, source, key, onda2=True)
    return db_path, source, provider, key


class TestOnda1Leilao:

    def test_put_leilao_reflete_em_leilao(self, env_onda1):
        """Onda 1 fresh: PUT em leilao -> em_leilao True (hoje hardcoded False)."""
        db_path, source, provider, key = env_onda1
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_status(cod_put, "leilão")
        source.set_mudancas({"PETR4|ASK": 1.0})  # força caminho FRESH Onda 1
        dados = provider.capturar_dados_mercado()

        e = dados[key]
        assert e["status_put"] == "leilão"
        assert e["status_call"] == "aberto"
        assert e["status_ativo"] == "aberto"
        assert e["em_leilao"] is True

    def test_ativo_leilao_reflete_em_leilao(self, env_onda1):
        """Onda 1 fresh: ATIVO em leilao -> em_leilao True."""
        db_path, source, provider, key = env_onda1
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_status(ativo, "leilão")
        source.set_mudancas({"PETR4|ASK": 1.0})
        dados = provider.capturar_dados_mercado()

        assert dados[key]["em_leilao"] is True

    def test_post_loop_serve_put_leilao(self, env_onda1):
        """Post-loop: entry cacheada com PUT em leilao continua em_leilao True."""
        db_path, source, provider, key = env_onda1
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_status(cod_put, "leilão")
        source.set_mudancas({"PETR4|ASK": 1.0})
        provider.capturar_dados_mercado()  # ciclo A (fresh, status leilão)

        # Ciclo B: nada de PETR4 mudou -> Onda 1 skip -> post-loop serve o cache
        source.set_mudancas({"IBOV|ULT": 1.0})
        dados = provider.capturar_dados_mercado()

        e = dados[key]
        assert e["em_leilao"] is True, "post-loop nao pode limpar o leilao"

    def test_tudo_aberto_em_leilao_false(self, env_onda1):
        """Guard: tudo 'aberto' -> em_leilao False (sem falso positivo)."""
        db_path, source, provider, key = env_onda1
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_mudancas({"PETR4|ASK": 1.0})
        dados = provider.capturar_dados_mercado()

        e = dados[key]
        assert e["em_leilao"] is False
        assert e["status_put"] == "aberto"
        assert e["status_call"] == "aberto"
        assert e["status_ativo"] == "aberto"


class TestOnda2Leilao:

    def test_put_leilao_reflete(self, env_onda2):
        """Guard: Onda 2 ja deriva em_leilao dos status (regressao)."""
        db_path, source, provider, key = env_onda2
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_status(cod_put, "leilão")
        source.set_mudancas({"PETR4|ASK": 1.0})
        dados = provider.capturar_dados_mercado()

        assert dados[key]["em_leilao"] is True


class TestUsecaseForwarding:

    def test_varrer_repassa_status_ao_dto(self, env_onda1):
        """Elo 7: o varrer repassa status per-perna da entry ao DTO."""
        db_path, source, provider, key = env_onda1
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        dados = {
            key: {
                "preco_ativo": 18.0, "strike_rtd": 18.0,
                "of_compra_ativo": 17.9, "of_venda_ativo": 18.1,
                "of_compra_put": 2.0, "of_venda_put": 2.1,
                "of_compra_call": 2.5, "of_venda_call": 2.6,
                "premio_put": 2.0, "premio_call": 2.5,
                "vov_put_boca": 2000.0, "voc_call_boca": 2000.0,
                "em_leilao": True,
                "status_put": "leilão",
                "status_call": "aberto",
                "status_ativo": "aberto",
            }
        }

        uc = MonitorOportunidadesUseCase(db_path)
        opps = uc.varrer(
            dados,
            inst_map=provider._get_inst_map(),
            chaves=[key],
            chaves_parsed=[tuple(key.split("|"))],
        )

        assert opps, "deve produzir ao menos uma oportunidade"
        o = opps[0]
        assert o.em_leilao is True
        assert o.leilao_label == "Leilão PUT"


class TestLeilaoLabel:

    def test_label_vazio(self):
        assert _opp().leilao_label == ""

    def test_label_put(self):
        assert _opp(status_put="Leilão").leilao_label == "Leilão PUT"

    def test_label_call(self):
        assert _opp(status_call="Leilão").leilao_label == "Leilão CALL"

    def test_label_ativo(self):
        assert _opp(status_ativo="Leilão").leilao_label == "Leilão Ativo"

    def test_label_put_call(self):
        assert _opp(status_put="Leilão", status_call="Leilão").leilao_label == "Leilão PUT + CALL"

    def test_label_todas(self):
        assert _opp(status_put="Leilão", status_call="Leilão", status_ativo="Leilão").leilao_label == "Leilão Ativo + PUT + CALL"

    def test_label_fechado(self):
        assert _opp(status_put="Fechado").leilao_label == "PUT: Fechado"