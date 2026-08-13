import logging
import time

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.application.dtos.dtos_vendida import OportunidadeVendida
from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    TaxaAluguelRepository,
)

logger = logging.getLogger(__name__)


class MonitorVendidasUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._custos_b3 = CalculadoraCustosB3()

    def recarregar_parametros(self):
        self.param_repo.invalidate_cache()

    def _get_param(self, chave: str, default=0.0):
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def _get_taxa_cdi(self) -> float:
        return float(self.param_repo.get_by_chave("taxa_cdi").valor)

    def _calcular_cdi_periodo(self, dias_corridos: int) -> float:
        du = dc_to_du(None, None, dias_corridos)
        if du <= 0:
            return 0.0
        return (1 + self._get_taxa_cdi()) ** (du / 252) - 1

    def _lote_liquidez(self, operacao: str) -> int:
        chave = f"vendidas_lote_liquidez_{operacao.lower()}"
        return int(self._get_param(chave, 100))

    def varrer(self, dados_mercado: dict[str, dict],
               inst_map: dict | None = None,
               chaves: list | None = None,
               chaves_parsed: list | None = None,
               pipeline_tracker: PipelineTracker | None = None) -> list[OportunidadeVendida]:
        _ts = time.perf_counter()
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        hoje = date.today()
        if inst_map is None:
            inst_map = self.inst_repo.get_all_mapped()
        taxa_repo = TaxaAluguelRepository(self.db_path)
        taxa_map = taxa_repo.get_latest_all()
        premio_risco = self._get_param("vendidas_premio_risco", 1.08)
        dias_minimos = int(self._get_param("perf_dias_minimos", 10))
        dist_min_ativo = self._get_param("sbth_vendida_dist_ativo", 1.20)
        taxa_cdi = self._get_taxa_cdi()
        lote_box = self._lote_liquidez("BOX_VENDIDO")
        lote_sbth = self._lote_liquidez("SBTH_VENDIDA")
        self._ultimo_pipeline = pipeline_tracker

        chaves_com_chave = 0
        chaves_com_inst = 0
        chaves_dentro_dias = 0
        chaves_com_strike = 0
        resultados: list[OportunidadeVendida] = []

        for key, mercado in dados_mercado.items():
            if "|" not in key:
                continue
            chaves_com_chave += 1
            ativo, cod_put = key.split("|", 1)
            inst = inst_map.get((ativo, cod_put))
            if not inst or not inst.vencimento or inst.vencimento <= hoje:
                continue
            chaves_com_inst += 1
            if inst.dias_ate_vencimento is None or inst.dias_ate_vencimento < dias_minimos:
                continue
            chaves_dentro_dias += 1

            strike = mercado.get("strike_rtd")
            if not strike or strike <= 0:
                continue
            chaves_com_strike += 1

            preco_ativo = mercado.get("preco_ativo", 0.0) or 0.0
            of_compra_ativo = mercado.get("of_compra_ativo", 0.0) or 0.0
            of_venda_call = mercado.get("of_venda_call", 0.0) or 0.0
            of_compra_put = mercado.get("of_compra_put", 0.0) or 0.0
            vov_put = mercado.get("vov_put_boca", 0.0) or mercado.get("vov_put", 0.0) or 0.0
            voc_call = mercado.get("voc_call_boca", 0.0) or mercado.get("voc_call", 0.0) or 0.0
            qul_put = mercado.get("qul_put", 0.0) or 0.0
            qul_call = mercado.get("qul_call", 0.0) or 0.0

            em_leilao = mercado.get("em_leilao", False)

            # Box Vendida: vende ativo (bid) + vende PUT (bid) + compra CALL (ask)
            recebimento_box = of_compra_ativo + of_compra_put - of_venda_call
            cond_box = recebimento_box > strike and of_compra_ativo > 0 and of_venda_call > 0 and of_compra_put > 0

            # SBTH Vendida: vende ativo (bid) + vende PUT (bid); filtro DIST parametrizado
            recebimento_sbth = of_compra_ativo + of_compra_put
            cond_sbth = (
                strike > of_compra_ativo * dist_min_ativo  # usa BID (vende ativo → recebe BID)
                and recebimento_sbth > strike
                and of_compra_ativo > 0
                and of_compra_put > 0
            )

            du_vendidas = dc_to_du(None, None, inst.dias_ate_vencimento)
            if du_vendidas <= 0:
                cdi_periodo = 0.0
            else:
                cdi_periodo = (1 + taxa_cdi) ** (du_vendidas / 252) - 1

            money_put = max(strike - preco_ativo, 0.0)
            money_call = max(preco_ativo - strike, 0.0)
            taxa_aluguel = taxa_map.get(inst.ativo).taxa_atual if taxa_map and taxa_map.get(inst.ativo) else 0.0

            if cond_box:
                lote_put = lote_box
                lote_call = lote_box
                liq_ok = vov_put >= lote_put and voc_call >= lote_call
                capital = strike
                pct = (recebimento_box - strike) / capital if capital > 0 else 0.0
                pct_cdi = pct / cdi_periodo if cdi_periodo > 0 else 0.0
                viavel = pct_cdi >= premio_risco and liq_ok  # leilão: identifica visualmente, não descarta
                premio_medio_box_vendido = (
                    (of_compra_put + of_venda_call) / 2 if of_compra_put > 0 and of_venda_call > 0 else 0.0
                )
                custo = self._custos_b3.calcular_custos_vendida(
                    preco_ativo=of_compra_ativo if of_compra_ativo > 0 else preco_ativo,
                    premio_medio_opcoes=premio_medio_box_vendido,
                    n_pernas_opcoes=2,
                    n_acoes=1,
                )
                ganho_antes_ir = recebimento_box - strike - custo
                ir_box = self._custos_b3.ajustar_ir(max(ganho_antes_ir, 0.0))
                ganho_liq = ganho_antes_ir - ir_box
                pct_liq = ganho_liq / capital if capital > 0 else 0.0
                pct_cdi_liq = pct_liq / cdi_periodo if cdi_periodo > 0 else 0.0
                resultados.append(OportunidadeVendida(
                    ativo=ativo,
                    strike=strike,
                    vencimento=inst.vencimento,
                    dias=inst.dias_ate_vencimento,
                    cod_put=inst.cod_put,
                    cod_call=inst.cod_call,
                    tipo_opcao=inst.tipo_opcao.value,
                    classificacao="BOX_VENDIDO",
                    detectado_em=agora,
                    recebimento=round(recebimento_box, 2),
                    pct_ganho=round(pct, 6),
                    pct_cdi=round(pct_cdi, 4),
                    viavel=viavel,
                    em_leilao=em_leilao,
                    liq_put_x_lote=vov_put - lote_put,
                    liq_call_x_lote=voc_call - lote_call,
                    preco_ativo=round(preco_ativo, 2),
                    of_compra_put=round(of_compra_put, 2),
                    of_venda_call=round(of_venda_call, 2),
                    qul_put=round(qul_put),
                    qul_call=round(qul_call),
                    money_put=round(money_put, 2),
                    money_call=round(money_call, 2),
                    custo=round(custo, 2),
                    taxa_aluguel=round(taxa_aluguel, 2),
                    pct_ganho_bruto=round(pct, 6),
                    pct_ganho_liquido=round(pct_liq, 6),
                    pct_cdi_bruto=round(pct_cdi, 4),
                    pct_cdi_liquido=round(pct_cdi_liq, 4),
                    ts_ativo_ask=mercado.get("ts_ativo_ask"),
                    ts_ativo_bid=mercado.get("ts_ativo_bid"),
                    ts_origem_ativo=mercado.get("ts_origem_ativo"),
                    idade_origem_ativo=mercado.get("idade_origem_ativo"),
                    ts_scan=mercado.get("ts_scan"),
                    onda=mercado.get("onda"),
                ))

            if cond_sbth:
                lote_put = lote_sbth
                lote_call = lote_sbth
                liq_ok = vov_put >= lote_put  # only put needs liquidity
                capital = strike
                pct = (recebimento_sbth - strike) / capital if capital > 0 else 0.0
                pct_cdi = pct / cdi_periodo if cdi_periodo > 0 else 0.0
                viavel = pct_cdi >= premio_risco and liq_ok  # leilão: identifica visualmente, não descarta
                custo = self._custos_b3.calcular_custos_vendida(
                    preco_ativo=of_compra_ativo if of_compra_ativo > 0 else preco_ativo,
                    premio_medio_opcoes=of_compra_put if of_compra_put > 0 else 0.0,
                    n_pernas_opcoes=1,
                    n_acoes=1,
                )
                ganho_antes_ir = recebimento_sbth - strike - custo
                ir_sbth = self._custos_b3.ajustar_ir(max(ganho_antes_ir, 0.0))
                ganho_liq = ganho_antes_ir - ir_sbth
                pct_liq = ganho_liq / capital if capital > 0 else 0.0
                pct_cdi_liq = pct_liq / cdi_periodo if cdi_periodo > 0 else 0.0
                resultados.append(OportunidadeVendida(
                    ativo=ativo,
                    strike=strike,
                    vencimento=inst.vencimento,
                    dias=inst.dias_ate_vencimento,
                    cod_put=inst.cod_put,
                    cod_call=inst.cod_call,
                    tipo_opcao=inst.tipo_opcao.value,
                    classificacao="SBTH_VENDIDA",
                    detectado_em=agora,
                    recebimento=round(recebimento_sbth, 2),
                    pct_ganho=round(pct, 6),
                    pct_cdi=round(pct_cdi, 4),
                    viavel=viavel,
                    em_leilao=em_leilao,
                    liq_put_x_lote=vov_put - lote_put,
                    liq_call_x_lote=0,
                    preco_ativo=round(preco_ativo, 2),
                    of_compra_put=round(of_compra_put, 2),
                    of_venda_call=round(of_venda_call, 2),
                    qul_put=round(qul_put),
                    qul_call=round(qul_call),
                    money_put=round(money_put, 2),
                    money_call=round(money_call, 2),
                    custo=round(custo, 2),
                    taxa_aluguel=round(taxa_aluguel, 2),
                    pct_ganho_bruto=round(pct, 6),
                    pct_ganho_liquido=round(pct_liq, 6),
                    pct_cdi_bruto=round(pct_cdi, 4),
                    pct_cdi_liquido=round(pct_cdi_liq, 4),
                    ts_ativo_ask=mercado.get("ts_ativo_ask"),
                    ts_ativo_bid=mercado.get("ts_ativo_bid"),
                    ts_origem_ativo=mercado.get("ts_origem_ativo"),
                    idade_origem_ativo=mercado.get("idade_origem_ativo"),
                    ts_scan=mercado.get("ts_scan"),
                    onda=mercado.get("onda"),
                ))

        n_box = sum(1 for r in resultados if r.classificacao == "BOX_VENDIDO")
        n_sbth = sum(1 for r in resultados if r.classificacao == "SBTH_VENDIDA")
        n_viaveis = sum(1 for r in resultados if r.viavel)
        resultados.sort(key=lambda o: (not o.viavel, -o.pct_cdi))

        if self._ultimo_pipeline is not None:
            self._ultimo_pipeline.nome_estrategia = "BOX/SBTH VENDIDO"
            self._ultimo_pipeline.add_stage("1. Com chave composta", len(dados_mercado), chaves_com_chave)
            self._ultimo_pipeline.add_stage("2. Instrumento válido", chaves_com_chave, chaves_com_inst, "Instrumento não encontrado ou vencido")
            self._ultimo_pipeline.add_stage("3. DTE mínimo", chaves_com_inst, chaves_dentro_dias, f"DTE < {dias_minimos}d")
            self._ultimo_pipeline.add_stage("4. Strike RTD", chaves_dentro_dias, chaves_com_strike, "Strike ausente/zero")
            self._ultimo_pipeline.add_stage("5. Resultados", chaves_com_strike, len(resultados), f"BOX={n_box}, SBTH={n_sbth}")
            self._ultimo_pipeline.add_stage("6. Viáveis", len(resultados), n_viaveis, f"Prêmio-risco {premio_risco}xCDI")

        logger.info("Consumers: vendidas=%.3fs | n_in=%d n_inst=%d n_dte=%d n_strike=%d n_opp=%d",
                     time.perf_counter() - _ts,
                     chaves_com_chave, chaves_com_inst, chaves_dentro_dias, chaves_com_strike, len(resultados))
        return resultados
