"""Harness de regressao: Onda 2 antiga NAO pode sobreviver via post-loop sem revalidacao.

PERGUNTA: um instrumento processado na Onda 2 em um ciclo anterior pode continuar
alimentando os monitores (BOX/SBTH VENDIDO) com valores ANTIGOS quando, no ciclo
atual, NAO e revalidado pela Onda 2?

Caminho auditado: FRESH da Onda 2 com preco_ativo ausente -> `_sem_ativo_skip`
(mercado_data_provider.py:801-807) -> `continue` sem tocar em `_dados_cache`
-> post-loop (linha 903-909) copia a entry ANTIGA para `dados_mercado`.

CORRECAO aplicada (fix de fechamento da auditoria): quando o preco do ativo falta
no FRESH, a entry do cache e invalidada (stale=True + pop), espelhando o padrao do
caminho de REUSO. A entry nao revalidada desaparece de `_dados_cache` e o post-loop
nao pode devolve-la; quando o preco volta, o FRESH a recria normalmente.

Cenarios comparados (mesmo provider, mesmo ciclo):
  A) VALEA3  - Onda 1 apenas (nunca promovido)        -> revalidado na Onda 1
  B) PETR4   - Onda 2 no ciclo N, NAO revalidado no N+1 -> NAO volta no N+1 (fix)
  C) BRAS3   - Onda 2 no ciclo N, REVALIDADO no N+1     -> valores novos

Tambem demonstra:
- mpp_habilitado e irrelevante para a promocao/uso da Onda 2 (o provider nao o le).
- fazer_manutencao() nunca despromove uma chave da Onda 2 (_chaves_detalhes_completos
  so ganha chaves; so e limpo em recarregar_instrumentos/recarregar_parametros).

USO:  python scripts/harness_onda2_sem_repromocao.py
"""

import os
import sys
import time
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.application.use_cases.experimental.vetor_monitor_vendidas import VetorMonitorVendidasUseCase
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider


class FakeSource:
    """Fonte fake que emula Profit RTD (polling + CAB skip) — sem is_stale_campo."""

    disponivel = True
    suporta_push = False
    suporta_cab_skip = True
    is_stale_campo = None
    stale_campo_s = 15.0

    def __init__(self):
        self._cache: dict[tuple[str, FieldName], float | None] = {}
        self._status: dict[str, str] = {}

    def set_campo(self, codigo, campo, valor):
        self._cache[(codigo, campo)] = valor

    def set_status(self, codigo, status):
        self._status[codigo] = status

    def registrar_topico(self, codigo, campo) -> int:
        return 0

    def registrar_lista(self, registros) -> int:
        return len(registros)

    def registrar_status(self, codigo) -> int:
        return 0

    def ler_campo_cache(self, codigo, campo, allow_stale=False):
        return self._cache.get((codigo, campo))

    def ler_campos(self, codigo, *campos, allow_stale=False):
        return {c: self._cache.get((codigo, c)) for c in campos}

    def ler_status_cache(self, codigo) -> str:
        return self._status.get(codigo, "aberto")

    def forcar_leitura(self, codigo, campo):
        return self._cache.get((codigo, campo))

    def refresh(self, timeout_ms=0) -> dict:
        return {}

    def desconectar(self):
        self._cache.clear()

    def reconectar(self) -> bool:
        return True

    def invalidar_cache(self, codigo, campo):
        self._cache.pop((codigo, campo), None)

    def get_ts_campo(self, codigo, campo):
        return time.time()


def _montar_book(source, ativo, cod_put, cod_call, preco, bid_ativo,
                 put_ask, put_bid, call_bid, call_ask, cab):
    source.set_campo(ativo, FieldName.ASK, preco)
    source.set_campo(ativo, FieldName.BID, bid_ativo)
    source.set_campo(cod_put, FieldName.ASK, put_ask)
    source.set_campo(cod_put, FieldName.BID, put_bid)
    source.set_campo(cod_put, FieldName.VOL_ASK, 5000.0)
    source.set_campo(cod_put, FieldName.QTD_LAST, 3000.0)
    source.set_campo(cod_call, FieldName.BID, call_bid)
    source.set_campo(cod_call, FieldName.ASK, call_ask)
    source.set_campo(cod_call, FieldName.VOL_BID, 5000.0)
    source.set_campo(cod_call, FieldName.QTD_LAST, 3000.0)
    source.set_status(ativo, "aberto")
    source.set_status(cod_put, "aberto")
    source.set_status(cod_call, "aberto")
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(cod_call, FieldName.BOOK_HEADER, cab[1])


def setup():
    tmp = tempfile.mkdtemp(prefix="spreadhunter_harness_onda2_")
    db_path = os.path.join(tmp, "harness.db")
    conn = init_db(db_path)
    conn.close()
    ParametroRepository(db_path).seed_defaults()

    repo = InstrumentoRepository(db_path)
    repo.invalidate_cache()
    hoje = date.today()
    insts = [
        InstrumentoOpcional(ativo="VALEA3", cod_put="VALEQ180", cod_call="VALER180",
                            vencimento=hoje + timedelta(days=20), tipo_opcao=TipoOpcao.AMERICANA),
        InstrumentoOpcional(ativo="PETR4", cod_put="PETRG180", cod_call="PETRH180",
                            vencimento=hoje + timedelta(days=20), tipo_opcao=TipoOpcao.AMERICANA),
        InstrumentoOpcional(ativo="BRAS3", cod_put="BRASG180", cod_call="BRASH180",
                            vencimento=hoje + timedelta(days=20), tipo_opcao=TipoOpcao.AMERICANA),
    ]
    for inst in insts:
        repo.save(inst)

    source = FakeSource()
    provider = MercadoDataProvider(db_path, source)

    keys = {inst.ativo: f"{inst.ativo}|{inst.cod_put}" for inst in insts}
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    provider._ativos_registrados = {i.ativo for i in insts}
    provider._chaves_registradas = set(keys.values())
    provider._chaves_com_book = set(keys.values())
    # Promocao simulada (fazer_manutencao promoveu ANTES): B e C na Onda 2; A nao.
    provider._chaves_detalhes_completos = {keys["PETR4"], keys["BRAS3"]}
    return db_path, source, provider, keys


def principal():
    print("=" * 78)
    print("HARNESS — Onda 2 antiga sobrevive via post-loop sem revalidacao?")
    print("=" * 78)

    db_path, source, provider, keys = setup()
    inst_map = provider._get_inst_map()
    key_a, key_b, key_c = keys["VALEA3"], keys["PETR4"], keys["BRAS3"]
    inst_b = inst_map[tuple(key_b.split("|"))]

    # Strike real das puts (nao usar ASK da put)
    _STRIKE_A = 18.00
    _STRIKE_B = 18.00
    _STRIKE_C = 12.00
    source.set_campo(inst_b.cod_put, FieldName.STRIKE, _STRIKE_B)
    source.set_campo(inst_b.cod_call, FieldName.STRIKE, _STRIKE_B)
    inst_a = inst_map[tuple(key_a.split("|"))]
    inst_c = inst_map[tuple(key_c.split("|"))]
    source.set_campo(inst_a.cod_put, FieldName.STRIKE, _STRIKE_A)
    source.set_campo(inst_a.cod_call, FieldName.STRIKE, _STRIKE_A)
    source.set_campo(inst_c.cod_put, FieldName.STRIKE, _STRIKE_C)
    source.set_campo(inst_c.cod_call, FieldName.STRIKE, _STRIKE_C)

    # ---------------------------------------------------------------- ciclo N
    print("\n--- CICLO N: dados reais; B e C na Onda 2, A na Onda 1 -----------")
    _montar_book(source, "VALEA3", inst_a.cod_put, inst_a.cod_call,
                 preco=16.00, bid_ativo=15.98, put_ask=3.20, put_bid=3.10,
                 call_bid=0.20, call_ask=0.22, cab=(110.0, 110.0))
    _montar_book(source, "PETR4", inst_b.cod_put, inst_b.cod_call,
                 preco=14.00, bid_ativo=13.95, put_ask=4.40, put_bid=4.30,
                 call_bid=0.04, call_ask=0.05, cab=(150.0, 150.0))
    _montar_book(source, "BRAS3", inst_c.cod_put, inst_c.cod_call,
                 preco=10.00, bid_ativo=9.95, put_ask=3.10, put_bid=3.00,
                 call_bid=0.10, call_ask=0.12, cab=(120.0, 120.0))

    dados_n = provider.capturar_dados_mercado()
    e_b_n = dict(dados_n[key_b])
    e_c_n = dict(dados_n[key_c])
    print(f"  B(PETR4)  onda={e_b_n.get('onda')} preco={e_b_n['preco_ativo']} "
          f"of_compra_ativo={e_b_n['of_compra_ativo']}")
    print(f"  C(BRAS3)  onda={e_c_n.get('onda')} preco={e_c_n['preco_ativo']} "
          f"of_compra_ativo={e_c_n['of_compra_ativo']}")
    print(f"  A(VALEA3) onda={dados_n[key_a].get('onda')} preco={dados_n[key_a]['preco_ativo']}")
    assert e_b_n.get("onda") == 2 and e_c_n.get("onda") == 2 and dados_n[key_a].get("onda") == 1
    assert key_b in provider._dados_cache, "ciclo N: B deveria estar no cache"

    # ---------------------------------------------------------- ciclo N+1
    print("\n--- CICLO N+1: mercado muda; B NAO e revalidado (preco ausente), "
          "A e C revalidados ---")
    # A: revalidado na Onda 1 (preco novo)
    _montar_book(source, "VALEA3", inst_a.cod_put, inst_a.cod_call,
                 preco=16.20, bid_ativo=16.18, put_ask=3.25, put_bid=3.15,
                 call_bid=0.18, call_ask=0.20, cab=(112.0, 112.0))
    # B: preco_ativo (ASK do ativo) AUSENTE + CAB muda -> caminho FRESH -> sem_ativo_skip.
    source.set_campo("PETR4", FieldName.ASK, None)
    source.set_campo("PETR4", FieldName.BID, None)
    source.set_campo(inst_b.cod_put, FieldName.BOOK_HEADER, 151.0)
    source.set_campo(inst_b.cod_call, FieldName.BOOK_HEADER, 151.0)
    # força o fallback _preco_ativo_cache_fresco a expirar (janela 15s)
    provider._precos_ativo_cache_ts["PETR4"] = time.time() - 60
    # C: revalidado na Onda 2 com BID do ativo AUSENTE (oportunidade some)
    _montar_book(source, "BRAS3", inst_c.cod_put, inst_c.cod_call,
                 preco=10.00, bid_ativo=None, put_ask=3.10, put_bid=3.00,
                 call_bid=0.10, call_ask=0.12, cab=(121.0, 121.0))

    dados_n1 = provider.capturar_dados_mercado()

    e_c_n1 = dict(dados_n1[key_c])
    e_a_n1 = dict(dados_n1[key_a])

    print(f"  B(PETR4)  presente em dados? {key_b in dados_n1} | "
          f"em _dados_cache? {key_b in provider._dados_cache}")
    print(f"  C(BRAS3)  onda={e_c_n1.get('onda')} preco={e_c_n1['preco_ativo']} "
          f"of_compra_ativo={e_c_n1['of_compra_ativo']} (BID ausente -> 0.0)")
    print(f"  A(VALEA3) onda={e_a_n1.get('onda')} preco={e_a_n1['preco_ativo']}")
    print(f"  [cache] chave em _chaves_com_book? {key_b in provider._chaves_com_book} | "
          f"chave em _chaves_detalhes_completos? {key_b in provider._chaves_detalhes_completos}")

    # Assertions: B NAO volta (entry invalidada pelo fix); C/A revalidados ok.
    assert key_b not in dados_n1, "B nao pode voltar pelo post-loop sem revalidacao (fix)"
    assert key_b not in provider._dados_cache, "B deve ser invalidado do _dados_cache (fix)"
    assert key_b in provider._chaves_com_book, "B continua registrado (so o dado e invalidado)"
    assert e_c_n1["of_compra_ativo"] == 0.0, "C revalidado com BID ausente -> zerado"
    assert e_c_n1["preco_ativo"] == 10.00
    assert e_a_n1["preco_ativo"] == 16.20, "A revalidado na Onda 1"
    assert e_a_n1.get("stale") is False

    # ------------------------------------------------------ impacto no monitor
    print("\n--- IMPACTO NO MONITOR (VetorMonitorVendidasUseCase) -----------------")
    uc = VetorMonitorVendidasUseCase(db_path)

    def _opps(dados, rotulo):
        ops = uc.varrer(dados, inst_map=inst_map, chaves=list(dados.keys()),
                        chaves_parsed=[k.split("|") for k in dados.keys()])
        linhas = [f"{o.classificacao}({o.ativo}) receb={o.recebimento} viavel={o.viavel} "
                  f"ts_scan={o.ts_scan:.3f}" for o in ops]
        print(f"  [{rotulo}] {len(ops)} oportunidade(s):")
        for ln in linhas:
            print(f"    - {ln}")
        return ops

    opps_n = _opps(dados_n, "ciclo N")
    opps_n1 = _opps(dados_n1, "ciclo N+1")

    ops_b_n = [o for o in opps_n if o.ativo == "PETR4"]
    ops_c_n = [o for o in opps_n if o.ativo == "BRAS3"]
    ops_b_n1 = [o for o in opps_n1 if o.ativo == "PETR4"]
    ops_c_n1 = [o for o in opps_n1 if o.ativo == "BRAS3"]

    assert ops_b_n, "ciclo N: PETR4 deveria surfacar oportunidade (dados reais)"
    assert ops_c_n, "ciclo N: BRAS3 deveria surfacar oportunidade (dados reais)"
    assert not ops_b_n1, "ciclo N+1: PETR4 (nao revalidado) NAO pode manter oportunidade (fix)"
    assert not ops_c_n1, "ciclo N+1: BRAS3 (revalidado, BID ausente) perde a oportunidade"

    print("\n  [EVIDENCIA 1] Ciclo N+1: PETR4 (sem revalidacao) NAO aparece em "
          "dados_mercado nem no cache -> monitor NAO gera falso positivo.")
    print("  [EVIDENCIA 2] BRAS3 (revalidado) corretamente perde a oportunidade "
          "quando o BID some; VALEA3 (Onda 1) revalidado normalmente.")

    # --------------------------------------- manutenção não despromove + MPP
    print("\n--- FATO ESTRUTURAL: fazer_manutencao nao despromove; MPP nao promove ----")
    source._cache.clear()
    provider.fazer_manutencao()
    ainda_onda2 = key_b in provider._chaves_detalhes_completos
    ainda_book = key_b in provider._chaves_com_book
    print(f"  apos fazer_manutencao() com liquidez zero: "
          f"B ainda em _chaves_detalhes_completos? {ainda_onda2} | "
          f"ainda em _chaves_com_book? {ainda_book}")
    assert ainda_onda2 and ainda_book

    import inspect
    src_provider = inspect.getsource(MercadoDataProvider)
    print(f"  'mpp_habilitado' aparece no provider? "
          f"{'mpp_habilitado' in src_provider} (promocao/uso da Onda 2 independe do MPP)")

    print("\nRESULTADO: CORRIGIDO — entry nao revalidada e invalidada do cache "
          "(stale+pop) e NAO volta pelo post-loop; sem falso positivo no monitor.")
    print("Fix de fechamento da auditoria aplicado (mercado_data_provider.py).")


if __name__ == "__main__":
    principal()