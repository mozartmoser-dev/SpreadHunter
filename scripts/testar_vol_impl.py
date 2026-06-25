import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient

client = OpcoesNetClient()

for ativo in ["PETR4", "VALE3", "ITUB4", "BBAS3", "WEGE3"]:
    print(f"\n=== {ativo} ===")
    hist = client.get_stock_history_formatted(ativo, 252)
    if not hist:
        print("  Sem dados")
        continue
    print(f"  Total candles: {len(hist)}")

    # Estrutura do primeiro registro
    amostra = hist[0]
    print(f"  Chaves: {list(amostra.keys())}")

    # Conta quantos têm vol_impl não nulo
    com_vi = [c for c in hist if c.get("vol_impl") is not None and c["vol_impl"] > 0]
    print(f"  Registros com vol_impl > 0: {len(com_vi)} / {len(hist)}")

    if com_vi:
        valores = [c["vol_impl"] for c in com_vi]
        print(f"  vol_impl: min={min(valores):.4f}  max={max(valores):.4f}  media={sum(valores)/len(valores):.4f}")
        print(f"  Últimos 5 vol_impl: {[round(v, 4) for v in valores[-5:]]}")

    # Conta vol_hist
    com_vh = [c for c in hist if c.get("vol_hist") is not None and c["vol_hist"] > 0]
    print(f"  Registros com vol_hist > 0: {len(com_vh)} / {len(hist)}")
    if com_vh:
        vh = [c["vol_hist"] for c in com_vh]
        print(f"  vol_hist: min={min(vh):.4f}  max={max(vh):.4f}  ultimo={vh[-1]:.4f}")

print("\n>>> JSON completo do primeiro candle de PETR4:")
raw = client.get_stock_history("PETR4")
if raw:
    fields = raw.get("data_fields", [])
    rows = raw.get("data_rows", [])
    print(f"  Fields: {fields}")
    if rows:
        print(f"  1ª row: {rows[0]}")
        if len(rows) > 1:
            print(f"  2ª row: {rows[1]}")
