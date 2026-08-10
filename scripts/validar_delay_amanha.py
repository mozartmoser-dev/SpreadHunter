"""Validação do delay OpenFast (T1-T6) fora da interface.

Uso: python scripts/validar_delay_amanha.py [--segundos 90] [--ativos VALE3,PETR4]

Requisitos: FastTrade aberto em 127.0.0.1:557 (mercado em horário B3).
Mercado fechado => o socket responde mas sem atualizações novas (delay infra).
Mercado aberto  => mede o delay real de ponta a ponta (T1->T6).

Imprime relatório comparativo com os números de pregão de 10/08/2026:
  T1->T3 recv->cache      : 1.5ms med / 154ms p95
  T3->T4 cache->refresh   : 3.7s  med / 11.6s p95
  monitor_geral_captura   : ~1.2-1.5s inicio (degradando até 15s)
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SH_TRACE_CHAVE_ANTERIOR = os.environ.get("SH_TRACE_CHAVE")


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida o delay OpenFast T1-T6 sem UI.")
    parser.add_argument("--segundos", type=int, default=90, help="duração da medição (s)")
    parser.add_argument("--ativos", default="VALE3,PETR4", help="ativos a assinar")
    args = parser.parse_args()

    os.environ["SH_TRACE_LIMIT_S"] = "0"
    os.environ["SH_TRACE_CHAVE"] = "*"

    from src.domain.services.market_data_source import criar_data_source, FieldName
    from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider

    import sqlite3
    from src.infrastructure.persistence.database import get_db_path
    db = get_db_path()
    ativos = [a.strip().upper() for a in args.ativos.split(",") if a.strip()]

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(ativos))
        rows = conn.execute(
            f"SELECT cod_put, cod_call, ativo, vencimento, tipo_opcao, strike "
            f"FROM instrumentos_base WHERE UPPER(ativo) IN ({placeholders}) "
            f"ORDER BY vencimento LIMIT 60",
            ativos,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("Nenhum instrumento encontrado no banco para os ativos informados.")
        sys.exit(1)

    print(f"Dados: {len(rows)} instrumentos em {ativos}")
    print(f"DB: {db}")
    print("Conectando no FastTrade (127.0.0.1:557)...")

    rtd = criar_data_source("openfast")
    if not rtd.disponivel:
        print("ERRO: FastTrade não respondeu. Abra o FastTrade/OpenFast e rode de novo.")
        sys.exit(1)
    print(f"Conectado. feed={rtd.feed_state}")

    provider = MercadoDataProvider(db, rtd)

    # Assina os ativos (preços base) e os pares
    for a in ativos:
        rtd.registrar_topico(a, FieldName.ASK)
        rtd.registrar_topico(a, FieldName.BID)
    for r in rows:
        rtd.registrar_topico(r["cod_put"], FieldName.ASK)
        rtd.registrar_topico(r["cod_put"], FieldName.BID)
        rtd.registrar_topico(r["cod_call"], FieldName.ASK)
        rtd.registrar_topico(r["cod_call"], FieldName.BID)

    # Aguarda o primeiro burst pós assinatura
    print("Aguardando burst inicial (5s)...")
    time.sleep(5.0)
    rtd.refresh(0)

    tempos_captura: list[float] = []
    tempos_total: list[float] = []
    n_ciclos = 0
    t_fim = time.time() + args.segundos

    print(f"Medindo {args.segundos}s de ciclos de captura...")
    while time.time() < t_fim:
        t0 = time.perf_counter()
        dados = provider.capturar_dados_mercado()
        dt = time.perf_counter() - t0
        tempos_captura.append(dt)
        n_ciclos += 1
        print(f"  ciclo {n_ciclos}: captura={dt*1000:7.1f}ms  entradas={len(dados)}")
        time.sleep(0.5)

    print()
    print("=" * 62)
    print("RELATÓRIO DE DELAY (T1-T6)")
    print("=" * 62)
    if tempos_captura:
        med = statistics.median(tempos_captura)
        p95 = sorted(tempos_captura)[int(len(tempos_captura) * 0.95)]
        print(f"capturar_dados_mercado: n={len(tempos_captura)} "
              f"mediana={med*1000:.0f}ms p95={p95*1000:.0f}ms "
              f"max={max(tempos_captura)*1000:.0f}ms")
        print(f"  (referência 10/08: inicio ~1.3s, degradando até 15s)")
        print(f"  ALVO pós-fix: manter mediana < ~1.0-1.2s sem degradar")

    # Merge: retira o trace (força flush)
    try:
        from src.infrastructure.providers import stale_trace
        stale_trace._flush()
    except Exception:
        pass

    log = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "logs", "stale_trace.log")
    with open(log, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        offset_inicio = f.tell()
    if os.path.exists(log):
        _relatorio_t1_t4(log, offset_inicio)

    rtd.desconectar()
    print("Desconectado. Fim da validação.")


def _relatorio_t1_t4(path: str, offset_inicio: int = 0) -> None:
    t1: dict[tuple[str, str], float] = {}
    t3: dict[tuple[str, str], float] = {}
    t4: dict[tuple[str, str], float] = {}
    d13: list[float] = []
    d34: list[float] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        if offset_inicio > 0:
            f.seek(offset_inicio, 0)
        for line in f:
            p = line.rstrip("\n").split("|")
            tag = p[0]
            if tag == "T1":
                t1[(p[4], p[5])] = float(p[3])
            elif tag == "T3":
                ch = (p[3], p[4])
                ts = float(p[2])
                if ch in t1:
                    d13.append(ts - t1[ch])
                t3[ch] = ts
            elif tag == "T4":
                ch = (p[3], p[4])
                ts = float(p[2])
                if ch in t3:
                    d34.append(ts - t3[ch])
                t4[ch] = ts

    def resumo(vals: list[float]) -> str:
        if not vals:
            return "n=0 (sem dados)"
        vals.sort()
        med = statistics.median(vals)
        p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
        mx = vals[-1]
        return f"n={len(vals)} mediana={med*1000:.1f}ms p95={p95*1000:.1f}ms max={mx*1000:.1f}ms"

    print()
    print("TRACE T1-T4 (do stale_trace.log desta execução):")
    print(f"  T1->T3 recv->cache     : {resumo(d13)}")
    print(f"  T3->T4 cache->refresh  : {resumo(d34)}")
    print("  (referência 10/08: T1->T3 1.5ms med / 154ms p95 | T3->T4 3.7s med / 11.6s p95)")
    if d34:
        med34 = statistics.median(d34)
        if med34 > 2.0:
            print("  >> AVISO: T3->T4 alto. O ciclo de varredura ainda segura a entrega.")
        else:
            print("  >> T3->T4 abaixo de 2s => entrega acompanha o ciclo.")


if __name__ == "__main__":
    main()