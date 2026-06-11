"""
ImportFlash: varre opcoes.net.br e atualiza o banco do SpreadHunter.

Captura o modelo (A=Americana / E=Europeia) de cada opção via API.

Uso:
    python scripts/validar_opcoes/importflash.py [--excluir IBOV11 ...] [--delay 1.0]
"""

import sys
import time
import sqlite3
from collections import defaultdict
from pathlib import Path
from datetime import date

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPTS_DIR.parent.parent

sys.path.insert(0, str(PROJECT_DIR))

REAL_DB = PROJECT_DIR / "config" / "spreadhunter.db"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ImportFlash: atualiza base via opcoes.net.br")
    parser.add_argument("--excluir", nargs="*", default=["IBOV11"], help="Ativos a excluir")
    parser.add_argument("--delay", type=float, default=0.35, help="Delay entre reqs (s)")
    args = parser.parse_args()

    from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
    from src.domain.entities.instrumento_opcional import TipoOpcao

    client = OpcoesNetClient()
    ativos = client.fetch_available_assets()
    if not ativos:
        print("ERRO: nao foi possivel obter lista de ativos de opcoes.net.br")
        return 1
    print(f"Ativos encontrados: {len(ativos)}")

    excluir = [e.upper() for e in (args.excluir or [])]

    import_max_months = 9
    try:
        conn_cfg = sqlite3.connect(str(REAL_DB))
        row_black = conn_cfg.execute(
            "SELECT valor FROM parametros_operacionais WHERE chave = 'black_list_import'"
        ).fetchone()
        row_meses = conn_cfg.execute(
            "SELECT valor FROM parametros_operacionais WHERE chave = 'import_max_months'"
        ).fetchone()
        conn_cfg.close()
        if row_black and row_black[0]:
            black_ativos = [a.strip().upper() for a in str(row_black[0]).split(",") if a.strip()]
            for a in black_ativos:
                if a not in excluir:
                    excluir.append(a)
            print(f"Blacklist do banco: {', '.join(black_ativos)}")
        if row_meses and row_meses[0]:
            try:
                import_max_months = int(float(row_meses[0]))
            except (ValueError, TypeError):
                pass
    except Exception as e:
        print(f"Aviso: nao foi possivel ler parametros do banco: {e}")

    from dateutil.relativedelta import relativedelta

    data_limite = date.today() + relativedelta(months=import_max_months)
    print(f"Limite de vencimento: {data_limite} ({import_max_months} meses)")

    t0 = time.perf_counter()

    print("=" * 50)
    print("IMPORTFLASH - Varrendo opcoes.net.br com captura MOD (A/E)...")
    print("=" * 50)

    todos_pares = []

    for idx, ativo in enumerate(ativos, 1):
        if ativo.upper() in excluir:
            print(f"[{idx:>3d}/{len(ativos)}] {ativo:<10s} EXCLUIDO")
            continue

        print(f"[{idx:>3d}/{len(ativos)}] {ativo:<10s}...", end=" ", flush=True)
        try:
            opcoes = client.fetch_all_options(ativo, delay=args.delay)
        except Exception as e:
            print(f"ERRO: {e}")
            continue

        if not opcoes:
            print("0 opcoes")
            continue

        opcoes_filtradas = [r for r in opcoes if r.get("vencimento", "") <= data_limite.isoformat()]
        if not opcoes_filtradas:
            print("0 opcoes (todas fora do limite)")
            continue
        qtd_removidas = len(opcoes) - len(opcoes_filtradas)

        grupos: dict = defaultdict(lambda: {"PUT": "", "CALL": "", "MOD": ""})
        for r in opcoes_filtradas:
            key = (r["ativo"], r["vencimento"], r["strike"])
            if r["tipo"] == "PUT":
                grupos[key]["PUT"] = r["ticker"]
            else:
                grupos[key]["CALL"] = r["ticker"]
                if r.get("mod"):
                    grupos[key]["MOD"] = r["mod"]

        pares = []
        for (ativo_key, ven, strike), p in grupos.items():
            cod_put = p["PUT"]
            cod_call = p["CALL"]
            if not cod_put or not cod_call:
                continue
            mod = p.get("MOD", "")
            if mod == "E":
                tipo = TipoOpcao.EUROPEIA
            elif mod == "A":
                tipo = TipoOpcao.AMERICANA
            else:
                continue
            pares.append((ativo_key, cod_put, cod_call, ven, strike, tipo.value))

        todos_pares.extend(pares)
        suffix = f" ({qtd_removidas} fora do limite)" if qtd_removidas else ""
        print(f"{len(pares)} pares{suffix}")

    if not todos_pares:
        print("\nNenhum par encontrado.")
        return 1

    print(f"\nTotal de pares: {len(todos_pares)}")

    # --- Grava no banco real ---
    print("\n" + "=" * 50)
    print("Gravando no banco do SpreadHunter...")
    print("=" * 50)

    conn = sqlite3.connect(str(REAL_DB))
    conn.execute("DELETE FROM instrumentos_base")
    conn.commit()

    inseridas = 0
    for ativo, cod_put, cod_call, ven, strike, tipo in todos_pares:
        try:
            conn.execute(
                "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao) VALUES (?, ?, ?, ?, ?)",
                (ativo, cod_put, cod_call, ven, tipo),
            )
            inseridas += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM instrumentos_base").fetchone()[0]
    conn.close()

    dur = time.perf_counter() - t0
    print(f"\n{'=' * 50}")
    print(f"IMPORTFLASH CONCLUIDO em {dur:.0f}s ({dur/60:.1f}min)")
    print(f"{'=' * 50}")
    print(f"Pares importados: {inseridas}")
    excl_str = ", ".join(excluir) if excluir else "nenhum"
    print(f"Ativos excluidos: {excl_str}")
    print(f"Total no banco: {total} registros")
    print(f"MOD capturado: A=Americana / E=Europeia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
