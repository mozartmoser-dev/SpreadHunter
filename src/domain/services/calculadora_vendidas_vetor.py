"""Cálculo vetorizado (numpy) das oportunidades vendidas (BOX/SBTH).

Reproduz exatamente a semântica escalar de ``monitor_vendidas.py`` /
``CalculadoraCustosB3.calcular_custos_vendida``. Nenhum arredondamento é
feito aqui — a montagem do DTO arredonda, como no escalar.
"""

from dataclasses import dataclass

import numpy as np

from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


@dataclass(slots=True)
class ResultadoVendidasVetor:
    recebimento_box: np.ndarray
    cond_box: np.ndarray
    recebimento_sbth: np.ndarray
    cond_sbth: np.ndarray
    cdi_periodo: np.ndarray
    pct_box: np.ndarray
    pct_cdi_box: np.ndarray
    viavel_box: np.ndarray
    liq_put_x_lote_box: np.ndarray
    liq_call_x_lote_box: np.ndarray
    custo_box: np.ndarray
    ganho_antes_ir_box: np.ndarray
    ir_box: np.ndarray
    ganho_liq_box: np.ndarray
    pct_liq_box: np.ndarray
    pct_cdi_liq_box: np.ndarray
    pct_sbth: np.ndarray
    pct_cdi_sbth: np.ndarray
    viavel_sbth: np.ndarray
    liq_put_x_lote_sbth: np.ndarray
    custo_sbth: np.ndarray
    ganho_antes_ir_sbth: np.ndarray
    ir_sbth: np.ndarray
    ganho_liq_sbth: np.ndarray
    pct_liq_sbth: np.ndarray
    pct_cdi_liq_sbth: np.ndarray


def calcular_vendidas(
    *,
    preco_ativo: np.ndarray,
    of_compra_ativo: np.ndarray,
    of_compra_put: np.ndarray,
    of_venda_call: np.ndarray,
    strike: np.ndarray,
    dias: np.ndarray,
    vov_put: np.ndarray,
    voc_call: np.ndarray,
    dist_min_ativo: float,
    premio_risco: float,
    lote_box: int,
    lote_sbth: int,
    taxa_cdi: float,
    custos_b3: CalculadoraCustosB3 | None = None,
) -> ResultadoVendidasVetor:
    """Calcula BOX/SBTH vendidas para as linhas válidas (pré-filtradas)."""
    if custos_b3 is None:
        custos_b3 = CalculadoraCustosB3()
    n = len(preco_ativo)

    recebimento_box = of_compra_ativo + of_compra_put - of_venda_call
    cond_box = (
        (recebimento_box > strike)
        & (of_compra_ativo > 0)
        & (of_venda_call > 0)
        & (of_compra_put > 0)
    )

    recebimento_sbth = of_compra_ativo + of_compra_put
    cond_sbth = (
        (strike > of_compra_ativo * dist_min_ativo)
        & (recebimento_sbth > strike)
        & (of_compra_ativo > 0)
        & (of_compra_put > 0)
    )

    du = np.where(dias > 0, np.maximum(1, np.round(dias * 252.0 / 365.0).astype(int)), 0)
    cdi_periodo = np.where(du > 0, (1.0 + taxa_cdi) ** (du / 252.0) - 1.0, 0.0)

    preco_uso = np.where(of_compra_ativo > 0, of_compra_ativo, preco_ativo)
    taxa_total = custos_b3.taxa_total()
    taxa_total_stock = custos_b3.taxa_total_stock()
    taxa_ir = custos_b3.taxa_ir

    # BOX
    premio_medio_box = np.where(
        (of_compra_put > 0) & (of_venda_call > 0),
        (of_compra_put + of_venda_call) / 2.0,
        0.0,
    )
    custo_box = np.where(
        preco_uso > 0,
        taxa_total * premio_medio_box * 2.0 * 2.0 + taxa_total_stock * preco_uso * 1.0 * 2.0,
        0.0,
    )
    pct_box = np.divide(recebimento_box - strike, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi_box = np.divide(pct_box, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)
    liq_put_x_lote_box = vov_put - lote_box
    liq_call_x_lote_box = voc_call - lote_box
    liq_ok_box = (vov_put >= lote_box) & (voc_call >= lote_box)
    viavel_box = (pct_cdi_box >= premio_risco) & liq_ok_box
    ganho_antes_ir_box = recebimento_box - strike - custo_box
    ir_box = np.where(ganho_antes_ir_box > 0, ganho_antes_ir_box * taxa_ir, 0.0)
    ganho_liq_box = ganho_antes_ir_box - ir_box
    pct_liq_box = np.divide(ganho_liq_box, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi_liq_box = np.divide(pct_liq_box, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)

    # SBTH
    premio_medio_sbth = np.where(of_compra_put > 0, of_compra_put, 0.0)
    custo_sbth = np.where(
        preco_uso > 0,
        taxa_total * premio_medio_sbth * 1.0 * 2.0 + taxa_total_stock * preco_uso * 1.0 * 2.0,
        0.0,
    )
    pct_sbth = np.divide(recebimento_sbth - strike, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi_sbth = np.divide(pct_sbth, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)
    liq_put_x_lote_sbth = vov_put - lote_sbth
    liq_ok_sbth = vov_put >= lote_sbth
    viavel_sbth = (pct_cdi_sbth >= premio_risco) & liq_ok_sbth
    ganho_antes_ir_sbth = recebimento_sbth - strike - custo_sbth
    ir_sbth = np.where(ganho_antes_ir_sbth > 0, ganho_antes_ir_sbth * taxa_ir, 0.0)
    ganho_liq_sbth = ganho_antes_ir_sbth - ir_sbth
    pct_liq_sbth = np.divide(ganho_liq_sbth, strike, out=np.zeros(n, dtype=float), where=strike > 0)
    pct_cdi_liq_sbth = np.divide(pct_liq_sbth, cdi_periodo, out=np.zeros(n, dtype=float), where=cdi_periodo > 0)

    return ResultadoVendidasVetor(
        recebimento_box=recebimento_box,
        cond_box=cond_box,
        recebimento_sbth=recebimento_sbth,
        cond_sbth=cond_sbth,
        cdi_periodo=cdi_periodo,
        pct_box=pct_box,
        pct_cdi_box=pct_cdi_box,
        viavel_box=viavel_box,
        liq_put_x_lote_box=liq_put_x_lote_box,
        liq_call_x_lote_box=liq_call_x_lote_box,
        custo_box=custo_box,
        ganho_antes_ir_box=ganho_antes_ir_box,
        ir_box=ir_box,
        ganho_liq_box=ganho_liq_box,
        pct_liq_box=pct_liq_box,
        pct_cdi_liq_box=pct_cdi_liq_box,
        pct_sbth=pct_sbth,
        pct_cdi_sbth=pct_cdi_sbth,
        viavel_sbth=viavel_sbth,
        liq_put_x_lote_sbth=liq_put_x_lote_sbth,
        custo_sbth=custo_sbth,
        ganho_antes_ir_sbth=ganho_antes_ir_sbth,
        ir_sbth=ir_sbth,
        ganho_liq_sbth=ganho_liq_sbth,
        pct_liq_sbth=pct_liq_sbth,
        pct_cdi_liq_sbth=pct_cdi_liq_sbth,
    )