"""
Standalone: busca dados de opções do opcoes.net.br via requisição direta HTML
(sem Playwright, sem navegador) e salva em banco de teste isolado.

Uso:
    python scripts/validar_opcoes/fetch_opcoes.py PETR4
"""

import sys
import re
import sqlite3
import time
import random
import argparse
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup


URL_TPL = "https://opcoes.net.br/matriz-opcoes-strike-x-vencimento/{tipo}s/{ativo}"
TEST_DB = Path(__file__).resolve().parent / "teste_opcoes.db"
REQ_DELAY = 1.5  # segundos entre requisições pro mesmo ativo

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://opcoes.net.br/",
    })
    return s


def parse_valor(texto: str) -> float:
    """Converte '1,19' brasileiro para float 1.19"""
    return float(texto.replace(".", "").replace(",", ".").strip())


def parse_data(texto: str) -> str:
    """Converte '29/05/2026' para '2026-05-29'"""
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date().isoformat()


def extrair_serie(ticker: str) -> str:
    """Extrai a letra-série do ticker de opção ex: PETRH694 -> H"""
    m = re.search(r"[A-Z]", ticker[len(ticker) - 5:]) if len(ticker) >= 5 else None
    m2 = re.search(r"[A-Z]{1,2}", ticker[4:6]) if len(ticker) >= 6 else None
    return (m2.group() if m2 else "") or (m.group() if m else "")


def fetch_matriz(ativo: str, tipo: str, session: requests.Session | None = None) -> list[dict]:
    """
    Retorna lista de { ticker, strike, vencimento, tipo, ativo }
    """
    fechar = session is None
    if session is None:
        session = _session()

    url = URL_TPL.format(tipo=tipo, ativo=ativo.upper())
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as e:
        if resp.status_code == 404:
            print(f"  [AVISO] Página não encontrada para {tipo}s de {ativo}")
        else:
            print(f"  [ERRO] HTTP {resp.status_code} para {tipo}s de {ativo}: {e}")
        return []
    except requests.RequestException as e:
        print(f"  [ERRO] Falha na requisição para {tipo}s de {ativo}: {e}")
        return []

    if fechar:
        session.close()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table")
    if not table:
        print(f"  [AVISO] Nenhuma tabela encontrada para {tipo}s de {ativo}")
        return []

    thead = table.find("thead")
    tbody = table.find("tbody")
    if not thead or not tbody:
        return []

    headers = thead.find_all("th")[1:]
    vencimentos = [parse_data(th.get_text(strip=True)) for th in headers]

    resultados = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        strike = parse_valor(tds[0].get_text(strip=True))
        for i, td in enumerate(tds[1:]):
            a = td.find("a")
            if a and a.get("href"):
                ticker = a.get_text(strip=True)
                if i < len(vencimentos):
                    resultados.append({
                        "ticker": ticker,
                        "strike": strike,
                        "vencimento": vencimentos[i],
                        "tipo": tipo.upper(),
                        "ativo": ativo.upper(),
                    })
    return resultados


def init_test_db(db_path: Path):
    """Cria banco de teste com schema igual ao instrumentos_base do SpreadHunter"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS instrumentos_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ativo TEXT NOT NULL,
            cod_put TEXT NOT NULL DEFAULT '',
            cod_call TEXT NOT NULL DEFAULT '',
            vencimento DATE NOT NULL,
            tipo_opcao TEXT NOT NULL,
            strike REAL NOT NULL DEFAULT 0,
            fonte TEXT DEFAULT 'opcoes.net.br',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ib_ativo ON instrumentos_base(ativo)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ib_ticker ON instrumentos_base(cod_put, cod_call)
    """)
    conn.commit()
    return conn


def salvar_resultados(conn, resultados: list[dict]):
    """Salva resultados no banco de teste sem duplicar"""
    conn.execute("DELETE FROM instrumentos_base WHERE fonte = 'opcoes.net.br'")
    inserted = 0
    for r in resultados:
        col_ticker = "cod_put" if r["tipo"] == "PUT" else "cod_call"
        try:
            conn.execute(
                f"""INSERT INTO instrumentos_base
                    (ativo, vencimento, tipo_opcao, {col_ticker}, strike, fonte)
                    VALUES (?, ?, ?, ?, ?, 'opcoes.net.br')""",
                (r["ativo"], r["vencimento"], r["tipo"], r["ticker"], r["strike"]),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Busca opções do opcoes.net.br para teste")
    parser.add_argument("ativo", help="Código do ativo (ex: PETR4)")
    parser.add_argument("--db", default=str(TEST_DB), help="Caminho do banco de teste")
    parser.add_argument("--delay", type=float, default=REQ_DELAY, help="Delay entre requisições (s)")
    args = parser.parse_args()

    ativo = args.ativo.upper()
    db_path = Path(args.db)

    session = _session()

    print(f"Buscando {ativo} em opcoes.net.br...")
    print(f"  CALLs...", end=" ", flush=True)
    calls = fetch_matriz(ativo, "CALL", session)
    print(f"{len(calls)} opções encontradas")

    time.sleep(args.delay)

    print(f"  PUTs...", end=" ", flush=True)
    puts = fetch_matriz(ativo, "PUT", session)
    print(f"{len(puts)} opções encontradas")

    session.close()

    total = calls + puts
    if not total:
        print("Nenhuma opção encontrada. Verifique o ativo.")
        return 1

    conn = init_test_db(db_path)
    inseridos = salvar_resultados(conn, total)
    conn.close()

    puts_count = sum(1 for r in total if r["tipo"] == "PUT")
    calls_count = sum(1 for r in total if r["tipo"] == "CALL")
    print(f"\nSalvos {inseridos} registros em {db_path}")
    print(f"  PUTs : {puts_count}")
    print(f"  CALLs: {calls_count}")

    uniq_venc = sorted(set(r["vencimento"] for r in total))
    print(f"  Vencimentos: {len(uniq_venc)}")
    print(f"  Período: {uniq_venc[0]} a {uniq_venc[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
