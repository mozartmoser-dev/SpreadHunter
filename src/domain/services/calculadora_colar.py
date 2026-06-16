import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3

logger = logging.getLogger(__name__)


class TipoColar(Enum):
    TRADICIONAL = "Viés Neutro"
    STRIKES_ABAIXO = "Viés Baixa"
    STRIKES_ACIMA = "Viés Alta"


class RiscoLeilao(Enum):
    BAIXO = "Baixo"
    MEDIO = "Médio"
    ALTO = "Alto"


@dataclass(slots=True)
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
    melhor_retorno: float
    pct_ganho: float
    pct_cdi: float
    pct_cdi_melhor: float
    tipo: TipoColar
    risco_leilao: RiscoLeilao
    viavel: bool
    em_leilao: bool
    custo_b3: float = 0.0
    custo_ir: float = 0.0
    custo_ir_melhor: float = 0.0
    pct_cdi_liquido: float = 0.0
    pct_cdi_melhor_liquido: float = 0.0
    iv_call: float = 0.0
    iv_put: float = 0.0
    pop_upside: float | None = None
    pop_downside: float | None = None
    score: float = 0.0


@dataclass(slots=True)
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
    def __init__(self, taxa_cdi: float, premio_risco_colar: float = 1.05, colar_risco_baixo_vov_min: float = 1000.0, custos_b3: CalculadoraCustosB3 | None = None, taxa_ir: float | None = None):
        self.taxa_cdi = taxa_cdi
        self.premio_risco_colar = premio_risco_colar
        self.colar_risco_baixo_vov_min = colar_risco_baixo_vov_min
        self.custos_b3 = custos_b3 or CalculadoraCustosB3(taxa_ir=taxa_ir)

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

            intrinsic = max(S - K, 0) if tipo_opcao == 'call' else max(K - S, 0)
            if abs(preco - intrinsic) < 1e-10:
                return 0.0

            a, b = 1e-8, 5.0
            fa, fb = f(a), f(b)
            for _ in range(20):
                if fa * fb < 0:
                    return brentq(f, a, b)
                if fa == 0:
                    return 0.0
                if fb == 0:
                    b *= 2
                    fb = f(b)
                    continue
                if abs(fa) < abs(fb):
                    a = max(a / 2, 1e-12)
                    fa = f(a)
                else:
                    b *= 2
                    fb = f(b)
            return None
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
        if vov_put >= self.colar_risco_baixo_vov_min and voc_call >= self.colar_risco_baixo_vov_min:
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
            logger.debug("Collar CALC %s %s %s: preco_ativo<=0 ou dias<=0", ativo, cod_put, cod_call)
            return None
        if premio_put <= 0 or premio_call <= 0:
            logger.debug("Collar CALC %s %s %s: premio<=0 put=%s call=%s", ativo, cod_put, cod_call, premio_put, premio_call)
            return None

        tipo = self.classificar_tipo(preco_ativo, strike_put, strike_call)
        em_leilao = status_put != "Aberto" or status_call != "Aberto"

        preco_compra = preco_compra_ativo if (preco_compra_ativo and preco_compra_ativo > 0) else 0.0
        if preco_compra <= 0:
            logger.debug("Collar CALC %s %s %s: preco_compra_ativo=%.2f (ask do ativo zerado)", ativo, cod_put, cod_call, preco_compra_ativo or 0)
            return None
        custo_liquido = preco_compra + premio_put - premio_call
        if custo_liquido <= 0:
            logger.debug("Collar CALC %s %s %s: custo_liquido<=0 (compra=%.2f + put=%.2f - call=%.2f)", ativo, cod_put, cod_call, preco_compra, premio_put, premio_call)
            return None

        cdi_periodo = self.calcular_cdi_periodo(dc_to_du(None, None, dias))
        if cdi_periodo <= 0:
            return None

        pior_retorno = self.calcular_pior_retorno(custo_liquido, strike_put, strike_call)
        melhor_retorno = max(strike_put, strike_call) - custo_liquido

        premio_medio = (premio_put + premio_call) / 2
        custo_b3 = (self.custos_b3.custos_opcao(premio_medio, n_pernas=2) +
                    self.custos_b3.custos_stock(preco_compra, n_acoes=1))
        pior_retorno_liquido = pior_retorno - custo_b3
        melhor_retorno_liquido = melhor_retorno - custo_b3

        custo_ir_pior = self.custos_b3.ajustar_ir(max(pior_retorno_liquido, 0.0))
        custo_ir_melhor = self.custos_b3.ajustar_ir(max(melhor_retorno_liquido, 0.0))
        pior_retorno_liquido_ir = pior_retorno_liquido - custo_ir_pior
        melhor_retorno_liquido_ir = melhor_retorno_liquido - custo_ir_melhor

        pct_ganho = pior_retorno_liquido / custo_liquido
        pct_cdi = pct_ganho / cdi_periodo
        pct_cdi_melhor = (melhor_retorno_liquido / custo_liquido) / cdi_periodo if cdi_periodo > 0 else 0
        pct_cdi_liquido = (pior_retorno_liquido_ir / custo_liquido) / cdi_periodo if cdi_periodo > 0 else 0.0
        pct_cdi_melhor_liquido = (melhor_retorno_liquido_ir / custo_liquido) / cdi_periodo if cdi_periodo > 0 else 0.0
        risco = self.calcular_risco_leilao(vov_put, voc_call, status_put, status_call)
        viavel = pct_cdi >= self.premio_risco_colar and not em_leilao

        du_bs = dc_to_du(None, None, dias)
        T = du_bs / 252.0
        r = np.log(1 + self.taxa_cdi)
        iv_call = self.calcular_iv(preco_ativo, strike_call, T, r, premio_call, 'call')
        iv_put = self.calcular_iv(preco_ativo, strike_put, T, r, premio_put, 'put')
        pop_upside = pop_downside = None
        if iv_call is not None and iv_put is not None:
            sigma_medio = (iv_call + iv_put) / 2
            if sigma_medio > 0:
                pop_upside = self.calcular_probabilidade_upside(preco_ativo, strike_call, T, r, sigma_medio)
                pop_downside = self.calcular_probabilidade_downside(preco_ativo, strike_put, T, r, sigma_medio)
        elif iv_call is not None and iv_call > 0:
            pop_upside = self.calcular_probabilidade_upside(preco_ativo, strike_call, T, r, iv_call)
            pop_downside = self.calcular_probabilidade_downside(preco_ativo, strike_put, T, r, iv_call)
        elif iv_put is not None and iv_put > 0:
            pop_upside = self.calcular_probabilidade_upside(preco_ativo, strike_call, T, r, iv_put)
            pop_downside = self.calcular_probabilidade_downside(preco_ativo, strike_put, T, r, iv_put)

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
            custo_b3=round(custo_b3, 4),
            custo_ir=round(custo_ir_pior, 4),
            custo_ir_melhor=round(custo_ir_melhor, 4),
            pior_retorno=round(pior_retorno, 4),
            melhor_retorno=round(melhor_retorno, 4),
            pct_ganho=round(pct_ganho, 6),
            pct_cdi=round(pct_cdi, 4),
            pct_cdi_melhor=round(pct_cdi_melhor, 4),
            pct_cdi_liquido=round(pct_cdi_liquido, 4),
            pct_cdi_melhor_liquido=round(pct_cdi_melhor_liquido, 4),
            tipo=tipo,
            risco_leilao=risco,
            viavel=viavel,
            em_leilao=em_leilao,
            iv_call=round(iv_call * 100, 2) if iv_call is not None else 0.0,
            iv_put=round(iv_put * 100, 2) if iv_put is not None else 0.0,
            pop_upside=round(pop_upside * 100, 1) if pop_upside is not None else None,
            pop_downside=round(pop_downside * 100, 1) if pop_downside is not None else None,
        )
