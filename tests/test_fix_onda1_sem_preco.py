"""Regressao do follow-up: Onda 1 com preco do ativo ausente nao mantem entrada antiga.

Cobria o caminho da Onda 1 em ``MercadoDataProvider`` (linhas ~867-868): quando
``preco_ativo`` (ASK do ativo) esta ausente/<=0, o ciclo dava ``continue`` sem
invalidar a entry antiga de ``_dados_cache`` — o post-loop devolvia o snapshot
ANTIGO para ``dados_mercado``.

Correcao: no skip por preco ausente da Onda 1, a entry e invalidada
(``stale=True`` + ``pop``), espelhando exatamente o padrao validado no fix da
Onda 2 (``_sem_ativo_skip``). Quando o preco volta, a entrada e recriada.

Requisitos cobertos:
A) entrada antiga nao sobrevive quando o preco fica ausente;
B) post-loop nao devolve a entrada antiga;
C) quando o preco volta, a entrada e recriada;
D) caminho normal da Onda 1 permanece igual;
E) Colar/Collar Calendario nao recebem snapshot antigo (key ausente de dados_mercado);
F) caminho push (OpenFast) da Onda 1 sem regressao.
"""

import time
from datetime import date, timedelta

import pytest

from src.application.use_cases.monitor_colares import MonitorColaresUseCase
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.infrastructure.persistence.database import get_connection, init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider


class FakeRTD:
    """Emula Profit RTD: polling, sem push, sem is_stale_campo."""

    disponivel = True
    suporta_push = False
    suporta_cab_skip = True
    is_stale_campo = None
    stale_campo_s = 15.0

    def __init__(self):
        self._cache = {}
        self._status = {}

    def set_campo(self, codigo, campo, valor):
        self._cache[(codigo, campo)] = valor

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
        return {}

    def desconectar(self):
        self._cache.clear()

    def reconectar(self):
        return True

    def invalidar_cache(self, codigo, campo):
        self._cache.pop((codigo, campo), None)

    def get_ts_campo(self, codigo, campo):
        return time.time()


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


def _set_book_onda1(source, inst, key, preco=14.00, bid_ativo=13.95,
                    put_ask=4.40, put_bid=4.30, call_bid=0.04, call_ask=0.05):
    ativo, cod_put = key.split("|", 1)
    source.set_campo(ativo, FieldName.ASK, preco)
    source.set_campo(ativo, FieldName.BID, bid_ativo)
    source.set_campo(cod_put, FieldName.ASK, put_ask)
    source.set_campo(cod_put, FieldName.BID, put_bid)
    source.set_campo(inst.cod_call, FieldName.BID, call_bid)
    source.set_campo(inst.cod_call, FieldName.ASK, call_ask)
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    source.set_status(ativo, "aberto")
    source.set_status(cod_put, "aberto")
    source.set_status(inst.cod_call, "aberto")


def _expira_preco_ativo(provider, ativo):
    provider._precos_ativo_cache.pop(ativo, None)
    provider._precos_ativo_cache_ts.pop(ativo, None)


@pytest.fixture
def env_rtd(tmp_path):
    """Profit RTD, chave APENAS na Onda 1 (nao promovida)."""
    db_path = tmp_path / "fix_onda1_sem_preco.db"
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
    ))
    source = FakeRTD()
    provider = MercadoDataProvider(db_path, source)
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    provider._ativos_registrados = {"PETR4"}
    key = "PETR4|PETRG180"
    provider._chaves_registradas = {key}
    provider._chaves_com_book = {key}
    return db_path, source, provider, key


@pytest.fixture
def env_push(tmp_path):
    """OpenFast, chave APENAS na Onda 1; strike vem do banco."""
    db_path = tmp_path / "fix_onda1_sem_preco_push.db"
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
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE instrumentos_base SET strike = ? WHERE ativo = ? AND cod_put = ?",
        (18.00, "PETR4", "PETRG180"),
    )
    conn.commit()
    conn.close()
    source = FakePush()
    provider = MercadoDataProvider(db_path, source)
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    provider._ativos_registrados = {"PETR4"}
    key = "PETR4|PETRG180"
    provider._chaves_registradas = {key}
    provider._chaves_com_book = {key}
    return db_path, source, provider, key


class TestOnda1SemPreco:

    def test_a_entrada_antiga_nao_sobrevive_quando_preco_ausente(self, env_rtd):
        """(A) preco ausente na Onda 1 -> skip invalida a entry do cache."""
        db_path, source, provider, key = env_rtd
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_onda1(source, inst, key)
        dados_a = provider.capturar_dados_mercado()
        assert key in dados_a
        assert dados_a[key].get("onda") == 1
        assert key in provider._dados_cache

        # Ciclo B: ASK do ativo ausente + preco de frescor expirado
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        dados_b = provider.capturar_dados_mercado()

        assert key not in dados_b, "entrada antiga nao pode sobreviver sem revalidacao"
        assert key not in provider._dados_cache, "entry deve ser invalidada do cache"

    def test_b_post_loop_nao_devolve_entrada_antiga(self, env_rtd):
        """(B) o post-loop nao devolve a entry antiga (chave continua registrada)."""
        db_path, source, provider, key = env_rtd
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_onda1(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        dados_b = provider.capturar_dados_mercado()

        assert key not in dados_b, "post-loop nao pode devolver a entry antiga"
        assert key in provider._chaves_com_book, "chave continua registrada (so o dado invalida)"

    def test_c_preco_volta_recria_entry(self, env_rtd):
        """(C) quando o preco volta, a Onda 1 recria a entry normalmente."""
        db_path, source, provider, key = env_rtd
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_onda1(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        # Ciclo B: preco ausente -> skip (entry invalidada)
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        dados_b = provider.capturar_dados_mercado()
        assert key not in dados_b
        assert key not in provider._dados_cache

        # Ciclo C: preco volta (mercado novo) -> entry recriada
        _set_book_onda1(source, inst, key, preco=13.65, bid_ativo=13.60)
        dados_c = provider.capturar_dados_mercado()

        e = dados_c[key]
        assert e["preco_ativo"] == 13.65
        assert e["of_compra_ativo"] == 13.60
        assert e["of_venda_ativo"] == 13.65
        assert e.get("stale") is False
        assert e.get("onda") == 1
        assert key in provider._dados_cache

    def test_d_caminho_normal_onda1_inalterado(self, env_rtd):
        """(D) preco presente -> Onda 1 segue escrevendo/atualizando em cada ciclo."""
        db_path, source, provider, key = env_rtd
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_onda1(source, inst, key)
        dados_a = provider.capturar_dados_mercado()
        e_a = dados_a[key]
        assert e_a["preco_ativo"] == 14.00
        assert e_a["of_compra_ativo"] == 13.95
        assert e_a["of_venda_put"] == 4.40
        assert e_a["of_compra_call"] == 0.04

        _set_book_onda1(source, inst, key, preco=13.65, bid_ativo=13.60,
                        put_ask=4.45, put_bid=4.35, call_bid=0.03, call_ask=0.04)
        dados_b = provider.capturar_dados_mercado()
        e_b = dados_b[key]
        assert e_b["preco_ativo"] == 13.65
        assert e_b["of_compra_ativo"] == 13.60
        assert e_b["of_venda_put"] == 4.45
        assert e_b["of_compra_call"] == 0.03
        assert e_b.get("stale") is False
        assert key in provider._dados_cache

    def test_e_colar_nao_recebe_snapshot_antigo(self, env_rtd):
        """(E) Colar/Collar Calendario iteram dados_mercado -> key ausente = sem snapshot."""
        db_path, source, provider, key = env_rtd
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_onda1(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        dados_b = provider.capturar_dados_mercado()

        # Garantia central: o snapshot antigo NAO existe em dados_mercado.
        assert key not in dados_b, "consumidores nao podem receber snapshot antigo"

        # End-to-end: o use case de colar, alimentado com esses dados, nao ve PETR4.
        uc = MonitorColaresUseCase(db_path)
        resultados = uc.varrer(None, dados_mercado=dados_b)
        assert not any(getattr(r, "ativo", None) == "PETR4" for r in resultados), (
            "Colar nao pode surfacar operacao com snapshot antigo"
        )

    def test_f_push_onda1_preco_ausente_nao_sobrevive(self, env_push):
        """(F) OpenFast (push) Onda 1: mesmo comportamento (caminho compartilhado)."""
        db_path, source, provider, key = env_push
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_onda1(source, inst, key)
        source.set_mudancas({"PETR4|ULT": 1.0})
        dados_a = provider.capturar_dados_mercado()
        assert key in dados_a
        assert key in provider._dados_cache

        # Ciclo B: pernas sujas mas ASK do ativo ausente -> skip -> entry invalidada
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        dados_b = provider.capturar_dados_mercado()

        assert key not in dados_b
        assert key not in provider._dados_cache

        # Ciclo C: preco volta -> recriada (push normal sem regressao)
        _set_book_onda1(source, inst, key, preco=13.65, bid_ativo=13.60)
        dados_c = provider.capturar_dados_mercado()
        assert dados_c[key]["preco_ativo"] == 13.65
        assert dados_c[key].get("stale") is False
        assert key in provider._dados_cache