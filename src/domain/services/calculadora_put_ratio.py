from dataclasses import dataclass
from datetime import date, datetime

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
    custo_b3: float
    custo_ir: float
    lucro_liquido: float
    capital_margem: float
    pct_cdi: float
    pct_cdi_liquido: float
    iv_put_pct: float
    em_leilao: bool
    viavel: bool
    detectado_em: datetime | None = None


class CalculadoraPutRatio:
    def __init__(self, taxa_cdi: float = 0.1450, premio_risco: float = 1.5,
                 taxa_emolumento: float | None = None, taxa_liquidacao: float | None = None,
                 taxa_ir: float | None = None, taxa_registro: float | None = None,
                 iss: float | None = None):
        self.taxa_cdi = taxa_cdi
        self.premio_risco = premio_risco
        self.custos_b3 = CalculadoraCustosB3(taxa_emolumento, taxa_liquidacao, taxa_ir, taxa_registro, iss)

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
        iv_put_pct: float = 0.0,
        qtd_min_perna: int = 0,
        du: int | None = None,
    ) -> ResultadoPutRatio | None:
        if strike_k1 <= strike_k2:
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

        premio_medio = (ask_put_k1 + bid_put_k2) / 2
        custo_b3 = self.custos_b3.custos_opcao(premio_medio, n_pernas=2)
        lucro_liquido = credito_bruto - custo_b3

        custo_ir = self.custos_b3.ajustar_ir(lucro_liquido)
        lucro_liquido_pos_ir = lucro_liquido - custo_ir

        capital_margem = n2 * strike_k2 * 100.0

        du_val = du if du is not None else dc_to_du(None, None, dias)
        cdi_periodo = (1 + self.taxa_cdi) ** (du_val / 252.0) - 1 if du_val > 0 else 0.0

        pct_lucro = max_profit / capital_margem if capital_margem > 0 else 0.0
        pct_cdi = pct_lucro / cdi_periodo if cdi_periodo > 0 else 0.0

        pct_liq = lucro_liquido_pos_ir / capital_margem if capital_margem > 0 else 0.0
        pct_cdi_liquido = pct_liq / cdi_periodo if cdi_periodo > 0 else 0.0

        tem_profundidade = qtd_ask_put_k1 > 0 or qtd_bid_put_k2 > 0
        profundidade_ok = (
            not tem_profundidade
            or qtd_min_perna <= 0
            or (qtd_ask_put_k1 >= qtd_min_perna and qtd_bid_put_k2 >= qtd_min_perna)
        )

        viavel = (
            pct_cdi >= self.premio_risco
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
            custo_b3=round(custo_b3, 4),
            custo_ir=round(custo_ir, 4),
            lucro_liquido=round(lucro_liquido, 2),
            capital_margem=round(capital_margem, 2),
            pct_cdi=round(pct_cdi, 4),
            pct_cdi_liquido=round(pct_cdi_liquido, 4),
            iv_put_pct=round(iv_put_pct, 2),
            em_leilao=em_leilao,
            viavel=viavel,
        )
