from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

from src.domain.services.calendario_b3 import dc_to_du, frac_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


class TipoColarCalendario(Enum):
    ALTA = "Alta"
    BAIXA = "Baixa"
    NEUTRO = "Neutro"


@dataclass(slots=True)
class ResultadoColarCalendario:
    ativo: str
    vencimento_call: date
    vencimento_put: date
    dte_call: int
    dte_put: int
    dte_extra: int
    strike_call: float
    strike_put: float
    cod_call: str
    cod_put: str
    preco_ativo: float
    premio_call: float
    premio_put: float
    net_credito: float
    iv_call: float
    iv_put: float
    valor_put_venc_call: float
    pnl_stock: float
    pnl_projetado: float
    capital_empregado: float
    pct_retorno: float
    pct_cdi: float
    delta_total: float
    theta_call: float
    theta_put: float
    theta_liquido: float
    viavel: bool
    tipo: TipoColarCalendario
    r: float = 0.1450
    custo_b3: float = 0.0
    custo_ir: float = 0.0
    pct_cdi_liquido: float = 0.0
    score: float = 0.0
    risco_max: float = 0.0
    iv_rank: float = 0.0
    iv_rank_call: float = 0.0
    iv_rank_put: float = 0.0
    vega_call: float = 0.0
    vega_put: float = 0.0
    vega_liquido: float = 0.0
    gamma_call: float = 0.0
    gamma_put: float = 0.0
    score_iv: float = 0.0
    preco_compra: float = 0.0
    be_baixa: float | None = None
    be_alta: float | None = None
    be_baixa_intrinseco: float | None = None
    be_alta_intrinseco: float | None = None
    ratio_call: float = 1.0
    ratio_put: float = 1.0
    is_cauda: bool = False
    is_otimizado: bool = False
    estagio_otimizado: str | None = None
    detectado_em: datetime | None = None
    qtd_acao: int = 100
    qtd_call: int = 100
    qtd_put: int = 100


class CalculadoraColarCalendario:
    def __init__(self, taxa_cdi: float = 0.1450, premio_risco: float = 1.2, custos_b3: CalculadoraCustosB3 | None = None, taxa_ir: float | None = None, limiar_pct: float = 0.15, be_range_mult: float = 0.15):
        self.taxa_cdi = taxa_cdi
        self.premio_risco = premio_risco
        self.custos_b3 = custos_b3 or CalculadoraCustosB3(taxa_ir=taxa_ir)
        self.limiar_pct = limiar_pct
        self.be_range_mult = be_range_mult

    @staticmethod
    def black_scholes(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == 'call':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @staticmethod
    def bs_theta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        sqrt_T = np.sqrt(T)
        pdf_d1 = norm.pdf(d1)
        if option_type == 'call':
            theta = (-S * pdf_d1 * sigma) / (2 * sqrt_T) - r * K * np.exp(-r * T) * norm.cdf(d2)
        else:
            theta = (-S * pdf_d1 * sigma) / (2 * sqrt_T) + r * K * np.exp(-r * T) * norm.cdf(-d2)
        return theta / 365

    @staticmethod
    def bs_vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        return S * norm.pdf(d1) * np.sqrt(T) / 100

    @staticmethod
    def bs_gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        return norm.pdf(d1) / (S * sigma * np.sqrt(T))

    @staticmethod
    def bs_delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        if sigma <= 0 or T <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        if option_type == 'call':
            return norm.cdf(d1)
        return norm.cdf(d1) - 1

    @staticmethod
    def implied_volatility(S: float, K: float, T: float, r: float, market_price: float, option_type: str) -> float | None:
        if market_price <= 0 or T <= 0:
            return None
        def f(sigma):
            return CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, option_type) - market_price
        try:
            return brentq(f, 1e-6, 5.0)
        except (ValueError, RuntimeError):
            return None

    def calcular_cdi_periodo(self, dias_uteis: int) -> float:
        if dias_uteis <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (dias_uteis / 252) - 1

    @staticmethod
    def calcular_preco_ajustado_dividendos(
        dividendos: list[tuple[date, float]],
        preco_ativo: float,
        r: float,
        dte_max: int,
    ) -> float:
        hoje = date.today()
        total_pv = 0.0
        for data_ex, valor in dividendos:
            dias_ate_ex = (data_ex - hoje).days
            if dias_ate_ex <= 0 or dias_ate_ex > dte_max:
                continue
            t = dias_ate_ex / 365
            total_pv += valor * np.exp(-r * t)
        return preco_ativo - total_pv

    def classificar_tipo(self, preco_ativo: float, strike_call: float, strike_put: float) -> TipoColarCalendario:
        meio = (strike_call + strike_put) / 2
        dist = abs(preco_ativo - meio)
        limiar = (strike_call - strike_put) * self.limiar_pct
        if dist <= limiar:
            return TipoColarCalendario.NEUTRO
        if preco_ativo < meio:
            return TipoColarCalendario.ALTA
        return TipoColarCalendario.BAIXA

    @staticmethod
    def _pnl_at_call_expiry(
        S: float, S0: float, Kc: float, Kp: float,
        Pc: float, Pp: float, T_rem: float, rf: float, iv_p: float,
    ) -> float:
        stock_pnl = min(S, Kc) - S0
        call_pnl = Pc
        if T_rem > 0 and iv_p > 1e-10:
            d1 = (np.log(S / Kp) + (rf + 0.5 * iv_p ** 2) * T_rem) / (iv_p * np.sqrt(T_rem))
            d2 = d1 - iv_p * np.sqrt(T_rem)
            put_val = Kp * np.exp(-rf * T_rem) * norm.cdf(-d2) - S * norm.cdf(-d1)
        else:
            put_val = max(Kp - S, 0)
        return stock_pnl + call_pnl + (put_val - Pp)

    def _calcular_breakevens(
        self, S0: float, Kc: float, Kp: float,
        Pc: float, Pp: float, dte_extra: int, rf: float, iv_p: float,
    ) -> tuple[float | None, float | None]:
        from scipy.optimize import brentq
        T_rem = dte_extra / 365 if dte_extra > 0 else 0
        def _f(S):
            return self._pnl_at_call_expiry(S, S0, Kc, Kp, Pc, Pp, T_rem, rf, iv_p)
        x_min = min(Kp, S0) * (1 - self.be_range_mult)
        x_max = max(Kc, S0) * (1 + self.be_range_mult)
        f_min = _f(x_min)
        f_kc = _f(Kc)
        f_max = _f(x_max)
        be_baixa = be_alta = None
        if f_min < 0 < f_kc:
            try:
                be_baixa = brentq(_f, x_min, Kc)
            except (ValueError, RuntimeError):
                pass
        if f_kc > 0 > f_max:
            try:
                be_alta = brentq(_f, Kc, x_max)
            except (ValueError, RuntimeError):
                pass
        return (round(be_baixa, 2) if be_baixa is not None else None,
                round(be_alta, 2) if be_alta is not None else None)

    def _calcular_breakevens_intrinseco(
        self, S0: float, Kc: float, Kp: float,
        Pc: float, Pp: float,
    ) -> tuple[float | None, float | None]:
        from scipy.optimize import brentq
        def _pnl_intrinseco(S):
            stock_pnl = min(S, Kc) - S0
            call_pnl = Pc
            put_val = max(Kp - S, 0)
            return stock_pnl + call_pnl + (put_val - Pp)
        x_min = min(Kp, S0) * (1 - self.be_range_mult)
        x_max = max(Kc, S0) * (1 + self.be_range_mult)
        f_min = _pnl_intrinseco(x_min)
        f_kc = _pnl_intrinseco(Kc)
        f_max = _pnl_intrinseco(x_max)
        be_baixa = be_alta = None
        if f_min < 0 < f_kc:
            try:
                be_baixa = brentq(_pnl_intrinseco, x_min, Kc)
            except (ValueError, RuntimeError):
                pass
        if f_kc > 0 > f_max:
            try:
                be_alta = brentq(_pnl_intrinseco, Kc, x_max)
            except (ValueError, RuntimeError):
                pass
        return (round(be_baixa, 2) if be_baixa is not None else None,
                round(be_alta, 2) if be_alta is not None else None)

    def calcular(
        self,
        preco_ativo: float,
        strike_call: float,
        strike_put: float,
        premio_call: float,
        premio_put: float,
        cod_call: str,
        cod_put: str,
        dte_call: int,
        dte_put: int,
        ativo: str,
        vencimento_call: date,
        vencimento_put: date,
        r: float | None = None,
        preco_compra_ativo: float | None = None,
        dividendos: list[tuple[date, float]] | None = None,
        iv_hist_min: float | None = None,
        iv_hist_max: float | None = None,
        qtd_acao: int = 1,
        qtd_call: int = 1,
        qtd_put: int = 1,
    ) -> ResultadoColarCalendario | None:
        if r is None:
            r = self.taxa_cdi

        if preco_ativo <= 0 or dte_call <= 0 or dte_put <= 0:
            return None
        if premio_call <= 0 or premio_put <= 0:
            return None

        T_call = dc_to_du(None, None, dte_call) / 252.0
        T_put = dc_to_du(None, None, dte_put) / 252.0
        dte_extra = dte_put - dte_call
        r_cont = np.log(1 + r)

        S_bs_call = preco_ativo
        S_bs_put = preco_ativo
        if dividendos:
            S_bs_call = self.calcular_preco_ajustado_dividendos(dividendos, preco_ativo, r, dte_call)
            S_bs_put = self.calcular_preco_ajustado_dividendos(dividendos, preco_ativo, r, dte_put)
            if S_bs_call <= 0 or S_bs_put <= 0:
                return None

        iv_call = self.implied_volatility(S_bs_call, strike_call, T_call, r_cont, premio_call, 'call')
        iv_put = self.implied_volatility(S_bs_put, strike_put, T_put, r_cont, premio_put, 'put')

        if iv_call is None or iv_put is None:
            return None

        preco_compra = preco_compra_ativo if (preco_compra_ativo and preco_compra_ativo > 0) else preco_ativo

        net_credito = premio_call * qtd_call - premio_put * qtd_put

        delta_call = self.bs_delta(S_bs_call, strike_call, T_call, r_cont, iv_call, 'call')
        delta_put = self.bs_delta(S_bs_put, strike_put, T_put, r_cont, iv_put, 'put')
        delta_total = 1.0 - delta_call + delta_put
        delta_put_abs = abs(delta_put)
        # Classifica pelo delta total da estrutura (stock + short call + long put)
        # |delta_total| ≤ 0.05 → Neutro; > 0 → Alta; < 0 → Baixa
        limiar = 0.05
        if abs(delta_total) <= limiar:
            tipo = TipoColarCalendario.NEUTRO
        elif delta_total > 0:
            tipo = TipoColarCalendario.ALTA
        else:
            tipo = TipoColarCalendario.BAIXA

        theta_call = self.bs_theta(S_bs_call, strike_call, T_call, r_cont, iv_call, 'call')
        theta_put = self.bs_theta(S_bs_put, strike_put, T_put, r_cont, iv_put, 'put')
        theta_liquido = abs(theta_call) - abs(theta_put)

        T_put_rem = dc_to_du(None, None, dte_extra) / 252.0 if dte_extra > 0 else 0
        valor_put_vc = self.black_scholes(S_bs_call, strike_put, T_put_rem, r_cont, iv_put, 'put') if T_put_rem > 0 else 0

        # Modelo COBERTO: compra acoes + short call + long put
        # Unit PnL first, then scale by qtd
        pnl_call_unit = premio_call
        pnl_stock_unit = min(preco_ativo, strike_call) - preco_compra
        pnl_put_unit = valor_put_vc - premio_put

        pnl_call = pnl_call_unit * qtd_call
        pnl_stock = pnl_stock_unit * qtd_acao
        pnl_put = pnl_put_unit * qtd_put
        pnl_projetado = pnl_call + pnl_stock + pnl_put

        if pnl_projetado <= 0:
            return None

        du_total = dc_to_du(None, None, dte_call)
        cdi_periodo = self.calcular_cdi_periodo(du_total)
        if cdi_periodo <= 0:
            return None

        capital_empregado = preco_compra * qtd_acao + premio_put * qtd_put - premio_call * qtd_call
        capital_base = abs(capital_empregado) if capital_empregado <= 0 else capital_empregado
        risco_max = max(0.0, capital_empregado - min(strike_call, strike_put) * qtd_acao) if capital_empregado > 0 else capital_base

        vega_call = self.bs_vega(S_bs_call, strike_call, T_call, r_cont, iv_call)
        vega_put = self.bs_vega(S_bs_put, strike_put, T_put, r_cont, iv_put)
        vega_liquido = vega_put - vega_call
        gamma_call = self.bs_gamma(S_bs_call, strike_call, T_call, r_cont, iv_call)
        gamma_put = self.bs_gamma(S_bs_put, strike_put, T_put, r_cont, iv_put)

        iv_rank = 0.0
        iv_rank_call = 0.0
        iv_rank_put = 0.0
        if iv_hist_min is not None and iv_hist_max is not None and iv_hist_max > iv_hist_min:
            iv_rank_call = (iv_call - iv_hist_min) / (iv_hist_max - iv_hist_min)
            iv_rank_put = (iv_put - iv_hist_min) / (iv_hist_max - iv_hist_min)
            iv_rank = (iv_rank_call + iv_rank_put) / 2

        custo_b3 = (self.custos_b3.custos_opcao(premio_call, n_pernas=1) * qtd_call +
                    self.custos_b3.custos_opcao(premio_put, n_pernas=1) * qtd_put +
                    self.custos_b3.custos_stock(preco_compra, n_acoes=qtd_acao))
        pnl_projetado_liquido = pnl_projetado - custo_b3

        ganho_base = max(pnl_projetado_liquido, 0.0)
        custo_ir = self.custos_b3.ajustar_ir(ganho_base)
        pnl_projetado_ir = pnl_projetado_liquido - custo_ir

        pct_retorno = pnl_projetado_liquido / capital_base
        pct_retorno_bruto = pnl_projetado / capital_base
        pct_cdi_bruto = pct_retorno_bruto / cdi_periodo if cdi_periodo > 0 else 0
        pct_cdi = pct_retorno / cdi_periodo if cdi_periodo > 0 else 0
        pct_cdi_liquido = (pnl_projetado_ir / capital_base) / cdi_periodo if cdi_periodo > 0 else 0.0
        viavel = pct_cdi_bruto >= self.premio_risco

        be_baixa, be_alta = self._calcular_breakevens(
            preco_ativo, strike_call, strike_put,
            premio_call, premio_put, dte_extra, r, iv_put,
        )
        be_baixa_int, be_alta_int = self._calcular_breakevens_intrinseco(
            preco_ativo, strike_call, strike_put,
            premio_call, premio_put,
        )

        return ResultadoColarCalendario(
            ativo=ativo,
            vencimento_call=vencimento_call,
            vencimento_put=vencimento_put,
            dte_call=dte_call,
            dte_put=dte_put,
            dte_extra=dte_extra,
            strike_call=strike_call,
            strike_put=strike_put,
            cod_call=cod_call,
            cod_put=cod_put,
            preco_ativo=preco_ativo,
            premio_call=premio_call,
            premio_put=premio_put,
            net_credito=round(net_credito, 4),
            delta_total=round(delta_total, 4),
            custo_b3=round(custo_b3, 4),
            custo_ir=round(custo_ir, 4),
            iv_call=round(iv_call * 100, 2),
            iv_put=round(iv_put * 100, 2),
            valor_put_venc_call=round(valor_put_vc, 4),
            pnl_stock=round(pnl_stock, 4),
            pnl_projetado=round(pnl_projetado, 4),
            capital_empregado=round(capital_empregado, 4),
            pct_retorno=round(pct_retorno * 100, 4),
            pct_cdi=round(pct_cdi, 4),
            pct_cdi_liquido=round(pct_cdi_liquido, 4),
            theta_call=round(theta_call * 100, 4),
            theta_put=round(theta_put * 100, 4),
            theta_liquido=round(theta_liquido * 100, 4),
            tipo=tipo,
            viavel=viavel,
            r=r,
            be_baixa=be_baixa,
            be_alta=be_alta,
            be_baixa_intrinseco=be_baixa_int,
            be_alta_intrinseco=be_alta_int,
            risco_max=round(risco_max, 4),
            iv_rank=round(iv_rank, 4),
            iv_rank_call=round(iv_rank_call, 4),
            iv_rank_put=round(iv_rank_put, 4),
            vega_call=round(vega_call, 4),
            vega_put=round(vega_put, 4),
            vega_liquido=round(vega_liquido, 4),
            gamma_call=round(gamma_call, 4),
            gamma_put=round(gamma_put, 4),
            preco_compra=round(preco_compra, 2),
            qtd_acao=qtd_acao,
            qtd_call=qtd_call,
            qtd_put=qtd_put,
        )

    @staticmethod
    def gerar_explicacao(r: 'ResultadoColarCalendario', taxa_cdi: float = 0.1450) -> str:
        import numpy as np
        from scipy.stats import norm

        S0 = r.preco_ativo
        Kc, Kp = r.strike_call, r.strike_put
        Pc, Pp = r.premio_call, r.premio_put
        T_rem = r.dte_extra / 365
        iv_p = r.iv_put / 100

        rf = getattr(r, 'r', 0.1450)

        def bs_put(S, K, T, sigma):
            if T <= 0 or sigma <= 0:
                return max(K - S, 0)
            d1 = (np.log(S / K) + (rf + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            return K * np.exp(-rf * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        # Scaling factors: qtd * ratio
        qtd_acao = r.qtd_acao
        qtd_call_real = r.qtd_call * getattr(r, 'ratio_call', 1.0)
        qtd_put_real = r.qtd_put * getattr(r, 'ratio_put', 1.0)

        cap = S0 * qtd_acao + Pp * qtd_put_real - Pc * qtd_call_real
        net = Pc * qtd_call_real - Pp * qtd_put_real

        # Calcula o desvio padrao (sigma) do periodo a partir do IV medio
        iv_medio = ((r.iv_call / 100) + (r.iv_put / 100)) / 2
        T_call_ano = dc_to_du(None, None, r.dte_call) / 252.0
        sigma_pct = iv_medio * np.sqrt(T_call_ano) if iv_medio > 1e-10 else 0.0

        # 9 cenarios: 3 sigma downs, -5%, 0, +5%, 3 sigma ups
        if sigma_pct > 0.001:
            pares_cenarios = [
                (-3.0, f"\u22123\u03c3 (\u2212{3*sigma_pct*100:.1f}%)",  S0 * (1 - 3*sigma_pct)),
                (-2.0, f"\u22122\u03c3 (\u2212{2*sigma_pct*100:.1f}%)",  S0 * (1 - 2*sigma_pct)),
                (-1.0, f"\u22121\u03c3 (\u2212{1*sigma_pct*100:.1f}%)",  S0 * (1 - 1*sigma_pct)),
                (-0.5, f"\u22125% (\u2212{5/abs(sigma_pct)/100:.1f}\u03c3)", S0 * 0.95),
                (0.0,  f"0\u03c3 \u2014 Est\u00e1vel",                    S0),
                (0.5,  f"+5% (+{5/abs(sigma_pct)/100:.1f}\u03c3)",       S0 * 1.05),
                (1.0,  f"+1\u03c3 (+{1*sigma_pct*100:.1f}%)",            S0 * (1 + 1*sigma_pct)),
                (2.0,  f"+2\u03c3 (+{2*sigma_pct*100:.1f}%)",            S0 * (1 + 2*sigma_pct)),
                (3.0,  f"+3\u03c3 (+{3*sigma_pct*100:.1f}%)",            S0 * (1 + 3*sigma_pct)),
            ]
        else:
            pares_cenarios = [
                (-3.0, "Queda forte (S=\u221230%)",  S0 * 0.7),
                (-2.0, "Queda m\u00e9dia (S=\u221220%)", S0 * 0.8),
                (-1.0, "Queda leve (S=\u221210%)",   S0 * 0.9),
                (-0.5, "\u22125%",                    S0 * 0.95),
                (0.0,  "Est\u00e1vel (S=0%)",         S0),
                (0.5,  "+5%",                         S0 * 1.05),
                (1.0,  "Alta leve (S=+10%)",          S0 * 1.1),
                (2.0,  "Alta m\u00e9dia (S=+20%)",    S0 * 1.2),
                (3.0,  "Alta forte (S=+30%)",         S0 * 1.3),
            ]

        pdf_peak = norm.pdf(0.0, 0.0, 1.0)
        cenarios = []
        naked_pnl = max(0, qtd_call_real - qtd_acao)  # CALLs extras descobertas, se houver
        for n_sigma, label, S_T in pares_cenarios:
            if S_T > Kc:
                s_pnl_u = Kc - S0
                c_pnl_u = Pc
                put_bs_u = bs_put(S_T, Kp, T_rem, iv_p)
                p_pnl_u = put_bs_u - Pp
            else:
                put_bs_u = bs_put(S_T, Kp, T_rem, iv_p)
                pnl_no_ex = (S_T - S0) + Pc + (put_bs_u - Pp)
                pnl_ex = (Kp - S0) + Pc - Pp
                if pnl_ex > pnl_no_ex:
                    s_pnl_u, c_pnl_u, p_pnl_u = (Kp - S0), Pc, -Pp
                else:
                    s_pnl_u, c_pnl_u, p_pnl_u = (S_T - S0), Pc, (put_bs_u - Pp)
            # Scale by quantities
            s_pnl = s_pnl_u * qtd_acao
            c_pnl = c_pnl_u * min(qtd_call_real, qtd_acao)  # calls cobertas
            if naked_pnl > 0:
                naked = -naked_pnl * max(0, S_T - Kc)  # perda em calls nuas
            else:
                naked = 0.0
            p_pnl = p_pnl_u * qtd_put_real
            total = s_pnl + c_pnl + naked + p_pnl
            put_intrin = max(Kp - S_T, 0) * qtd_put_real
            put_extrin = (put_bs_u - max(Kp - S_T, 0)) * qtd_put_real

            # % Retorno e x CDI
            pct_ret = (total / cap) * 100 if cap > 0 else 0.0
            du_total = dc_to_du(None, None, r.dte_call)
            cdi_periodo = (1 + rf) ** (du_total / 252) - 1
            x_cdi = (total / cap) / cdi_periodo if cdi_periodo > 0 else 0.0

            # Líquido por cenário (B3 fixo + IR variável)
            pnl_pos_b3 = total - r.custo_b3
            ir_cenario = pnl_pos_b3 * 0.15 if pnl_pos_b3 > 0 else 0.0
            pnl_liquido_cenario = pnl_pos_b3 - ir_cenario
            x_cdi_liquido = (pnl_liquido_cenario / cap) / cdi_periodo if cdi_periodo > 0 else 0.0

            # Largura da barra da gaussiana (PDF normalizado)
            pdf = norm.pdf(n_sigma, 0.0, 1.0)
            bar_pct = max(4, int(28 * pdf / pdf_peak))
            put_bs_total = put_bs_u * qtd_put_real
            cenarios.append((n_sigma, label, S_T, s_pnl, c_pnl, put_bs_total, put_intrin, put_extrin, p_pnl, total, pct_ret, x_cdi, pnl_liquido_cenario, x_cdi_liquido, bar_pct))

        call_Itm = S0 > Kc
        call_intrin = max(S0 - Kc, 0) if call_Itm else 0
        call_extrin = Pc - call_intrin
        if call_Itm:
            call_premio_txt = f"(intrínseco R$ {call_intrin:.2f} + extrínseco R$ {call_extrin:.2f})"
        else:
            call_premio_txt = "(prêmio inteiramente extrínseco)"

        if sigma_pct > 0.001:
            nota_sigma = f" (1σ = {sigma_pct*100:.1f}%, IV médio {iv_medio*100:.0f}%, {r.dte_call} DTE)"
        else:
            nota_sigma = ""
        lines = [
            "<h3>📖 Explicação — Collar Calendário Coberto</h3>",
            f"<p><b>{r.ativo}</b> &mdash; {r.tipo.value}</p>",
            "<hr>",
            "<p><b>O que é esta estratégia?</b><br>",
            "Você compra a ação, vende uma CALL de curto prazo e compra uma PUT de prazo maior. ",
            "O lucro vem da diferença de decaimento temporal: a CALL perde valor mais rápido que a PUT ",
            f"nos primeiros {r.dte_call} dias, enquanto a PUT ainda tem {r.dte_extra}d de vida útil.</p>",
            "<hr>",
            "<p><b>Montagem:</b></p>",
            "<ul>",
            f"<li>Comprar ação ({qtd_acao}x): <b>−R$ {S0 * qtd_acao:.2f}</b></li>",
            f"<li>Vender CALL {r.cod_call} K={Kc:.2f} ({int(qtd_call_real)}x): <b>+R$ {Pc * qtd_call_real:.2f}</b> {call_premio_txt}</li>",
            f"<li>Comprar PUT {r.cod_put} K={Kp:.2f} ({int(qtd_put_real)}x): <b>−R$ {Pp * qtd_put_real:.2f}</b></li>",
            f"<li><b>Capital empregado = R$ {cap:.2f}</b> ({S0 * qtd_acao:.2f} + {Pp * qtd_put_real:.2f} − {Pc * qtd_call_real:.2f})</li>",
            f"<li>Débito/Crédito líquido: <b>R$ {net:.2f}</b></li>",
            "</ul>",
            "<hr>",
            f"<p><b>Cenários no vencimento da CALL ({r.dte_call}d):</b>{nota_sigma}</p>",
            "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; font-size:9pt;'>",
            "<tr style='background:#2d2d44;'>"
            "<th style='width:30px;'></th><th>Cenário</th><th>S_T</th><th>Ação</th><th>CALL</th>"
            "<th>PUT (BS)</th><th>Intrín</th><th>Extrín</th>"
             "<th>PnL Total</th><th>% Retorno</th><th>× CDI Bruto</th><th>× CDI Líq.</th></tr>",
        ]
        for n_sigma, label, S_T, s_pnl, c_pnl, put_bs, pint, pext, p_pnl, total, pct_ret, x_cdi, pnl_liq, x_cdi_liq, bar_pct in cenarios:
            cor = "#2ecc71" if total > 0 else "#e74c3c"
            svg_bar = (
                f'<svg width="28" height="18" viewBox="0 0 28 18">'
                f'<rect x="{(28-bar_pct)/2:.1f}" y="3" width="{bar_pct}" height="12" '
                f'fill="rgba(255,255,255,0.10)" rx="2"/></svg>'
            )
            lines.append(
                f"<tr>"
                f"<td style='text-align:center;'>{svg_bar}</td>"
                f"<td>{label}</td><td>R$ {S_T:.2f}</td><td>R$ {s_pnl:.2f}</td>"
                f"<td>R$ {c_pnl:.2f}</td><td>R$ {put_bs:.2f}</td>"
                f"<td>R$ {pint:.2f}</td><td>R$ {pext:.2f}</td>"
                f"<td style='color:{cor};font-weight:bold;'>R$ {total:.2f}</td>"
                f"<td>{pct_ret:.2f}%</td><td>{x_cdi:.2f}x</td><td>{x_cdi_liq:.2f}x</td></tr>"
            )
        lines.append("</table>")

        # Resumo estatístico dos cenários
        pnls = [c[9] for c in cenarios]
        rets = [c[10] for c in cenarios]
        cdi_vals = [c[11] for c in cenarios]
        cdi_liq_vals = [c[13] for c in cenarios]
        pior_pnl = min(pnls)
        melhor_pnl = max(pnls)
        lucros = sum(1 for v in pnls if v > 0)
        idx_pior = pnls.index(pior_pnl)
        idx_melhor = pnls.index(melhor_pnl)
        lines.append(
            f"<p><b>Resumo dos cenários:</b><br>"
            f"Pior PnL: {cenarios[idx_pior][1]} → <b>R$ {pior_pnl:.2f}</b> ({cenarios[idx_pior][10]:.2f}%, {cenarios[idx_pior][11]:.2f}x CDI Bruto / {cenarios[idx_pior][13]:.2f}x CDI Líq.)<br>"
            f"Melhor PnL: {cenarios[idx_melhor][1]} → <b>R$ {melhor_pnl:.2f}</b> ({cenarios[idx_melhor][10]:.2f}%, {cenarios[idx_melhor][11]:.2f}x CDI Bruto / {cenarios[idx_melhor][13]:.2f}x CDI Líq.)<br>"
            f"Faixa de ×CDI Bruto: {min(cdi_vals):.2f}x a {max(cdi_vals):.2f}x  |  "
            f"Faixa de ×CDI Líq.: {min(cdi_liq_vals):.2f}x a {max(cdi_liq_vals):.2f}x<br>"
            f"Cenários com lucro: <b>{lucros}/{len(cenarios)}</b> ({lucros/len(cenarios)*100:.0f}%)"
            f"</p>"
        )
        lines.append("<hr>")

        c_baixa = cenarios[0]
        c_baixa_label = c_baixa[1]
        tot_baixa = c_baixa[9]
        sinal_b = "lucro" if tot_baixa >= 0 else "prejuízo"
        lines.append(
            f"<p><b>Se o ativo cai para R$ {c_baixa[2]:.2f} ({c_baixa_label}):</b><br>"
            f"A CALL expira OTM → fica com +R$ {c_baixa[4]:.2f}.<br>"
            f"A PUT vale R$ {c_baixa[5]:.2f} pelo modelo BS "
            f"(intrínseco=R$ {c_baixa[6]:.2f}, extrínseco=R$ {c_baixa[7]:.2f}).<br>"
            f"<b>Resultado: R$ {tot_baixa:.2f} ({sinal_b})</b> "
            f"({c_baixa[10]:.2f}% / {c_baixa[11]:.2f}x CDI Bruto / {c_baixa[13]:.2f}x CDI Líq.) neste cenário.</p>"
        )

        c_proj = cenarios[4]
        call_itm_proj = S0 > Kc  # call esta ITM no spot atual?
        if call_itm_proj:
            call_texto = f"A CALL está ITM → ação vendida a R$ {Kc:.2f}, perda de R$ {c_proj[3]:.2f} na ação"
        else:
            call_texto = f"A CALL expira OTM → fica com +R$ {c_proj[4]:.2f}"
        lines.append(
            f"<p><b>Se o ativo mantém R$ {c_proj[2]:.2f} (cenário projetado):</b><br>"
            f"{call_texto}.<br>"
            f"A PUT ainda tem {r.dte_extra}d de vida, valendo R$ {c_proj[5]:.2f} "
            f"(intrínseco=R$ {c_proj[6]:.2f} + extrínseco=R$ {c_proj[7]:.2f}).<br>"
            f"<b>PnL = R$ {c_proj[9]:.2f}</b> ({c_proj[10]:.2f}% / {c_proj[11]:.2f}x CDI Bruto / {c_proj[13]:.2f}x CDI Líq.)</p>"
        )

        for idx, rotulo in [(8, "sobe para"), (5, "sobe levemente para")]:
            c_alta = cenarios[idx]
            c_alta_label = c_alta[1]
            tot_alta = c_alta[9]
            sinal_a = "lucro" if tot_alta >= 0 else "prejuízo"
            put_bs_a = c_alta[5]
            if put_bs_a < 0.01:
                put_texto = f"A PUT fica OTM → praticamente sem valor (BS=R$ {put_bs_a:.2f})"
            else:
                put_texto = f"A PUT fica OTM, mas ainda vale R$ {put_bs_a:.2f} (BS, {r.dte_extra}d restantes)"
            lines.append(
                f"<p><b>Se o ativo {rotulo} R$ {c_alta[2]:.2f} ({c_alta_label}):</b><br>"
                f"A CALL está ITM → ação é vendida a R$ {Kc:.2f}, "
                f"{'lucro' if c_alta[3] >= 0 else 'perda'} de R$ {c_alta[3]:.2f} na ação.<br>"
                f"{put_texto}<br>"
                f"<b>Resultado: R$ {tot_alta:.2f} ({sinal_a}).</b> "
                f"({c_alta[10]:.2f}% / {c_alta[11]:.2f}x CDI Bruto / {c_alta[13]:.2f}x CDI Líq.)</p>"
            )

        # Breakevens
        if r.be_baixa is not None or r.be_alta is not None:
            lines.append("<p><b>Breakevens B&S (com valor extrínseco da PUT):</b><br>")
            if r.be_baixa is not None:
                lines.append(f"BE Baixa: R$ {r.be_baixa:.2f}<br>")
            if r.be_alta is not None:
                lines.append(f"BE Alta: R$ {r.be_alta:.2f}<br>")
            if r.be_baixa is not None and r.be_alta is not None:
                lines.append("Considera o valor extrínseco residual da PUT no vencimento da CALL.</p>")
            else:
                lines.append("</p>")
        if r.be_baixa_intrinseco is not None or r.be_alta_intrinseco is not None:
            lines.append("<p><b>Breakevens Intrínseco (só valor intrínseco da PUT):</b><br>")
            if r.be_baixa_intrinseco is not None:
                lines.append(f"BE Baixa: R$ {r.be_baixa_intrinseco:.2f}<br>")
            if r.be_alta_intrinseco is not None:
                lines.append(f"BE Alta: R$ {r.be_alta_intrinseco:.2f}<br>")
            if r.be_baixa_intrinseco is not None and r.be_alta_intrinseco is not None:
                lines.append("Ignora valor extrínseco — cenário conservador (PUT vale só intrínseco).</p>")
            else:
                lines.append("</p>")
        if r.be_baixa is not None or r.be_alta is not None or r.be_baixa_intrinseco is not None or r.be_alta_intrinseco is not None:
            lines.append("<hr>")

        if sigma_pct > 0.001:
            p1s = [c for c in cenarios if abs(c[0]) <= 1.0]
            p2s = [c for c in cenarios if abs(c[0]) <= 2.0]
            p3s = [c for c in cenarios if abs(c[0]) <= 3.0]
            pnl_1s = [c[9] for c in p1s]
            pnl_2s = [c[9] for c in p2s]
            pnl_3s = [c[9] for c in p3s]
            lines.append(
                f"<p><b>Distribuição normal (σ = {sigma_pct*100:.1f}%):</b><br>"
                f"±1σ (~68% dos casos): PnL de R$ {min(pnl_1s):.2f} a R$ {max(pnl_1s):.2f}, "
                f"{len([c for c in p1s if c[9] > 0])}/{len(p1s)} positivos<br>"
                f"±2σ (~95% dos casos): PnL de R$ {min(pnl_2s):.2f} a R$ {max(pnl_2s):.2f}, "
                f"{len([c for c in p2s if c[9] > 0])}/{len(p2s)} positivos<br>"
                f"±3σ (~99,7% dos casos): PnL de R$ {min(pnl_3s):.2f} a R$ {max(pnl_3s):.2f}, "
                f"{len([c for c in p3s if c[9] > 0])}/{len(p3s)} positivos"
                f"</p>"
            )
            lines.append("<hr>")

        pnl_b3 = r.pnl_projetado - r.custo_b3
        pnl_liquido = pnl_b3 - r.custo_ir
        resumo_pnl = "lucro" if r.pnl_projetado >= 0 else "prejuízo"
        ext = abs(r.pnl_projetado)
        if call_Itm:
            lines.append(
                f"<p><b>Resumo:</b><br>"
                f"A CALL está ITM (acima do strike). O prêmio de R$ {Pc:.2f} "
                f"cobre a perda de R$ {S0 - Kc:.2f} na venda da ação. "
                f"O {resumo_pnl} bruto de R$ {ext:.2f} "
                f"({r.pct_retorno:.2f}% / {r.pct_cdi:.2f}x CDI Bruto) é o "
                f"extrínseco da CALL menos o custo líquido da PUT.</p>"
            )
        else:
            lines.append(
                f"<p><b>Resumo:</b><br>"
                f"Esta estratégia aposta que o ativo estará <b>próximo de R$ {Kc:.2f}</b> "
                f"no vencimento da CALL. O {resumo_pnl} bruto de R$ {ext:.2f} "
                f"({r.pct_retorno:.2f}% / {r.pct_cdi:.2f}x CDI Bruto) vem do "
                f"valor extrínseco residual da PUT. O resultado real "
                f"depende de onde o ativo estará naquele dia.</p>"
            )

        lines.append(
            "<p><b>Custos aplicados:</b><br>"
            f"PnL Bruto: <b>R$ {r.pnl_projetado:.2f}</b><br>"
            f"− Custos B3 (emol+liq+reg+ISS): <b>−R$ {r.custo_b3:.2f}</b><br>"
            f"= PnL pós-B3: <b>R$ {pnl_b3:.2f}</b><br>"
            f"− IR (15%): <b>−R$ {r.custo_ir:.2f}</b><br>"
            f"<b>= PnL Líquido: R$ {pnl_liquido:.2f}</b><br>"
            f"× CDI Bruto: {r.pct_cdi:.2f}x  |  × CDI Líquido: {r.pct_cdi_liquido:.2f}x"
            "</p>"
        )

        lines.append("<hr>")
        lines.append("<p><b>▸ Manejos Possíveis no vencimento da CALL:</b></p><ul>")

        if call_Itm:
            lines.append(
                f"<li><b>Exercício automático:</b> A CALL está ITM → a ação é vendida a "
                f"<b>R$ {Kc:.2f}</b>. Você recebe R$ {Pc:.2f} de prêmio e "
                f"a PUT residual ({r.dte_extra}d) vira proteção gratuita ou pode "
                f"ser vendida para realizar lucro extra.</li>"
                f"<li><b>Rolar para Bear Collar:</b> Se ainda quer exposição, recompre "
                f"a CALL (valor intrínseco ~R$ {S0 - Kc:.2f}) e venda uma CALL mais OTM "
                f"com o mesmo vencimento. A PUT existente vira a proteção do Bear Collar.</li>"
            )
        else:
            lines.append(
                f"<li><b>CALL OTM:</b> CALL expira sem valor. A ação fica livre — "
                f"você pode vendê-la no mercado e manter a PUT como seguro, ou "
                f"recomprar a PUT e encerrar tudo com lucro de R$ {Pc:.2f} (prêmio da CALL).</li>"
                f"<li><b>Rolar a CALL:</b> Vender outra CALL com mais DTE para coletar "
                f"mais prêmio, mantendo a PUT como proteção de longo prazo.</li>"
            )

        lines.append(
            f"<li><b>Fechamento antecipado:</b> Recompre a CALL e venda a PUT — "
            f"o lucro/prejuízo depende do valor de mercado no momento. "
            f"Use o gráfico de payoff para simular cenários.</li>"
            f"<li><b>Manutenção:</b> Se a PUT residual tem valor extrínseco significativo, "
            f"espere até o vencimento dela para maximizar o decaimento temporal.</li>"
        )
        lines.append("</ul>")

        return "\n".join(lines)
