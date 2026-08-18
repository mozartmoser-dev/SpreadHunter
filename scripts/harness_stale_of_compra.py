"""Harness de reproducao/regressao: of_compra_ativo stale no caminho de REUSO da Onda 2.

Reproduz o falso positivo de BOX/SBTH VENDIDO que acontecia quando o BID do
ativo nao chegava em um ciclo de reuso (`not cab_mudou and key in _dados_cache`)
— o valor antigo de ``of_compra_ativo`` persistia e inflava
`recebimento_box`/`recebimento_sbth`.

Apos a correcao, este harness ASSERTS o comportamento corrigido:
- BID ausente -> of_compra_ativo zerado (nao preserva valor antigo);
- BID > preco_ativo -> zerado (espelha a Onda 1);
- entry com stale=True e invalidada do _dados_cache e nao volta pelo post-loop;
- BOX/SBTH nao disparam mais com o valor stale.

Como: dirige o MERCADO_DATA_PROVIDER REAL com um FakeSource que implementa o
protocolo MarketDataSource, temp DB via init_db+seed_defaults, estado interno
pre-semeado (Onda 2 completa) e CAB estavel entre ciclos A/B.

Uso:  python scripts/harness_stale_of_compra.py
"""

import os
import sys
import time
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.domain.services.calculadora_vendidas_vetor import calcular_vendidas
from src.application.use_cases.experimental.vetor_monitor_vendidas import VetorMonitorVendidasUseCase
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider


# ---------------------------------------------------------------------------
# Fake source (MarketDataSource protocol)
# ---------------------------------------------------------------------------
class FakeSource:
    """Fonte fake que emula Profit RTD (polling + CAB skip)."""

    disponivel = True
    suporta_push = False
    suporta_cab_skip = True
    is_stale_campo = None  # RTD nao expoe -> _fonte_controla_frescor() False
    stale_campo_s = 15.0

    def __init__(self):
        self._cache: dict[tuple[str, FieldName], float | None] = {}
        self._status: dict[str, str] = {}

    def set_campo(self, codigo: str, campo: FieldName, valor: float | None):
        self._cache[(codigo, campo)] = valor

    def set_status(self, codigo: str, status: str):
        self._status[codigo] = status

    # --- protocolo ---------------------------------------------------------
    def registrar_topico(self, codigo: str, campo: FieldName) -> int:
        return 0

    def registrar_lista(self, registros) -> int:
        return len(registros)

    def registrar_status(self, codigo: str) -> int:
        return 0

    def ler_campo_cache(self, codigo: str, campo: FieldName, allow_stale: bool = False) -> float | None:
        return self._cache.get((codigo, campo))

    def ler_campos(self, codigo: str, *campos: FieldName, allow_stale: bool = False) -> dict:
        return {c: self._cache.get((codigo, c)) for c in campos}

    def ler_status_cache(self, codigo: str) -> str:
        return self._status.get(codigo, "aberto")

    def forcar_leitura(self, codigo: str, campo: FieldName) -> float | None:
        return self._cache.get((codigo, campo))

    def refresh(self, timeout_ms: int = 0) -> dict:
        return {}

    def desconectar(self):
        self._cache.clear()

    def reconectar(self) -> bool:
        return True

    def invalidar_cache(self, codigo: str, campo: FieldName):
        self._cache.pop((codigo, campo), None)

    def get_ts_campo(self, codigo: str, campo: FieldName) -> float | None:
        return time.time()


def _entry_ciclo_a():
    """Entry tipica pos-ciclo A (caminho fresh da Onda 2) com BID presente."""
    return {
        "preco_ativo": 14.00,
        "strike_rtd": 18.00,
        "of_compra_ativo": 13.95,
        "of_venda_ativo": 14.00,
        "of_compra_put": 4.30,
        "of_venda_put": 4.40,
        "of_compra_call": 0.04,
        "of_venda_call": 0.05,
        "premio_put": 4.40,
        "premio_call": 0.04,
        "vov_put": 5000.0,
        "voc_call": 5000.0,
        "vov_put_boca": 5000.0,
        "voc_call_boca": 5000.0,
        "qul_put": 3000.0,
        "qul_call": 3000.0,
        "em_leilao": False,
        "status_put": "aberto",
        "status_call": "aberto",
        "status_ativo": "aberto",
        "ts_ativo_ask": time.time(),
        "ts_ativo_bid": time.time(),
        "ts_scan": time.time(),
        "onda": 2,
        "stale": False,
    }


def setup_provider():
    """Temp DB + instrumento PETR4 + provider com Onda 2 pre-semeada."""
    tmp = tempfile.mkdtemp(prefix="spreadhunter_harness_")
    db_path = os.path.join(tmp, "harness.db")
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

    source = FakeSource()
    provider = MercadoDataProvider(db_path, source)

    key = "PETR4|PETRG180"
    # Estado interno: Onda 1 completa + detalhes completos registrados
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    provider._ativos_registrados = {"PETR4"}
    provider._chaves_registradas = {key}
    provider._chaves_com_book = {key}
    provider._chaves_detalhes_completos = {key}
    return db_path, source, provider, key


def cenario1_bid_ausente():
    """REUSO + BID AUSENTE: of_compra_ativo NAO congela no valor do ciclo A (corrigido)."""
    print("=" * 78)
    print("CENARIO 1 — REUSO ONDA 2 + BID AUSENTE (of_compra_ativo stale)")
    print("=" * 78)

    db_path, source, provider, key = setup_provider()
    ativo, cod_put = key.split("|", 1)
    inst = provider._get_inst_map()[(ativo, cod_put)]

    # --- Ciclo A: book completo (BID presente), ativo em 14.00 -------------
    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    source.set_campo(cod_put, FieldName.ASK, 4.40)
    source.set_campo(cod_put, FieldName.BID, 4.30)
    source.set_campo(cod_put, FieldName.VOL_ASK, 5000.0)
    source.set_campo(cod_put, FieldName.QTD_LAST, 3000.0)
    source.set_campo(inst.cod_call, FieldName.BID, 0.04)
    source.set_campo(inst.cod_call, FieldName.ASK, 0.05)
    source.set_campo(inst.cod_call, FieldName.VOL_BID, 5000.0)
    source.set_campo(inst.cod_call, FieldName.QTD_LAST, 3000.0)
    source.set_status(ativo, "aberto")
    source.set_status(cod_put, "aberto")
    source.set_status(inst.cod_call, "aberto")

    # CAB do ciclo A fica registrado em _cab_anterior pelo caminho fresh
    cab_a = (150.0, 150.0)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab_a[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab_a[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)

    dados_a = provider.capturar_dados_mercado()
    entry_a = dict(dados_a[key])
    print(f"[ciclo A] preco_ativo={entry_a['preco_ativo']}  "
          f"of_compra_ativo={entry_a['of_compra_ativo']}  "
          f"of_venda_ativo={entry_a['of_venda_ativo']}")

    # --- Ciclo B: mercado cai, ASK novo, BID AUSENTE (None) ----------------
    cab_b = cab_a  # CAB igual -> cab_mudou=False -> caminho de REUSO
    source.set_campo(ativo, FieldName.ASK, 13.65)
    source.set_campo(ativo, FieldName.BID, None)          # <<< BID nao chega
    source.set_campo(cod_put, FieldName.ASK, 4.45)
    source.set_campo(cod_put, FieldName.BID, 4.35)
    source.set_campo(inst.cod_call, FieldName.BID, 0.03)
    source.set_campo(inst.cod_call, FieldName.ASK, 0.04)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab_b[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab_b[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)

    dados_b = provider.capturar_dados_mercado()
    entry_b = dados_b[key]

    print(f"[ciclo B] preco_ativo={entry_b['preco_ativo']}  "
          f"of_compra_ativo={entry_b['of_compra_ativo']}  "
          f"of_venda_ativo={entry_b['of_venda_ativo']}")
    print(f"  -> _cab_anterior match, cab_mudou=False, branch REUSO (count_cab_skip={provider._scan_count})")

    assert entry_b["preco_ativo"] == 13.65, "preco_ativo deveria atualizar (ASK novo)"
    assert entry_b["of_venda_ativo"] == 13.65, "of_venda_ativo deveria atualizar (ASK novo)"
    assert entry_b["of_compra_ativo"] == 0.0, (
        f"BID ausente nao pode preservar valor antigo (13.95); recebeu {entry_b['of_compra_ativo']}"
    )
    print(f"  [EVIDENCIA] BID ausente -> of_compra_ativo = {entry_b['of_compra_ativo']} "
          f"(valor antigo 13.95 NAO preservado; BID real ~13.60)")
    return entry_b, dict(entry_a)


def cenario2_3_impacto(entry_b):
    """IMPACTO NUMERICO via calcular_vendidas + VetorMonitorVendidasUseCase."""
    print()
    print("=" * 78)
    print("CENARIOS 2 e 3 — IMPACTO BOX/SBTH VENDIDO (pos-fix vs valor antigo)")
    print("=" * 78)

    # entry_b = saida REAL do provider apos o fix (BID ausente -> of_compra_ativo=0.0)
    # O valor que o bug preservava antes do fix era 13.95.
    bug_antigo = dict(entry_b)
    bug_antigo["of_compra_ativo"] = 13.95
    corrigida = dict(entry_b)
    corrigida["of_compra_ativo"] = 13.60  # BID real de mercado

    def _calc(entry, rotulo):
        r = calcular_vendidas(
            preco_ativo=np.array([entry["preco_ativo"]], dtype=float),
            of_compra_ativo=np.array([entry["of_compra_ativo"]], dtype=float),
            of_compra_put=np.array([entry["of_compra_put"]], dtype=float),
            of_venda_call=np.array([entry["of_venda_call"]], dtype=float),
            strike=np.array([entry["strike_rtd"]], dtype=float),
            dias=np.array([20], dtype=int),
            vov_put=np.array([entry["vov_put"]], dtype=float),
            voc_call=np.array([entry["voc_call"]], dtype=float),
            dist_min_ativo=1.2,
            premio_risco=1.1,
            lote_box=100,
            lote_sbth=100,
            taxa_cdi=0.14,
        )
        print(f"[{rotulo}]")
        print(f"  recebimento_box = {r.recebimento_box[0]:.4f}  cond_box={bool(r.cond_box[0])}  "
              f"pct_cdi_box={r.pct_cdi_box[0]:.4f}  viavel_box={bool(r.viavel_box[0])}")
        print(f"  recebimento_sbth= {r.recebimento_sbth[0]:.4f}  cond_sbth={bool(r.cond_sbth[0])}  "
              f"pct_cdi_sbth={r.pct_cdi_sbth[0]:.4f}  viavel_sbth={bool(r.viavel_sbth[0])}")
        return r

    r_bug = _calc(bug_antigo, "ANTES do fix (valor stale 13.95 preservado)  -> falso positivo")
    r_fix = _calc(entry_b, "POS-FIX (provider: BID ausente -> of_compra_ativo=0.0)")
    r_corr = _calc(corrigida, "BID real de mercado (13.60)")

    assert bool(r_bug.cond_box[0]) and bool(r_bug.cond_sbth[0]), (
        "o valor antigo (13.95) e que gerava o falso positivo (documentado)"
    )
    assert not bool(r_fix.cond_box[0]) and not bool(r_fix.cond_sbth[0]), (
        "pos-fix com BID ausente nenhum dos dois dispara"
    )
    assert not bool(r_corr.cond_box[0]) and not bool(r_corr.cond_sbth[0]), (
        "com o BID correto nenhum dos dois dispara"
    )
    print("  [EVIDENCIA] ANTES do fix: cond_box/cond_sbth=True (falso positivo).")
    print("  [EVIDENCIA] POS-fix: cond_box/cond_sbth=False (sem oportunidade).")
    print("  Delta recebimento_box = %.4f | Delta recebimento_sbth = %.4f"
          % (r_bug.recebimento_box[0] - r_fix.recebimento_box[0],
             r_bug.recebimento_sbth[0] - r_fix.recebimento_sbth[0]))

    # Use case real (pipeline completo) com a entry pos-fix
    db_path, source, provider, key = setup_provider()
    inst_map = provider._get_inst_map()
    uc = VetorMonitorVendidasUseCase(db_path)
    opps = uc.varrer({key: entry_b}, inst_map=inst_map, chaves=[key], chaves_parsed=[key.split("|")])
    print()
    print(f"[VetorMonitorVendidasUseCase.varrer] com entry POS-FIX -> {len(opps)} oportunidade(s):")
    for o in opps:
        print(f"  - {o.classificacao}: recebimento={o.recebimento} "
              f"viavel={o.viavel} preco_ativo={o.preco_ativo}")
    assert len(opps) == 0, "pos-fix a entrada nao deve surfacer nenhuma oportunidade"
    opps2 = uc.varrer({key: bug_antigo}, inst_map=inst_map, chaves=[key], chaves_parsed=[key.split("|")])
    print(f"[VetorMonitorVendidasUseCase.varrer] com entry do bug (13.95) -> {len(opps2)} oportunidade(s) "
          f"(documentado: o bug surfacava falso positivo)")
    assert len(opps2) >= 1, "o valor antigo que o bug preservava surfacava falso positivo"


def cenario4_preco_ativo_ask():
    """AS K AUSENTE no reuso: preco_ativo/of_venda_ativo ficam stale (caminho comprado)."""
    print()
    print("=" * 78)
    print("CENARIO 4 — ASK AUSENTE no reuso: preco_ativo/of_venda_ativo congelam")
    print("=" * 78)
    db_path, source, provider, key = setup_provider()
    ativo, cod_put = key.split("|", 1)
    inst = provider._get_inst_map()[(ativo, cod_put)]

    # Ciclo A com book completo
    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    for cod, ask, bid in [(cod_put, 4.40, 4.30), (inst.cod_call, 0.05, 0.04)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    cab = (150.0, 150.0)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    provider.capturar_dados_mercado()

    # Ciclo B: ASK ausente, BID presente novo
    source.set_campo(ativo, FieldName.ASK, None)
    source.set_campo(ativo, FieldName.BID, 13.70)
    dados_b = provider.capturar_dados_mercado()
    entry = dados_b[key]
    print(f"[ciclo B] preco_ativo={entry['preco_ativo']} "
          f"of_venda_ativo={entry['of_venda_ativo']} "
          f"of_compra_ativo={entry['of_compra_ativo']} (BID novo)")
    assert entry["of_compra_ativo"] == 13.70
    assert entry["preco_ativo"] == 14.00, "preco_ativo congelou no valor antigo (ASK ausente)"
    assert entry["of_venda_ativo"] == 14.00, "of_venda_ativo congelou (ASK ausente)"
    print("  [EVIDENCIA] preco_ativo/of_venda_ativo (lado COMPRADO) tambem congelam "
          "quando o ASK nao chega.")


def cenario5_opcoes_stale():
    """Pernas PUT/CALL ausentes no reuso: premios congelam."""
    print()
    print("=" * 78)
    print("CENARIO 5 — OPCOES AUSENTES no reuso: premios de PUT/CALL congelam")
    print("=" * 78)
    db_path, source, provider, key = setup_provider()
    ativo, cod_put = key.split("|", 1)
    inst = provider._get_inst_map()[(ativo, cod_put)]

    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    for cod, ask, bid in [(cod_put, 4.40, 4.30), (inst.cod_call, 0.05, 0.04)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    cab = (150.0, 150.0)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    provider.capturar_dados_mercado()

    # Ciclo B: tudo None exceto ASK do ativo
    source.set_campo(ativo, FieldName.ASK, 13.65)
    source.set_campo(cod_put, FieldName.ASK, None)
    source.set_campo(cod_put, FieldName.BID, None)
    source.set_campo(inst.cod_call, FieldName.BID, None)
    source.set_campo(inst.cod_call, FieldName.ASK, None)
    dados_b = provider.capturar_dados_mercado()
    entry = dados_b[key]
    print(f"[ciclo B] of_compra_put={entry['of_compra_put']} "
          f"of_venda_put={entry['of_venda_put']} "
          f"of_compra_call={entry['of_compra_call']} of_venda_call={entry['of_venda_call']} "
          f"| of_compra_ativo={entry['of_compra_ativo']}")
    assert entry["of_compra_put"] == 4.30
    assert entry["of_venda_put"] == 4.40
    assert entry["of_compra_call"] == 0.04
    assert entry["of_venda_call"] == 0.05
    assert entry["of_compra_ativo"] == 0.0, (
        f"BID 13.95 > preco_ativo 13.65 -> deve ser zerado (cap Onda 1); "
        f"recebeu {entry['of_compra_ativo']}"
    )
    print("  [EVIDENCIA] 4 pernas de opcao congelam quando ausentes (sem regressao); "
          "BID do ativo acima do preco e zerado.")


def cenario6_reconexao():
    """RECONEXAO: desconectar() limpa cache da fonte; _dados_cache do provider persiste."""
    print()
    print("=" * 78)
    print("CENARIO 6 — RECONEXAO: _dados_cache nao e limpo; stale continua servido")
    print("=" * 78)
    db_path, source, provider, key = setup_provider()
    ativo, cod_put = key.split("|", 1)
    inst = provider._get_inst_map()[(ativo, cod_put)]

    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    for cod, ask, bid in [(cod_put, 4.40, 4.30), (inst.cod_call, 0.05, 0.04)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    cab = (150.0, 150.0)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    provider.capturar_dados_mercado()
    print(f"  cache pre-reconexao: of_compra_ativo={provider._dados_cache[key]['of_compra_ativo']}")

    # Fonte desconecta (limpa cache interno) e reconecta
    source.desconectar()
    source.reconectar()
    n_provider_cache = len(provider._dados_cache)
    print(f"  apos desconectar(): cache da FONTE vazio; _dados_cache do provider = {n_provider_cache} entries")

    # Pushs voltam apos reconexao: ASK do ativo novo, BID AINDA ausente; books retomam.
    # _cab_anterior do provider persistiu -> cab_mudou=False -> caminho de REUSO.
    source.set_campo(ativo, FieldName.ASK, 13.65)
    source.set_campo(ativo, FieldName.BID, None)
    for cod, ask, bid in [(cod_put, 4.45, 4.35), (inst.cod_call, 0.04, 0.03)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    dados_b = provider.capturar_dados_mercado()
    entry = dados_b[key]
    print(f"[ciclo pos-reconexao] of_compra_ativo={entry['of_compra_ativo']} "
          f"(pre_reconexao era 13.95; BID ainda ausente)")
    assert entry["of_compra_ativo"] == 0.0, "BID ausente apos reconexao nao pode ressuscitar valor antigo"
    print("  [EVIDENCIA] apos reconexao o BID ausente zera of_compra_ativo — "
          "valor antigo nao volta ao pipeline.")


def cenario7_post_loop():
    """POST-LOOP: entry da Onda 1 nao tocada e devolvida via dict(cached)."""
    print()
    print("=" * 78)
    print("CENARIO 7 — POST-LOOP: key nao tocada e servida via dict(cached)")
    print("=" * 78)
    db_path, source, provider, key = setup_provider()
    # Segunda chave (Onda 1 apenas, sem detalhes completos)
    key2 = "PETR4|PETRG124"
    provider._chaves_registradas.add(key2)
    provider._chaves_com_book.add(key2)
    provider._dados_cache[key2] = dict(_entry_ciclo_a())
    provider._dados_cache[key2]["of_compra_ativo"] = 12.40

    ativo, cod_put = key.split("|", 1)
    inst = provider._get_inst_map()[(ativo, cod_put)]
    cab = (150.0, 150.0)
    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    for cod, ask, bid in [(cod_put, 4.40, 4.30), (inst.cod_call, 0.05, 0.04)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    dados = provider.capturar_dados_mercado()

    assert key2 in dados, "key2 deveria ser servida pelo post-loop"
    assert dados[key2]["of_compra_ativo"] == 12.40
    assert dados[key2].get("stale") is not True, "post-loop continua servindo entries NAO-stale"
    print(f"  [EVIDENCIA] key {key2} (nao tocada) servida pelo post-loop com "
          f"of_compra_ativo={dados[key2]['of_compra_ativo']} (valor antigo de _dados_cache, nao-stale).")
    print(f"  entrada servida == dict(cached) (shallow copy); em_leilao forçado False: "
          f"{dados[key2]['em_leilao']}")


def cenario8_flag_stale():
    """FLAG STALE: entry entra com stale=True e NENHUM use case consome."""
    print()
    print("=" * 78)
    print("CENARIO 8 — FLAG 'stale' e decorativa")
    print("=" * 78)
    db_path, source, provider, key = setup_provider()
    ativo, cod_put = key.split("|", 1)
    inst = provider._get_inst_map()[(ativo, cod_put)]

    source.set_campo(ativo, FieldName.ASK, 14.00)
    source.set_campo(ativo, FieldName.BID, 13.95)
    for cod, ask, bid in [(cod_put, 4.40, 4.30), (inst.cod_call, 0.05, 0.04)]:
        source.set_campo(cod, FieldName.ASK, ask)
        source.set_campo(cod, FieldName.BID, bid)
    cab = (150.0, 150.0)
    source.set_campo(cod_put, FieldName.BOOK_HEADER, cab[0])
    source.set_campo(inst.cod_call, FieldName.BOOK_HEADER, cab[1])
    source.set_campo(cod_put, FieldName.STRIKE, 18.00)
    source.set_campo(inst.cod_call, FieldName.STRIKE, 18.00)
    provider.capturar_dados_mercado()

    # Ciclo B: sem ASK do ativo E sem preco em cache -> stale=True; entry e
    # invalidada do _dados_cache e NAO volta pelo post-loop (corrigido).
    provider._precos_ativo_cache.pop(ativo, None)
    provider._precos_ativo_cache_ts.pop(ativo, None)
    source.set_campo(ativo, FieldName.ASK, None)
    source.set_campo(ativo, FieldName.BID, None)
    dados_b = provider.capturar_dados_mercado()
    print(f"  key presente no resultado? {key in dados_b}")
    print(f"  _dados_cache ainda tem a key? {key in provider._dados_cache}")
    assert key not in dados_b, "entry stale nao pode voltar pelo post-loop"
    assert key not in provider._dados_cache, "entry stale deve ser invalidada do _dados_cache"
    print("  [EVIDENCIA] entry stale=TRUE e invalidada do cache e nao volta pelo post-loop.")
    # Verificar que nenhum use case lê "stale"
    import glob as _glob
    hits = []
    for f in _glob.glob("src/application/use_cases/**/*.py", recursive=True):
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if ".get(\"stale\"" in line or "[\"stale\"]" in line or "get('stale'" in line:
                    hits.append(f"{f}:{i}")
    print(f"  [EVIDENCIA] referencias a entry['stale'] em use_cases: {len(hits)}")
    for h in hits:
        print(f"    {h}")


def cenario9_gate_frescor():
    """GATE DE FRESCOR e inerte nas duas fontes."""
    print()
    print("=" * 78)
    print("CENARIO 9 — GATE DE FRESCOR INERTE (RTD sem is_stale_campo; OpenFast _campo_stale False)")
    print("=" * 78)
    db_path, source, provider, key = setup_provider()
    print(f"  RTD-like: _fonte_controla_frescor() = {provider._fonte_controla_frescor()}")
    assert provider._fonte_controla_frescor() is False
    print("  -> fonte RTD NAO expoe is_stale_campo; gate nunca roda.")

    # OpenFast-like: suporta_push=True; _campo_stale sempre False
    class FakePush(FakeSource):
        suporta_push = True
        suporta_cab_skip = False

        def is_stale_campo(self, codigo, campo):
            return True  # "forcaria" stale se fosse consultado

    source2 = FakePush()
    provider2 = MercadoDataProvider(db_path, source2)
    campo = FieldName.ASK
    print(f"  OpenFast-like: _fonte_controla_frescor() = {provider2._fonte_controla_frescor()} "
          f"(is_stale_campo EXISTE)")
    print(f"  OpenFast-like: _campo_stale('PETR4', ASK) = {provider2._campo_stale('PETR4', campo)} "
          f"(is_stale_campo retornaria True, mas suporta_push=True anula)")
    assert provider2._campo_stale("PETR4", campo) is False
    print("  -> gate nunca bloqueia: push-based tem semantica 'sem push = nao mudou'.")

    # _ler_campos com allow_stale=True para push
    source2.set_campo("PETR4", FieldName.ASK, 14.0)
    campos = source2.ler_campos("PETR4", FieldName.ASK, allow_stale=True)
    print(f"  _ler_campos(push, allow_stale=True) retorna valor mesmo marcado stale: {campos}")


def cenario10_tabela():
    """TABELA NUMERICA RESUMO."""
    print()
    print("=" * 78)
    print("CENARIO 10 — TABELA RESUMO (dados congelados)")
    print("=" * 78)
    dados = {
        "preco_ativo": 13.65,
        "strike_rtd": 18.00,
        "of_compra_put": 4.35,
        "of_venda_call": 0.04,
        "vov_put": 5000.0,
        "voc_call": 5000.0,
    }
    print(f"  {'BID usado':<34}{'receb BOX':>10}{'cond BOX':>10}{'receb SBTH':>12}{'cond SBTH':>11}")
    for rotulo, bid in [("BID real (13.60)", 13.60),
                        ("ANTES do fix: stale (13.95)", 13.95),
                        ("POS-FIX: BID ausente (0.0)", 0.0)]:
        r = calcular_vendidas(
            preco_ativo=np.array([dados["preco_ativo"]]),
            of_compra_ativo=np.array([bid]),
            of_compra_put=np.array([dados["of_compra_put"]]),
            of_venda_call=np.array([dados["of_venda_call"]]),
            strike=np.array([dados["strike_rtd"]]),
            dias=np.array([20]),
            vov_put=np.array([dados["vov_put"]]),
            voc_call=np.array([dados["voc_call"]]),
            dist_min_ativo=1.2,
            premio_risco=1.1,
            lote_box=100,
            lote_sbth=100,
            taxa_cdi=0.14,
        )
        print(f"  {rotulo:<28}{r.recebimento_box[0]:>10.4f}{str(bool(r.cond_box[0])):>10}"
              f"{r.recebimento_sbth[0]:>12.4f}{str(bool(r.cond_sbth[0])):>11}")


def main():
    entry_b, entry_a = cenario1_bid_ausente()
    cenario2_3_impacto(entry_b)
    cenario4_preco_ativo_ask()
    cenario5_opcoes_stale()
    cenario6_reconexao()
    cenario7_post_loop()
    cenario8_flag_stale()
    cenario9_gate_frescor()
    cenario10_tabela()
    print()
    print("=" * 78)
    print("RESULTADO: falso positivo de BOX/SBTH vendido eliminado; asserts validam o fix.")
    print("=" * 78)


if __name__ == "__main__":
    main()