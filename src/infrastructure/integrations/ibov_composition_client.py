from __future__ import annotations

import json
import logging
import os
from typing import NamedTuple

logger = logging.getLogger(__name__)

_IBOV_TOP50_DEFAULT: list[dict[str, float | str]] = [
    {"ticker": "VALE3", "peso": 13.76},
    {"ticker": "ITUB4", "peso": 8.42},
    {"ticker": "PETR4", "peso": 5.80},
    {"ticker": "PETR3", "peso": 4.07},
    {"ticker": "BBDC4", "peso": 3.98},
    {"ticker": "SBSP3", "peso": 3.54},
    {"ticker": "BPAC11", "peso": 3.14},
    {"ticker": "WEGE3", "peso": 3.19},
    {"ticker": "B3SA3", "peso": 2.99},
    {"ticker": "ITSA4", "peso": 2.97},
    {"ticker": "BBAS3", "peso": 2.64},
    {"ticker": "ABEV3", "peso": 2.50},
    {"ticker": "EMBJ3", "peso": 2.74},
    {"ticker": "EQTL3", "peso": 2.05},
    {"ticker": "RDOR3", "peso": 1.89},
]


def _pesos_acumulados(items: list[dict]) -> list[dict]:
    acc = 0.0
    out = []
    for it in items:
        acc += float(it["peso"])
        out.append({**it, "acum": round(acc, 2), "corte": acc >= 50.0})
    return out


class IbovCompositionClient:
    _cache: list[dict] | None = None

    def __init__(self, config_path: str | None = None):
        self._config_path = config_path

    def get_top50_percent(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        dados = self._carregar()
        cortados = [d for d in dados if not d.get("corte")]
        self._cache = cortados
        return cortados

    def get_all(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        dados = self._carregar()
        self._cache = dados
        return dados

    def _carregar(self) -> list[dict]:
        path = self._config_path
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    return _pesos_acumulados(raw)
            except Exception as e:
                logger.warning("Erro lendo %s: %s", path, e)
        return _pesos_acumulados(list(_IBOV_TOP50_DEFAULT))
