"""Regressao do falso positivo de BOX/SBTH VENDIDO por of_compra_ativo stale.

Cobria o caminho de REUSO da Onda 2 em ``MercadoDataProvider`` (Profit RTD,
polling + CAB skip): quando o BID do ativo nao chega (ou chega acima do preco),
o valor antigo de ``of_compra_ativo`` era preservado e inflava
``recebimento_box``/``recebimento_sbth`` (falso positivo).

Correcao (mercado_data_provider.py):
1. BID ausente/invalido no reuso -> of_compra_ativo = 0.0 (espelha a Onda 1);
2. entry com stale=True e invalidada do _dados_cache (pop) e o post-loop nao a
   devolve via ``dict(cached)``.

Requisitos cobertos: A) BID stale nao sobrevive ao reuso; B) stale=True nao
volta pelo post-loop; C) BID ausente nao congela valor anterior; D) BID >
preco_ativo nao e aceito; E/F) BOX_VENDIDO/SBTH_VENDIDA nao disparam mais;
G) preco_ativo/ASK segue funcionando; H) 4 pernas de opcoes sem regressao;
I) reconexao nao ressuscita valores stale; J) caminho normal inalterado.
"""

import time
from datetime import date, timedelta

import numpy as np
import pytest

from src.application.use_cases.experimental.vetor_monitor_vendidas import (
    VetorMonitorVendidasUseCase,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.calculadora_vendidas_vetor import calcular_vendidas
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


@pytest.fixture
def env(tmp_path):
    db_path = tmp_path / "fix_stale_of_compra.db"
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
    key = "PETR4|PETRG180"
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    provider._ativos_registrados = {"PETR4"}
    provider._chaves_registradas = {key}
    provider._chaves_com_book = {key}
    provider._chaves_detalhes_completos = {key}
    return db_path, source, provider, key


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


class TestBidStaleNaoSobreviveAoReuso:

    def test_a_c_bid_ausente_nao_congela_valor_anterior(self, env):
        """(A/C) BID ausente no reuso -> of_compra_ativo zerado, nao congela 13.95."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)

        provider.capturar_dados_mercado()  # ciclo A (fresh, BID 13.95)

        # Ciclo B: mercado cai (ASK 13.65), BID nao chega (None)
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, None)
        dados = provider.capturar_dados_mercado()

        entry = dados[key]
        assert entry["preco_ativo"] == 13.65
        assert entry["of_compra_ativo"] == 0.0, "BID ausente nao pode preservar 13.95"

    def test_d_bid_maior_que_preco_nao_e_aceito(self, env):
        """(D) BID acima do preco (defasado) e zerado, espelhando a Onda 1."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A (preco 14.00, BID 13.95)

        # Ciclo B: ASK novo 13.65; BID ainda defasado em 13.95 (acima do preco)
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, 13.95)
        dados = provider.capturar_dados_mercado()

        entry = dados[key]
        assert entry["preco_ativo"] == 13.65
        assert entry["of_compra_ativo"] == 0.0, "BID 13.95 > preco 13.65 deve ser zerado"

    def test_b_stale_true_nao_volta_pelo_post_loop(self, env):
        """(B) stale=True invalida a entry do cache; post-loop nao a devolve."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        # Ciclo B: sem ASK e sem preco em cache -> stale=True
        provider._precos_ativo_cache.pop(ativo, None)
        provider._precos_ativo_cache_ts.pop(ativo, None)
        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, None)
        dados = provider.capturar_dados_mercado()

        assert key not in dados, "entry stale nao pode voltar pelo post-loop"
        assert key not in provider._dados_cache, "entry stale deve ser invalidada do cache"


class TestFalsoPositivoEliminado:

    def _entry_vendidas(self, of_compra_ativo, **kwargs):
        base = {
            "preco_ativo": 13.65,
            "strike_rtd": 18.00,
            "of_compra_put": 4.35,
            "of_venda_call": 0.04,
            "vov_put": 5000.0,
            "voc_call": 5000.0,
        }
        base["of_compra_ativo"] = of_compra_ativo
        base.update(kwargs)
        return base

    def test_e_box_vendido_nao_dispara_mais(self, env):
        """(E) BOX_VENDIDO: valor que antes disfarçava False->True agora fica False."""
        for of_compra_ativo, esperado in [(0.0, False), (13.95, True)]:
            entry = self._entry_vendidas(of_compra_ativo)
            r = calcular_vendidas(
                preco_ativo=np.array([entry["preco_ativo"]]),
                of_compra_ativo=np.array([entry["of_compra_ativo"]]),
                of_compra_put=np.array([entry["of_compra_put"]]),
                of_venda_call=np.array([entry["of_venda_call"]]),
                strike=np.array([entry["strike_rtd"]]),
                dias=np.array([20]),
                vov_put=np.array([entry["vov_put"]]),
                voc_call=np.array([entry["voc_call"]]),
                dist_min_ativo=1.2,
                premio_risco=1.1,
                lote_box=100,
                lote_sbth=100,
                taxa_cdi=0.14,
            )
            assert bool(r.cond_box[0]) is esperado, of_compra_ativo

    def test_f_sbth_vendida_nao_dispara_mais(self, env):
        """(F) SBTH_VENDIDA: valor que antes disfarçava False->True agora fica False."""
        for of_compra_ativo, esperado in [(0.0, False), (13.95, True)]:
            entry = self._entry_vendidas(of_compra_ativo)
            r = calcular_vendidas(
                preco_ativo=np.array([entry["preco_ativo"]]),
                of_compra_ativo=np.array([entry["of_compra_ativo"]]),
                of_compra_put=np.array([entry["of_compra_put"]]),
                of_venda_call=np.array([entry["of_venda_call"]]),
                strike=np.array([entry["strike_rtd"]]),
                dias=np.array([20]),
                vov_put=np.array([entry["vov_put"]]),
                voc_call=np.array([entry["voc_call"]]),
                dist_min_ativo=1.2,
                premio_risco=1.1,
                lote_box=100,
                lote_sbth=100,
                taxa_cdi=0.14,
            )
            assert bool(r.cond_sbth[0]) is esperado, of_compra_ativo

    def test_use_case_saida_provider_nao_surfaca_oportunidade(self, env):
        """(E/F) entry pos-fix (of_compra_ativo=0.0) nao surfaca BOX/SBTH no use case."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        # Ciclo B: BID ausente -> of_compra_ativo=0.0
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, None)
        dados = provider.capturar_dados_mercado()
        entry = dados[key]
        assert entry["of_compra_ativo"] == 0.0

        uc = VetorMonitorVendidasUseCase(db_path)
        opps = uc.varrer(
            {key: entry}, inst_map=provider._get_inst_map(),
            chaves=[key], chaves_parsed=[key.split("|")],
        )
        assert len(opps) == 0, "saida pos-fix nao pode gerar falso positivo"


class TestSemRegressao:

    def test_g_ask_preco_ativo_continua_funcionando(self, env):
        """(G) ASK/preco_ativo segue atualizando no reuso com dados validos."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        # Ciclo B: ASK novo e BID valido (abaixo do preco) -> ambos atualizam
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, 13.60)
        dados = provider.capturar_dados_mercado()

        entry = dados[key]
        assert entry["preco_ativo"] == 13.65
        assert entry["of_venda_ativo"] == 13.65
        assert entry["of_compra_ativo"] == 13.60, "BID valido (<= preco) deve ser aceito"

    def test_g_ask_ausente_preco_usado_do_cache_fresco(self, env):
        """(G) ASK ausente: preco_ativo cai no cache de frescor; BID valido aceito."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A (preco 14.00)

        source.set_campo(ativo, FieldName.ASK, None)
        source.set_campo(ativo, FieldName.BID, 13.70)
        dados = provider.capturar_dados_mercado()

        entry = dados[key]
        assert entry["preco_ativo"] == 14.00, "preco do cache de frescor"
        assert entry["of_compra_ativo"] == 13.70

    def test_h_pernas_opcoes_sem_regressao(self, env):
        """(H) 4 pernas de opcoes ausentes congelam (sem regressao)."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A

        # Ciclo B: opcoes ausentes; ASK ativo novo; BID ativo defasado (> preco)
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(cod_put, FieldName.ASK, None)
        source.set_campo(cod_put, FieldName.BID, None)
        source.set_campo(inst.cod_call, FieldName.BID, None)
        source.set_campo(inst.cod_call, FieldName.ASK, None)
        dados = provider.capturar_dados_mercado()

        entry = dados[key]
        assert entry["of_compra_put"] == 4.30
        assert entry["of_venda_put"] == 4.40
        assert entry["of_compra_call"] == 0.04
        assert entry["of_venda_call"] == 0.05
        assert entry["of_compra_ativo"] == 0.0, "BID 13.95 > preco 13.65 -> zerado"

    def test_i_reconexao_nao_ressuscita_valores_stale(self, env):
        """(I) apos desconectar/reconectar, BID ausente zera (nada ressurge)."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        provider.capturar_dados_mercado()  # ciclo A (BID 13.95)

        source.desconectar()
        source.reconectar()
        assert len(provider._dados_cache) == 1, "_dados_cache do provider nao e limpo"

        # Pushs voltam: ASK novo, BID ainda ausente
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, None)
        for cod, ask, bid in [(cod_put, 4.45, 4.35), (inst.cod_call, 0.04, 0.03)]:
            source.set_campo(cod, FieldName.ASK, ask)
            source.set_campo(cod, FieldName.BID, bid)
        source.set_campo(cod_put, FieldName.BOOK_HEADER, 150.0)
        source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, 150.0)
        source.set_campo(cod_put, FieldName.STRIKE, 18.00)
        source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
        dados = provider.capturar_dados_mercado()

        entry = dados[key]
        assert entry["of_compra_ativo"] == 0.0, "reconexao nao ressuscita o BID antigo"

    def test_j_caminho_normal_inalterado(self, env):
        """(J) ciclo A + reuso com dados validos produz entradas iguais ao esperado."""
        db_path, source, provider, key = env
        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        dados_a = provider.capturar_dados_mercado()

        entry_a = dados_a[key]
        assert entry_a["preco_ativo"] == 14.00
        assert entry_a["of_compra_ativo"] == 13.95
        assert entry_a["of_venda_ativo"] == 14.00
        assert entry_a["of_compra_put"] == 4.30
        assert entry_a["of_venda_put"] == 4.40
        assert entry_a["of_compra_call"] == 0.04
        assert entry_a["of_venda_call"] == 0.05
        assert entry_a.get("stale") is False
        assert key in provider._dados_cache

        # Reuso com tudo presente (BID valido, opcoes validas) -> valores atualizam
        source.set_campo(ativo, FieldName.ASK, 13.65)
        source.set_campo(ativo, FieldName.BID, 13.60)
        source.set_campo(cod_put, FieldName.ASK, 4.45)
        source.set_campo(cod_put, FieldName.BID, 4.35)
        source.set_campo(inst.cod_call, FieldName.BID, 0.03)
        source.set_campo(inst.cod_call, FieldName.ASK, 0.04)
        dados_b = provider.capturar_dados_mercado()

        entry_b = dados_b[key]
        assert entry_b["preco_ativo"] == 13.65
        assert entry_b["of_compra_ativo"] == 13.60
        assert entry_b["of_venda_ativo"] == 13.65
        assert entry_b["of_compra_put"] == 4.35
        assert entry_b["of_venda_put"] == 4.45
        assert entry_b["of_compra_call"] == 0.03
        assert entry_b["of_venda_call"] == 0.04
        assert entry_b.get("stale") is False

    def test_post_loop_continua_servindo_nao_stale(self, env):
        """Post-loop segue servindo entries nao-stale (key nao tocada)."""
        db_path, source, provider, key = env
        key2 = "PETR4|PETRG124"
        provider._chaves_registradas.add(key2)
        provider._chaves_com_book.add(key2)
        entry_onda1 = {
            "preco_ativo": 12.40, "strike_rtd": 12.4,
            "of_compra_ativo": 12.40, "of_venda_ativo": 12.40,
            "of_compra_put": 0.1, "of_venda_put": 0.1,
            "of_compra_call": 0.1, "of_venda_call": 0.1,
            "em_leilao": False, "stale": False, "onda": 1,
        }
        provider._dados_cache[key2] = entry_onda1

        ativo, cod_put = key.split("|", 1)
        inst = provider._get_inst_map()[(ativo, cod_put)]
        _set_book_completo(source, inst, key)
        dados = provider.capturar_dados_mercado()

        assert key2 in dados, "post-loop deve servir key nao-stale"
        assert dados[key2]["of_compra_ativo"] == 12.40