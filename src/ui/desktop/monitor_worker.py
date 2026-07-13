import logging
import time
import os
import psutil

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.application.use_cases.monitor_vendidas import MonitorVendidasUseCase
from src.application.use_cases.monitor_colares import MonitorColaresUseCase
from src.application.use_cases.monitor_colares_calendario import MonitorColaresCalendarioUseCase
from src.application.use_cases.monitor_box import MonitorBoxUseCase
from src.application.use_cases.monitor_vendidas import MonitorVendidasUseCase
from src.application.use_cases.monitor_venda_coberta import MonitorVendaCobertaUseCase
from src.application.use_cases.mpp_use_case import MPPUseCase
from src.domain.services.pipeline_tracker import PipelineTracker
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona, ResultadoCaudaAssincrona
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.domain.services.market_data_source import criar_data_source, MarketDataSource
from src.application.dtos.dtos import EngineStatsDTO
from src.infrastructure.persistence.repositories.repositories import HistoricoSimulacoesRepository

logger = logging.getLogger(__name__)


class MonitorWorker(QThread):
    oportunidades_atualizadas = Signal(list)
    oportunidades_vendidas_atualizadas = Signal(list)
    oportunidades_coberta_atualizadas = Signal(list)
    status_message = Signal(str)
    rtd_status = Signal(bool)
    engine_stats_updated = Signal(object)
    colares_atualizados = Signal(list)
    colares_calendario_atualizados = Signal(list)
    boxes_atualizados = Signal(list)
    mpp_atualizados = Signal(list)
    mre_atualizados = Signal(list)
    mpp_status_changed = Signal(bool)

    def __init__(self, db_path: str, rtd: object = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._rtd_main = rtd
        self._mercado_provider = None
        self._monitor_uc = MonitorOportunidadesUseCase(db_path)
        self._monitor_vendidas_uc = MonitorVendidasUseCase(db_path)
        self._monitor_coberta_uc = MonitorVendaCobertaUseCase(db_path)
        self._monitor_colares_uc = MonitorColaresUseCase(db_path)
        self._monitor_colares_cal_uc = MonitorColaresCalendarioUseCase(db_path)
        self._monitor_mpp_uc = MPPUseCase(db_path)
        self._mpp_habilitado = self._ler_mpp_habilitado_db()
        self._mpp_cycle = 0
        self._mpp_carga_completa = False
        self._mpp_estrutural_carregado = False
        self._mpp_interval_cache: int | None = None

        self._monitor_box_uc = MonitorBoxUseCase(db_path, self._monitor_mpp_uc)
        self._running = False
        self._paused = False
        self._interval_ms = 3000
        self._mostrar_tp_op = False
        self._colar_cycle = 0
        self._colar_interval = 10
        self._colar_cal_cycle = 0
        self._colar_cal_interval = 3
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()
        self._forcar_colar = False
        self._colar_auto = False
        self._colar_mutex = QMutex()
        self._forcar_colar_cal = False
        self._colar_cal_auto = False
        self._colar_cal_ativos: list[str] | None = None
        self._colar_cal_params: dict | None = None
        self._colar_cal_mutex = QMutex()
        self._forcar_box = False
        self._box_auto = False
        self._box_mutex = QMutex()
        self._box_cycle = 0
        self._ultimo_dados_mercado: dict | None = None
        self._rtd_estava_stale: bool = False
        self._manutencao_cycle = 0
        self._rtd_reconnect_cycle = 0

    def run(self):
        com_initialized = False
        fonte = self._ler_param_str("fonte_market_data", "profit")
        usa_com = (fonte not in ("openfast", "mock"))
        if usa_com:
            try:
                import pythoncom
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                com_initialized = True
                logger.info("COM inicializado para fonte de dados.")
            except ImportError:
                logger.warning("MonitorWorker: pythoncom não disponível. Thread rodará sem COM.")
                self.status_message.emit("Aviso: pythoncom ausente. RTD indisponível.")

        fonte_nome = {"openfast": "Open Fast Socket", "profit": "Profit RTD", "mock": "Mock (Teste)"}.get(fonte, fonte)
        logger.info("MonitorWorker: iniciando fonte de dados: %s", fonte_nome)

        rtd = self._rtd_main
        if not rtd or not getattr(rtd, 'disponivel', False):
            if fonte == "openfast":
                delay_ms = self._ler_param_int("openfast_send_delay_ms", 1)
                rtd = criar_data_source("openfast", send_delay_ms=delay_ms)
            elif fonte == "mock":
                rtd = criar_data_source("mock", db_path=self.db_path)
                self._rtd_main = rtd
            else:
                rtd = criar_data_source("profit")
        self._mercado_provider = MercadoDataProvider(self.db_path, rtd)
        self.rtd_status.emit(getattr(rtd, 'disponivel', False))

        self._running = True
        logger.info("MonitorWorker: fonte de dados %s — disponivel=%s", fonte_nome, getattr(rtd, 'disponivel', False))

        if self._mpp_habilitado:
            self._carregar_mpp_estrutural()
            self._mpp_estrutural_carregado = True

        while self._running:
            if self._paused:
                self._mutex.lock()
                self._wait_condition.wait(self._mutex)
                self._mutex.unlock()
                if not self._running:
                    break

            try:
                t_start_cycle = time.perf_counter()
                # 1. Varredura Geral de Oportunidades (Monitor Principal)
                self._processar_monitor_geral(rtd)
                t1 = time.perf_counter()

                # 2. Varredura de Colares
                self._processar_colares(rtd)
                t2 = time.perf_counter()

                # 3. Varredura de Collar Calendário
                self._processar_colar_calendario(rtd)
                t3 = time.perf_counter()

                # 4. Varredura de Box Spread 4 Pontas
                self._processar_box_4p(rtd)
                t4 = time.perf_counter()

                # 5. Manutenção (detecção novos books, Onda 2, background scan)
                self._processar_manutencao()
                t5 = time.perf_counter()

                # 6. Tentativa de reconexão da fonte a cada ~30s se estiver offline
                if not rtd.disponivel:
                    self._rtd_reconnect_cycle += 1
                    if self._rtd_reconnect_cycle % 10 == 0:
                        if rtd.reconectar():
                            logger.info("Fonte de dados reconectada durante ciclo de varredura.")
                            self.rtd_status.emit(True)
                            self._mercado_provider.source = rtd
                else:
                    self._rtd_reconnect_cycle = 0

                # 7. MPP — Motor de Priorização de Pescaria (só após carga completa)
                if self._mpp_habilitado and self._mpp_carga_completa:
                    self._processar_mpp(rtd)
                t6 = time.perf_counter()

                dt_monitor = t1 - t_start_cycle
                dt_colar = t2 - t1
                dt_cal = t3 - t2
                dt_box = t4 - t3
                dt_manut = t5 - t4
                dt_mpp = t6 - t5
                dt_cycle = t6 - t_start_cycle
                if dt_cycle > 0.5:
                    logger.info("Ciclo: monitor=%.3fs colar=%.3fs cal=%.3fs box=%.3fs manut=%.3fs mpp=%.3fs total=%.3fs",
                                 dt_monitor, dt_colar, dt_cal, dt_box, dt_manut, dt_mpp, dt_cycle)

                # 7. Coleta Estatísticas do Motor
                self._emitir_estatisticas_engine(t_start_cycle)

            except Exception as e:
                logger.error("MonitorWorker: erro na varredura: %s", e)
                self.status_message.emit("Erro na varredura: {}".format(str(e)))

            self.msleep(self._interval_ms)

        rtd.desconectar()
        if com_initialized:
            import pythoncom
            pythoncom.CoUninitialize()
        logger.info("MonitorWorker: thread finalizada.")

    def pausar(self):
        self._paused = True
        logger.info("MonitorWorker: pausado.")

    def retomar(self):
        self._paused = False
        if self._mercado_provider and hasattr(self._mercado_provider, 'source'):
            source = self._mercado_provider.source
            if source and not source.disponivel:
                if source.reconectar():
                    logger.info("Fonte de dados reconectada ao retomar.")
                else:
                    logger.info("Fonte de dados ainda indisponivel ao retomar.")
            self.rtd_status.emit(source.disponivel if source else False)
        self._mutex.lock()
        self._wait_condition.wakeAll()
        self._mutex.unlock()
        logger.info("MonitorWorker: retomado.")

    def parar(self):
        self._running = False
        self._paused = False
        self._mutex.lock()
        self._wait_condition.wakeAll()
        self._mutex.unlock()
        self.wait(3000)
        logger.info("MonitorWorker: parado.")

    def set_interval(self, ms: int):
        self._interval_ms = max(2000, ms)

    def _ler_param_int(self, chave: str, default: int) -> int:
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self.db_path)
        param = repo.get_by_chave(chave)
        if param is not None:
            try:
                return int(float(param.valor))
            except (ValueError, TypeError):
                pass
        return default

    def _ler_param_str(self, chave: str, default: str) -> str:
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self.db_path)
        param = repo.get_by_chave(chave)
        if param is not None:
            try:
                return str(param.valor)
            except (ValueError, TypeError):
                pass
        return default

    def _ler_param_float(self, chave: str, default: float) -> float:
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self.db_path)
        param = repo.get_by_chave(chave)
        if param is not None:
            try:
                return float(param.valor)
            except (ValueError, TypeError):
                pass
        return default

    def recarregar_parametros(self):
        self._monitor_uc.recarregar_parametros()
        self._monitor_vendidas_uc.recarregar_parametros()
        self._monitor_coberta_uc.recarregar_parametros()
        self._monitor_colares_uc.recarregar_parametros()
        self._monitor_colares_cal_uc.recarregar_parametros()
        self._monitor_box_uc.recarregar_parametros()
        self._monitor_mpp_uc._param_repo.invalidate_cache()
        self.invalidar_cache_mpp_interval()
        if self._mercado_provider:
            self._mercado_provider.recarregar_parametros()
        mpp_hab = self._ler_mpp_habilitado_db()
        if mpp_hab != self._mpp_habilitado:
            self._mpp_habilitado = mpp_hab
            if mpp_hab:
                if self._mpp_carga_completa and self._mpp_estrutural_carregado:
                    self.mpp_status_changed.emit(True)
                else:
                    self.mpp_status_changed.emit(False)
            else:
                self.mpp_status_changed.emit(False)

    def recarregar_instrumentos(self):
        from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
        InstrumentoRepository.invalidate_cache()
        if self._mercado_provider:
            self._mercado_provider.recarregar_instrumentos()
        self._mpp_carga_completa = False
        self.mpp_status_changed.emit(False)

    def solicitar_varredura_colar(self):
        self._colar_mutex.lock()
        self._forcar_colar = True
        self._colar_mutex.unlock()

    def iniciar_auto_colar(self):
        self._colar_mutex.lock()
        self._colar_auto = True
        self._forcar_colar = True
        self._colar_cycle = 0
        self._colar_mutex.unlock()

    def parar_auto_colar(self):
        self._colar_mutex.lock()
        self._colar_auto = False
        self._forcar_colar = False
        self._colar_cycle = 0
        self._colar_mutex.unlock()

    def solicitar_varredura_colar_cal(self):
        self._colar_cal_mutex.lock()
        self._forcar_colar_cal = True
        self._colar_cal_mutex.unlock()

    def iniciar_auto_colar_cal(self, ativos: list[str] | None = None, params: dict | None = None):
        self._colar_cal_mutex.lock()
        self._colar_cal_auto = True
        self._forcar_colar_cal = True
        self._colar_cal_cycle = 0
        self._colar_cal_ativos = ativos
        self._colar_cal_params = params
        self._colar_cal_mutex.unlock()

    def parar_auto_colar_cal(self):
        self._colar_cal_mutex.lock()
        self._colar_cal_auto = False
        self._forcar_colar_cal = False
        self._colar_cal_cycle = 0
        self._colar_cal_mutex.unlock()

    def iniciar_auto_box(self):
        self._box_mutex.lock()
        self._box_auto = True
        self._forcar_box = True
        self._box_mutex.unlock()

    def parar_auto_box(self):
        self._box_mutex.lock()
        self._box_auto = False
        self._forcar_box = False
        self._box_mutex.unlock()

    def set_mostrar_tp_op(self, mostrar: bool):
        self._mostrar_tp_op = mostrar

    def _processar_monitor_geral(self, rtd):
        dados_mercado = self._mercado_provider.capturar_dados_mercado()
        self._ultimo_dados_mercado = dados_mercado
        if not dados_mercado:
            return

        resultados = self._monitor_uc.varrer(dados_mercado, pipeline_tracker=PipelineTracker())
        
        if not self._mostrar_tp_op:
            resultados = [r for r in resultados
                          if not (hasattr(r, 'classificacao')
                                  and r.classificacao == 'TP.Op')]

        self.oportunidades_atualizadas.emit(resultados)

        # Box/SBTH Vendido
        vendidas = self._monitor_vendidas_uc.varrer(dados_mercado, pipeline_tracker=PipelineTracker())
        if not self._mostrar_tp_op:
            vendidas = [r for r in vendidas if r.viavel]
        self.oportunidades_vendidas_atualizadas.emit(vendidas)

        # Venda Coberta
        coberta = self._monitor_coberta_uc.varrer(dados_mercado, pipeline_tracker=PipelineTracker())
        if not self._mostrar_tp_op:
            coberta = [r for r in coberta if r.viavel]
        self.oportunidades_coberta_atualizadas.emit(coberta)

    def _processar_colares(self, rtd):
        self._colar_mutex.lock()
        self._colar_cycle += 1
        deve_escanear = self._forcar_colar
        if not deve_escanear and self._colar_auto:
            deve_escanear = (self._colar_cycle % self._colar_interval == 0)
        if deve_escanear:
            self._forcar_colar = False
        self._colar_mutex.unlock()

        if deve_escanear:
            dados_md = getattr(self, '_ultimo_dados_mercado', None)
            if not dados_md or len(dados_md) < 50:
                return
            tracker = PipelineTracker()
            resultados = self._monitor_colares_uc.varrer(None, dados_mercado=dados_md, pipeline_tracker=tracker)
            self.colares_atualizados.emit(resultados)

    def _processar_colar_calendario(self, rtd):
        self._colar_cal_mutex.lock()
        self._colar_cal_cycle += 1
        deve_escanear = self._forcar_colar_cal
        if not deve_escanear and self._colar_cal_auto:
            deve_escanear = (self._colar_cal_cycle % self._colar_cal_interval == 0)

        ativos = self._colar_cal_ativos
        params = self._colar_cal_params
        if deve_escanear:
            self._forcar_colar_cal = False
        self._colar_cal_mutex.unlock()

        if deve_escanear:
            dados_md = getattr(self, '_ultimo_dados_mercado', None)
            tracker = PipelineTracker()
            resultados = self._monitor_colares_cal_uc.varrer(rtd, dados_md, params, ativos, pipeline_tracker=tracker)
            try:
                if resultados:
                    otimizadas = self._processar_otimizado(resultados)
                else:
                    otimizadas = []
                if otimizadas:
                    resultados.extend(otimizadas)
                    tracker.add_stage(
                        "14. Pós-processamento (Otimizado)",
                        len(resultados), len(otimizadas),
                        f"{len(otimizadas)} variantes otimizadas adicionadas"
                    )
            except Exception:
                logger.exception("Erro ao processar Otimizado")
                tracker.add_stage("14. Pós-processamento (Otimizado)", 0, 0, "ERRO")

            self.colares_calendario_atualizados.emit(resultados)

    def _processar_cauda(self, resultados: list) -> list:
        from src.domain.services.calculadora_colar_calendario import ResultadoColarCalendario
        cauda_results: list = []
        taxa_cdi = self._ler_param_float("taxa_cdi", 0.145)
        calda_premio_risco = self._ler_param_float("calda_premio_risco", 2.5)
        calda_desvios_cauda = self._ler_param_float("calda_desvios_cauda", 3.0)
        calda_ratio_max = self._ler_param_int("calda_ratio_max", 50)
        calda_ratio_put_min = self._ler_param_float("calda_ratio_put_min", 0.3)
        calda_ratio_put_step = self._ler_param_float("calda_ratio_put_step", 0.01)

        for r in resultados:
            if not r.viavel:
                continue
            cauda = CalculadoraCaudaAssincrona.calcular(
                preco_ativo=r.preco_ativo,
                strike_call=r.strike_call,
                strike_put=r.strike_put,
                premio_call=r.premio_call,
                premio_put=r.premio_put,
                dte_call=r.dte_call,
                ativo=r.ativo,
                iv_call_pct=r.iv_call,
                pnl_projetado_base=r.pnl_projetado,
                capital_empregado_base=r.capital_empregado,
                pct_cdi_base=r.pct_cdi,
                taxa_cdi=taxa_cdi,
                calda_premio_risco=calda_premio_risco,
                calda_desvios_cauda=calda_desvios_cauda,
                calda_ratio_max=calda_ratio_max,
                calda_ratio_put_min=calda_ratio_put_min,
                calda_ratio_put_step=calda_ratio_put_step,
                custo_b3_base=r.custo_b3,
                preco_compra=r.preco_compra,
                iv_put_pct=r.iv_put,
                dte_put=r.dte_put,
                qtd_acao=r.qtd_acao,
            )
            if cauda is None:
                continue

            novo = ResultadoColarCalendario(
                ativo=r.ativo,
                vencimento_call=r.vencimento_call,
                vencimento_put=r.vencimento_put,
                dte_call=r.dte_call,
                dte_put=r.dte_put,
                dte_extra=r.dte_extra,
                strike_call=r.strike_call,
                strike_put=r.strike_put,
                cod_call=r.cod_call,
                cod_put=r.cod_put,
                preco_ativo=r.preco_ativo,
                premio_call=r.premio_call,
                premio_put=r.premio_put,
                net_credito=round(r.premio_call - r.premio_put, 4),
                iv_call=r.iv_call,
                iv_put=r.iv_put,
                valor_put_venc_call=r.valor_put_venc_call,
                pnl_stock=r.pnl_stock,
                pnl_projetado=cauda.pnl_projetado,
                capital_empregado=r.capital_empregado,
                pct_retorno=0.0,
                pct_cdi=cauda.pct_cdi_com_ratio,
                delta_total=r.delta_total,
                theta_call=r.theta_call,
                theta_put=r.theta_put,
                theta_liquido=r.theta_liquido,
                viavel=True,
                tipo=r.tipo,
                r=taxa_cdi,
                custo_b3=cauda.custo_b3_base,
                score=round(cauda.score_cauda, 4),
                preco_compra=r.preco_compra,
                be_baixa=r.be_baixa,
                be_alta=cauda.breakeven_direito,
                ratio_call=cauda.ratio_call,
                ratio_put=cauda.ratio_put,
                is_cauda=True,
                qtd_acao=r.qtd_acao,
                qtd_call=r.qtd_call,
                qtd_put=r.qtd_put,
            )
            cauda_results.append(novo)
        return cauda_results

    def _processar_otimizado(self, resultados: list) -> list:
        from src.domain.services.calculadora_colar_calendario import ResultadoColarCalendario
        from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
        ui_results: list = []
        repo = HistoricoSimulacoesRepository(self.db_path)
        taxa_cdi = self._ler_param_float("taxa_cdi", 0.145)
        otimizado_desvios_sigma = self._ler_param_float("otimizado_desvios_sigma", 2.0)
        otimizado_sigma_rendimento = self._ler_param_float("otimizado_sigma_rendimento", 2.0)
        otimizado_ratio_put_min = self._ler_param_float("otimizado_ratio_put_min", 0.80)
        otimizado_ratio_max = self._ler_param_float("otimizado_ratio_max", 1.40)
        otimizado_ratio_put_step = self._ler_param_float("otimizado_ratio_put_step", 0.10)
        emol = self._ler_param_float("taxa_emolumento_pct", 0.00025)
        liq = self._ler_param_float("taxa_liquidacao_pct", 0.000275)
        ir = self._ler_param_float("taxa_ir_pct", 0.15)
        custos_b3_calc = CalculadoraCustosB3(emol, liq, ir)

        for r in resultados:
            if not r.viavel:
                continue
            variantes = CalculadoraCaudaAssincrona.processar_otimizado(
                preco_ativo=r.preco_ativo,
                strike_call=r.strike_call,
                strike_put=r.strike_put,
                premio_call=r.premio_call,
                premio_put=r.premio_put,
                dte_call=r.dte_call,
                ativo=r.ativo,
                iv_call_pct=r.iv_call,
                pnl_projetado_base=r.pnl_projetado,
                capital_empregado_base=r.capital_empregado,
                pct_cdi_base=r.pct_cdi,
                taxa_cdi=taxa_cdi,
                otimizado_ratio_put_min=otimizado_ratio_put_min,
                otimizado_ratio_max=otimizado_ratio_max,
                otimizado_desvios_sigma=otimizado_desvios_sigma,
                otimizado_ratio_put_step=otimizado_ratio_put_step,
                otimizado_sigma_rendimento=otimizado_sigma_rendimento,
                custo_b3_base=r.custo_b3,
                preco_compra=r.preco_compra,
                iv_put_pct=r.iv_put,
                dte_put=r.dte_put,
                qtd_acao=r.qtd_acao,
            )
            if not variantes:
                continue

            premio_risco = self._ler_param_float("premio_risco_colar_calendario", 0.9)
            registros = []
            for v in variantes:
                if v.estagio != "Base" and v.pct_cdi_com_ratio < max(r.pct_cdi, premio_risco):
                    continue
                n = v.ratio_call
                m = v.ratio_put
                custo_b3_variante = (
                    custos_b3_calc.custos_opcao(r.premio_call, n_pernas=1, ida_e_volta=True) * n
                    + custos_b3_calc.custos_opcao(r.premio_put, n_pernas=1, ida_e_volta=True) * m
                    + custos_b3_calc.custos_stock(r.preco_compra or r.preco_ativo, n_acoes=1)
                )

                registros.append({
                    "id_chassi": v.id_chassi,
                    "estagio": v.estagio,
                    "ativo": v.ativo,
                    "preco_ativo": v.preco_ativo,
                    "strike_call": v.strike_call,
                    "strike_put": v.strike_put,
                    "dte_original": v.dte_call,
                    "iv_call": v.iv_call,
                    "ratio_call": v.ratio_call,
                    "ratio_put": v.ratio_put,
                    "pnl_cauda_esq": v.pnl_na_cauda_esquerda,
                    "pnl_cauda_dir": v.pnl_na_cauda_direita,
                    "be_esq": v.breakeven_esquerdo,
                    "be_dir": v.breakeven_direito,
                    "pct_cdi": v.pct_cdi_com_ratio,
                    "qtd_acao": r.qtd_acao,
                    "premio_call": r.premio_call,
                    "premio_put": r.premio_put,
                    "preco_compra": r.preco_compra or r.preco_ativo,
                })

                novo = ResultadoColarCalendario(
                    ativo=r.ativo,
                    vencimento_call=r.vencimento_call,
                    vencimento_put=r.vencimento_put,
                    dte_call=r.dte_call,
                    dte_put=r.dte_put,
                    dte_extra=r.dte_extra,
                    strike_call=r.strike_call,
                    strike_put=r.strike_put,
                    cod_call=r.cod_call,
                    cod_put=r.cod_put,
                    preco_ativo=r.preco_ativo,
                    premio_call=r.premio_call,
                    premio_put=r.premio_put,
                    net_credito=round(r.premio_call - r.premio_put, 4),
                    iv_call=r.iv_call,
                    iv_put=r.iv_put,
                    valor_put_venc_call=r.valor_put_venc_call,
                    pnl_stock=r.pnl_stock,
                    pnl_projetado=round(v.pnl_com_ratio, 4),
                    capital_empregado=r.capital_empregado,
                    pct_retorno=0.0,
                    pct_cdi=v.pct_cdi_com_ratio,
                    delta_total=r.delta_total,
                    theta_call=r.theta_call,
                    theta_put=r.theta_put,
                    theta_liquido=r.theta_liquido,
                    viavel=True,
                    tipo=r.tipo,
                    r=taxa_cdi,
                    custo_b3=round(custo_b3_variante, 4),  # fix: custo real por ratio
                    score=0.0,
                    preco_compra=r.preco_compra,
                    be_baixa=v.breakeven_esquerdo,
                    be_alta=v.breakeven_direito,
                    ratio_call=v.ratio_call,
                    ratio_put=v.ratio_put,
                    is_otimizado=True,
                    estagio_otimizado=v.estagio,
                    detectado_em=r.detectado_em,
                    qtd_acao=r.qtd_acao,
                    qtd_call=r.qtd_call,
                    qtd_put=r.qtd_put,
                )
                ui_results.append(novo)

            if registros:
                repo.salvar_lote(registros)

        return ui_results

    def _processar_box_4p(self, rtd):
        self._box_mutex.lock()
        self._box_cycle += 1
        deve_escanear = self._forcar_box
        if not deve_escanear and self._box_auto:
            box_interval = self._ler_param_int("box_scan_interval", 5)
            deve_escanear = (self._box_cycle % box_interval == 0)
        if deve_escanear:
            self._forcar_box = False
        self._box_mutex.unlock()

        if deve_escanear:
            tracker = PipelineTracker()
            resultados = self._monitor_box_uc.varrer(rtd, pipeline_tracker=tracker)
            self.boxes_atualizados.emit(resultados)

    def _emitir_estatisticas_engine(self, t_start_cycle):
        t_elapsed_ms = int((time.perf_counter() - t_start_cycle) * 1000)
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except Exception:
            cpu = 0.0
            mem = 0.0

        engine_stats = self._mercado_provider.get_engine_stats() if self._mercado_provider else {}
        stale = engine_stats.get('dados_stale', False)
        stats = EngineStatsDTO(
            scan_time_ms=t_elapsed_ms,
            cpu_pct=cpu,
            mem_mb=mem,
            total_instrumentos=engine_stats.get('total', 0),
            monitored_onda1=engine_stats.get('onda1', 0),
            monitored_onda2=engine_stats.get('onda2', 0),
            registrado=engine_stats.get('registrado', False),
            progresso_idx=engine_stats.get('progresso_idx', 0),
            dados_stale=stale,
            ultimo_refresh_ha_segundos=engine_stats.get('ultimo_refresh_ha_segundos', -1),
            ciclos_sem_dados=engine_stats.get('ciclos_sem_dados', 0),
        )
        self.engine_stats_updated.emit(stats)

    def _carregar_mpp_estrutural(self):
        try:
            self._monitor_mpp_uc.carregar_estrutural()
            logger.info("MPP estrutural carregado com sucesso")
            self.status_message.emit("MPP: dados estruturais carregados")
        except Exception as e:
            logger.error(f"Falha ao carregar MPP estrutural: {e}")
            self.status_message.emit(f"MPP: erro ao carregar dados estruturais ({e})")

    def _tentar_ativar_mpp(self):
        if not self._mpp_habilitado:
            return False
        if self._mpp_carga_completa and self._mpp_estrutural_carregado:
            self.mpp_status_changed.emit(True)
            return True
        return False

    def _ler_mpp_habilitado_db(self) -> bool:
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        try:
            repo = ParametroRepository(self.db_path)
            param = repo.get_by_chave("mpp_habilitado")
            return bool(param.valor) if param else False
        except Exception:
            return False

    def _processar_manutencao(self):
        self._manutencao_cycle += 1
        # Roda a cada 2 ciclos do monitor. Com _interval_ms=3000, sai a cada ~6s.
        if self._manutencao_cycle % 2 != 0 or not self._mercado_provider:
            return
        t0 = time.perf_counter()
        self._mercado_provider.fazer_manutencao()
        logger.info("Manutenção: novos books + prioridades em %.2fs", time.perf_counter() - t0)

        if self._mpp_habilitado and not self._mpp_carga_completa:
            stats = self._mercado_provider.get_engine_stats()
            if stats.get('registrado', False) and stats.get('onda1', 0) > 0:
                self._mpp_carga_completa = True
                self.mpp_status_changed.emit(True)
                logger.info("MPP: carga completa, instantâneo ativado")

        # Limpeza periodica das tabelas temporais do MPP (snapshot, historico,
        # spread_history). Com _interval_ms=3000, 1440 ciclos ~= 72 min.
        if self._manutencao_cycle % 1440 == 0:
            t1 = time.perf_counter()
            self._monitor_mpp_uc.limpar_snapshots_antigos()
            logger.debug("Limpeza de tabelas temporais em %.2fs", time.perf_counter() - t1)

    def _processar_mpp(self, rtd):
        self._mpp_cycle += 1
        if self._mpp_cycle % self._mpp_interval != 0:
            return
        try:
            resultados_box, recomendacoes = self._monitor_mpp_uc.calcular_instantaneo(rtd)
            self.mpp_atualizados.emit(resultados_box)
            self.mre_atualizados.emit(recomendacoes)
        except Exception as e:
            logger.error(f"Erro no MPP: {e}")

    @property
    def _mpp_interval(self) -> int:
        if self._mpp_interval_cache is None:
            from src.infrastructure.persistence.repositories.repositories import ParametroRepository
            repo = ParametroRepository(self.db_path)
            param = repo.get_by_chave("mpp_instantaneo_interval")
            self._mpp_interval_cache = int(param.valor) if param else 24
        return self._mpp_interval_cache

    def invalidar_cache_mpp_interval(self):
        self._mpp_interval_cache = None


