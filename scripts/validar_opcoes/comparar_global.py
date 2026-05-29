"""
Comparação global: SpreadHunter vs opcoes.net.br para todos os ativos.
"""

import sys
import sqlite3
from pathlib import Path

REAL_DB = Path(__file__).resolve().parent.parent.parent / "config" / "spreadhunter.db"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes_completo.db"


def main():
    real_conn = sqlite3.connect(str(REAL_DB))
    test_conn = sqlite3.connect(str(TEST_DB))

    real_conn.row_factory = sqlite3.Row
    test_conn.row_factory = sqlite3.Row

    # --- Monta tickers do SpreadHunter ---
    real_tickers = {}
    for r in real_conn.execute("SELECT ativo, cod_put, cod_call, vencimento FROM instrumentos_base"):
        for col in ("cod_put", "cod_call"):
            tk = r[col]
            if tk:
                ven = str(r["vencimento"])[:10] if r["vencimento"] else ""
                real_tickers[tk] = {"ativo": r["ativo"], "vencimento": ven}

    # --- Monta tickers do opcoes.net.br ---
    test_tickers = {}
    for r in test_conn.execute("SELECT ativo, cod_put, cod_call, vencimento FROM instrumentos_base WHERE fonte='opcoes.net.br'"):
        for col in ("cod_put", "cod_call"):
            tk = r[col]
            if tk:
                ven = str(r["vencimento"])[:10] if r["vencimento"] else ""
                test_tickers[tk] = {"ativo": r["ativo"], "vencimento": ven}

    real_conn.close()
    test_conn.close()

    real_set = set(real_tickers.keys())
    test_set = set(test_tickers.keys())

    comuns = real_set & test_set
    apenas_real = real_set - test_set
    apenas_test = test_set - real_set

    # Divergências de vencimento nos tickers em comum
    diverg_venc = 0
    for tk in comuns:
        if real_tickers[tk]["vencimento"] != test_tickers[tk]["vencimento"]:
            diverg_venc += 1

    print(f"{'='*60}")
    print(f"COMPARAÇÃO GLOBAL: SpreadHunter vs opcoes.net.br")
    print(f"{'='*60}")
    print(f"{'':40s} {'SpreadHunter':>15s} {'opcoes.net.br':>15s}")
    print(f"{'Tickers únicos':40s} {len(real_set):>15d} {len(test_set):>15d}")
    print(f"{'Em comum':40s} {len(comuns):>15d} {len(comuns):>15d}")
    print(f"{'Apenas no SH':40s} {len(apenas_real):>15d} {'---':>15s}")
    print(f"{'Apenas no site':40s} {'---':>15s} {len(apenas_test):>15d}")

    print(f"\nCobertura do site nos dados do SH: {len(comuns)/len(real_set)*100:.1f}%" if real_set else "")
    print(f"Cobertura do SH nos dados do site: {len(comuns)/len(test_set)*100:.1f}%" if test_set else "")

    if diverg_venc:
        print(f"\n[!] Tickers em comum com VENCIMENTO diferente: {diverg_venc}")
    else:
        print(f"\n[OK] Vencimentos conferem para todos os {len(comuns)} tickers em comum")

    # Top 10 ativos com mais divergências
    if apenas_test:
        print(f"\n--- Ativos com mais tickers NOVOS (só no site) ---")
        contagem = {}
        for tk in apenas_test:
            ativo = test_tickers[tk]["ativo"]
            contagem[ativo] = contagem.get(ativo, 0) + 1
        for ativo, cnt in sorted(contagem.items(), key=lambda x: -x[1])[:10]:
            print(f"  {ativo:<10s} {cnt:>5d} novos tickers")

    if apenas_real:
        print(f"\n--- Ativos com mais tickers AUSENTES (só no SH) ---")
        contagem = {}
        for tk in apenas_real:
            ativo = real_tickers[tk]["ativo"]
            contagem[ativo] = contagem.get(ativo, 0) + 1
        for ativo, cnt in sorted(contagem.items(), key=lambda x: -x[1])[:10]:
            print(f"  {ativo:<10s} {cnt:>5d} tickers só no SH")

    # Resumo final
    pct = len(comuns) / len(test_set) * 100 if test_set else 0
    print(f"\n{'='*60}")
    if pct > 95:
        print(f"[OK] Base do SpreadHunter esta atualizada ({pct:.1f}% de cobertura)")
    elif pct > 80:
        print(f"[!] Diferencas moderadas ({pct:.1f}%) -- valeria atualizar")
    else:
        print(f"[-] Diferencas significativas ({pct:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
