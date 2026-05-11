from src.application.dtos.dtos import OportunidadeMonitor
from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calculadora_box_sbth import CalculadoraBoxSbth, DadosMercado
from src.domain.rules.classificacao_oportunidade import ClassificacaoOportunidade
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)


class MonitorOportunidadesUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None

    def _get_calculadora(self) -> CalculadoraBoxSbth:
        if self._calculadora is None:
            taxa_cdi = self._get_param("taxa_cdi", 0.15)
            premio_box = self._get_param("premio_risco_box", 1.5)
            premio_sbth = self._get_param("premio_risco_sbth", 1.2)
            self._calculadora = CalculadoraBoxSbth(taxa_cdi, premio_box, premio_sbth)
        return self._calculadora

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def recarregar_parametros(self):
        self._calculadora = None

    def varrer(self, dados_mercado: dict[str, dict]) -> list[OportunidadeMonitor]:
        calc = self._get_calculadora()
        instrumentos = self.inst_repo.get_all()
        resultados = []

        for inst in instrumentos:
            key = "{}_{}_{}".format(inst.ativo, inst.strike, inst.vencimento.isoformat())
            mercado = dados_mercado.get(key)
            if mercado is None:
                continue

            if mercado.get("preco_ativo", 0) <= 0:
                continue

            dados = DadosMercado(
                preco_ativo=mercado["preco_ativo"],
                of_compra_ativo=mercado.get("of_compra_ativo", 0.0),
                of_venda_ativo=mercado.get("of_venda_ativo", 0.0),
                of_compra_put=mercado.get("of_compra_put", 0.0),
                of_venda_put=mercado.get("of_venda_put", 0.0),
                of_compra_call=mercado.get("of_compra_call", 0.0),
                of_venda_call=mercado.get("of_venda_call", 0.0),
                strike=inst.strike,
                premio_put=mercado.get("premio_put", 0.0),
                premio_call=mercado.get("premio_call", 0.0),
                dias=inst.dias_ate_vencimento,
                em_leilao=mercado.get("em_leilao", False),
                status_put=mercado.get("status_put", ""),
                status_call=mercado.get("status_call", ""),
                status_ativo=mercado.get("status_ativo", ""),
            )

            resultado = calc.calcular(dados)

            viavel = resultado.operacao in ("BOX", "SBTH", "BOXSBTH")

            resultados.append(OportunidadeMonitor(
                instrumento_id=inst.id or 0,
                ativo=inst.ativo,
                strike=inst.strike,
                vencimento=inst.vencimento.isoformat(),
                dias=dados.dias,
                cod_put=inst.cod_put,
                cod_call=inst.cod_call,
                tipo_opcao=inst.tipo_opcao.value,
                classificacao=resultado.classificacao,
                operacao=resultado.operacao,
                custo_sbth=resultado.custo_sbth,
                pct_ganho_sbth=resultado.pct_ganho_sbth,
                pct_cdi_sbth=resultado.pct_cdi_sbth,
                custo_box=resultado.custo_box,
                pct_ganho_box=resultado.pct_ganho_box,
                pct_cdi_box=resultado.pct_cdi_box,
                cdi_periodo=resultado.cdi_periodo,
                viavel=viavel,
            ))

        resultados.sort(key=lambda o: (not o.viavel, -max(o.pct_cdi_box, o.pct_cdi_sbth)))
        return resultados
