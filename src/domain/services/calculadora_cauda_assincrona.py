import math
from dataclasses import dataclass

from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_colar_calendario import CalculadoraColarCalendario


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
    ratio_call: float
    ratio_put: float
    pnl_com_ratio: float
    pct_cdi_com_ratio: float
    pnl_na_cauda_esquerda: float
    pnl_na_cauda_direita: float
    range_ok: bool
    breakeven_esquerdo: float | None
    breakeven_direito: float | None
    viavel: bool
    custo_b3_base: float = 0.0
    score_cauda: float = 0.0


class CalculadoraCaudaAssincrona:
    """Pós-processa um ResultadoColarCalendario viável e encontra o par
    (ratio_call, ratio_put) que maximiza o %CDI mantendo PnL > 0 em ±Nσ."""

    @staticmethod
    def _delta_pnl(
        S: float, S_ref: float, Kc: float, Kp: float, n: int, m: float,
        bs_put_ref: float = 0.0, bs_put_S: float = 0.0,
    ) -> float:
        """Variação do PnL ao mover o spot de S_ref para S.
        Usa B&S para a PUT (tempo residual), intrínseco para a CALL (expirou)."""
        return ((S - S_ref)
                - n * (max(0, S - Kc) - max(0, S_ref - Kc))
                + m * (bs_put_S - bs_put_ref))

    @staticmethod
    def _breakeven_esquerdo(
        S0: float, Kp: float, Pc: float, Pp: float, n: int, m: float,
    ) -> float | None:
        """Preço do ativo onde PnL = 0 no lado esquerdo (S < Kp)."""
        if m >= 1.0:
            return None
        num = S0 - n * Pc - m * (Kp - Pp)
        den = 1 - m
        if den <= 0 or num <= 0:
            return None
        return num / den

    @staticmethod
    def _breakeven_direito(
        S0: float, Kc: float, Pc: float, Pp: float, n: int, m: float,
    ) -> float | None:
        """Preço do ativo onde PnL = 0 no lado direito (S > Kc)."""
        if n <= 1:
            return None
        num = n * (Kc + Pc) - S0 - m * Pp
        den = n - 1
        if den <= 0 or num <= 0:
            return None
        return num / den

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
        calda_ratio_put_min: float = 0.3,
        calda_ratio_put_step: float = 0.1,
        calda_capital_minimo_pct: float = 0.0,
        custo_b3_base: float = 0.0,
        preco_compra: float | None = None,
        iv_put_pct: float | None = None,
        dte_put: int = 0,
        diagnostico: list | None = None,
    ) -> ResultadoCaudaAssincrona | None:
        def _diag(msg: str) -> None:
            if diagnostico is not None:
                diagnostico.append(msg)

        iv = iv_call_pct / 100.0
        if iv <= 0 or dte_call <= 0 or preco_ativo <= 0:
            _diag(f"IV={iv_call_pct}% DTE={dte_call} preco={preco_ativo} — parametros invalidos")
            return None

        du_total = dc_to_du(None, None, dte_call)
        cdi_periodo = (1 + taxa_cdi) ** (du_total / 252.0) - 1
        if cdi_periodo <= 0:
            _diag(f"CDI periodo={cdi_periodo:.6f} — invalido")
            return None

        target_pnl = capital_empregado_base * cdi_periodo * calda_premio_risco
        gap = target_pnl - pnl_projetado_base

        sigma_p = iv * math.sqrt(dte_call / 252.0)

        s_end_l = preco_ativo * (1 - calda_desvios_cauda * sigma_p)
        s_end_r = preco_ativo * (1 + calda_desvios_cauda * sigma_p)
        k_3sigma = s_end_r

        S0_cost = preco_compra if (preco_compra and preco_compra > 0) else preco_ativo
        extra_call_pnl = premio_call - max(0, preco_ativo - strike_call)

        dte_extra = max(0, dte_put - dte_call)
        iv_put = (iv_put_pct / 100.0) if (iv_put_pct and iv_put_pct > 0) else 0.0
        usar_bs = (iv_put > 0 and dte_extra > 0)
        if usar_bs:
            T_extra = dc_to_du(None, None, dte_extra) / 252.0
            r_cont = math.log(1 + taxa_cdi)
            bs_put_ref = CalculadoraColarCalendario.black_scholes(
                preco_ativo, strike_put, T_extra, r_cont, iv_put, 'put'
            )
            bs_end_l = CalculadoraColarCalendario.black_scholes(
                s_end_l, strike_put, T_extra, r_cont, iv_put, 'put'
            )
            bs_end_r = CalculadoraColarCalendario.black_scholes(
                s_end_r, strike_put, T_extra, r_cont, iv_put, 'put'
            )
            custo_put = premio_put - bs_put_ref
        else:
            bs_put_ref = bs_end_l = bs_end_r = 0.0
            custo_put = premio_put - max(0, strike_put - preco_ativo)

        # Ratios em float: n = 1.00 a 1+calda_ratio_max/100, m = calda_ratio_put_min a 1.00
        base_pct = max(1, int(calda_ratio_put_step * 100))
        n_max_ratio = 1.0 + calda_ratio_max / 100.0
        n_vals = [round(x / 100.0, 2) for x in range(100, int(n_max_ratio * 100 + 1), base_pct)]
        m_vals = [round(x / 100.0, 2) for x in range(
            max(1, int(calda_ratio_put_min * 100)), 101, base_pct
        )]

        candidatos = []

        for n in n_vals:
            if gap <= 0 and n > 1.0:
                continue

            for m in m_vals:
                pnl_spot = pnl_projetado_base + (n - 1) * extra_call_pnl - (1 - m) * custo_put
                if pnl_spot <= 0:
                    continue

                delta_l = CalculadoraCaudaAssincrona._delta_pnl(
                    s_end_l, preco_ativo, strike_call, strike_put, n, m,
                    bs_put_ref, bs_end_l,
                )
                delta_r = CalculadoraCaudaAssincrona._delta_pnl(
                    s_end_r, preco_ativo, strike_call, strike_put, n, m,
                    bs_put_ref, bs_end_r,
                )
                cap_abs = capital_empregado_base if capital_empregado_base > 0 else abs(capital_empregado_base)
                if cap_abs <= 0:
                    continue
                if cdi_periodo > 0:
                    piso_pnl = cdi_periodo * cap_abs
                    if min(pnl_spot + delta_l, pnl_spot + delta_r) < piso_pnl:
                        continue

                pct_cdi_n = (pnl_spot / cap_abs) / cdi_periodo if cdi_periodo > 0 else 0.0
                candidatos.append((n, m, pnl_spot, pct_cdi_n,
                                   pnl_spot + delta_l, pnl_spot + delta_r,
                                   cap_abs))

        if not candidatos:
            _diag(f"Nenhum par (n,m) atinge CDI>={calda_premio_risco:.1f}x em +/-{calda_desvios_cauda}s "
                  f"com n<=1+{calda_ratio_max}% e m>={calda_ratio_put_min:.1f}")
            return None

        melhor = max(candidatos, key=lambda x: x[3])
        melhor_n, melhor_m, melhor_pnl, melhor_cdi, pnl_end_l, pnl_end_r, cap_abs = melhor
        pct_cdi_final = (melhor_pnl / cap_abs) / cdi_periodo if cdi_periodo > 0 and cap_abs > 0 else 0.0

        be_esq = CalculadoraCaudaAssincrona._breakeven_esquerdo(
            S0_cost, strike_put, premio_call, premio_put, melhor_n, melhor_m
        )
        be_dir = CalculadoraCaudaAssincrona._breakeven_direito(
            S0_cost, strike_call, premio_call, premio_put, melhor_n, melhor_m
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
            ratio_put=round(melhor_m, 2),
            pnl_com_ratio=round(melhor_pnl, 4),
            pct_cdi_com_ratio=round(pct_cdi_final, 4),
            pnl_na_cauda_esquerda=round(pnl_end_l, 4),
            pnl_na_cauda_direita=round(pnl_end_r, 4),
            range_ok=True,
            breakeven_esquerdo=round(be_esq, 2) if be_esq is not None else None,
            breakeven_direito=round(be_dir, 2) if be_dir is not None else None,
            viavel=True,
            custo_b3_base=custo_b3_base,
            score_cauda=round(pct_cdi_final / max(calda_premio_risco, 0.01), 4),
        )
