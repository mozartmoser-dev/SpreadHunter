"""
Compara dados do SpreadHunter com dados do opcoes.net.br para um ativo.

Uso:
    python scripts/validar_opcoes/comparar.py PETR4
    python scripts/validar_opcoes/comparar.py PETR4 --detalhado
"""

import sys
import argparse
import sqlite3
from pathlib import Path

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes.db"


def conectar(path):
    if not path.exists():
        print(f"ERRO: banco não encontrado: {path}")
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def main():
    parser = argparse.ArgumentParser(description="Compara base SpreadHunter vs opcoes.net.br")
    parser.add_argument("ativo", help="Código do ativo (ex: PETR4)")
    parser.add_argument("--detalhado", action="store_true", help="Mostra divergências detalhadas")
    args = parser.parse_args()

    ativo = args.ativo.upper()

    real_conn = conectar(REAL_DB)
    test_conn = conectar(TEST_DB)

    if not real_conn or not test_conn:
        return 1

    # --- Lê dados do SpreadHunter ---
    real_rows = real_conn.execute(
        """SELECT DISTINCT ativo, cod_put, cod_call, vencimento, tipo_opcao
           FROM instrumentos_base WHERE ativo = ?""", (ativo,)
    ).fetchall()

    # --- Lê dados do opcoes.net.br ---
    test_rows = test_conn.execute(
        """SELECT ativo, cod_put, cod_call, vencimento, tipo_opcao, strike
           FROM instrumentos_base WHERE ativo = ?""", (ativo,)
    ).fetchall()

    real_conn.close()
    test_conn.close()

    # Monta conjuntos
    def tickers_unicos(rows):
        result = set()
        for r in rows:
            for col in ("cod_put", "cod_call"):
                val = r[col]
                if val:
                    result.add(val)
        return result

    def pares_unicos(rows):
        result = set()
        for r in rows:
            cod_put = r["cod_put"] or ""
            cod_call = r["cod_call"] or ""
            ven = r["vencimento"]
            key = (cod_put, cod_call, str(ven)[:10])
            result.add(key)
        return result

    real_tickers = tickers_unicos(real_rows)
    test_tickers = tickers_unicos(test_rows)
    real_pares = pares_unicos(real_rows)
    test_pares = pares_unicos(test_rows)

    # Estatísticas básicas
    puts_real = sum(1 for r in real_rows if r["tipo_opcao"] == "PUT" or "P" in (r["cod_put"] or ""))
    calls_real = len(real_rows) - puts_real if puts_real < len(real_rows) else len(real_rows)

    puts_test = sum(1 for r in test_rows if r["tipo_opcao"] == "PUT")
    calls_test = sum(1 for r in test_rows if r["tipo_opcao"] == "CALL")

    print(f"=== Comparação: {ativo} ===")
    print(f"{'':30s} {'SpreadHunter':>15s} {'opcoes.net.br':>15s}")
    print(f"{'Total registros':30s} {len(real_rows):>15d} {len(test_rows):>15d}")
    print(f"{'PUTs':30s} {puts_real:>15d} {puts_test:>15d}")
    print(f"{'CALLs':30s} {calls_real:>15d} {calls_test:>15d}")
    print(f"{'Tickers únicos':30s} {len(real_tickers):>15d} {len(test_tickers):>15d}")
    print(f"{'Pares (cod_put, cod_call, ven)':30s} {len(real_pares):>15d} {len(test_pares):>15d}")

    # Divergências
    so_no_real = real_tickers - test_tickers
    so_no_test = test_tickers - real_tickers

    print(f"\n=== Tickers APENAS no SpreadHunter (ausentes no opcoes.net.br): {len(so_no_real)} ===")
    for t in sorted(so_no_real)[:20]:
        print(f"  {t}")
    if len(so_no_real) > 20:
        print(f"  ... e mais {len(so_no_real) - 20}")

    print(f"\n=== Tickers APENAS no opcoes.net.br (ausentes no SpreadHunter): {len(so_no_test)} ===")
    for t in sorted(so_no_test)[:20]:
        print(f"  {t}")
    if len(so_no_test) > 20:
        print(f"  ... e mais {len(so_no_test) - 20}")

    # Tickers em comum (podem ter diferença de strike)
    tickers_comuns = real_tickers & test_tickers
    print(f"\n=== Tickers em comum: {len(tickers_comuns)} ===")

    # Compara pares (cod_put, cod_call, vencimento)
    pares_comuns = real_pares & test_pares
    apenas_real = real_pares - test_pares
    apenas_test = test_pares - real_pares
    print(f"  Pares em comum: {len(pares_comuns)}")
    print(f"  Pares só no SpreadHunter: {len(apenas_real)}")
    print(f"  Pares só no opcoes.net.br: {len(apenas_test)}")

    if args.detalhado:
        print(f"\n--- Detalhamento de pares só no SpreadHunter ---")
        for par in sorted(apenas_real)[:15]:
            cp, cc, ven = par
            print(f"  PUT={cp} CALL={cc} ven={ven}")
        if len(apenas_real) > 15:
            print(f"  ... e mais {len(apenas_real) - 15}")

        print(f"\n--- Detalhamento de pares só no opcoes.net.br ---")
        for par in sorted(apenas_test)[:15]:
            cp, cc, ven = par
            print(f"  PUT={cp} CALL={cc} ven={ven}")
        if len(apenas_test) > 15:
            print(f"  ... e mais {len(apenas_test) - 15}")

    # Resumo
    pct_cobertura = len(tickers_comuns) / len(test_tickers) * 100 if test_tickers else 0
    print(f"\n=== RESUMO ===")
    print(f"Cobertura do opcoes.net.br nos dados do SpreadHunter: {pct_cobertura:.1f}%")
    if so_no_real:
        print(f"⚠️  {len(so_no_real)} tickers existem no SpreadHunter mas NÃO foram encontrados no opcoes.net.br")
    if so_no_test:
        print(f"ℹ️  {len(so_no_test)} tickers do opcoes.net.br NÃO estão no SpreadHunter")
    if pct_cobertura > 95:
        print("✅ Base do SpreadHunter está atualizada com a fonte pública!")
    elif pct_cobertura > 80:
        print("⚠️  Base com pequenas diferenças - verificar")
    else:
        print("❌ Diferenças significativas - vale investigar")

    return 0


if __name__ == "__main__":
    sys.exit(main())
