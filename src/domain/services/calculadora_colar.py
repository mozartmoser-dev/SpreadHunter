from dataclasses import dataclass
from datetime import date
from enum import Enum


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

    def calcular_cdi_periodo(self, dias: int) -> float:
        if dias <= 0:
            return 0.0
        return (1 + self.taxa_cdi) ** (dias / 365) - 1

    def classificar_tipo(self, preco_ativo: float, strike_put: float, strike_call: float) -> TipoColar:
        if preco_ativo < strike_put < strike_call:
            return TipoColar.STRIKES_ACIMA
        if strike_put < strike_call < preco_ativo:
            return TipoColar.STRIKES_ABAIXO
        return TipoColar.TRADICIONAL

    def calcular_pior_retorno(self, tipo: TipoColar, custo_liquido: float, strike_put: float, strike_call: float) -> float:
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
    ) -> ResultadoColar | None:
        if preco_ativo <= 0 or dias <= 0:
            return None
        if premio_put <= 0 or premio_call <= 0:
            return None

        tipo = self.classificar_tipo(preco_ativo, strike_put, strike_call)
        em_leilao = status_put != "Aberto" or status_call != "Aberto"

        custo_liquido = preco_ativo + premio_put - premio_call
        if custo_liquido <= 0:
            return None

        cdi_periodo = self.calcular_cdi_periodo(dias)
        if cdi_periodo <= 0:
            return None

        pior_retorno = self.calcular_pior_retorno(tipo, custo_liquido, strike_put, strike_call)
        pct_ganho = pior_retorno / custo_liquido
        pct_cdi = pct_ganho / cdi_periodo
        risco = self.calcular_risco_leilao(vov_put, voc_call, status_put, status_call)
        viavel = pct_cdi >= self.premio_risco_colar and not em_leilao

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
        )
