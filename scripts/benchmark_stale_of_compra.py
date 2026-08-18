"""Benchmark simples do impacto da correcao de stale of_compra_ativo.

Mede o custo medio por ciclo de `capturar_dados_mercado()` no caminho de REUSO
da Onda 2 com N instrumentos e dados validos (sem stale). Compara o mesmo
script rodado com e sem o fix (as 3 alteracoes em mercado_data_provider.py).

Uso:
  python scripts/benchmark_stale_of_compra.py [n_instrumentos] [n_ciclos]
"""

import os
import sys
import time
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.services.market_data_source import FieldName
from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider


class FakeRTD:
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


def build(n_instr):
    tmp = tempfile.mkdtemp(prefix="bench_stale_")
    db_path = os.path.join(tmp, "bench.db")
    conn = init_db(db_path)
    conn.close()
    ParametroRepository(db_path).seed_defaults()

    repo = InstrumentoRepository(db_path)
    repo.invalidate_cache()
    venc = date.today() + timedelta(days=20)
    for i in range(n_instr):
        strike = 10.0 + i * 0.5
        s = int(strike * 10)
        repo.save(InstrumentoOpcional(
            ativo="PETR4",
            cod_put=f"PETRG{s}",
            cod_call=f"PETRH{s}",
            vencimento=venc,
            tipo_opcao=TipoOpcao.AMERICANA,
        ))

    source = FakeRTD()
    provider = MercadoDataProvider(db_path, source)
    provider._registrado = True
    provider._refresh_pos_onda1 = True
    provider._ativos_registrados = {"PETR4"}

    keys = []
    for i in range(n_instr):
        strike = 10.0 + i * 0.5
        s = int(strike * 10)
        key = f"PETR4|PETRG{s}"
        keys.append(key)
        provider._chaves_registradas.add(key)
        provider._chaves_com_book.add(key)
        provider._chaves_detalhes_completos.add(key)
        # valores do book
        cod_put = f"PETRG{s}"
        cod_call = f"PETRH{s}"
        source.set_campo(cod_put, FieldName.ASK, 0.40)
        source.set_campo(cod_put, FieldName.BID, 0.30)
        source.set_campo(cod_put, FieldName.VOL_ASK, 5000.0)
        source.set_campo(cod_put, FieldName.QTD_LAST, 3000.0)
        source.set_campo(cod_call, FieldName.BID, 0.05)
        source.set_campo(cod_call, FieldName.ASK, 0.06)
        source.set_campo(cod_call, FieldName.VOL_BID, 5000.0)
        source.set_campo(cod_call, FieldName.QTD_LAST, 3000.0)
        source.set_campo(cod_put, FieldName.BOOK_HEADER, 100.0 + i)
        source.set_campo(cod_call, FieldName.BOOK_HEADER, 100.0 + i)
        source.set_campo(cod_put, FieldName.STRIKE, strike)
        source.set_campo(cod_call, FieldName.STRIKE, strike)
        source.set_status(cod_put, "aberto")
        source.set_status(cod_call, "aberto")

    source.set_campo("PETR4", FieldName.ASK, 14.00)
    source.set_campo("PETR4", FieldName.BID, 13.95)
    source.set_status("PETR4", "aberto")
    return provider, source, keys


def main():
    n_instr = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    n_ciclos = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    provider, source, keys = build(n_instr)

    # ciclo A: caminho fresh (popula _dados_cache e _cab_anterior)
    provider.capturar_dados_mercado()
    assert len(provider._dados_cache) == n_instr, len(provider._dados_cache)

    # ciclo B..N: reuso (dados estaveis, BID valido)
    tempos = []
    for _ in range(n_ciclos):
        t0 = time.perf_counter()
        dados = provider.capturar_dados_mercado()
        tempos.append(time.perf_counter() - t0)
        assert len(dados) == n_instr, len(dados)

    med = sum(tempos) / len(tempos)
    p95 = sorted(tempos)[int(len(tempos) * 0.95) - 1]
    print(f"instrumentos={n_instr} ciclos_reuso={n_ciclos}")
    print(f"ciclo_medio={med * 1000:.3f} ms  p95={p95 * 1000:.3f} ms  "
          f"us_por_instruto={(med / n_instr) * 1e6:.2f}")


if __name__ == "__main__":
    main()