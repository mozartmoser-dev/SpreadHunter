"""
Importa novos tickers do opcoes.net.br para o SpreadHunter.

Agrupa PUTs e CALLs por (ativo, vencimento, strike) e insere
apenas pares onde pelo menos um dos tickers e inedito.
"""

import sys
import sqlite3
from pathlib import Path
from collections import defaultdict

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes_completo.db"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--forcar", action="store_true")
    args = parser.parse_args()

    real_conn = sqlite3.connect(str(REAL_DB))
    test_conn = sqlite3.connect(str(TEST_DB))
    real_conn.row_factory = sqlite3.Row
    test_conn.row_factory = sqlite3.Row

    # --- 1. Tickers ja existentes no SH ---
    existentes = set()
    for r in real_conn.execute("SELECT cod_put, cod_call FROM instrumentos_base"):
        if r["cod_put"]:
            existentes.add(r["cod_put"])
        if r["cod_call"]:
            existentes.add(r["cod_call"])
    print(f"Tickers ja existentes no SH: {len(existentes)}")

    # --- 2. Agrupar test DB por (ativo, vencimento, strike) ---
    test_rows = test_conn.execute(
        "SELECT ativo, vencimento, strike, cod_put, cod_call FROM instrumentos_base WHERE fonte='opcoes.net.br'"
    ).fetchall()

    grupos = defaultdict(lambda: {"PUT": "", "CALL": ""})
    for r in test_rows:
        key = (r["ativo"], str(r["vencimento"])[:10], r["strike"])
        if r["cod_put"]:
            grupos[key]["PUT"] = r["cod_put"]
        if r["cod_call"]:
            grupos[key]["CALL"] = r["cod_call"]

    # --- 3. Filtrar apenas pares novos ---
    insercoes = []
    for (ativo, ven, strike), pares in sorted(grupos.items()):
        cod_put = pares["PUT"]
        cod_call = pares["CALL"]
        if not cod_put and not cod_call:
            continue
        if cod_put in existentes or cod_call in existentes:
            continue
        insercoes.append((ativo, cod_put, cod_call, ven, strike))

    print(f"Novos pares a inserir: {len(insercoes)}")

    if not insercoes:
        print("Nada a fazer.")
        return 0

    if args.dry_run:
        print(f"\nTop 10 ativos com novas insercoes:")
        cont = defaultdict(int)
        for ativo, _, _, _, _ in insercoes:
            cont[ativo] += 1
        for ativo, cnt in sorted(cont.items(), key=lambda x: -x[1])[:10]:
            print(f"  {ativo:<10s} {cnt:>5d} novos pares")
        return 0

    if not args.forcar:
        print(f"\nConfirmar insercao de {len(insercoes)} pares? (s/N): ", end="", flush=True)
        resp = sys.stdin.readline().strip().lower()
        if resp != "s":
            print("Cancelado.")
            return 0

    # --- 4. Inserir no SH ---
    inseridas = 0
    for ativo, cod_put, cod_call, ven, strike in insercoes:
        try:
            real_conn.execute(
                "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao) "
                "VALUES (?, ?, ?, ?, 'E')",
                (ativo, cod_put, cod_call, ven),
            )
            inseridas += 1
        except sqlite3.IntegrityError:
            pass

    real_conn.commit()

    total = real_conn.execute("SELECT COUNT(*) FROM instrumentos_base").fetchone()[0]
    real_conn.close()
    test_conn.close()

    print(f"\nInseridos: {inseridas} novos pares")
    print(f"Total do SH apos operacao: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
