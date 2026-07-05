from dataclasses import dataclass
from datetime import date

from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


@dataclass(slots=True)
class ResultadoBox:
    ativo: str
    vencimento: date
    strike_k1: float
    strike_k2: float
    cod_call_k1: str
    cod_put_k1: str
    cod_call_k2: str
    cod_put_k2: str
    bid_call_k1: float
    ask_put_k1: float
    ask_call_k2: float
    bid_put_k2: float
    qtd_bid_call_k1: int
    qtd_ask_put_k1: int
    qtd_ask_call_k2: int
    qtd_bid_put_k2: int
    clr: float
    distancia: float
    lucro: float
    custo_b3: float
    custo_ir: float
    lucro_liquido: float
    lucro_pct: float
    pct_cdi: float
    pct_cdi_liquido: float
    em_leilao: bool
    viavel: bool
    dias: int
    taxa_aluguel: float = 0.0


class CalculadoraBox:
    def __init__(self, taxa_cdi: float = 0.1450, premio_risco: float = 1.08,
                 taxa_emolumento: float | None = None, taxa_liquidacao: float | None = None,
                 taxa_ir: float | None = None):
        # CDI lido do banco (parametro taxa_cdi), usuario atualiza manualmente na tabela.
        # IR fixo em 15% porque 99,9% das operacoes sao swing trade.
        self.taxa_cdi = taxa_cdi
        self.premio_risco = premio_risco
        self.custos_b3 = CalculadoraCustosB3(taxa_emolumento, taxa_liquidacao, taxa_ir)

    def calcular_cdi_periodo(self, dias_corridos: int) -> float:
        du = dc_to_du(None, None, dias_corridos)
        if du <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (du / 252) - 1

    def calcular(
        self,
        strike_k1: float,
        strike_k2: float,
        bid_call_k1: float,
        ask_put_k1: float,
        ask_call_k2: float,
        bid_put_k2: float,
        qtd_bid_call_k1: int,
        qtd_ask_put_k1: int,
        qtd_ask_call_k2: int,
        qtd_bid_put_k2: int,
        cod_call_k1: str,
        cod_put_k1: str,
        cod_call_k2: str,
        cod_put_k2: str,
        ativo: str,
        vencimento: date,
        dias: int,
        em_leilao: bool,
        qtd_min_perna: int = 0,
    ) -> ResultadoBox | None:
        if strike_k1 >= strike_k2:
            return None
        if any(p <= 0 for p in (bid_call_k1, ask_put_k1, ask_call_k2, bid_put_k2)):
            return None
        if dias <= 0:
            return None

        distancia = strike_k2 - strike_k1
        clr = (bid_call_k1 + bid_put_k2) - (ask_put_k1 + ask_call_k2)
        lucro = clr - distancia

        premio_medio = (bid_call_k1 + ask_put_k1 + ask_call_k2 + bid_put_k2) / 4
        custo_b3 = self.custos_b3.custos_opcao(premio_medio, n_pernas=4)
        lucro_liquido = lucro - custo_b3

        custo_ir = self.custos_b3.ajustar_ir(lucro_liquido)
        lucro_liquido_pos_ir = lucro_liquido - custo_ir

        lucro_pct_bruto = lucro / distancia if distancia > 0 else 0.0
        lucro_pct = lucro_liquido / distancia if distancia > 0 else 0.0
        cdi_periodo = self.calcular_cdi_periodo(dias)
        pct_cdi_bruto = lucro_pct_bruto / cdi_periodo if cdi_periodo > 0 else 0.0
        pct_cdi = lucro_pct / cdi_periodo if cdi_periodo > 0 else 0.0
        lucro_pct_liq = lucro_liquido_pos_ir / distancia if distancia > 0 else 0.0
        pct_cdi_liquido = lucro_pct_liq / cdi_periodo if cdi_periodo > 0 else 0.0

        tem_dado_profundidade = (
            qtd_bid_call_k1 > 0 or qtd_ask_put_k1 > 0
            or qtd_ask_call_k2 > 0 or qtd_bid_put_k2 > 0
        )
        # A execucao parcial eh tratada pelo PNT ao exportar a operacao.
        # O scanner apenas valida se ha profundidade minima para montar a estrutura.
        profundidade_ok = (
            not tem_dado_profundidade
            or qtd_min_perna <= 0
            or (
                qtd_bid_call_k1 >= qtd_min_perna
                and qtd_ask_put_k1 >= qtd_min_perna
                and qtd_ask_call_k2 >= qtd_min_perna
                and qtd_bid_put_k2 >= qtd_min_perna
            )
        )

        viavel = (
            pct_cdi_bruto >= self.premio_risco
            and lucro_liquido > 0
            and not em_leilao
            and profundidade_ok
        )

        return ResultadoBox(
            ativo=ativo,
            vencimento=vencimento,
            strike_k1=strike_k1,
            strike_k2=strike_k2,
            cod_call_k1=cod_call_k1,
            cod_put_k1=cod_put_k1,
            cod_call_k2=cod_call_k2,
            cod_put_k2=cod_put_k2,
            bid_call_k1=round(bid_call_k1, 2),
            ask_put_k1=round(ask_put_k1, 2),
            ask_call_k2=round(ask_call_k2, 2),
            bid_put_k2=round(bid_put_k2, 2),
            qtd_bid_call_k1=qtd_bid_call_k1,
            qtd_ask_put_k1=qtd_ask_put_k1,
            qtd_ask_call_k2=qtd_ask_call_k2,
            qtd_bid_put_k2=qtd_bid_put_k2,
            clr=round(clr, 2),
            distancia=round(distancia, 2),
            lucro=round(lucro, 2),
            custo_b3=round(custo_b3, 4),
            custo_ir=round(custo_ir, 4),
            lucro_liquido=round(lucro_liquido, 2),
            lucro_pct=round(lucro_pct, 6),
            pct_cdi=round(pct_cdi, 4),
            pct_cdi_liquido=round(pct_cdi_liquido, 4),
            em_leilao=em_leilao,
            viavel=viavel,
            dias=dias,
        )
