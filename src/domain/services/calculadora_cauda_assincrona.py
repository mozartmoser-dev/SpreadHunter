import math
from dataclasses import dataclass

from src.domain.services.calendario_b3 import dc_to_du


@dataclass(slots=True)
class ResultadoCaudaAssincrona:
    ativo: str
    strike_call: float
    strike_put: float
    dte_call: int
    preco_ativo: float
    premio_call: float
    premio_put: float
    iv_call: float
    pnl_base: float
    pnl_projetado: float
    capital_base: float
    pct_cdi_base: float
    target_pnl: float
    gap: float
    sigma_periodo: float
    k_3sigma: float
    ratio_call: int
    pnl_com_ratio: float
    pct_cdi_com_ratio: float
    breakeven_superior: float | None
    breakeven_ok: bool
    viavel: bool
    custo_b3_base: float = 0.0
    score_cauda: float = 0.0


class CalculadoraCaudaAssincrona:
    """Pós-processa um ResultadoColarCalendario viável e calcula o ratio
    ótimo de CALLs extras no mesmo strike para atingir o target CDI,
    respeitando o breakeven superior ≥ 3σ."""

    @staticmethod
    def calcular(
        *,
        preco_ativo: float,
        strike_call: float,
        strike_put: float,
        premio_call: float,
        premio_put: float,
        dte_call: int,
        ativo: str,
        iv_call_pct: float,
        pnl_projetado_base: float,
        capital_empregado_base: float,
        pct_cdi_base: float,
        taxa_cdi: float = 0.1450,
        calda_premio_risco: float = 2.5,
        calda_desvios_cauda: float = 3.0,
        calda_ratio_max: int = 50,
        custo_b3_base: float = 0.0,
        preco_compra: float | None = None,
    ) -> ResultadoCaudaAssincrona | None:
        iv = iv_call_pct / 100.0
        if iv <= 0 or dte_call <= 0 or preco_ativo <= 0:
            return None

        du_total = dc_to_du(None, None, dte_call)
        cdi_periodo = (1 + taxa_cdi) ** (du_total / 252.0) - 1
        if cdi_periodo <= 0:
            return None

        target_pnl = capital_empregado_base * cdi_periodo * calda_premio_risco
        gap = target_pnl - pnl_projetado_base

        if gap <= 0:
            return None

        sigma_p = iv * math.sqrt(dte_call / 252.0)
        k_3sigma = preco_ativo * (1 + calda_desvios_cauda * sigma_p)

        cost = preco_compra if (preco_compra and preco_compra > 0) else preco_ativo

        extra_call_pnl = premio_call - max(0, preco_ativo - strike_call)
        melhor_n: int | None = None
        melhor_pnl = 0.0

        for n in range(1, calda_ratio_max + 1):
            pnl_com_ratio = pnl_projetado_base + extra_call_pnl * (n - 1)
            if pnl_com_ratio <= 0:
                continue

            if n == 1:
                if pnl_com_ratio >= target_pnl:
                    melhor_n = n
                    melhor_pnl = pnl_com_ratio
                continue

            be = CalculadoraCaudaAssincrona._breakeven_superior(
                cost, strike_call, premio_call, premio_put, n
            )
            if be is not None and be >= k_3sigma and pnl_com_ratio >= target_pnl:
                melhor_n = n
                melhor_pnl = pnl_com_ratio
                break

        if melhor_n is None or melhor_n < 1:
            return None

        capital_base_abs = capital_empregado_base
        if capital_base_abs <= 0:
            capital_base_abs = abs(capital_base_abs)
        pct_cdi_com_ratio = (melhor_pnl / capital_base_abs) / cdi_periodo if cdi_periodo > 0 and capital_base_abs > 0 else 0.0

        if melhor_n == 1:
            be_final = None
        else:
            be_final = CalculadoraCaudaAssincrona._breakeven_superior(
                cost, strike_call, premio_call, premio_put, melhor_n
            )

        return ResultadoCaudaAssincrona(
            ativo=ativo,
            strike_call=strike_call,
            strike_put=strike_put,
            dte_call=dte_call,
            preco_ativo=preco_ativo,
            premio_call=premio_call,
            premio_put=premio_put,
            iv_call=iv_call_pct,
            pnl_base=pnl_projetado_base,
            pnl_projetado=round(melhor_pnl, 4),
            capital_base=capital_empregado_base,
            pct_cdi_base=pct_cdi_base,
            target_pnl=round(target_pnl, 4),
            gap=round(gap, 4),
            sigma_periodo=round(sigma_p, 4),
            k_3sigma=round(k_3sigma, 4),
            ratio_call=melhor_n,
            pnl_com_ratio=round(melhor_pnl, 4),
            pct_cdi_com_ratio=round(pct_cdi_com_ratio, 4),
            breakeven_superior=round(be_final, 2) if be_final is not None else None,
            breakeven_ok=(be_final is not None and be_final >= k_3sigma) if melhor_n > 1 else True,
            viavel=True,
            custo_b3_base=custo_b3_base,
            score_cauda=round(pct_cdi_com_ratio / max(calda_premio_risco, 0.01), 4),
        )

    @staticmethod
    def _breakeven_superior(
        preco_compra: float, strike_call: float,
        premio_call: float, premio_put: float, n: int,
    ) -> float | None:
        if n <= 1:
            return None
        num = n * (strike_call + premio_call) - preco_compra - premio_put
        den = n - 1
        if den <= 0 or num <= 0:
            return None
        return num / den
