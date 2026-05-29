"""
Análise detalhada dos tickers que estão no opcoes.net.br mas não no SpreadHunter.

Uso:
    python scripts/validar_opcoes/analisar_divergencias.py PETR4
"""

import sys
import argparse
import sqlite3
from pathlib import Path
from collections import Counter, defaultdict
from datetime import date, datetime

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes.db"


def conectar(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def extrair_serie(ticker):
    """Extrai letra-série do ticker: PETRH694 -> H, PETRE359W5 -> E"""
    base = ticker[4:]  # remove "PETR"
    letras = ""
    for ch in base:
        if ch.isalpha() or ch in "W":
            letras += ch
        else:
            break
    return letras


def extrair_strike_num(ticker):
    """Extrai número do strike do ticker: PETRH694 -> 6.94"""
    base = ticker[4:]
    nums = ""
    for ch in base:
        if ch.isdigit():
            nums += ch
    if len(nums) <= 2:
        return 0
    return float(nums[:-2] + "." + nums[-2:])


def classificar_serie(serie):
    """Classifica o tipo de série baseado nas letras"""
    serie = serie.upper()
    if "W" in serie:
        return "Semanal (W)"
    if len(serie) >= 2 and serie[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and serie[1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        return "Série dupla"
    return f"Série {serie}"


SERIE_MES = {
    "A": "Jan", "B": "Fev", "C": "Mar", "D": "Abr",
    "E": "Mai", "F": "Jun", "G": "Jul", "H": "Ago",
    "I": "Set", "J": "Out", "K": "Nov", "L": "Dez",
    "M": "Jan", "N": "Fev", "O": "Mar", "P": "Abr",
    "Q": "Mai", "R": "Jun", "S": "Jul", "T": "Ago",
    "U": "Set", "V": "Out", "W": "Nov", "X": "Dez",
    "Z": "Qualquer",
}


def serie_para_mes(serie):
    if not serie:
        return "?"
    return SERIE_MES.get(serie[0].upper(), "?")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ativo", help="Código do ativo (ex: PETR4)")
    args = parser.parse_args()
    ativo = args.ativo.upper()

    real_conn = conectar(REAL_DB)
    test_conn = conectar(TEST_DB)

    real_tickers = set()
    for r in real_conn.execute(
        "SELECT cod_put, cod_call FROM instrumentos_base WHERE ativo = ?", (ativo,)
    ).fetchall():
        if r["cod_put"]:
            real_tickers.add(r["cod_put"])
        if r["cod_call"]:
            real_tickers.add(r["cod_call"])

    test_rows = test_conn.execute(
        "SELECT * FROM instrumentos_base WHERE ativo = ? AND fonte = 'opcoes.net.br'", (ativo,)
    ).fetchall()

    real_conn.close()
    test_conn.close()

    # Apenas no site
    apenas_site = [r for r in test_rows if r["cod_put"] and r["cod_put"] not in real_tickers]

    if not apenas_site:
        # tenta coluna cod_call
        apenas_site = [r for r in test_rows if r["cod_call"] and r["cod_call"] not in real_tickers]

    print(f"=== Análise: {len(apenas_site)} tickers só no opcoes.net.br ({ativo}) ===\n")

    # Distribuição por letra-série
    series = Counter()
    strikes = []
    vencimentos = defaultdict(list)
    por_mes = Counter()
    hoje = date.today()

    for r in apenas_site:
        ticker = r["cod_put"] or r["cod_call"]
        serie = extrair_serie(ticker)
        series[serie] += 1
        strike = extrair_strike_num(ticker)
        if strike:
            strikes.append(strike)
        ven = r["vencimento"]
        if ven:
            ven_str = str(ven)[:10]
            vencimentos[ven_str].append(ticker)
            if len(ven_str) >= 7:
                mes_key = ven_str[:7]
                por_mes[mes_key] += 1

    print("Distribuição por letra-série:")
    for serie, count in series.most_common():
        mes = serie_para_mes(serie)
        print(f"  {serie:>8s} ({mes:>4s}): {count:>4d} opções")

    print(f"\nDistribuição por mês de vencimento:")
    for mes in sorted(por_mes):
        print(f"  {mes}: {por_mes[mes]:>4d} opções")

    print(f"\nFaixa de strikes: R$ {min(strikes):.2f} a R$ {max(strikes):.2f}")

    semanas = sum(1 for r in apenas_site if "W" in (r["cod_put"] or r["cod_call"] or ""))
    print(f"\nSéries semanais (W): {semanas}")
    print(f"Séries regulares: {len(apenas_site) - semanas}")

    print(f"\n--- Amostra (primeiros 30 tickers) ---")
    for r in sorted(apenas_site, key=lambda x: x["vencimento"] or "")[:30]:
        ticker = r["cod_put"] or r["cod_call"]
        ven = r["vencimento"]
        serie = extrair_serie(ticker)
        strike = extrair_strike_num(ticker)
        print(f"  {ticker:>12s}  strike={strike:>7.2f}  ven={ven}  série={serie}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
