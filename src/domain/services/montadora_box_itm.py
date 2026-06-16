from dataclasses import dataclass

from src.domain.entities.estrutura_operacional import TipoEstrutura
from src.domain.entities.perna_operacao import PernaOperacao, Lado


@dataclass(slots=True)
class BoxItmBasket:
    tipo: TipoEstrutura
    pernas: list[PernaOperacao]
    coefic_alvo: float
    coefic_mercado: float
    taxa_ganho: float


class MontadoraBoxItm:
    def __init__(self, profundidade_call_itm: int = -1):
        self.profundidade_call_itm = profundidade_call_itm

    def montar_3_pernas(
        self,
        cod_call_itm: str,
        cod_put_atm: str,
        cod_call_atm: str,
        estrutura_id: int,
        coefic_alvo: float = 0.0,
        coefic_mercado: float = 0.0,
        taxa_ganho: float = 0.0,
    ) -> BoxItmBasket:
        pernas = [
            PernaOperacao(
                estrutura_id=estrutura_id,
                codigo=cod_call_itm,
                lado=Lado.COMPRA,
                quantidade=100,
                profundidade=self.profundidade_call_itm,
                ordem=1,
            ),
            PernaOperacao(
                estrutura_id=estrutura_id,
                codigo=cod_put_atm,
                lado=Lado.COMPRA,
                quantidade=100,
                profundidade=0,
                ordem=2,
            ),
            PernaOperacao(
                estrutura_id=estrutura_id,
                codigo=cod_call_atm,
                lado=Lado.VENDA,
                quantidade=100,
                profundidade=0,
                ordem=3,
            ),
        ]

        return BoxItmBasket(
            tipo=TipoEstrutura.BOX_ITM_BASKET,
            pernas=pernas,
            coefic_alvo=coefic_alvo,
            coefic_mercado=coefic_mercado,
            taxa_ganho=taxa_ganho,
        )

    def calcular_coeficientes(
        self,
        strike_atm: float,
        strike_itm: float,
        premio_call_atm: float,
        premio_call_itm: float,
        premio_put_atm: float,
        taxa_ganho: float = 0.0,
    ) -> tuple[float, float]:
        """Retorna (coefic_alvo, coefic_mercado) como frações do spread.

        coefic_alvo  = fração máxima aceitável do spread (ex: 0.90 para taxa_ganho=10%)
        coefic_mercado = custo real da estrutura dividido pelo spread
        Operação é viável quando coefic_mercado <= coefic_alvo.
        """
        spread = strike_atm - strike_itm
        if spread <= 0:
            return (0.0, 0.0)

        custo_estrutura = premio_call_itm + premio_put_atm - premio_call_atm

        # coefic_alvo: fração do spread que é o máximo que podemos pagar
        # (1 - taxa_ganho/100) → para taxa=10%, alvo é 90% do spread
        coefic_alvo = (100.0 - taxa_ganho) / 100.0 if taxa_ganho >= 0 else 1.0
        coefic_mercado = custo_estrutura / spread if spread != 0 else 0.0

        return (round(coefic_alvo, 4), round(coefic_mercado, 4))
