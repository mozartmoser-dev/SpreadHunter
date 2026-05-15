from src.application.dtos.dtos import BasketGerada
from src.domain.entities.estrutura_operacional import EstruturaOperacional, TipoEstrutura
from src.domain.services.elegibilidade_pescaria import ElegibilidadePescaria, CandidatoPescaria
from src.domain.services.montadora_box_itm import MontadoraBoxItm
from src.infrastructure.importers.excel_importer import extrair_strike
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    EstruturaRepository,
    PernaRepository,
)


class GerarBasketItmUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.est_repo = EstruturaRepository(db_path)
        self.perna_repo = PernaRepository(db_path)

    def executar(
        self,
        ativo: str,
        vencimento: str,
        strike_atm: float,
        taxa_ganho: float,
        candidatos_dados: list[dict],
    ) -> list[BasketGerada]:
        eleg = ElegibilidadePescaria(taxa_ganho=taxa_ganho)
        montadora = MontadoraBoxItm(profundidade_call_itm=-1)

        candidatos = [
            CandidatoPescaria(
                instrumento_id=c.get("instrumento_id", 0),
                ativo=c["ativo"],
                vencimento=c["vencimento"],
                strike_call_itm=c["strike_call_itm"],
                cod_call_itm=c["cod_call_itm"],
                of_venda_call=c.get("of_venda_call", 0.0),
                preco_ativo=c.get("preco_ativo", 0.0),
                col31_valor=c.get("col31_valor", 0.0),
            )
            for c in candidatos_dados
        ]

        elegidos = eleg.filtrar_candidatos(candidatos, ativo, vencimento, strike_atm)

        instrumentos_atm = self.inst_repo.get_by_ativo(ativo)
        cod_put_atm = ""
        cod_call_atm = ""
        for inst in instrumentos_atm:
            inst_strike = extrair_strike(inst.cod_put)
            if inst.vencimento.isoformat() == vencimento and inst_strike is not None and abs(inst_strike - strike_atm) < 0.01:
                cod_put_atm = inst.cod_put
                cod_call_atm = inst.cod_call
                break

        baskets = []
        for candidato in elegidos:
            estrutura = self.est_repo.save(EstruturaOperacional(
                oportunidade_id=None,
                tipo=TipoEstrutura.BOX_ITM_BASKET,
                coefic_alvo=0.0,
                coefic_mercado=0.0,
                taxa_ganho=taxa_ganho,
            ))

            basket = montadora.montar_3_pernas(
                cod_call_itm=candidato.cod_call_itm,
                cod_put_atm=cod_put_atm,
                cod_call_atm=cod_call_atm,
                estrutura_id=estrutura.id,
                taxa_ganho=taxa_ganho,
            )

            for perna in basket.pernas:
                self.perna_repo.save(perna)

            baskets.append(BasketGerada(
                estrutura_id=estrutura.id,
                tipo=TipoEstrutura.BOX_ITM_BASKET.value,
                ativo=ativo,
                strike_atm=strike_atm,
                strike_itm=candidato.strike_call_itm,
                pernas=[
                    {"codigo": p.codigo, "lado": p.lado.value, "quantidade": p.quantidade, "profundidade": p.profundidade}
                    for p in basket.pernas
                ],
                coefic_alvo=basket.coefic_alvo,
                coefic_mercado=basket.coefic_mercado,
            ))

        return baskets
