import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)
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
    lado_protegido: str | None = None
    custo_protecao_total: float = 0.0
    pnl_liquido_pos_protecao: float = 0.0
    strike_protecao_call: float | None = None
    strike_protecao_put: float | None = None
    qtd_protecao_call: int = 0
    qtd_protecao_put: int = 0
    custo_protecao_call: float = 0.0
    custo_protecao_put: float = 0.0
    viavel_protecao: bool = False
    strikes_bwb_call: str | None = None
    strikes_bwb_put: str | None = None
    premios_bwb_call: str | None = None
    premios_bwb_put: str | None = None
    custo_borboleta_call: float = 0.0
    custo_borboleta_put: float = 0.0
    lotes_bwb_call: int = 0
    lotes_bwb_put: int = 0
    cod_prot_call: str | None = None
    cod_prot_put: str | None = None
    premio_book_call: float = 0.0
    premio_book_put: float = 0.0
    score_ev: float = 0.0
    score_ev_pct: float = 0.0
    zonas_ev_json: str | None = None


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
        T_rem = dc_to_du(None, None, dte_extra) / 252.0 if dte_extra > 0 else 0
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
        if qtd_acao % 100 != 0 or qtd_call % 100 != 0 or qtd_put % 100 != 0:
            logger.debug("CollarCal CALC %s: qtd nao multipla de 100 acao=%d call=%d put=%d", ativo, qtd_acao, qtd_call, qtd_put)
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

        pct_retorno = pnl_projetado / capital_base if capital_base > 0 else 0
        pct_cdi = pct_retorno / cdi_periodo if cdi_periodo > 0 else 0
        pct_cdi_liquido = (pnl_projetado_ir / capital_base) / cdi_periodo if cdi_periodo > 0 else 0.0
        viavel = pct_cdi >= self.premio_risco

        be_baixa, be_alta = self._calcular_breakevens(
            preco_ativo, strike_call, strike_put,
            premio_call, premio_put, dte_extra, r_cont, iv_put,
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
    @staticmethod
    def gerar_explicacao(r: 'ResultadoColarCalendario', taxa_cdi: float = 0.1450) -> str:
        import numpy as np
        from scipy.stats import norm

        S0 = r.preco_ativo
        Kc, Kp = r.strike_call, r.strike_put
        Pc, Pp = r.premio_call, r.premio_put
        T_rem = dc_to_du(None, None, r.dte_extra) / 252.0 if r.dte_extra > 0 else 0.0
        iv_p = r.iv_put / 100
        iv_call_dec = r.iv_call / 100.0
        rf = np.log(1 + getattr(r, 'r', 0.1450))

        is_otimizado = getattr(r, 'is_otimizado', False)
        estagio = getattr(r, 'estagio_otimizado', None)
        ratio_call = getattr(r, 'ratio_call', 1.0)
        ratio_put = getattr(r, 'ratio_put', 1.0)
        be_baixa = getattr(r, 'be_baixa', None)
        be_alta = getattr(r, 'be_alta', None)

        qtd_acao = r.qtd_acao
        _LOTE = 100
        raw_call = r.qtd_call * ratio_call
        raw_put = r.qtd_put * ratio_put
        qtd_call_real = max(1, int(raw_call / _LOTE + 0.5)) * _LOTE if qtd_acao > 0 else raw_call
        qtd_put_real = max(0, int(raw_put / _LOTE + 0.5)) * _LOTE if qtd_acao > 0 else raw_put

        cap = S0 * qtd_acao + Pp * qtd_put_real - Pc * qtd_call_real
        net = Pc * qtd_call_real - Pp * qtd_put_real

        # ── MOD (tipo_opcao) da CALL via DB ──
        mod_call = None
        try:
            from src.infrastructure.persistence.database import get_connection
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT tipo_opcao FROM instrumentos_base WHERE ativo = ? AND cod_put = ?",
                    (r.ativo, r.cod_put)
                ).fetchone()
                if row:
                    mod_call_db = row["tipo_opcao"]
                    mod_call = "AMERICANA" if mod_call_db in ("AMERICANA", "A") else "EUROPEIA"
            finally:
                conn.close()
        except Exception:
            pass

        def bs_put(S, K, T, sigma):
            if T <= 0 or sigma <= 0:
                return max(K - S, 0)
            d1 = (np.log(S / K) + (rf + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            return K * np.exp(-rf * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        # ── Cenários ──
        T_call_ano = dc_to_du(None, None, r.dte_call) / 252.0
        sigma_pct = iv_call_dec * np.sqrt(T_call_ano) if iv_call_dec > 1e-10 else 0.0

        if sigma_pct > 0.001:
            drift = (rf - 0.5 * iv_call_dec ** 2) * T_call_ano
            pares_cenarios = [
                (-3.0, f"\u22123\u03c3 (\u2212{3*sigma_pct*100:.1f}%)",  S0 * np.exp(drift - 3*sigma_pct)),
                (-2.0, f"\u22122\u03c3 (\u2212{2*sigma_pct*100:.1f}%)",  S0 * np.exp(drift - 2*sigma_pct)),
                (-1.0, f"\u22121\u03c3 (\u2212{sigma_pct*100:.1f}%)",  S0 * np.exp(drift - sigma_pct)),
                (-0.5, f"\u22125%", S0 * np.exp(drift - 0.5*sigma_pct)),
                (0.0,  f"0\u03c3 \u2014 Est\u00e1vel",                    S0 * np.exp(drift)),
                (0.5,  f"+5%",       S0 * np.exp(drift + 0.5*sigma_pct)),
                (1.0,  f"+1\u03c3 (+{sigma_pct*100:.1f}%)",            S0 * np.exp(drift + sigma_pct)),
                (2.0,  f"+2\u03c3 (+{2*sigma_pct*100:.1f}%)",            S0 * np.exp(drift + 2*sigma_pct)),
                (3.0,  f"+3\u03c3 (+{3*sigma_pct*100:.1f}%)",            S0 * np.exp(drift + 3*sigma_pct)),
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
        naked_call = max(0, qtd_call_real - qtd_acao)

        # ── Título ──
        titulo = f"Collar Calendário Otimizado — {estagio}" if (is_otimizado and estagio) else "Collar Calendário Coberto"
        lines = [
            f"<h3>\U0001f4d6 Explica\u00e7\u00e3o \u2014 {titulo}</h3>",
            f"<p><b>{r.ativo}</b> &mdash; {r.tipo.value}</p>",
            "<hr>",
        ]

        # ── Estratégia ──
        if is_otimizado:
            lines.append("<p><b>Estrat\u00e9gia otimizada:</b><br>")
            if ratio_call > 1.0:
                lines.append(
                    f"<b>{ratio_call:.2f}\u00d7 CALLs</b> vendidas por a\u00e7\u00e3o "
                    f"(+{qtd_call_real - qtd_acao} CALLs extras vs base 1:1). "
                    f"Isso aumenta o pr\u00eamio recebido, mas cria exposi\u00e7\u00e3o naked no upside.<br>"
                )
            if ratio_put < 1.0:
                lines.append(
                    f"<b>{ratio_put:.2f}\u00d7 PUTs</b> compradas por a\u00e7\u00e3o "
                    f"(\u2212{int(qtd_acao - qtd_put_real)} PUTs vs base 1:1). "
                    f"Menos prote\u00e7\u00e3o na cauda, mas reduz o custo.<br>"
                )
            lines.append(
                "Validado por stress-test: PnL > 0 nos extremos de \u00b12.2\u03c3.</p>"
            )
        else:
            lines.append(
                "<p><b>O que \u00e9 esta estrat\u00e9gia?</b><br>"
                "Compra a\u00e7\u00e3o, vende CALL curta e compra PUT longa. "
                "Lucro vem do decaimento temporal diferencial: CALL perde valor mais r\u00e1pido "
                f"nos primeiros {r.dte_call}d, enquanto PUT ainda tem {r.dte_extra}d de vida.</p>"
            )
        lines.append("<hr>")

        # ── Montagem ──
        lines.append("<p><b>Montagem:</b></p><ul>")
        lines.append(f"<li>A\u00e7\u00e3o ({qtd_acao}x): <b>\u2212R$ {S0 * qtd_acao:.2f}</b></li>")
        lines.append(
            f"<li>Vender CALL {r.cod_call} K={Kc:.2f} "
            f"({int(qtd_call_real)}x, ratio {ratio_call:.2f}): <b>+R$ {Pc * qtd_call_real:.2f}</b></li>"
        )
        lines.append(
            f"<li>Comprar PUT {r.cod_put} K={Kp:.2f} "
            f"({int(qtd_put_real)}x, ratio {ratio_put:.2f}): <b>\u2212R$ {Pp * qtd_put_real:.2f}</b></li>"
        )
        lines.append(
            f"<li><b>Capital = R$ {cap:.2f}</b></li>"
            f"<li>D\u00e9bito/Cr\u00e9dito: <b>R$ {net:.2f}</b></li>"
        )
        lines.append("</ul><hr>")

        # ── Cenários ──
        du_total = dc_to_du(None, None, r.dte_call)
        cdi_periodo = np.exp(rf * du_total / 252) - 1
        nota_sigma = f" (1\u03c3={sigma_pct*100:.1f}%, IV call {iv_call_dec*100:.0f}%, {r.dte_call}d)" if sigma_pct > 0.001 else ""

        k_tail_c = getattr(r, 'strike_protecao_call', None)
        k_tail_p = getattr(r, 'strike_protecao_put', None)
        q_tc = getattr(r, 'qtd_protecao_call', 0) or 0
        q_tp = getattr(r, 'qtd_protecao_put', 0) or 0
        tem_tail = (k_tail_c and q_tc > 0) or (k_tail_p and q_tp > 0)

        lines.append(
            f"<p><b>Cen\u00e1rios no vencimento da CALL ({r.dte_call}d):</b>{nota_sigma}</p>"
            "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; font-size:9pt;'>"
            "<tr style='background:#2d2d44;'>"
            "<th></th><th>Cen\u00e1rio</th><th>S_T</th><th>A\u00e7\u00e3o</th><th>CALL</th>"
            "<th>PUT (BS)</th><th>PnL Total</th><th>% Ret</th><th>\u00d7 CDI</th>"
            + ("<th>\U0001f6e1 PnL Tail</th><th>\u00d7 CDI Tail</th></tr>" if tem_tail else "</tr>")
        )

        cenarios = []
        for n_sigma, label, S_T in pares_cenarios:
            s_pnl_u = S_T - S0
            c_pnl_u = Pc - max(0, S_T - Kc)
            put_bs_u = bs_put(S_T, Kp, T_rem, iv_p)
            p_pnl_u = put_bs_u - Pp

            s_pnl = s_pnl_u * qtd_acao
            c_pnl = c_pnl_u * qtd_call_real
            p_pnl = p_pnl_u * qtd_put_real
            naked = -naked_call * max(0, S_T - Kc) if naked_call > 0 else 0.0

            total = s_pnl + c_pnl + naked + p_pnl
            pct_ret = (total / cap) * 100 if cap > 0 else 0.0
            x_cdi = (total / cap) / cdi_periodo if cdi_periodo > 0 and cap > 0 else 0.0

            # ── Tail Protect scenario ──
            tail_payoff = 0.0
            c_tc = getattr(r, 'custo_protecao_call', 0.0) or 0.0
            c_tp = getattr(r, 'custo_protecao_put', 0.0) or 0.0
            if k_tail_c and q_tc > 0:
                tail_payoff += (max(0, S_T - k_tail_c) - (c_tc / max(q_tc, 1))) * q_tc
            if k_tail_p and q_tp > 0:
                tail_payoff += (max(0, k_tail_p - S_T) - (c_tp / max(q_tp, 1))) * q_tp
            total_tail = total + tail_payoff
            x_cdi_tail = (total_tail / cap) / cdi_periodo if cdi_periodo > 0 and cap > 0 else 0.0

            pdf = norm.pdf(n_sigma, 0.0, 1.0)
            bar_pct = max(4, int(28 * pdf / pdf_peak))
            cenarios.append((n_sigma, label, S_T, s_pnl, c_pnl, put_bs_u * qtd_put_real, total, pct_ret, x_cdi, bar_pct, tem_tail, total_tail, x_cdi_tail))

        for n_sigma, label, S_T, s_pnl, c_pnl, put_bs, total, pct_ret, x_cdi, bar_pct, __, total_tail, x_cdi_tail in cenarios:
            cor = "#2ecc71" if total > 0 else "#e74c3c"
            svg_bar = (
                f'<svg width="28" height="18" viewBox="0 0 28 18">'
                f'<rect x="{(28-bar_pct)/2:.1f}" y="3" width="{bar_pct}" height="12" '
                f'fill="rgba(255,255,255,0.10)" rx="2"/></svg>'
            )
            row = (
                f"<tr>"
                f"<td style='text-align:center;'>{svg_bar}</td>"
                f"<td>{label}</td><td>R$ {S_T:.2f}</td><td>R$ {s_pnl:.2f}</td>"
                f"<td>R$ {c_pnl:.2f}</td><td>R$ {put_bs:.2f}</td>"
                f"<td style='color:{cor};font-weight:bold;'>R$ {total:.2f}</td>"
                f"<td>{pct_ret:.2f}%</td><td>{x_cdi:.2f}x</td>"
            )
            if tem_tail:
                cor_tail = "#2ecc71" if total_tail > 0 else "#e74c3c"
                row += (f"<td style='color:{cor_tail};font-weight:bold;'>R$ {total_tail:.2f}</td>"
                        f"<td>{x_cdi_tail:.2f}x</td>")
            row += "</tr>"
            lines.append(row)
        lines.append("</table>")

        pnls = [c[6] for c in cenarios]
        cdi_vals = [c[8] for c in cenarios]
        lines.append(
            f"<p><b>Resumo:</b> \u00d7CDI de {min(cdi_vals):.2f}x a {max(cdi_vals):.2f}x | "
            f"Lucro em {sum(1 for v in pnls if v > 0)}/{len(pnls)} cen\u00e1rios</p><hr>"
        )

        # ── Breakevens ──
        if be_baixa is not None or be_alta is not None:
            lines.append("<p><b>Breakevens (PnL = 0):</b><br>")
            if be_baixa is not None:
                lines.append(f"BE Baixa = R$ {be_baixa:.2f}<br>")
            if be_alta is not None:
                lines.append(f"BE Alta = R$ {be_alta:.2f}<br>")
            lines.append("</p><hr>")

        # ── BWB ──
        lado_protegido = getattr(r, 'lado_protegido', None)
        custo_prot = getattr(r, 'custo_protecao_total', 0.0) or 0.0
        pnl_pos_bwb = getattr(r, 'pnl_liquido_pos_protecao', 0.0) or 0.0
        pnl_atual = r.pnl_projetado

        if lado_protegido and lado_protegido not in ("nenhum", None) and custo_prot > 0:
            is_bwb = bool(getattr(r, 'strikes_bwb_call', None))
            titulo = "\U0001f6e1 Prote\u00e7\u00e3o BWB (Broken Wing Butterfly):" if is_bwb else "\U0001f6e1 Prote\u00e7\u00e3o:"
            lines.append(f"<p><b>{titulo}</b></p><ul>")
            lines.append(f"<li>Lado protegido: <b>{lado_protegido}</b></li>")
            lines.append(f"<li>PnL antes da prote\u00e7\u00e3o: <b>R$ {pnl_atual:.2f}</b></li>")
            lines.append(f"<li>Custo da prote\u00e7\u00e3o: <b>\u2212R$ {custo_prot:.2f}</b></li>")
            lines.append(f"<li><b>PnL L\u00edquido P\u00f3s-BWB: R$ {pnl_pos_bwb:.2f}</b></li>")

            k_bwb_c = getattr(r, 'strike_protecao_call', None)
            k_bwb_p = getattr(r, 'strike_protecao_put', None)
            q_bwb_c = getattr(r, 'qtd_protecao_call', 0) or 0
            q_bwb_p = getattr(r, 'qtd_protecao_put', 0) or 0

            if k_bwb_c and q_bwb_c > 0:
                lines.append(f"<li>Compra CALL K={k_bwb_c:.2f} ({q_bwb_c}x) \u2014 prote\u00e7\u00e3o cauda direita</li>")
            if k_bwb_p and q_bwb_p > 0:
                lines.append(f"<li>Compra PUT K={k_bwb_p:.2f} ({q_bwb_p}x) \u2014 prote\u00e7\u00e3o cauda esquerda</li>")

            pct_cdi_antes = (pnl_atual / cap) / cdi_periodo if cdi_periodo > 0 and cap > 0 else 0.0
            pct_cdi_depois = (pnl_pos_bwb / cap) / cdi_periodo if cdi_periodo > 0 and cap > 0 else 0.0
            lines.append(f"<li>\u00d7 CDI: {pct_cdi_antes:.2f}x \u2192 <b>{pct_cdi_depois:.2f}x</b> (ap\u00f3s BWB)</li>")

            score_ev = getattr(r, 'score_ev', 0.0) or 0.0
            score_ev_pct = getattr(r, 'score_ev_pct', 0.0) or 0.0
            if score_ev != 0.0:
                cor_ev = "#2ecc71" if score_ev > 0 else "#e74c3c"
                lines.append(f"<li><b>E[PnL] (Valor Esperado): <span style='color:{cor_ev};'>R$ {score_ev:,.2f}</span> ({score_ev_pct:+.2f}%)</b></li>")
            lines.append("</ul><hr>")

        # ── Tail Protect ──
        cod_tail_c = getattr(r, 'cod_prot_call', None)
        cod_tail_p = getattr(r, 'cod_prot_put', None)
        k_tail_c = getattr(r, 'strike_protecao_call', None)
        k_tail_p = getattr(r, 'strike_protecao_put', None)
        custo_tail = getattr(r, 'custo_protecao_total', 0.0) or 0.0
        pnl_tail = getattr(r, 'pnl_liquido_pos_protecao', 0.0) or 0.0
        if (cod_tail_c or cod_tail_p) and custo_tail > 0 and not (lado_protegido and lado_protegido not in ("nenhum", None)):
            lines.append("<p><b>\U0001f6e1 Tail Protect (Prote\u00e7\u00e3o Simples):</b></p><ul>")
            if cod_tail_c and k_tail_c:
                premio_tc = getattr(r, 'premio_book_call', 0.0) or getattr(r, 'premio_ask_protecao_call', 0.0) or 0.0
                lines.append(f"<li>Compra CALL {cod_tail_c} K={k_tail_c:.2f} \u2014 ask R$ {premio_tc:.4f}/a\u00e7\u00e3o</li>")
            if cod_tail_p and k_tail_p:
                premio_tp = getattr(r, 'premio_book_put', 0.0) or getattr(r, 'premio_ask_protecao_put', 0.0) or 0.0
                lines.append(f"<li>Compra PUT {cod_tail_p} K={k_tail_p:.2f} \u2014 ask R$ {premio_tp:.4f}/a\u00e7\u00e3o</li>")
            lines.append(f"<li>Custo total: <b>R$ {custo_tail:.2f}</b></li>")
            lines.append(f"<li>PnL p\u00f3s-prote\u00e7\u00e3o: <b>R$ {pnl_tail:.2f}</b></li>")
            pct_cdi_tail = (pnl_tail / cap) / cdi_periodo if cdi_periodo > 0 and cap > 0 else 0.0
            lines.append(f"<li>\u00d7 CDI p\u00f3s-Tail: <b>{pct_cdi_tail:.2f}x</b></li>")
            lines.append("</ul><hr>")

        # ── MOD / Risco de Exercício ──
        lines.append("<p><b>\u26a0\ufe0f An\u00e1lise MOD (Risco de Exerc\u00edcio):</b></p><ul>")
        if mod_call:
            call_label = "Americana (A)" if mod_call == "AMERICANA" else "Europeia (E)"
            lines.append(f"<li>CALL {r.cod_call}: <b>{call_label}</b> \u2014 Voc\u00ea est\u00e1 <b>VENDIDO</b></li>")
        else:
            lines.append(f"<li>CALL {r.cod_call}: MOD n\u00e3o dispon\u00edvel (verificar cadastro)</li>")
        lines.append(f"<li>PUT {r.cod_put}: <b>Europeia (E)</b> \u2014 Voc\u00ea est\u00e1 <b>COMPRADO</b></li>")

        if mod_call == "AMERICANA":
            lines.append(
                "<li style='color:#e74c3c;'><b>\u26a0\ufe0f RISCO:</b> CALL Americana vendida "
                "pode ser exercida a qualquer momento. Se o ativo subir e a CALL ficar deep ITM, "
                "voc\u00ea pode ser for\u00e7ado a entregar as a\u00e7\u00f5es antes do vencimento.</li>"
                "<li style='color:#f39c12;'>Mitiga\u00e7\u00e3o: Dividendos s\u00e3o o principal gatilho "
                "de exerc\u00edcio antecipado em CALLs. Monitore a data-ex.</li>"
            )
        elif mod_call == "EUROPEIA":
            lines.append(
                "<li style='color:#2ecc71;'><b>\u2705 SEM RISCO</b> de exerc\u00edcio antecipado: "
                "CALL Europeia s\u00f3 exerce no vencimento.</li>"
                "<li><b>Ambas Europeias:</b> Se liquidez sumir, exerc\u00edcio no vencimento "
                "\u00e9 autom\u00e1tico e garantido pelo MOD.</li>"
            )

        lines.append(
            "<li style='color:#2ecc71;'><b>\u2705 PUT Europeia comprada:</b> Voc\u00ea controla o exerc\u00edcio. "
            "Sem risco de ser exercido contra voc\u00ea.</li>"
        )
        lines.append("</ul><hr>")

        # ── Custos ──
        pnl_b3 = pnl_atual - r.custo_b3
        pnl_liquido = pnl_b3 - r.custo_ir
        lines.append(
            "<p><b>Custos:</b><br>"
            f"PnL com ratio: <b>R$ {pnl_atual:.2f}</b><br>"
            f"\u2212 Custos B3: <b>\u2212R$ {r.custo_b3:.2f}</b><br>"
            f"= PnL p\u00f3s-B3: <b>R$ {pnl_b3:.2f}</b><br>"
            f"\u2212 IR (15%): <b>\u2212R$ {r.custo_ir:.2f}</b><br>"
            f"<b>= PnL L\u00edquido: R$ {pnl_liquido:.2f}</b><br>"
            f"\u00d7 CDI: {r.pct_cdi:.2f}x"
        )
        if is_otimizado and lado_protegido and lado_protegido != "nenhum" and custo_prot > 0:
            x_cdi_pos_bwb = (pnl_pos_bwb / cap) / cdi_periodo if cdi_periodo > 0 and cap > 0 else 0.0
            lines.append(f"  |  \u00d7 CDI P\u00f3s-BWB: {x_cdi_pos_bwb:.2f}x")
        lines.append("</p><hr>")

        # ── Manejos ──
        call_Itm = S0 > Kc
        lines.append("<p><b>\u25b8 Manejos no vencimento da CALL:</b></p><ul>")
        if call_Itm:
            lines.append(
                f"<li><b>Exerc\u00edcio autom\u00e1tico:</b> CALL ITM \u2192 a\u00e7\u00e3o vendida a R$ {Kc:.2f}. "
                f"PUT residual ({r.dte_extra}d) vira prote\u00e7\u00e3o gratuita.</li>"
            )
        else:
            lines.append(
                f"<li><b>CALL OTM:</b> Expira sem valor. A\u00e7\u00e3o fica livre.</li>"
            )
        if naked_call > 0:
            lines.append(
                f"<li style='color:#e74c3c;'><b>Aten\u00e7\u00e3o:</b> {int(naked_call)} CALLs nuas. "
                f"Se S &gt; Kc=R$ {Kc:.2f}, recompre antes do vencimento para evitar perda ilimitada.</li>"
            )
        if mod_call == "AMERICANA":
            lines.append(
                "<li style='color:#f39c12;'><b>CALL Americana:</b> Risco de exerc\u00edcio antecipado. "
                "Monitore eventos corporativos (dividendos, JCP).</li>"
            )
        lines.append(
            f"<li><b>Fechamento antecipado:</b> Recompre CALL e venda PUT.</li>"
            f"<li><b>Manuten\u00e7\u00e3o:</b> Se PUT tem valor extr\u00ednseco, aguarde decaimento.</li>"
        )
        lines.append("</ul>")

        return "\n".join(lines)
