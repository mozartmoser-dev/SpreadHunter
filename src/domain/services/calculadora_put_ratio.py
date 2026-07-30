import math
from dataclasses import dataclass
from datetime import date, datetime

from scipy.stats import norm

from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3

RATIOS_DEFAULT = [(1, 2), (2, 3), (1, 3)]


@dataclass(slots=True)
class ResultadoPutRatio:
    ativo: str
    vencimento: date
    dias: int
    strike_k1: float
    strike_k2: float
    n1: int
    n2: int
    ratio_label: str
    cod_put_k1: str
    cod_put_k2: str
    ask_put_k1: float
    bid_put_k2: float
    qtd_ask_put_k1: int
    qtd_bid_put_k2: int
    credito_bruto: float
    max_profit: float
    be_down: float
    credit_yield: float
    yield_cdi: float
    sigma_be: float
    protecao_pct: float
    pop_pct: float
    score: float
    zona: str
    custo_b3: float
    custo_ir: float
    lucro_liquido: float
    capital_margem: float
    spot: float
    iv_put_pct: float
    delta_k1: float
    delta_k2: float
    em_leilao: bool
    viavel: bool
    iv_rank: float = 0.0
    iv_percentile: float = 0.0
    detectado_em: datetime | None = None


class CalculadoraPutRatio:

    def __init__(self, taxa_cdi: float = 0.1450, premio_risco: float = 1.0,
                 taxa_emolumento: float | None = None, taxa_liquidacao: float | None = None,
                 taxa_ir: float | None = None, taxa_registro: float | None = None,
                 iss: float | None = None,
                 peso_alpha: float = 0.7, peso_beta: float = 0.0, peso_gamma: float = 0.3):
        self.taxa_cdi = taxa_cdi
        self.premio_risco = premio_risco
        self.custos_b3 = CalculadoraCustosB3(taxa_emolumento, taxa_liquidacao, taxa_ir, taxa_registro, iss)
        self.peso_alpha = peso_alpha
        self.peso_beta = peso_beta
        self.peso_gamma = peso_gamma

    @staticmethod
    def delta_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
        if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
            return 0.0
        d1 = (math.log(S / K) + (r + sigma * sigma / 2) * T) / (sigma * math.sqrt(T))
        return norm.cdf(d1) - 1.0

    @staticmethod
    def estimar_iv(preco_mercado: float, S: float, K: float, T: float, r: float) -> float:
        if preco_mercado <= 0 or S <= 0 or K <= 0 or T <= 0:
            return 0.0
        intrinsic = max(K - S, 0.0)
        if preco_mercado <= intrinsic:
            return 0.15
        sigma = 0.30
        for _ in range(20):
            d1 = (math.log(S / K) + (r + sigma * sigma / 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            preco_bs = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            vega = S * math.sqrt(T) * norm.pdf(d1)
            if vega < 1e-6:
                break
            diff = preco_bs - preco_mercado
            sigma -= diff / vega
            if abs(diff) < 0.0001:
                break
        return max(0.05, min(2.0, sigma))

    def calcular(
        self,
        strike_k1: float,
        strike_k2: float,
        n1: int,
        n2: int,
        ask_put_k1: float,
        bid_put_k2: float,
        qtd_ask_put_k1: int,
        qtd_bid_put_k2: int,
        cod_put_k1: str,
        cod_put_k2: str,
        ativo: str,
        vencimento: date,
        dias: int,
        em_leilao: bool,
        preco_ativo: float = 0.0,
        qtd_min_perna: int = 0,
        du: int | None = None,
        iv_k1: float | None = None,
        iv_k2: float | None = None,
    ) -> ResultadoPutRatio | None:
        if strike_k1 <= strike_k2:
            return None
        if n2 <= n1:
            return None
        if ask_put_k1 <= 0 or bid_put_k2 <= 0:
            return None
        if dias <= 0:
            return None

        credito_bruto = n2 * bid_put_k2 - n1 * ask_put_k1
        if credito_bruto <= 0:
            return None

        max_profit = n1 * (strike_k1 - strike_k2) + credito_bruto
        n_excedente = n2 - n1
        if n_excedente > 0:
            be_down = strike_k2 - (max_profit / n_excedente)
        else:
            be_down = 0.0

        T = dias / 365.0
        r_cont = math.log(1 + self.taxa_cdi)
        if iv_k1 is not None and iv_k2 is not None:
            pass
        else:
            mid_k1 = ask_put_k1
            mid_k2 = bid_put_k2
            if iv_k1 is None:
                iv_k1 = self.estimar_iv(mid_k1, preco_ativo, strike_k1, T, r_cont) if preco_ativo > 0 else 0.0
            if iv_k2 is None:
                iv_k2 = self.estimar_iv(mid_k2, preco_ativo, strike_k2, T, r_cont) if preco_ativo > 0 else 0.0
        iv_media = (iv_k1 + iv_k2) / 2 if iv_k1 > 0 and iv_k2 > 0 else max(iv_k1, iv_k2)

        delta_k1 = self.delta_put(preco_ativo, strike_k1, T, r_cont, iv_k1) if iv_k1 > 0 else 0.0
        delta_k2 = self.delta_put(preco_ativo, strike_k2, T, r_cont, iv_k2) if iv_k2 > 0 else 0.0

        premio_medio = (ask_put_k1 + bid_put_k2) / 2
        custo_b3 = self.custos_b3.custos_opcao(premio_medio, n_pernas=2)
        lucro_liquido = credito_bruto - custo_b3

        custo_ir = self.custos_b3.ajustar_ir(lucro_liquido)
        lucro_liquido_pos_ir = lucro_liquido - custo_ir

        capital_margem = (n2 - n1) * strike_k2
        risco_por_acao = (n2 - n1) * strike_k2

        du_val = du if du is not None else dc_to_du(None, None, dias)
        cdi_periodo = (1 + self.taxa_cdi) ** (du_val / 252.0) - 1 if du_val > 0 else 0.0

        credit_yield = credito_bruto / risco_por_acao if risco_por_acao > 0 else 0.0
        yield_cdi = credit_yield / cdi_periodo if cdi_periodo > 0 else 0.0

        protecao_pct = 0.0
        if preco_ativo > 0 and be_down > 0:
            protecao_pct = (preco_ativo - be_down) / preco_ativo

        sigma_be = 0.0
        if preco_ativo > 0 and iv_media > 0 and be_down > 0:
            iv_mod = min(iv_media, 1.0)
            sigma_periodo = iv_mod * math.sqrt(T)
            if sigma_periodo > 0:
                sigma_be = (preco_ativo - be_down) / (preco_ativo * sigma_periodo)

        zona = "C"
        if sigma_be >= 2.0:
            zona = "A"
        elif sigma_be >= 1.5:
            zona = "B"

        pop_pct = round(norm.cdf(sigma_be) * 100.0, 1) if sigma_be > 0 else 0.0

        alpha, beta, gamma = self.peso_alpha, self.peso_beta, self.peso_gamma
        score = (alpha * protecao_pct) + (beta * (max_profit / preco_ativo if preco_ativo > 0 else 0.0)) + (gamma * (credito_bruto / preco_ativo if preco_ativo > 0 else 0.0))
        score = round(score * 100, 2)

        tem_profundidade = qtd_ask_put_k1 > 0 or qtd_bid_put_k2 > 0
        profundidade_ok = (
            qtd_min_perna <= 0
            or (tem_profundidade and qtd_ask_put_k1 >= qtd_min_perna and qtd_bid_put_k2 >= qtd_min_perna)
        )

        viavel = (
            credito_bruto > 0
            and lucro_liquido > 0
            and profundidade_ok
        )

        ratio_label = f"{n1}x{n2}"

        return ResultadoPutRatio(
            ativo=ativo,
            vencimento=vencimento,
            dias=dias,
            strike_k1=round(strike_k1, 2),
            strike_k2=round(strike_k2, 2),
            n1=n1,
            n2=n2,
            ratio_label=ratio_label,
            cod_put_k1=cod_put_k1,
            cod_put_k2=cod_put_k2,
            ask_put_k1=round(ask_put_k1, 2),
            bid_put_k2=round(bid_put_k2, 2),
            qtd_ask_put_k1=qtd_ask_put_k1,
            qtd_bid_put_k2=qtd_bid_put_k2,
            credito_bruto=round(credito_bruto, 2),
            max_profit=round(max_profit, 2),
            be_down=round(be_down, 2),
            credit_yield=round(credit_yield, 6),
            yield_cdi=round(yield_cdi, 4),
            sigma_be=round(sigma_be, 2),
            protecao_pct=round(protecao_pct, 4),
            pop_pct=pop_pct,
            score=round(score, 2),
            zona=zona,
            custo_b3=round(custo_b3, 4),
            custo_ir=round(custo_ir, 4),
            lucro_liquido=round(lucro_liquido, 2),
            capital_margem=round(capital_margem, 2),
            spot=round(preco_ativo, 2),
            iv_put_pct=round(iv_media * 100, 2),
            delta_k1=round(delta_k1, 4),
            delta_k2=round(delta_k2, 4),
            em_leilao=em_leilao,
            viavel=viavel,
        )
