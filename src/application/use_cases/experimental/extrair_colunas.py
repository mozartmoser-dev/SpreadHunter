"""Helpers puros de extração de colunas a partir do dict de mercado.

Reproduzem exatamente a semântica escalar dos use cases atuais
(monitor_vendidas / monitor_venda_coberta):

- Campos numéricos: ``mercado.get(chave, default) or default`` (truthiness).
- Campos encadeados: ``mercado.get(boca, default) or mercado.get(normal, default) or default``.
- ``strike_rtd``: aceito apenas se truthy e > 0, senão 0.0.
- Pass-through (``ts_*`` / ``onda``): valor bruto, sem fallback.

Nenhum arredondamento é feito aqui — apenas extração.
"""

from typing import Any

import numpy as np


def or_default(mercado: dict, chave: str, default: float = 0.0) -> Any:
    """Equivalente a ``mercado.get(chave, default) or default`` (truthiness)."""
    return mercado.get(chave, default) or default


def or_chain(mercado: dict, chaves: list[str], default: float = 0.0) -> Any:
    """Encadeia chaves com ``or`` (ex.: vov_put_boca or vov_put or 0.0)."""
    for chave in chaves:
        valor = mercado.get(chave, default)
        if valor:
            return valor
    return default


def strike_limpo(mercado: dict) -> float:
    """Strike RTD: aceito apenas se truthy e > 0, senão 0.0."""
    s = mercado.get("strike_rtd")
    return s if (s and s > 0) else 0.0


def extrair(chaves: list, dados_mercado: dict, chave: str,
            default: float = 0.0, dtype: Any = float) -> np.ndarray:
    """Extrai array com fallback truthiness por chave (``get(...) or default``)."""
    return np.array([dados_mercado[k].get(chave, default) or default for k in chaves], dtype=dtype)


def extrair_encadeado(chaves: list, dados_mercado: dict,
                      chaves_fallback: list[str], default: float = 0.0) -> np.ndarray:
    """Extrai array com encadeamento truthiness (boca -> normal -> default)."""
    return np.array([or_chain(dados_mercado[k], chaves_fallback, default) for k in chaves], dtype=float)


def extrair_passthrough(chaves: list, dados_mercado: dict, chave: str) -> list:
    """Extrai campos pass-through sem fallback (ts_* / onda / idade)."""
    return [dados_mercado[k].get(chave) for k in chaves]
