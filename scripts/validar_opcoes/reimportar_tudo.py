"""
Limpa e reimporta toda a base de opcoes do zero a partir do opcoes.net.br.

Uso:
    python scripts/validar_opcoes/reimportar_tudo.py [--excluir IBOV11 PETR4 ...]
"""

import sys
import sqlite3
from pathlib import Path
from collections import defaultdict

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes_completo.db"
EXCLUIR_PADRAO = ["IBOV11"]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--excluir", nargs="*", default=EXCLUIR_PADRAO,
                        help="Ativos para excluir da importacao")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    excluir = set(a.upper() for a in args.excluir)

    test_conn = sqlite3.connect(str(TEST_DB))
    test_conn.row_factory = sqlite3.Row

    # Agrupa por (ativo, vencimento, strike) -> pares PUT/CALL
    rows = test_conn.execute(
        "SELECT ativo, vencimento, strike, cod_put, cod_call FROM instrumentos_base WHERE fonte='opcoes.net.br'"
    ).fetchall()
    test_conn.close()

    grupos = defaultdict(lambda: {"PUT": "", "CALL": ""})
    for r in rows:
        key = (r["ativo"], str(r["vencimento"])[:10], r["strike"])
        if r["cod_put"]:
            grupos[key]["PUT"] = r["cod_put"]
        if r["cod_call"]:
            grupos[key]["CALL"] = r["cod_call"]

    pares = []
    pulados_excluir = 0
    for (ativo, ven, strike), p in grupos.items():
        if ativo in excluir:
            pulados_excluir += 1
            continue
        if p["PUT"] and p["CALL"]:
            pares.append((ativo, p["PUT"], p["CALL"], ven))

    print(f"Total de pares no site: {len(grupos)}")
    print(f"Pulados (excluidos: {', '.join(sorted(excluir)) if excluir else 'nenhum'}): {pulados_excluir}")
    print(f"Pares a importar: {len(pares)}")

    if args.dry_run:
        print("\n[Dry-run] Nenhuma alteracao foi feita.")
        return 0

    print(f"\nIsso vai SUBSTITUIR todos os dados de instrumentos_base. Confirma? (s/N): ", end="", flush=True)
    resp = sys.stdin.readline().strip().lower()
    if resp != "s":
        print("Cancelado.")
        return 0

    real_conn = sqlite3.connect(str(REAL_DB))
    real_conn.row_factory = sqlite3.Row

    # Preserva registros dos ativos excluidos antes de limpar
    preservados = []
    if excluir:
        placeholders = ",".join("?" for _ in excluir)
        preservados = real_conn.execute(
            f"SELECT * FROM instrumentos_base WHERE ativo IN ({placeholders})",
            tuple(sorted(excluir)),
        ).fetchall()

    real_conn.execute("DELETE FROM instrumentos_base")
    real_conn.commit()

    # Reinsere ativos excluidos (ex: IBOV11)
    for r in preservados:
        real_conn.execute(
            "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao) "
            "VALUES (?, ?, ?, ?, ?)",
            (r["ativo"], r["cod_put"], r["cod_call"], str(r["vencimento"])[:10] if r["vencimento"] else None, r["tipo_opcao"]),
        )

    inseridas = 0
    for ativo, cod_put, cod_call, ven in pares:
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

    preservados_str = f" (mais {len(preservados)} preservados de {', '.join(sorted(excluir))})" if preservados else ""
    print(f"\nDeletados: todos os registros antigos")
    print(f"Inseridos: {inseridas} pares do site")
    print(f"Preservados: {len(preservados)} registros de ativos excluidos{preservados_str}")
    print(f"Total final: {total} registros")
    return 0


if __name__ == "__main__":
    sys.exit(main())
