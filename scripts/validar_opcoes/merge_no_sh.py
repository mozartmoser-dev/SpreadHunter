"""
Limpa séries próximas ao vencimento e mescla dados novos do opcoes.net.br
no banco do SpreadHunter.

Uso:
    python scripts/validar_opcoes/merge_no_sh.py

Flags:
    --dry-run   : apenas mostra o que seria feito, sem alterar nada
    --forcar    : executa sem pedir confirmação
"""

import sys
import sqlite3
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes_completo.db"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra, nao altera")
    parser.add_argument("--forcar", action="store_true", help="Executa sem confirmar")
    args = parser.parse_args()

    hoje = date.today()
    corte = hoje + timedelta(days=4)  # 2026-05-29
    corte_str = corte.isoformat()

    real_conn = sqlite3.connect(str(REAL_DB))
    test_conn = sqlite3.connect(str(TEST_DB))
    real_conn.row_factory = sqlite3.Row
    test_conn.row_factory = sqlite3.Row

    # --- 1. Contar o que será deletado ---
    a_deletar = real_conn.execute(
        "SELECT COUNT(*) FROM instrumentos_base WHERE vencimento <= ?",
        (corte_str,),
    ).fetchone()[0]

    print(f"Data de corte: {corte_str} (daqui a 4 dias, {corte.strftime('%d/%m/%Y')})")
    print(f"Registros a DELETAR do SpreadHunter: {a_deletar}")

    # --- 2. Contar o que será inserido ---
    # Agrupa test DB por (ativo, vencimento, strike) para formar pares PUT/CALL
    test_rows = test_conn.execute(
        "SELECT ativo, vencimento, strike, tipo_opcao, cod_put, cod_call "
        "FROM instrumentos_base WHERE fonte='opcoes.net.br'"
    ).fetchall()

    grupos = defaultdict(lambda: {"PUT": "", "CALL": ""})
    for r in test_rows:
        strike = r["strike"]
        tipo = r["tipo_opcao"]
        ticker = r["cod_put"] or r["cod_call"]
        if ticker and tipo in ("PUT", "CALL"):
            key = (r["ativo"], str(r["vencimento"])[:10], strike)
            grupos[key][tipo] = ticker

    # Tickers já existentes no SH
    existentes = set()
    for r in real_conn.execute("SELECT cod_put, cod_call FROM instrumentos_base"):
        if r["cod_put"]:
            existentes.add(r["cod_put"])
        if r["cod_call"]:
            existentes.add(r["cod_call"])

    novos = 0
    novos_por_ativo = defaultdict(int)
    insercoes = []

    for (ativo, ven, strike), pares in sorted(grupos.items()):
        cod_put = pares["PUT"]
        cod_call = pares["CALL"]
        if not cod_put or not cod_call:
            continue
        if cod_put in existentes or cod_call in existentes:
            continue
        insercoes.append((ativo, cod_put, cod_call, ven))
        novos += 1
        novos_por_ativo[ativo] += 1

    print(f"Novos pares a INSERIR: {novos}")

    if args.dry_run:
        print(f"\n[Dry-run] Nenhuma alteracao foi feita.")
        if novos:
            print(f"\nTop 10 ativos com novos pares:")
            for ativo, cnt in sorted(novos_por_ativo.items(), key=lambda x: -x[1])[:10]:
                print(f"  {ativo:<10s} {cnt:>5d} novos pares")
        return 0

    # --- 3. Executar ---
    if not args.forcar:
        print(f"\nDeseja executar? (s/N): ", end="", flush=True)
        resp = sys.stdin.readline().strip().lower()
        if resp != "s":
            print("Cancelado.")
            return 0

    # Deleta antigas (vencimento <= corte)
    real_conn.execute("DELETE FROM instrumentos_base WHERE vencimento <= ?", (corte_str,))
    real_conn.commit()

    # Insere novas (apenas pares com tickers ineditos)
    inseridas = 0
    for ativo, cod_put, cod_call, ven in insercoes:
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

    total_final = real_conn.execute("SELECT COUNT(*) FROM instrumentos_base").fetchone()[0]
    real_conn.close()
    test_conn.close()

    print(f"\nConcluido!")
    print(f"  Deletados: {a_deletar}")
    print(f"  Inseridos: {inseridas}")
    print(f"  Total apos operacao: {total_final}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
