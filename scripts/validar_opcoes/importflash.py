"""
ImportFlash: varre opcoes.net.br e atualiza o banco do SpreadHunter.

Uso:
    python scripts/validar_opcoes/importflash.py [--excluir IBOV11 ...] [--delay 1.0]
"""

import sys
import time
import subprocess
import sqlite3
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPTS_DIR.parent.parent

REAL_DB = PROJECT_DIR / "config" / "spreadhunter.db"
TEST_DB = SCRIPTS_DIR / "teste_opcoes_completo.db"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ImportFlash: atualiza base via opcoes.net.br")
    parser.add_argument("--excluir", nargs="*", default=["IBOV11"], help="Ativos a excluir")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay entre reqs (s)")
    parser.add_argument("--incluir", action="append", default=None, help="Ativo extra para incluir (pode repetir)")
    args = parser.parse_args()

    if args.incluir is None:
        args.incluir = ["VALE3"]

    t0 = time.perf_counter()

    # --- Passo 1: Varredura ---
    print("=" * 50)
    print("IMPORTFLASH - PASSO 1/2: Varrendo opcoes.net.br...")
    print("=" * 50)

    incluir_args = []
    for a in args.incluir:
        incluir_args += ["--incluir", a]

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "varrer_todos.py"),
         "--delay", str(args.delay),
         "--saida", str(TEST_DB)]
        + incluir_args,
        capture_output=False,
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        print(f"\n[ERRO] Varredura falhou (codigo {result.returncode})")
        return 1

    # --- Passo 2: Reimportar ---
    print("\n" + "=" * 50)
    print("IMPORTFLASH - PASSO 2/2: Reimportando no SpreadHunter...")
    print("=" * 50)

    excluir = args.excluir
    test_conn = sqlite3.connect(str(TEST_DB))
    rows = test_conn.execute(
        "SELECT ativo, vencimento, strike, cod_put, cod_call FROM instrumentos_base WHERE fonte='opcoes.net.br'"
    ).fetchall()
    test_conn.close()

    from collections import defaultdict
    grupos = defaultdict(lambda: {"PUT": "", "CALL": ""})
    for r in rows:
        key = (r[0], str(r[1])[:10], r[2])
        if r[3]:
            grupos[key]["PUT"] = r[3]
        if r[4]:
            grupos[key]["CALL"] = r[4]

    pares = [(a, p["PUT"], p["CALL"], v) for (a, v, s), p in grupos.items()
             if a not in excluir and p["PUT"] and p["CALL"]]

    real_conn = sqlite3.connect(str(REAL_DB))
    real_conn.row_factory = sqlite3.Row

    preservados = []
    if excluir:
        ph = ",".join("?" for _ in excluir)
        preservados = real_conn.execute(
            f"SELECT * FROM instrumentos_base WHERE ativo IN ({ph})", tuple(excluir)
        ).fetchall()

    real_conn.execute("DELETE FROM instrumentos_base")
    real_conn.commit()

    for r in preservados:
        real_conn.execute(
            "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao) VALUES (?, ?, ?, ?, ?)",
            (r["ativo"], r["cod_put"], r["cod_call"], str(r["vencimento"])[:10] if r["vencimento"] else None, r["tipo_opcao"]),
        )

    inseridas = 0
    for ativo, cod_put, cod_call, ven in pares:
        try:
            real_conn.execute(
                "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao) VALUES (?, ?, ?, ?, 'E')",
                (ativo, cod_put, cod_call, ven),
            )
            inseridas += 1
        except sqlite3.IntegrityError:
            pass

    real_conn.commit()
    total = real_conn.execute("SELECT COUNT(*) FROM instrumentos_base").fetchone()[0]
    real_conn.close()

    dur = time.perf_counter() - t0
    print(f"\n{'=' * 50}")
    print(f"IMPORTFLASH CONCLUIDO em {dur:.0f}s ({dur/60:.1f}min)")
    print(f"{'=' * 50}")
    print(f"Pares importados: {inseridas}")
    print(f"Preservados (excluidos): {len(preservados)}")
    excl_str = ", ".join(excluir) if excluir else "nenhum"
    print(f"Ativos excluidos: {excl_str}")
    print(f"Total no banco: {total} registros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
