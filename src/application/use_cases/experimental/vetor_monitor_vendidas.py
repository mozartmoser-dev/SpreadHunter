import logging
import time

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np

from src.application.dtos.dtos_vendida import OportunidadeVendida
from src.domain.services.calculadora_vendidas_vetor import calcular_vendidas
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    TaxaAluguelRepository,
)

logger = logging.getLogger(__name__)


class VetorMonitorVendidasUseCase:
    """Versão vetorizada (experimental) de ``MonitorVendidasUseCase.varrer``.

    Deve produzir resultados equivalentes ao escalar — fonte da verdade.
    """

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
        insts_validas = []
        _dias_validas: list = []
        _preco_ativo: list = []
        _of_compra_ativo: list = []
        _of_compra_put: list = []
        _of_venda_call: list = []
        _vov_put: list = []
        _voc_call: list = []
        _qul_put: list = []
        _qul_call: list = []
        _em_leilao: list = []
        _status_put: list = []
        _status_call: list = []
        _status_ativo: list = []
        _ts_ask: list = []
        _ts_bid: list = []
        _ts_origem: list = []
        _ts_time: list = []
        _ts_timeng: list = []
        _idade_origem: list = []
        _ts_scan: list = []
        _ondas: list = []

        _strikes: list = []

        for key, mercado in dados_mercado.items():
            if "|" not in key:
                continue
            chaves_com_chave += 1
            ativo, cod_put = key.split("|", 1)
            inst = inst_map.get((ativo, cod_put))
            if not inst or not inst.vencimento or inst.vencimento <= hoje:
                continue
            chaves_com_inst += 1
            dte = inst.dias_ate_vencimento
            if dte is None or dte < dias_minimos:
                continue
            chaves_dentro_dias += 1
            strike = mercado.get("strike_rtd")
            if not strike or strike <= 0:
                continue
            chaves_com_strike += 1
            insts_validas.append(inst)
            _dias_validas.append(dte)
            _strikes.append(strike)
            _preco_ativo.append(mercado.get("preco_ativo", 0.0) or 0.0)
            _of_compra_ativo.append(mercado.get("of_compra_ativo", 0.0) or 0.0)
            _of_compra_put.append(mercado.get("of_compra_put", 0.0) or 0.0)
            _of_venda_call.append(mercado.get("of_venda_call", 0.0) or 0.0)
            _vov_put.append(mercado.get("vov_put_boca", 0.0) or mercado.get("vov_put", 0.0) or 0.0)
            _voc_call.append(mercado.get("voc_call_boca", 0.0) or mercado.get("voc_call", 0.0) or 0.0)
            _qul_put.append(mercado.get("qul_put", 0.0) or 0.0)
            _qul_call.append(mercado.get("qul_call", 0.0) or 0.0)
            _em_leilao.append(mercado.get("em_leilao", False))
            _status_put.append(mercado.get("status_put", "") or "")
            _status_call.append(mercado.get("status_call", "") or "")
            _status_ativo.append(mercado.get("status_ativo", "") or "")
            _ts_ask.append(mercado.get("ts_ativo_ask"))
            _ts_bid.append(mercado.get("ts_ativo_bid"))
            _ts_origem.append(mercado.get("ts_origem_ativo"))
            _ts_time.append(mercado.get("ts_time_ativo"))
            _ts_timeng.append(mercado.get("ts_timeng_ativo"))
            _idade_origem.append(mercado.get("idade_origem_ativo"))
            _ts_scan.append(mercado.get("ts_scan"))
            _ondas.append(mercado.get("onda"))

        resultados: list[OportunidadeVendida] = []

        if insts_validas:
            res = calcular_vendidas(
                preco_ativo=np.array(_preco_ativo, dtype=float),
                of_compra_ativo=np.array(_of_compra_ativo, dtype=float),
                of_compra_put=np.array(_of_compra_put, dtype=float),
                of_venda_call=np.array(_of_venda_call, dtype=float),
                strike=np.array(_strikes, dtype=float),
                dias=np.array(_dias_validas, dtype=int),
                vov_put=np.array(_vov_put, dtype=float),
                voc_call=np.array(_voc_call, dtype=float),
                dist_min_ativo=dist_min_ativo,
                premio_risco=premio_risco,
                lote_box=lote_box,
                lote_sbth=lote_sbth,
                taxa_cdi=taxa_cdi,
                custos_b3=self._custos_b3,
            )

            _cond_box = res.cond_box.tolist()
            _cond_sbth = res.cond_sbth.tolist()
            _viavel_box = res.viavel_box.tolist()
            _viavel_sbth = res.viavel_sbth.tolist()
            _recebimento_box = res.recebimento_box.tolist()
            _pct_box = res.pct_box.tolist()
            _pct_cdi_box = res.pct_cdi_box.tolist()
            _custo_box = res.custo_box.tolist()
            _pct_liq_box = res.pct_liq_box.tolist()
            _pct_cdi_liq_box = res.pct_cdi_liq_box.tolist()
            _recebimento_sbth = res.recebimento_sbth.tolist()
            _pct_sbth = res.pct_sbth.tolist()
            _pct_cdi_sbth = res.pct_cdi_sbth.tolist()
            _custo_sbth = res.custo_sbth.tolist()
            _pct_liq_sbth = res.pct_liq_sbth.tolist()
            _pct_cdi_liq_sbth = res.pct_cdi_liq_sbth.tolist()
            _dias_l = _dias_validas

            for i, inst in enumerate(insts_validas):
                if not (_cond_box[i] or _cond_sbth[i]):
                    continue
                strike = float(_strikes[i])
                p_ativo = _preco_ativo[i]
                taxa_aluguel = taxa_map.get(inst.ativo).taxa_atual if taxa_map and taxa_map.get(inst.ativo) else 0.0
                money_put = max(strike - p_ativo, 0.0)
                money_call = max(p_ativo - strike, 0.0)

                if _cond_box[i]:
                    resultados.append(OportunidadeVendida(
                        ativo=inst.ativo,
                        strike=strike,
                        vencimento=inst.vencimento,
                        dias=_dias_l[i],
                        cod_put=inst.cod_put,
                        cod_call=inst.cod_call,
                        tipo_opcao=inst.tipo_opcao.value,
                        classificacao="BOX_VENDIDO",
                        detectado_em=agora,
                        recebimento=round(_recebimento_box[i], 2),
                        pct_ganho=round(_pct_box[i], 6),
                        pct_cdi=round(_pct_cdi_box[i], 4),
                        viavel=_viavel_box[i],
                        em_leilao=_em_leilao[i],
                        status_put=_status_put[i],
                        status_call=_status_call[i],
                        status_ativo=_status_ativo[i],
                        liq_put_x_lote=_vov_put[i] - lote_box,
                        liq_call_x_lote=_voc_call[i] - lote_box,
                        preco_ativo=round(p_ativo, 2),
                        of_compra_put=round(_of_compra_put[i], 2),
                        of_venda_call=round(_of_venda_call[i], 2),
                        qul_put=round(_qul_put[i]),
                        qul_call=round(_qul_call[i]),
                        money_put=round(money_put, 2),
                        money_call=round(money_call, 2),
                        custo=round(_custo_box[i], 2),
                        taxa_aluguel=round(taxa_aluguel, 2),
                        pct_ganho_bruto=round(_pct_box[i], 6),
                        pct_ganho_liquido=round(_pct_liq_box[i], 6),
                        pct_cdi_bruto=round(_pct_cdi_box[i], 4),
                        pct_cdi_liquido=round(_pct_cdi_liq_box[i], 4),
                        ts_ativo_ask=_ts_ask[i],
                        ts_ativo_bid=_ts_bid[i],
                        ts_origem_ativo=_ts_origem[i],
                        ts_time_ativo=_ts_time[i],
                        ts_timeng_ativo=_ts_timeng[i],
                        idade_origem_ativo=_idade_origem[i],
                        ts_scan=_ts_scan[i],
                        onda=_ondas[i],
                    ))

                if _cond_sbth[i]:
                    resultados.append(OportunidadeVendida(
                        ativo=inst.ativo,
                        strike=strike,
                        vencimento=inst.vencimento,
                        dias=_dias_l[i],
                        cod_put=inst.cod_put,
                        cod_call=inst.cod_call,
                        tipo_opcao=inst.tipo_opcao.value,
                        classificacao="SBTH_VENDIDA",
                        detectado_em=agora,
                        recebimento=round(_recebimento_sbth[i], 2),
                        pct_ganho=round(_pct_sbth[i], 6),
                        pct_cdi=round(_pct_cdi_sbth[i], 4),
                        viavel=_viavel_sbth[i],
                        em_leilao=bool(_em_leilao[i]),
                        status_put=_status_put[i],
                        status_call=_status_call[i],
                        status_ativo=_status_ativo[i],
                        liq_put_x_lote=_vov_put[i] - lote_sbth,
                        liq_call_x_lote=0.0,
                        preco_ativo=round(p_ativo, 2),
                        of_compra_put=round(_of_compra_put[i], 2),
                        of_venda_call=round(_of_venda_call[i], 2),
                        qul_put=round(_qul_put[i]),
                        qul_call=round(_qul_call[i]),
                        money_put=round(money_put, 2),
                        money_call=round(money_call, 2),
                        custo=round(_custo_sbth[i], 2),
                        taxa_aluguel=round(taxa_aluguel, 2),
                        pct_ganho_bruto=round(_pct_sbth[i], 6),
                        pct_ganho_liquido=round(_pct_liq_sbth[i], 6),
                        pct_cdi_bruto=round(_pct_cdi_sbth[i], 4),
                        pct_cdi_liquido=round(_pct_cdi_liq_sbth[i], 4),
                        ts_ativo_ask=_ts_ask[i],
                        ts_ativo_bid=_ts_bid[i],
                        ts_origem_ativo=_ts_origem[i],
                        ts_time_ativo=_ts_time[i],
                        ts_timeng_ativo=_ts_timeng[i],
                        idade_origem_ativo=_idade_origem[i],
                        ts_scan=_ts_scan[i],
                        onda=_ondas[i],
                    ))

        n_box = sum(1 for r in resultados if r.classificacao == "BOX_VENDIDO")
        n_sbth = sum(1 for r in resultados if r.classificacao == "SBTH_VENDIDA")
        n_viaveis = sum(1 for r in resultados if r.viavel)
        resultados.sort(key=lambda o: (not o.viavel, -o.pct_cdi))

        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "BOX/SBTH VENDIDO"
            pipeline_tracker.add_stage("1. Com chave composta", len(dados_mercado), chaves_com_chave)
            pipeline_tracker.add_stage("2. Instrumento válido", chaves_com_chave, chaves_com_inst, "Instrumento não encontrado ou vencido")
            pipeline_tracker.add_stage("3. DTE mínimo", chaves_com_inst, chaves_dentro_dias, f"DTE < {dias_minimos}d")
            pipeline_tracker.add_stage("4. Strike RTD", chaves_dentro_dias, chaves_com_strike, "Strike ausente/zero")
            pipeline_tracker.add_stage("5. Resultados", chaves_com_strike, len(resultados), f"BOX={n_box}, SBTH={n_sbth}")
            pipeline_tracker.add_stage("6. Viáveis", len(resultados), n_viaveis, f"Prêmio-risco {premio_risco}xCDI")

        logger.info("Consumers: vendidas_vet=%.3fs | n_in=%d n_inst=%d n_dte=%d n_strike=%d n_opp=%d",
                     time.perf_counter() - _ts,
                     chaves_com_chave, chaves_com_inst, chaves_dentro_dias, chaves_com_strike, len(resultados))
        return resultados