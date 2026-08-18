"""Regressao do `_sem_ativo_skip` + post-loop (entrada antiga da Onda 2).

Cobria o caminho FRESH da Onda 2 em ``MercadoDataProvider``: quando o preco do
ativo nao existe (ASK ausente + preco de frescor expirado) e a CAB muda, o ciclo
dava ``continue`` no bloco ``_sem_ativo_skip`` sem tocar em ``_dados_cache`` — a
entry ANTIGA (``stale=False``) sobrevivia e o post-loop a devolvia aos monitores
(falso positivo persistente de BOX/SBTH VENDIDO).

Correcao (mercado_data_provider.py): no skip por preco ausente, a entry do cache
e invalidada (``stale=True`` + ``pop``), espelhando o padrao do caminho de REUSO.
A entry nao revalidada some do ``_dados_cache`` e o post-loop nao a devolve; quando
o preco volta, o FRESH a recria normalmente (auto-recuperacao).

Requisitos cobertos:
A) entrada nao revalidada no ciclo atual NAO volta pelo post-loop;
B) preco que volta recria a entry (auto-recuperacao);
C) ciclos repetidos sem preco nao ressuscitam a entry;
D) caminho normal (preco presente) inalterado;
E) fluxo OpenFast (push) FRESH sem regressao;
F) fluxo OpenFast (push) REUSO sem regressao;
G) post-loop continua servindo entry Onda 1 push-skip (nao tocada);
H) end-to-end: monitor nao surfaca oportunidade antiga de ativo nao revalidado.
"""

import time
from datetime import date, timedelta

import pytest

from src.application.use_cases.experimental.vetor_monitor_vendidas import (
    VetorMonitorVendidasUseCase,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider


class FakeRTD:
    """Emula Profit RTD: polling + CAB skip, sem push, sem is_stale_campo."""

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


def _expira_preco_ativo(provider, ativo):
    provider._precos_ativo_cache.pop(ativo, None)
    provider._precos_ativo_cache_ts.pop(ativo, None)


def _setup_provider(db_path, source, key, onda2=True, strike=None):
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


@pytest.fixture
def env(tmp_path):
    """Profit RTD: polling + CAB skip (sem strike no banco, usa campo STRIKE)."""
    db_path = tmp_path / "fix_sem_ativo_skip.db"
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
    key = "PETR4|PETRG180"
    provider = _setup_provider(db_path, source, key)
    return db_path, source, provider, key


@pytest.fixture
def env_push(tmp_path):
    """OpenFast: push change-driven; strike vem do banco."""
    db_path = tmp_path / "fix_sem_ativo_skip_push.db"
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
    source = FakePush()
    key = "PETR4|PETRG180"
    provider = _setup_provider(db_path, source, key)
    return db_path, source, provider, key


class TestSemAtivoSkip:

    def test_a_entrada_nao_revalidada_nao_volta_pelo_post_loop(self, env):
        """(A) preco ausente + CAB mudou -> FRESH skip -> entry invalidada."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        dados_a = provider.capturar_dados_mercado()
        assert key in dados_a
        assert key in provider._dados_cache

        # Ciclo B: preco_ativo ausente + CAB muda -> caminho FRESH -> _sem_ativo_skip
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        source.set_campo(inst.cod_put, FieldName.BOOK_HEADER, 151.0)
        source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, 151.0)
        dados_b = provider.capturar_dados_mercado()

        assert key not in dados_b, "entrada nao revalidada nao pode voltar pelo post-loop"
        assert key not in provider._dados_cache, "entry deve ser invalidada do cache"
        assert key in provider._chaves_com_book, "chave continua registrada (dado e que invalida)"

    def test_b_preco_volta_recria_entry(self, env):
        """(B) quando o preco volta, o FRESH recria a entry (auto-recuperacao)."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        # Ciclo B: preco ausente -> skip (entry invalidada)
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        source.set_campo(inst.cod_put, FieldName.BOOK_HEADER, 151.0)
        source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, 151.0)
        dados_b = provider.capturar_dados_mercado()
        assert key not in dados_b
        assert key not in provider._dados_cache

        # Ciclo C: preco volta (mercado novo) -> entry recriada com valores novos
        _set_book_completo(source, inst, key)
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, 13.60)
        dados_c = provider.capturar_dados_mercado()

        e = dados_c[key]
        assert e["preco_ativo"] == 13.65
        assert e["of_compra_ativo"] == 13.60
        assert e["of_venda_ativo"] == 13.65
        assert e.get("stale") is False
        assert key in provider._dados_cache

    def test_c_ciclos_repetidos_sem_preco_nao_ressuscitam(self, env):
        """(C) varios ciclos sem preco -> a entry nunca ressuscita."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        for _ in range(3):
            source.set_campo(ativo, FieldName.ASK, None)
            source.set_campo(ativo, FieldName.BID, None)
            _expira_preco_ativo(provider, ativo)
            source.set_campo(inst.cod_put, FieldName.BOOK_HEADER, 151.0)
            source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, 151.0)
            dados = provider.capturar_dados_mercado()
            assert key not in dados, "ciclo sem preco nao pode servir entry antiga"
            assert key not in provider._dados_cache

    def test_d_caminho_normal_inalterado(self, env):
        """(D) preco presente em cada ciclo -> FRESH continua escrevendo (sem regressao)."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        dados_a = provider.capturar_dados_mercado()
        assert dados_a[key]["preco_ativo"] == 14.00
        assert dados_a[key]["of_compra_ativo"] == 13.95

        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, 13.60)
        dados_b = provider.capturar_dados_mercado()
        assert dados_b[key]["preco_ativo"] == 13.65
        assert dados_b[key]["of_compra_ativo"] == 13.60
        assert dados_b[key].get("stale") is False
        assert key in provider._dados_cache


class TestOpenFastSemRegressao:

    def test_e_push_fresh_onda2_normal(self, env_push):
        """(E) OpenFast FRESH (perna suja): entry correta, sem afetar o skip."""
        db_path, source, provider, key = env_push
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_mudancas({"PETR4|ULT": 1.0})
        dados = provider.capturar_dados_mercado()

        e = dados[key]
        assert e["preco_ativo"] == 14.00
        assert e["of_compra_ativo"] == 13.95
        assert e["of_venda_ativo"] == 14.00
        assert e["of_compra_put"] == 4.30
        assert e["of_venda_put"] == 4.40
        assert e["of_compra_call"] == 0.04
        assert e["of_venda_call"] == 0.05
        assert e.get("stale") is False
        assert key in provider._dados_cache

    def test_f_push_reuso_sem_mudanca_continua_servindo(self, env_push):
        """(F) OpenFast REUSO (sem mudanca): continua servindo e atualizando status."""
        db_path, source, provider, key = env_push
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        source.set_mudancas({"PETR4|ULT": 1.0})
        provider.capturar_dados_mercado()  # ciclo A (fresh)

        # Ciclo B: nenhuma perna de PETR4 suja -> REUSO (entry do cache)
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, None)
        source.set_mudancas({"IBOV|ULT": 1.0})
        dados_b = provider.capturar_dados_mercado()

        e = dados_b[key]
        assert e["preco_ativo"] == 13.65, "reuso atualiza preco via ASK"
        assert e["of_compra_ativo"] == 0.0, "BID ausente no reuso -> zerado (sem congelar)"
        assert e.get("stale") is False
        assert key in provider._dados_cache

    def test_g_onda1_push_skip_continua_servido_pelo_post_loop(self, env_push):
        """(G) post-loop segue servindo entry Onda 1 push-skip (nao tocada)."""
        db_path, source, provider, key = env_push
        repo = InstrumentoRepository(db_path)
        repo.save(InstrumentoOpcional(
            ativo="VALEA3",
            cod_put="VALEQ180",
            cod_call="VALER180",
            vencimento=date.today() + timedelta(days=20),
            tipo_opcao=TipoOpcao.AMERICANA,
            strike=18.00,
        ))
        provider._ativos_registrados.add("VALEA3")
        key2 = "VALEA3|VALEQ180"
        provider._chaves_registradas.add(key2)
        provider._chaves_com_book.add(key2)
        entry_onda1 = {
            "preco_ativo": 16.00, "strike_rtd": 18.0,
            "of_compra_ativo": 15.98, "of_venda_ativo": 16.00,
            "of_compra_put": 3.10, "of_venda_put": 3.20,
            "of_compra_call": 0.20, "of_venda_call": 0.22,
            "em_leilao": False, "stale": False, "onda": 1,
        }
        provider._dados_cache[key2] = entry_onda1

        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        # mudancas nao incluem VALEA3/pernas -> perna_mudou False -> skip Onda 1
        source.set_mudancas({"PETR4|ULT": 1.0})
        dados = provider.capturar_dados_mercado()

        assert key in dados, "PETR4 (Onda 2, dirty) continua normal"
        assert key2 in dados, "post-loop deve servir entry Onda 1 nao tocada"
        assert dados[key2]["of_compra_ativo"] == 15.98
        assert dados[key2]["em_leilao"] is False
        assert dados[key2].get("stale") is False


class TestMonitorNaoSurfacaOportunidadeAntiga:

    def test_h_uso_case_nao_surfaca_oportunidade_de_ativo_nao_revalidado(self, env):
        """(H) end-to-end: ativo nao revalidado nao mantem BOX/SBTH VENDIDO."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        dados_n = provider.capturar_dados_mercado()

        uc = VetorMonitorVendidasUseCase(db_path)
        opps_n = uc.varrer(
            dados_n, inst_map=provider._get_inst_map(),
            chaves=list(dados_n.keys()),
            chaves_parsed=[k.split("|") for k in dados_n.keys()],
        )
        assert any(o.ativo == "PETR4" for o in opps_n), "ciclo N com dados reais"

        # Ciclo N+1: preco ausente -> entry invalidada -> monitor sem PETR4
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        _expira_preco_ativo(provider, ativo)
        source.set_campo(inst.cod_put, FieldName.BOOK_HEADER, 151.0)
        source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, 151.0)
        dados_n1 = provider.capturar_dados_mercado()

        assert key not in dados_n1
        opps_n1 = uc.varrer(
            dados_n1, inst_map=provider._get_inst_map(),
            chaves=list(dados_n1.keys()),
            chaves_parsed=[k.split("|") for k in dados_n1.keys()],
        )
        assert not any(o.ativo == "PETR4" for o in opps_n1), (
            "ativo nao revalidado nao pode manter falso positivo"
        )