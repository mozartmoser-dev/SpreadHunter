"""
Varredura completa: busca opções de TODOS os ativos do SpreadHunter via opcoes.net.br.

Uso:
    python scripts/validar_opcoes/varrer_todos.py
    python scripts/validar_opcoes/varrer_todos.py --delay 1.0 --saida dados_completos.db
"""

import sys
import time
import sqlite3
from pathlib import Path
import fetch_opcoes as fop

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes_completo.db"


def listar_ativos(db_path, extras: list[str] | None = None) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute("SELECT DISTINCT ativo FROM instrumentos_base ORDER BY ativo")
    ativos = {r[0] for r in cur.fetchall()}
    conn.close()
    if extras:
        for a in extras:
            ativos.add(a.upper())
    return sorted(ativos)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Varredura completa de todos os ativos")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay entre CALL e PUT do mesmo ativo (s)")
    parser.add_argument("--saida", default=str(TEST_DB), help="Arquivo SQLite de saída")
    parser.add_argument("--incluir", action="append", default=None, help="Ativo extra para incluir (pode repetir)")
    args = parser.parse_args()

    ativos = listar_ativos(REAL_DB, args.incluir)
    total = len(ativos)
    print(f"Ativos a processar: {total}")
    print(f"Delay entre requisições: {args.delay}s")
    print(f"Saída: {Path(args.saida).resolve()}\n")

    # Inicializa banco de saída (limpa execução anterior)
    conn = fop.init_test_db(Path(args.saida))
    conn.execute("DELETE FROM instrumentos_base WHERE fonte = 'opcoes.net.br'")
    conn.commit()

    session = fop._session()
    ok = erro = 0
    pulados = 0
    total_opcoes = 0
    inicio = time.perf_counter()

    for idx, ativo in enumerate(ativos, 1):
        t0 = time.perf_counter()

        calls = fop.fetch_matriz(ativo, "CALL", session)
        time.sleep(args.delay)
        puts = fop.fetch_matriz(ativo, "PUT", session)

        combinados = calls + puts
        if not combinados:
            pulados += 1
            t = time.perf_counter() - t0
            print(f"[{idx:>3d}/{total}] {ativo:<10s} pulado (0 opções)  {t:.1f}s")
            continue

        # Salva no banco incremental
        inseridos = 0
        for r in combinados:
            col = "cod_put" if r["tipo"] == "PUT" else "cod_call"
            try:
                conn.execute(
                    f"INSERT INTO instrumentos_base (ativo, vencimento, tipo_opcao, {col}, strike, fonte) "
                    f"VALUES (?, ?, ?, ?, ?, 'opcoes.net.br')",
                    (r["ativo"], r["vencimento"], r["tipo"], r["ticker"], r["strike"]),
                )
                inseridos += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()

        total_opcoes += inseridos
        ok += 1
        t = time.perf_counter() - t0
        puts_c = sum(1 for r in combinados if r["tipo"] == "PUT")
        calls_c = sum(1 for r in combinados if r["tipo"] == "CALL")
        print(f"[{idx:>3d}/{total}] {ativo:<10s} OK  PUT={puts_c:>4d} CALL={calls_c:>4d}  {t:.1f}s")

    session.close()

    # Estatísticas finais
    dur = time.perf_counter() - inicio
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resumo_varredura (
            executado_em TEXT,
            total_ativos INTEGER,
            sucesso INTEGER,
            pulados INTEGER,
            total_opcoes INTEGER,
            duracao_seg REAL
        )
    """)
    conn.execute(
        "INSERT INTO resumo_varredura VALUES (datetime('now'), ?, ?, ?, ?, ?)",
        (total, ok, pulados, total_opcoes, dur),
    )
    conn.commit()
    conn.close()

    # Resumo
    puts_total = 0
    calls_total = 0
    conn = fop.init_test_db(Path(args.saida))
    cur = conn.execute("SELECT tipo_opcao, COUNT(*) FROM instrumentos_base WHERE fonte='opcoes.net.br' GROUP BY tipo_opcao")
    for tipo, cnt in cur.fetchall():
        if tipo == "PUT":
            puts_total = cnt
        elif tipo == "CALL":
            calls_total = cnt
    conn.close()

    print(f"\n{'='*50}")
    print(f"VARREDURA CONCLUÍDA")
    print(f"{'='*50}")
    print(f"Tempo total: {dur:.1f}s ({dur/60:.1f}min)")
    print(f"Ativos processados: {ok}/{total}")
    print(f"Pulados (sem opções): {pulados}")
    print(f"Total de opções salvas: {total_opcoes}")
    print(f"  PUTs : {puts_total}")
    print(f"  CALLs: {calls_total}")
    print(f"Média: {total_opcoes/ok:.0f} opções/ativo" if ok else "")
    print(f"Média: {dur/ok:.1f}s/ativo" if ok else "")

    return 0


if __name__ == "__main__":
    sys.exit(main())
