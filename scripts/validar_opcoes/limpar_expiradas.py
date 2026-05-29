"""
Deleta do SpreadHunter todas as series com vencimento ate a data especificada.

Uso:
    python scripts/validar_opcoes/limpar_expiradas.py 2026-05-29
    python scripts/validar_opcoes/limpar_expiradas.py 2026-05-29 --dry-run
"""

import sys
import sqlite3
from pathlib import Path
from datetime import date

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("corte", help="Data de corte (AAAA-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra, nao altera")
    args = parser.parse_args()

    conn = sqlite3.connect(str(REAL_DB))

    contar = conn.execute(
        "SELECT COUNT(*) FROM instrumentos_base WHERE vencimento <= ?",
        (args.corte,),
    ).fetchone()[0]

    print(f"Data de corte: {args.corte}")
    print(f"Registros a deletar: {contar}")

    if contar == 0:
        print("Nada a fazer.")
        return 0

    if args.dry_run:
        print("[Dry-run] Nenhuma alteracao foi feita.")
        return 0

    print(f"\nDeseja deletar {contar} registros? (s/N): ", end="", flush=True)
    resp = sys.stdin.readline().strip().lower()
    if resp != "s":
        print("Cancelado.")
        return 0

    conn.execute("DELETE FROM instrumentos_base WHERE vencimento <= ?", (args.corte,))
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM instrumentos_base").fetchone()[0]
    conn.close()

    print(f"Deletados: {contar}")
    print(f"Total apos operacao: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
