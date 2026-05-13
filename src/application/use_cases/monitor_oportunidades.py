from datetime import date

from src.application.dtos.dtos import OportunidadeMonitor
from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calculadora_box_sbth import CalculadoraBoxSbth, DadosMercado
from src.domain.rules.classificacao_oportunidade import ClassificacaoOportunidade
from src.infrastructure.importers.excel_importer import extrair_strike
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
            taxa_cdi = self._get_param("taxa_cdi", 0.1450)
            premio_box = self._get_param("premio_risco_box", 1.5)
            premio_sbth = self._get_param("premio_risco_sbth", 1.2)
            self._calculadora = CalculadoraBoxSbth(taxa_cdi, premio_box, premio_sbth)
        return self._calculadora

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def recarregar_parametros(self):
        self._calculadora = None

    def _lote_liquidez_put(self, operacao: str) -> float:
        if operacao in ("BOX", "BOXSBTH"):
            return self._get_param("box_qtd_put", 1000)
        return self._get_param("sbth_qtd_put", 1000)

    def _lote_liquidez_call(self, operacao: str) -> float:
        if operacao in ("BOX", "BOXSBTH"):
            return self._get_param("box_qtd_call", 1000)
        return 0.0

    def varrer(self, dados_mercado: dict[str, dict]) -> list[OportunidadeMonitor]:
        calc = self._get_calculadora()
        instrumentos = self.inst_repo.get_all()
        resultados = []
        hoje = date.today()

        for inst in instrumentos:
            if inst.vencimento is not None and inst.vencimento <= hoje:
                continue

            key = inst.cod_put
            mercado = dados_mercado.get(key)
            if mercado is None:
                continue
            if mercado.get("preco_ativo", 0) <= 0:
                continue

            opp = self._calcular_oportunidade(inst, mercado, calc)
            if opp is not None:
                resultados.append(opp)

        resultados.sort(key=lambda o: (not o.viavel, -max(o.pct_cdi_box, o.pct_cdi_sbth)))
        return resultados

    def _calcular_oportunidade(self, inst, mercado, calc):
        if mercado is None:
            return None
        strike_rtd = mercado.get("strike_rtd")
        strike = strike_rtd if strike_rtd and strike_rtd > 0 else (extrair_strike(inst.cod_put) or 0.0)

        dados = DadosMercado(
            preco_ativo=mercado["preco_ativo"],
            of_compra_ativo=mercado.get("of_compra_ativo", 0.0),
            of_venda_ativo=mercado.get("of_venda_ativo", 0.0),
            of_compra_put=mercado.get("of_compra_put", 0.0),
            of_venda_put=mercado.get("of_venda_put", 0.0),
            of_compra_call=mercado.get("of_compra_call", 0.0),
            of_venda_call=mercado.get("of_venda_call", 0.0),
            strike=strike,
            premio_put=mercado.get("premio_put", 0.0),
            premio_call=mercado.get("premio_call", 0.0),
            dias=inst.dias_ate_vencimento,
            em_leilao=mercado.get("em_leilao", False),
            status_put=mercado.get("status_put", ""),
            status_call=mercado.get("status_call", ""),
            status_ativo=mercado.get("status_ativo", ""),
            vov_put_boca=mercado.get("vov_put_boca", 0.0),
            voc_call_boca=mercado.get("voc_call_boca", 0.0),
            qul_put=mercado.get("qul_put", 0.0),
            qul_call=mercado.get("qul_call", 0.0),
        )
        resultado = calc.calcular(dados)

        lote_put = self._lote_liquidez_put(resultado.operacao)
        lote_call = self._lote_liquidez_call(resultado.operacao)
        liq_put_x_lote = dados.vov_put_boca - lote_put
        liq_call_x_lote = dados.voc_call_boca - lote_call

        tem_liquidez = liq_put_x_lote >= 0 and liq_call_x_lote >= 0
        viavel = (
            resultado.operacao in ("BOX", "SBTH", "BOXSBTH")
            and not dados.em_leilao
            and tem_liquidez
        )

        return OportunidadeMonitor(
            instrumento_id=inst.id or 0,
            ativo=inst.ativo,
            strike=strike,
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
            preco_compra_ativo=dados._preco_compra_ativo(),
            of_venda_put=dados.of_venda_put,
            of_compra_call=dados.of_compra_call,
            em_leilao=dados.em_leilao,
            liq_put_x_lote=liq_put_x_lote,
            liq_call_x_lote=liq_call_x_lote,
            of_compra_put=dados.of_compra_put,
            of_venda_call=dados.of_venda_call,
            qul_put=dados.qul_put,
            qul_call=dados.qul_call,
            money_put=max(dados.strike - dados.preco_ativo, 0.0),
            money_call=max(dados.preco_ativo - dados.strike, 0.0),
        )
