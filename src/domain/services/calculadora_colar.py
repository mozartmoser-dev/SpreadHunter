from dataclasses import dataclass
from datetime import date
from enum import Enum

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

from src.domain.services.calendario_b3 import dc_to_du


class TipoColar(Enum):
    TRADICIONAL = "Tradicional"
    STRIKES_ABAIXO = "Strikes Abaixo"
    STRIKES_ACIMA = "Strikes Acima"


class RiscoLeilao(Enum):
    BAIXO = "Baixo"
    MEDIO = "Médio"
    ALTO = "Alto"


@dataclass
class ResultadoColar:
    ativo: str
    vencimento: date
    dias: int
    strike_put: float
    strike_call: float
    cod_put: str
    cod_call: str
    preco_ativo: float
    premio_put: float
    premio_call: float
    custo_liquido: float
    pior_retorno: float
    pct_ganho: float
    pct_cdi: float
    tipo: TipoColar
    risco_leilao: RiscoLeilao
    viavel: bool
    em_leilao: bool
    iv_call: float = 0.0
    iv_put: float = 0.0
    pop_upside: float = 0.0
    pop_downside: float = 0.0


@dataclass
class DadosPata:
    strike: float
    codigo: str
    premio_compra: float
    premio_venda: float
    vov: float
    voc: float
    qul: float
    status: str


class CalculadoraColar:
    def __init__(self, taxa_cdi: float, premio_risco_colar: float = 1.0):
        self.taxa_cdi = taxa_cdi
        self.premio_risco_colar = premio_risco_colar

    @staticmethod
    def black_scholes_call(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return max(S - K, 0)
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

    @staticmethod
    def black_scholes_put(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return max(K - S, 0)
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @staticmethod
    def calcular_iv(S, K, T, r, preco, tipo_opcao):
        if T <= 0 or preco <= 0:
            return None
        try:
            def f(sigma):
                if tipo_opcao == 'call':
                    return CalculadoraColar.black_scholes_call(S, K, T, r, sigma) - preco
                return CalculadoraColar.black_scholes_put(S, K, T, r, sigma) - preco
            return brentq(f, 1e-6, 5.0)
        except (ValueError, RuntimeError):
            return None

    @staticmethod
    def calcular_probabilidade_upside(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0.0 if S < K else 1.0
        d2 = (np.log(S / K) + (r - 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        return float(norm.cdf(d2))

    @staticmethod
    def calcular_probabilidade_downside(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 1.0 if S < K else 0.0
        d2 = (np.log(S / K) + (r - 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        return float(norm.cdf(-d2))

    def calcular_cdi_periodo(self, dias_uteis: int) -> float:
        if dias_uteis <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (dias_uteis / 252) - 1

    def classificar_tipo(self, preco_ativo: float, strike_put: float, strike_call: float) -> TipoColar:
        if preco_ativo < strike_put < strike_call:
            return TipoColar.STRIKES_ACIMA
        if strike_put < strike_call < preco_ativo:
            return TipoColar.STRIKES_ABAIXO
        return TipoColar.TRADICIONAL

    def calcular_pior_retorno(self, custo_liquido: float, strike_put: float, strike_call: float) -> float:
        return min(strike_put, strike_call) - custo_liquido

    def calcular_risco_leilao(self, vov_put: float, voc_call: float, status_put: str, status_call: str) -> RiscoLeilao:
        if status_put != "Aberto" or status_call != "Aberto":
            return RiscoLeilao.ALTO
        if vov_put <= 0 or voc_call <= 0:
            return RiscoLeilao.ALTO
        if vov_put >= 1000 and voc_call >= 1000:
            return RiscoLeilao.BAIXO
        return RiscoLeilao.MEDIO

    def calcular(
        self,
        preco_ativo: float,
        strike_put: float,
        strike_call: float,
        premio_put: float,
        premio_call: float,
        cod_put: str,
        cod_call: str,
        dias: int,
        vov_put: float,
        voc_call: float,
        status_put: str,
        status_call: str,
        ativo: str,
        vencimento: date,
        preco_compra_ativo: float | None = None,
    ) -> ResultadoColar | None:
        if preco_ativo <= 0 or dias <= 0:
            return None
        if premio_put <= 0 or premio_call <= 0:
            return None

        tipo = self.classificar_tipo(preco_ativo, strike_put, strike_call)
        em_leilao = status_put != "Aberto" or status_call != "Aberto"

        preco_compra = preco_compra_ativo if (preco_compra_ativo and preco_compra_ativo > 0) else preco_ativo
        custo_liquido = preco_compra + premio_put - premio_call
        if custo_liquido <= 0:
            return None

        cdi_periodo = self.calcular_cdi_periodo(dc_to_du(None, None, dias))
        if cdi_periodo <= 0:
            return None

        pior_retorno = self.calcular_pior_retorno(custo_liquido, strike_put, strike_call)
        pct_ganho = pior_retorno / custo_liquido
        pct_cdi = pct_ganho / cdi_periodo
        risco = self.calcular_risco_leilao(vov_put, voc_call, status_put, status_call)
        viavel = pct_cdi >= self.premio_risco_colar and not em_leilao

        T = dias / 365
        r = self.taxa_cdi
        iv_call = self.calcular_iv(preco_ativo, strike_call, T, r, premio_call, 'call')
        iv_put = self.calcular_iv(preco_ativo, strike_put, T, r, premio_put, 'put')
        if iv_call and iv_put:
            pop_upside = self.calcular_probabilidade_upside(preco_ativo, strike_call, T, r, (iv_call + iv_put) / 2)
            pop_downside = self.calcular_probabilidade_downside(preco_ativo, strike_put, T, r, (iv_call + iv_put) / 2)
        else:
            pop_upside = pop_downside = 0.0

        return ResultadoColar(
            ativo=ativo,
            vencimento=vencimento,
            dias=dias,
            strike_put=strike_put,
            strike_call=strike_call,
            cod_put=cod_put,
            cod_call=cod_call,
            preco_ativo=preco_ativo,
            premio_put=premio_put,
            premio_call=premio_call,
            custo_liquido=round(custo_liquido, 4),
            pior_retorno=round(pior_retorno, 4),
            pct_ganho=round(pct_ganho, 6),
            pct_cdi=round(pct_cdi, 4),
            tipo=tipo,
            risco_leilao=risco,
            viavel=viavel,
            em_leilao=em_leilao,
            iv_call=round(iv_call * 100, 2) if iv_call else 0.0,
            iv_put=round(iv_put * 100, 2) if iv_put else 0.0,
            pop_upside=round(pop_upside * 100, 1),
            pop_downside=round(pop_downside * 100, 1),
        )
