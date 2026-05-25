from dataclasses import dataclass
from datetime import date
from enum import Enum
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


class TipoColarCalendario(Enum):
    ALTA = "Alta"
    BAIXA = "Baixa"
    NEUTRO = "Neutro"


@dataclass
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
    pnl_projetado: float
    pct_retorno: float
    pct_cdi: float
    theta_call: float
    theta_put: float
    theta_liquido: float
    tipo: TipoColarCalendario
    viavel: bool


class CalculadoraColarCalendario:
    def __init__(self, taxa_cdi: float = 0.1450, premio_risco: float = 1.0):
        self.taxa_cdi = taxa_cdi
        self.premio_risco = premio_risco

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
    def implied_volatility(S: float, K: float, T: float, r: float, market_price: float, option_type: str) -> float | None:
        if market_price <= 0 or T <= 0:
            return None
        def f(sigma):
            return CalculadoraColarCalendario.black_scholes(S, K, T, r, sigma, option_type) - market_price
        try:
            return brentq(f, 1e-6, 5.0)
        except (ValueError, RuntimeError):
            return None

    def calcular_cdi_periodo(self, dias: int) -> float:
        if dias <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (dias / 365) - 1

    def classificar_tipo(self, preco_ativo: float, strike_call: float, strike_put: float) -> TipoColarCalendario:
        meio = (strike_call + strike_put) / 2
        dist = abs(preco_ativo - meio)
        limiar = (strike_call - strike_put) * 0.15
        if dist <= limiar:
            return TipoColarCalendario.NEUTRO
        if preco_ativo < meio:
            return TipoColarCalendario.ALTA
        return TipoColarCalendario.BAIXA

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
        r: float = 0.1325,
    ) -> ResultadoColarCalendario | None:
        if preco_ativo <= 0 or dte_call <= 0 or dte_put <= 0:
            return None
        if premio_call <= 0 or premio_put <= 0:
            return None

        T_call = dte_call / 365
        T_put = dte_put / 365
        dte_extra = dte_put - dte_call

        iv_call = self.implied_volatility(preco_ativo, strike_call, T_call, r, premio_call, 'call')
        iv_put = self.implied_volatility(preco_ativo, strike_put, T_put, r, premio_put, 'put')

        if iv_call is None or iv_put is None:
            return None

        net_credito = premio_call - premio_put
        tipo = self.classificar_tipo(preco_ativo, strike_call, strike_put)

        theta_call = self.bs_theta(preco_ativo, strike_call, T_call, r, iv_call, 'call')
        theta_put = self.bs_theta(preco_ativo, strike_put, T_put, r, iv_put, 'put')
        theta_liquido = abs(theta_call) - abs(theta_put)

        T_put_rem = dte_extra / 365 if dte_extra > 0 else 0
        valor_put_vc = self.black_scholes(preco_ativo, strike_put, T_put_rem, r, iv_put, 'put') if T_put_rem > 0 else 0

        pnl_call = premio_call
        pnl_put = valor_put_vc - premio_put
        pnl_projetado = pnl_call + pnl_put

        if pnl_projetado <= 0:
            return None

        dias_total = dte_call
        cdi_periodo = self.calcular_cdi_periodo(dias_total)
        if cdi_periodo <= 0:
            return None

        pct_retorno = pnl_projetado / premio_put if premio_put > 0 else 0
        pct_cdi = pct_retorno / cdi_periodo if cdi_periodo > 0 else 0
        viavel = pct_cdi >= self.premio_risco

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
            iv_call=round(iv_call * 100, 2),
            iv_put=round(iv_put * 100, 2),
            valor_put_venc_call=round(valor_put_vc, 4),
            pnl_projetado=round(pnl_projetado, 4),
            pct_retorno=round(pct_retorno * 100, 4),
            pct_cdi=round(pct_cdi, 4),
            theta_call=round(theta_call * 100, 4),
            theta_put=round(theta_put * 100, 4),
            theta_liquido=round(theta_liquido * 100, 4),
            tipo=tipo,
            viavel=viavel,
        )
