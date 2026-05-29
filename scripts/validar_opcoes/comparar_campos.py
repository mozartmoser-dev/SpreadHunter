"""
Compara campo-a-campo tickers que existem em ambas as bases.

Uso:
    python scripts/validar_opcoes/comparar_campos.py PETR4
"""

import sys
import argparse
import sqlite3
from pathlib import Path

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes.db"


def conectar(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ativo", help="Código do ativo (ex: PETR4)")
    args = parser.parse_args()
    ativo = args.ativo.upper()

    real_conn = conectar(REAL_DB)
    test_conn = conectar(TEST_DB)

    # Mapa do SpreadHunter: ticker -> { vencimento, tipo (PUT/CALL), par }
    real_map = {}
    for r in real_conn.execute(
        "SELECT * FROM instrumentos_base WHERE ativo = ?", (ativo,)
    ).fetchall():
        ven = str(r["vencimento"])[:10] if r["vencimento"] else ""
        for col, tipo in [("cod_put", "PUT"), ("cod_call", "CALL")]:
            ticker = r[col]
            if ticker:
                real_map[ticker] = {
                    "vencimento": ven,
                    "tipo": tipo,
                }

    # Mapa do opcoes.net.br: ticker -> { vencimento, tipo, strike }
    test_map = {}
    for r in test_conn.execute(
        "SELECT * FROM instrumentos_base WHERE ativo = ?", (ativo,)
    ).fetchall():
        ven = str(r["vencimento"])[:10] if r["vencimento"] else ""
        for col, tipo in [("cod_put", "PUT"), ("cod_call", "CALL")]:
            ticker = r[col]
            if ticker:
                test_map[ticker] = {
                    "vencimento": ven,
                    "tipo": tipo,
                    "strike": r["strike"] or 0,
                }

    real_conn.close()
    test_conn.close()

    # Tickers em comum
    comuns = sorted(set(real_map.keys()) & set(test_map.keys()))
    apenas_real = sorted(set(real_map.keys()) - set(test_map.keys()))
    apenas_test = sorted(set(test_map.keys()) - set(real_map.keys()))

    print(f"=== Comparação campo-a-campo: {ativo} ===")
    print(f"Tickers em comum: {len(comuns)}")
    print(f"Tickers só no SH: {len(apenas_real)}")
    print(f"Tickers só no site: {len(apenas_test)}\n")

    # Compara campos dos tickers em comum
    divergencias_tipo = []
    divergencias_venc = []
    ok = 0

    for ticker in comuns:
        r = real_map[ticker]
        t = test_map[ticker]
        tipo_real = r["tipo"].upper().strip()
        tipo_test = t["tipo"].upper().strip()

        if tipo_real != tipo_test:
            divergencias_tipo.append((ticker, tipo_real, tipo_test))
            continue

        if r["vencimento"] != t["vencimento"]:
            divergencias_venc.append((ticker, r["vencimento"], t["vencimento"], r["tipo"]))
            continue

        ok += 1

    print(f"Campos OK (tipo + vencimento batem): {ok}/{len(comuns)}")

    if divergencias_tipo:
        print(f"\n=== DIVERGÊNCIAS DE TIPO ({len(divergencias_tipo)}) ===")
        print("  Ticker       SH-tipo  Site-tipo")
        for ticker, tr, tt in divergencias_tipo[:15]:
            print(f"  {ticker:<12s} {tr:<7s} {tt:<7s}")
        if len(divergencias_tipo) > 15:
            print(f"  ... e mais {len(divergencias_tipo) - 15}")

    if divergencias_venc:
        print(f"\n=== DIVERGÊNCIAS DE VENCIMENTO ({len(divergencias_venc)}) ===")
        print("  Ticker       SH-venc    Site-venc  Tipo")
        for ticker, rv, tv, tipo in divergencias_venc[:15]:
            print(f"  {ticker:<12s} {rv:<10s} {tv:<10s} {tipo}")
        if len(divergencias_venc) > 15:
            print(f"  ... e mais {len(divergencias_venc) - 15}")

    # Sumário
    print(f"\n=== RESUMO ===")
    if divergencias_tipo or divergencias_venc:
        print(f"DIVERGÊNCIAS ENCONTRADAS:")
        print(f"  Tipo: {len(divergencias_tipo)} tickers")
        print(f"  Vencimento: {len(divergencias_venc)} tickers")
    else:
        print("✅ TODOS os campos conferem entre as duas bases!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
