from dataclasses import dataclass


@dataclass(slots=True)
class CandidatoPescaria:
    instrumento_id: int
    ativo: str
    vencimento: str
    strike_call_itm: float
    cod_call_itm: str
    of_venda_call: float
    preco_ativo: float
    col31_valor: float


class ElegibilidadePescaria:
    def __init__(self, taxa_ganho: float, strike_max_pct: float = 0.70):
        self.taxa_ganho = taxa_ganho
        self.strike_max_pct = strike_max_pct

    def filtrar_candidatos(
        self,
        candidatos: list[CandidatoPescaria],
        ativo_referencia: str,
        vencimento_referencia: str,
        strike_atm: float,
    ) -> list[CandidatoPescaria]:
        elegidos = []
        for c in candidatos:
            if not self._criterios_basicos(c, ativo_referencia, vencimento_referencia):
                continue
            if not self._criterio_strike_itm(c):
                continue
            if not self._criterio_col31(c):
                continue
            if not self._criterio_oferta_venda(c):
                continue
            if not self._criterio_spread(c, strike_atm):
                continue
            elegidos.append(c)
        return elegidos

    def _criterios_basicos(self, c: CandidatoPescaria, ativo_ref: str, venc_ref: str) -> bool:
        return c.ativo == ativo_ref and c.vencimento == venc_ref

    def _criterio_strike_itm(self, c: CandidatoPescaria) -> bool:
        if c.preco_ativo <= 0:
            return False
        return c.strike_call_itm <= c.preco_ativo * self.strike_max_pct

    def _criterio_col31(self, c: CandidatoPescaria) -> bool:
        return c.col31_valor > 0

    def _criterio_oferta_venda(self, c: CandidatoPescaria) -> bool:
        return c.of_venda_call > 0

    def _criterio_spread(self, c: CandidatoPescaria, strike_atm: float) -> bool:
        spread = strike_atm - c.strike_call_itm
        if spread <= 0:
            return False
        valor_limite = spread * (100 - self.taxa_ganho) / 100
        return c.col31_valor >= valor_limite

    def calcular_valor_limite(self, strike_atm: float, strike_itm: float) -> float:
        spread = strike_atm - strike_itm
        if spread <= 0:
            return 0.0
        return spread * (100 - self.taxa_ganho) / 100
