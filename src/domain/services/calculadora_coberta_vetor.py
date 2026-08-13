"""Cálculo vetorizado (numpy) da Venda Coberta e Taxa Comprada.

Reproduz exatamente a semântica escalar de ``monitor_venda_coberta.py``
(``varrer`` e ``varrer_comprada``). Nenhum arredondamento é feito aqui —
a montagem do DTO arredonda, como no escalar.
"""

from dataclasses import dataclass

import numpy as np

from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


@dataclass(slots=True)
class ResultadoCobertaVetor:
    recebimento: np.ndarray
    cond: np.ndarray
    cdi_periodo: np.ndarray
    pct: np.ndarray
    pct_cdi: np.ndarray
    viavel: np.ndarray
    liq_call_x_lote: np.ndarray
    custo: np.ndarray
    ganho_antes_ir: np.ndarray
    ir: np.ndarray
    ganho_liq: np.ndarray
    pct_liq: np.ndarray
    pct_cdi_liq: np.ndarray


@dataclass(slots=True)
class ResultadoCompradaVetor:
    custo_montagem: np.ndarray
    cond: np.ndarray
    cdi_periodo: np.ndarray
    pct: np.ndarray
    pct_cdi: np.ndarray
    viavel: np.ndarray
    liq_call_x_lote: np.ndarray
    custo: np.ndarray
    ganho_antes_ir: np.ndarray
    ir: np.ndarray
    ganho_liq: np.ndarray
    pct_liq: np.ndarray
    pct_cdi_liq: np.ndarray


def _cdi_periodo(dias: np.ndarray, taxa_cdi: float) -> np.ndarray:
    du = np.where(dias > 0, np.maximum(1, np.round(dias * 252.0 / 365.0).astype(int)), 0)
    return np.where(du > 0, (1.0 + taxa_cdi) ** (du / 252.0) - 1.0, 0.0)


def _custos_vendida(preco_uso: np.ndarray, premio_medio: np.ndarray,
                    n_pernas: int, custos_b3: CalculadoraCustosB3) -> np.ndarray:
    taxa_total = custos_b3.taxa_total()
    taxa_total_stock = custos_b3.taxa_total_stock()
    return np.where(
        preco_uso > 0,
        taxa_total * premio_medio * n_pernas * 2.0 + taxa_total_stock * preco_uso * 1.0 * 2.0,
        0.0,
    )


def calcular_coberta(
    *,
    preco_ativo: np.ndarray,
    of_compra_ativo: np.ndarray,
    of_venda_call: np.ndarray,
    voc_call: np.ndarray,
    strike: np.ndarray,
    dias: np.ndarray,
    premio_risco: float,
    lote_call: int,
    taxa_cdi: float,
    custos_b3: CalculadoraCustosB3 | None = None,
) -> ResultadoCobertaVetor:
    """Cálculo da Venda Coberta (varrer) para as linhas válidas."""
    if custos_b3 is None:
        custos_b3 = CalculadoraCustosB3()
    n = len(preco_ativo)

    recebimento = of_compra_ativo - of_venda_call
    cond = (
        (strike < preco_ativo)
        & (recebimento > strike)
        & (of_compra_ativo > 0)
        & (of_venda_call > 0)
    )

    cdi_periodo = _cdi_periodo(dias, taxa_cdi)
    premio_medio = np.where(of_venda_call > 0, of_venda_call, 0.0)
    custo = _custos_vendida(preco_ativo, premio_medio, 1, custos_b3)

    pct = np.divide(recebimento - strike, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi = np.divide(pct, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)
    liq_call_x_lote = voc_call - lote_call
    viavel = (pct_cdi >= premio_risco) & (voc_call >= lote_call)

    ganho_antes_ir = recebimento - strike - custo
    ir = np.where(ganho_antes_ir > 0, ganho_antes_ir * custos_b3.taxa_ir, 0.0)
    ganho_liq = ganho_antes_ir - ir
    pct_liq = np.divide(ganho_liq, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi_liq = np.divide(pct_liq, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)

    return ResultadoCobertaVetor(
        recebimento=recebimento,
        cond=cond,
        cdi_periodo=cdi_periodo,
        pct=pct,
        pct_cdi=pct_cdi,
        viavel=viavel,
        liq_call_x_lote=liq_call_x_lote,
        custo=custo,
        ganho_antes_ir=ganho_antes_ir,
        ir=ir,
        ganho_liq=ganho_liq,
        pct_liq=pct_liq,
        pct_cdi_liq=pct_cdi_liq,
    )


def calcular_comprada(
    *,
    preco_ativo: np.ndarray,
    of_venda_ativo: np.ndarray,
    of_compra_call: np.ndarray,
    voc_call: np.ndarray,
    strike: np.ndarray,
    dias: np.ndarray,
    premio_risco: float,
    lote_liquidez: int,
    dist_max_pct: float,
    taxa_cdi: float,
    custos_b3: CalculadoraCustosB3 | None = None,
) -> ResultadoCompradaVetor:
    """Cálculo da Taxa Comprada (varrer_comprada) para as linhas válidas."""
    if custos_b3 is None:
        custos_b3 = CalculadoraCustosB3()
    n = len(preco_ativo)

    custo_montagem = of_venda_ativo - of_compra_call
    strike_max = preco_ativo * (1.0 - dist_max_pct)
    cond = (
        (strike <= strike_max)
        & (custo_montagem > 0)
        & (strike > custo_montagem)
        & (of_venda_ativo > 0)
        & (of_compra_call > 0)
    )

    cdi_periodo = _cdi_periodo(dias, taxa_cdi)
    premio_medio = np.where(of_compra_call > 0, of_compra_call, 0.0)
    custo = _custos_vendida(preco_ativo, premio_medio, 1, custos_b3)

    pct = np.divide(strike - custo_montagem, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi = np.divide(pct, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)
    liq_call_x_lote = voc_call - lote_liquidez
    viavel = (pct_cdi >= premio_risco) & (voc_call >= lote_liquidez)

    ganho_antes_ir = strike - custo_montagem - custo
    ir = np.where(ganho_antes_ir > 0, ganho_antes_ir * custos_b3.taxa_ir, 0.0)
    ganho_liq = ganho_antes_ir - ir
    pct_liq = np.divide(ganho_liq, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi_liq = np.divide(pct_liq, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)

    return ResultadoCompradaVetor(
        custo_montagem=custo_montagem,
        cond=cond,
        cdi_periodo=cdi_periodo,
        pct=pct,
        pct_cdi=pct_cdi,
        viavel=viavel,
        liq_call_x_lote=liq_call_x_lote,
        custo=custo,
        ganho_antes_ir=ganho_antes_ir,
        ir=ir,
        ganho_liq=ganho_liq,
        pct_liq=pct_liq,
        pct_cdi_liq=pct_cdi_liq,
    )