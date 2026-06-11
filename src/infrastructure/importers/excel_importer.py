import re
import math
from datetime import date, datetime


def sanitizar_strike(valor_bruto: float, preco_ref: float) -> float:
    if not preco_ref or preco_ref <= 0 or not valor_bruto or valor_bruto <= 0:
        return valor_bruto
    divisores = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
    melhor_strike = valor_bruto
    menor_score = float('inf')
    for d in divisores:
        tentativa = valor_bruto / d
        try:
            razao = tentativa / preco_ref
            penalidade = 0
            if razao < 0.1 or razao > 3.0:
                penalidade = 10.0
            score = abs(math.log(razao)) + penalidade
            if score < menor_score:
                menor_score = score
                melhor_strike = tentativa
        except (ValueError, ZeroDivisionError):
            continue
    return melhor_strike


def extrair_strike(codigo: str, preco_ref: float | None = None) -> float | None:
    if not codigo:
        return None
    nums = re.search(r'(\d+)[a-zA-Z]?$', codigo)
    if not nums:
        return None
    raw = nums.group(1)
    n_len = len(raw)
    try:
        val = float(raw)
        if preco_ref and preco_ref > 0:
            return sanitizar_strike(val, preco_ref)
        if n_len <= 2:
            return val
        if n_len == 3:
            return val / 10.0
        if n_len == 4:
            return val / 10.0
        if n_len >= 5:
            return val / 1000.0
        return val
    except:
        return None


def parse_vencimento(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None
