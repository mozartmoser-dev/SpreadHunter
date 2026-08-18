import logging
import time

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np

from src.application.dtos.dtos_venda_coberta import OportunidadeVendaCoberta
from src.application.use_cases.experimental.extrair_colunas import (
    extrair,
    extrair_encadeado,
    extrair_passthrough,
)
from src.domain.services.calculadora_coberta_vetor import calcular_coberta, calcular_comprada
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    TaxaAluguelRepository,
)

logger = logging.getLogger(__name__)


class VetorMonitorVendaCobertaUseCase:
    """Versão vetorizada (experimental) de ``MonitorVendaCobertaUseCase``.

    Implementa ``varrer`` (venda coberta) e ``varrer_comprada`` (taxa
    comprada). Deve produzir resultados equivalentes ao escalar.
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

    def _calcular_cdi_periodo(self, dias_corridos) -> float:
        from src.domain.services.calendario_b3 import dc_to_du

        du = dc_to_du(None, None, dias_corridos)
        if du <= 0:
            return 0.0
        return (1 + self._get_taxa_cdi()) ** (du / 252) - 1

    def varrer(self, dados_mercado: dict[str, dict],
               inst_map: dict | None = None,
               chaves: list | None = None,
               chaves_parsed: list | None = None,
               pipeline_tracker: PipelineTracker | None = None) -> list[OportunidadeVendaCoberta]:
        _ts = time.perf_counter()
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        hoje = date.today()
        if inst_map is None:
            inst_map = self.inst_repo.get_all_mapped()
        taxa_repo = TaxaAluguelRepository(self.db_path)
        taxa_map = taxa_repo.get_latest_all()
        premio_risco = self._get_param("venda_coberta_premio_risco", 1.08)
        dias_maximos = int(self._get_param("venda_coberta_dias_maximos", 30))
        taxa_cdi = self._get_taxa_cdi()
        lote_call = int(self._get_param("venda_coberta_lote_liquidez", 100))
        self._ultimo_pipeline = pipeline_tracker

        chaves_com_chave = 0
        chaves_com_inst = 0
        chaves_dentro_dias = 0
        chaves_com_strike = 0
        n_cond = 0
        chaves_validas: list[str] = []
        insts_validas = []

        for key, mercado in dados_mercado.items():
            if "|" not in key:
                continue
            chaves_com_chave += 1
            ativo, cod_put = key.split("|", 1)
            inst = inst_map.get((ativo, cod_put))
            if not inst or not inst.vencimento or inst.vencimento <= hoje:
                continue
            chaves_com_inst += 1
            if inst.dias_ate_vencimento is None or inst.dias_ate_vencimento > dias_maximos:
                continue
            chaves_dentro_dias += 1
            strike = mercado.get("strike_rtd")
            if not strike or strike <= 0:
                continue
            chaves_com_strike += 1
            chaves_validas.append(key)
            insts_validas.append(inst)

        resultados: list[OportunidadeVendaCoberta] = []

        if chaves_validas:
            preco_ativo = extrair(chaves_validas, dados_mercado, "preco_ativo")
            of_compra_ativo = extrair(chaves_validas, dados_mercado, "of_compra_ativo")
            of_venda_call = extrair(chaves_validas, dados_mercado, "of_venda_call")
            voc_call = extrair_encadeado(chaves_validas, dados_mercado, ["voc_call_boca", "voc_call"])
            qul_call = extrair(chaves_validas, dados_mercado, "qul_call")
            strikes = np_strikes(dados_mercado, chaves_validas)
            dias_arr = np_dias(insts_validas)

            res = calcular_coberta(
                preco_ativo=preco_ativo,
                of_compra_ativo=of_compra_ativo,
                of_venda_call=of_venda_call,
                voc_call=voc_call,
                strike=strikes,
                dias=dias_arr,
                premio_risco=premio_risco,
                lote_call=lote_call,
                taxa_cdi=taxa_cdi,
                custos_b3=self._custos_b3,
            )

            em_leilao_l = [dados_mercado[k].get("em_leilao", False) for k in chaves_validas]
            ts_ask = extrair_passthrough(chaves_validas, dados_mercado, "ts_ativo_ask")
            ts_bid = extrair_passthrough(chaves_validas, dados_mercado, "ts_ativo_bid")
            ts_origem = extrair_passthrough(chaves_validas, dados_mercado, "ts_origem_ativo")
            ts_time = extrair_passthrough(chaves_validas, dados_mercado, "ts_time_ativo")
            ts_timeng = extrair_passthrough(chaves_validas, dados_mercado, "ts_timeng_ativo")
            idade_origem = extrair_passthrough(chaves_validas, dados_mercado, "idade_origem_ativo")
            ts_scan = extrair_passthrough(chaves_validas, dados_mercado, "ts_scan")
            ondas = extrair_passthrough(chaves_validas, dados_mercado, "onda")

            for i, key in enumerate(chaves_validas):
                inst = insts_validas[i]
                strike = float(strikes[i])
                p_ativo = float(preco_ativo[i])
                taxa_aluguel = taxa_map.get(inst.ativo).taxa_atual if taxa_map and taxa_map.get(inst.ativo) else 0.0
                money_call = max(p_ativo - strike, 0.0)
                money_put = max(strike - p_ativo, 0.0)
                if not res.cond[i]:
                    continue
                n_cond += 1
                resultados.append(OportunidadeVendaCoberta(
                    ativo=inst.ativo,
                    strike=strike,
                    vencimento=inst.vencimento,
                    dias=inst.dias_ate_vencimento,
                    cod_put=inst.cod_put,
                    cod_call=inst.cod_call,
                    tipo_opcao=inst.tipo_opcao.value,
                    detectado_em=agora,
                    recebimento=round(float(res.recebimento[i]), 2),
                    pct_ganho=round(float(res.pct[i]), 6),
                    pct_cdi=round(float(res.pct_cdi[i]), 4),
                    viavel=bool(res.viavel[i]),
                    em_leilao=em_leilao_l[i],
                    liq_call_x_lote=float(voc_call[i] - lote_call),
                    preco_ativo=round(p_ativo, 2),
                    of_venda_call=round(float(of_venda_call[i]), 2),
                    qul_call=round(float(qul_call[i])),
                    money_put=round(money_put, 2),
                    money_call=round(money_call, 2),
                    custo=round(float(res.custo[i]), 2),
                    taxa_aluguel=round(taxa_aluguel, 2),
                    pct_ganho_bruto=round(float(res.pct[i]), 6),
                    pct_ganho_liquido=round(float(res.pct_liq[i]), 6),
                    pct_cdi_bruto=round(float(res.pct_cdi[i]), 4),
                    pct_cdi_liquido=round(float(res.pct_cdi_liq[i]), 4),
                    ts_ativo_ask=ts_ask[i],
                    ts_ativo_bid=ts_bid[i],
                    ts_origem_ativo=ts_origem[i],
                    ts_time_ativo=ts_time[i],
                    ts_timeng_ativo=ts_timeng[i],
                    idade_origem_ativo=idade_origem[i],
                    ts_scan=ts_scan[i],
                    onda=ondas[i],
                ))

        n_viaveis = sum(1 for r in resultados if r.viavel)
        resultados.sort(key=lambda o: (not o.viavel, -o.pct_cdi))

        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "VENDA COBERTA"
            pipeline_tracker.add_stage("1. Com chave composta", len(dados_mercado), chaves_com_chave)
            pipeline_tracker.add_stage("2. Instrumento válido", chaves_com_chave, chaves_com_inst, "Instrumento não encontrado ou vencido")
            pipeline_tracker.add_stage("3. DTE máximo", chaves_com_inst, chaves_dentro_dias, f"DTE > {dias_maximos}d")
            pipeline_tracker.add_stage("4. Strike RTD", chaves_dentro_dias, chaves_com_strike, "Strike ausente/zero")
            pipeline_tracker.add_stage("5. Condição preço", chaves_com_strike, n_cond, "Strike >= preço ativo ou recebimento<=strike")
            pipeline_tracker.add_stage("6. Resultados", n_cond, len(resultados))
            pipeline_tracker.add_stage("7. Viáveis", len(resultados), n_viaveis, f"Prêmio-risco {premio_risco}xCDI")

        logger.info("Consumers: coberta_v_vet=%.3fs | n_in=%d n_inst=%d n_dte=%d n_strike=%d n_opp=%d",
                     time.perf_counter() - _ts,
                     chaves_com_chave, chaves_com_inst, chaves_dentro_dias, chaves_com_strike, len(resultados))
        return resultados

    def varrer_comprada(self, dados_mercado: dict[str, dict],
                        inst_map: dict | None = None,
                        chaves: list | None = None,
                        chaves_parsed: list | None = None,
                        pipeline_tracker: PipelineTracker | None = None) -> list[OportunidadeVendaCoberta]:
        _ts = time.perf_counter()
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        hoje = date.today()
        if inst_map is None:
            inst_map = self.inst_repo.get_all_mapped()
        taxa_repo = TaxaAluguelRepository(self.db_path)
        taxa_map = taxa_repo.get_latest_all()
        premio_risco = self._get_param("taxa_comprada_premio_risco", 1.05)
        dias_maximos = int(self._get_param("taxa_comprada_dias_maximos", 10))
        dist_max_pct = self._get_param("taxa_comprada_dist_max_pct", 0.80)
        lote_liquidez = int(self._get_param("taxa_comprada_lote_liquidez", 1))
        taxa_cdi = self._get_taxa_cdi()
        chaves_com_inst = 0

        insts_validas = []
        _dias_validas: list = []
        _preco_ativo: list = []
        _of_venda_ativo: list = []
        _of_compra_call: list = []
        _voc_call: list = []
        _strikes: list = []
        _em_leilao: list = []
        _ts_ask: list = []
        _ts_bid: list = []
        _ts_origem: list = []
        _ts_time: list = []
        _ts_timeng: list = []
        _idade_origem: list = []
        _ts_scan: list = []
        _ondas: list = []

        for key, mercado in dados_mercado.items():
            if "|" not in key:
                continue
            ativo, cod_put = key.split("|", 1)
            inst = inst_map.get((ativo, cod_put))
            if not inst or not inst.vencimento or inst.vencimento <= hoje:
                continue
            chaves_com_inst += 1
            dte = inst.dias_ate_vencimento
            if dte is None or dte > dias_maximos:
                continue
            strike = mercado.get("strike_rtd")
            if not strike or strike <= 0:
                continue
            insts_validas.append(inst)
            _dias_validas.append(dte)
            _strikes.append(strike)
            _preco_ativo.append(mercado.get("preco_ativo", 0.0) or 0.0)
            _of_venda_ativo.append(mercado.get("of_venda_ativo", 0.0) or 0.0)
            _of_compra_call.append(mercado.get("of_compra_call", 0.0) or 0.0)
            _voc_call.append(mercado.get("voc_call_boca", 0.0) or mercado.get("voc_call", 0.0) or 0.0)
            _em_leilao.append(mercado.get("em_leilao", False))
            _ts_ask.append(mercado.get("ts_ativo_ask"))
            _ts_bid.append(mercado.get("ts_ativo_bid"))
            _ts_origem.append(mercado.get("ts_origem_ativo"))
            _ts_time.append(mercado.get("ts_time_ativo"))
            _ts_timeng.append(mercado.get("ts_timeng_ativo"))
            _idade_origem.append(mercado.get("idade_origem_ativo"))
            _ts_scan.append(mercado.get("ts_scan"))
            _ondas.append(mercado.get("onda"))

        resultados: list[OportunidadeVendaCoberta] = []

        if insts_validas:
            res = calcular_comprada(
                preco_ativo=np.array(_preco_ativo, dtype=float),
                of_venda_ativo=np.array(_of_venda_ativo, dtype=float),
                of_compra_call=np.array(_of_compra_call, dtype=float),
                voc_call=np.array(_voc_call, dtype=float),
                strike=np.array(_strikes, dtype=float),
                dias=np.array(_dias_validas, dtype=int),
                premio_risco=premio_risco,
                lote_liquidez=lote_liquidez,
                dist_max_pct=dist_max_pct,
                taxa_cdi=taxa_cdi,
                custos_b3=self._custos_b3,
            )

            _cond = res.cond.tolist()
            _viavel = res.viavel.tolist()
            _custo_montagem = res.custo_montagem.tolist()
            _pct = res.pct.tolist()
            _pct_cdi = res.pct_cdi.tolist()
            _custo = res.custo.tolist()
            _pct_liq = res.pct_liq.tolist()
            _pct_cdi_liq = res.pct_cdi_liq.tolist()
            _dias = _dias_validas

            for i, inst in enumerate(insts_validas):
                if not _cond[i]:
                    continue
                strike = _strikes[i]
                p_ativo = _preco_ativo[i]
                taxa_aluguel = taxa_map.get(inst.ativo).taxa_atual if taxa_map and taxa_map.get(inst.ativo) else 0.0
                money_call = max(p_ativo - strike, 0.0)
                money_put = max(strike - p_ativo, 0.0)
                resultados.append(OportunidadeVendaCoberta(
                    ativo=inst.ativo,
                    strike=strike,
                    vencimento=inst.vencimento,
                    dias=_dias[i],
                    cod_put=inst.cod_put,
                    cod_call=inst.cod_call,
                    tipo_opcao=inst.tipo_opcao.value,
                    detectado_em=agora,
                    classificacao="TAXA_COMPRADA",
                    recebimento=round(_custo_montagem[i], 2),
                    pct_ganho=round(_pct[i], 6),
                    pct_cdi=round(_pct_cdi[i], 4),
                    viavel=_viavel[i],
                    em_leilao=_em_leilao[i],
                    liq_call_x_lote=_voc_call[i] - lote_liquidez,
                    preco_ativo=round(p_ativo, 2),
                    of_venda_call=round(_of_compra_call[i], 2),
                    qul_call=round(_voc_call[i]),
                    money_put=round(money_put, 2),
                    money_call=round(money_call, 2),
                    custo=round(_custo[i], 2),
                    taxa_aluguel=round(taxa_aluguel, 2),
                    pct_ganho_bruto=round(_pct[i], 6),
                    pct_ganho_liquido=round(_pct_liq[i], 6),
                    pct_cdi_bruto=round(_pct_cdi[i], 4),
                    pct_cdi_liquido=round(_pct_cdi_liq[i], 4),
                    ts_ativo_ask=_ts_ask[i],
                    ts_ativo_bid=_ts_bid[i],
                    ts_origem_ativo=_ts_origem[i],
                    ts_time_ativo=_ts_time[i],
                    ts_timeng_ativo=_ts_timeng[i],
                    idade_origem_ativo=_idade_origem[i],
                    ts_scan=_ts_scan[i],
                    onda=_ondas[i],
                ))

        resultados.sort(key=lambda o: (not o.viavel, -o.pct_cdi))
        logger.info("Consumers: coberta_c_vet=%.3fs | n_opp=%d",
                     time.perf_counter() - _ts, len(resultados))
        return resultados


def np_strikes(dados_mercado: dict, chaves_validas: list) -> 'np.ndarray':
    import numpy as np
    return np.array([dados_mercado[k].get("strike_rtd", 0.0) or 0.0 for k in chaves_validas], dtype=float)


def np_dias(insts_validas: list) -> 'np.ndarray':
    import numpy as np
    return np.array([inst.dias_ate_vencimento or 0 for inst in insts_validas], dtype=int)