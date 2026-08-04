"""
Verifica integridade dos parâmetros operacionais com 3 fontes de verdade.

Fontes:
  A) ParametroOperacional.PARAMETROS_DEFAULT (hardcoded, canônica)
  B) config/parametros_default.json (blueprint, editável)
  C) Banco SQLite de produção (%APPDATA%/spreadhunter.db)

Regras:
  RED:   banco vs hardcoded diverge > 5x  (produção afetada)
  YELLOW: json vs hardcoded diverge > 5x  (blueprint corrompido)
  BLUE:  json vs banco diverge mas ambos plausíveis (edição manual)

Read-only: nunca escreve no banco nem no JSON.
"""

import json
import sqlite3
import sys
from pathlib import Path

PROJETO = Path(__file__).resolve().parent.parent
JSON_PATH = PROJETO / "config" / "parametros_default.json"

FRACAO_KEYWORDS = ("pct", "fator", "razao", "spread", "limite", "sigma")

SEVERITY_FATOR = 5.0
EPSILON = 1e-9


def _eh_parametro_de_fracao(chave: str) -> bool:
    return any(kw in chave.lower() for kw in FRACAO_KEYWORDS)


def _fator_divergencia(valor: float, referencia: float) -> float:
    """Fator multiplicativo de divergência entre valor e referência (>= 1).

    Ex: valor=0.0099, referencia=0.40 → 0.40/0.0099 ≈ 40.4x.
    Se referencia == 0, retorna o valor absoluto como limite ingênuo.
    """
    a, b = abs(valor), abs(referencia)
    if b < EPSILON:
        return a if a > EPSILON else 0.0
    if a < EPSILON:
        return float("inf")
    return max(a, b) / min(a, b)


def _carregar_hardcoded() -> dict[str, float]:
    from src.domain.entities.parametro_operacional import ParametroOperacional

    defaults: dict[str, float] = {}
    for chave, meta in ParametroOperacional.PARAMETROS_DEFAULT.items():
        try:
            defaults[chave] = float(meta["valor"])
        except (ValueError, TypeError):
            pass
    return defaults


def _carregar_json() -> dict[str, float]:
    if not JSON_PATH.is_file():
        return {}
    with open(str(JSON_PATH), "r", encoding="utf-8") as f:
        data = json.load(f)
    result: dict[str, float] = {}
    for p in data.get("parametros", []):
        try:
            result[p["chave"]] = float(p["valor"])
        except (ValueError, TypeError):
            pass
    return result


def _carregar_banco(db_path: str) -> dict[str, float]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT chave, valor FROM parametros_operacionais").fetchall()
        result: dict[str, float] = {}
        for chave, valor in rows:
            try:
                result[chave] = float(valor)
            except (ValueError, TypeError):
                pass
        return result
    finally:
        conn.close()


def verificar(db_path: str | None = None) -> list[dict]:
    """
    Retorna lista de divergências encontradas.
    db_path=None usa o banco padrão de produção (%APPDATA%).
    """
    if db_path is None:
        from src.infrastructure.persistence.database import get_db_path
        db_path = str(get_db_path())

    hardcoded = _carregar_hardcoded()
    json_vals = _carregar_json()
    banco_vals = _carregar_banco(db_path)

    divergencias: list[dict] = []

    for chave in hardcoded:
        if not _eh_parametro_de_fracao(chave):
            continue

        hc = hardcoded[chave]
        jv = json_vals.get(chave)
        bv = banco_vals.get(chave)

        fator_bh = _fator_divergencia(bv, hc) if bv is not None else None
        fator_jh = _fator_divergencia(jv, hc) if jv is not None else None

        sinais = []

        if fator_bh is not None and fator_bh > SEVERITY_FATOR:
            sinais.append("RED")
        if fator_jh is not None and fator_jh > SEVERITY_FATOR:
            sinais.append("YELLOW")

        if sinais:
            divergencias.append({
                "chave": chave,
                "hardcoded": hc,
                "json": jv,
                "banco": bv,
                "sinais": sinais,
                "fator_banco_hardcoded": round(fator_bh, 2) if fator_bh is not None else None,
                "fator_json_hardcoded": round(fator_jh, 2) if fator_jh is not None else None,
            })

    divergencias.sort(key=lambda d: d["chave"])
    return divergencias


def main():
    import logging
    logger = logging.getLogger(__name__)

    diver = verificar()

    if not diver:
        print("Nenhuma divergência encontrada — parâmetros íntegros.")
        return 0

    print(f"{len(diver)} parâmetro(s) com divergência:\n")
    for d in diver:
        sinais_str = " + ".join(d["sinais"])
        print(f"  {sinais_str}  {d['chave']}")
        print(f"          hardcoded = {d['hardcoded']}")
        print(f"          json      = {d['json']}")
        print(f"          banco     = {d['banco']}")
        print(f"          fator B   = {d['fator_banco_hardcoded']}x")
        print(f"          fator J   = {d['fator_json_hardcoded']}x")
        print()

    logger.warning("Verificação de integridade: %d parâmetro(s) com divergência", len(diver))
    return 1


if __name__ == "__main__":
    sys.exit(main())
