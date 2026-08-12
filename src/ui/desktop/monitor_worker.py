import logging
import time
import math
import os
import psutil

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from src.application.dtos.dtos import EngineStatsDTO
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.application.use_cases.monitor_vendidas import MonitorVendidasUseCase
from src.application.use_cases.monitor_colares import MonitorColaresUseCase
from src.application.use_cases.monitor_colares_calendario import MonitorColaresCalendarioUseCase
from src.application.use_cases.monitor_box import MonitorBoxUseCase
from src.application.use_cases.monitor_put_ratio import MonitorPutRatioUseCase
from src.application.use_cases.monitor_venda_coberta import MonitorVendaCobertaUseCase
from src.application.use_cases.mpp_use_case import MPPUseCase
from src.domain.services.pipeline_tracker import PipelineTracker
from src.domain.services.calculadora_cauda_assincrona import CalculadoraCaudaAssincrona, ResultadoCaudaAssincrona
from src.domain.services.calculadora_protecao_cauda import CalculadoraProtecaoCauda, ResultadoProtecaoCauda
from src.domain.services.calculadora_colar_calendario import ResultadoColarCalendario, TipoColarCalendario
from src.domain.services.calculadora_colar import ResultadoColar, TipoColar
from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
from src.infrastructure.persistence.repositories.repositories import (
    ParametroRepository, InstrumentoRepository, HistoricoSimulacoesRepository,
)
from src.domain.services.market_data_source import FieldName, criar_data_source
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.infrastructure.providers import stale_trace

logger = logging.getLogger(__name__)


def _profile_log_path():
    import tempfile
    return os.path.join(tempfile.gettempdir(), "spreadhunter_profile.tsv")


class StrategyToggle:
    """Controle genérico de scan cíclico com mutex."""

    def __init__(self, interval: int = 1, use_db_interval: str | None = None):
        self.cycle = 0
        self.interval = interval
        self.use_db_interval = use_db_interval
        self.forcar = False
        self.auto = False
        self.mutex = QMutex()

    def solicitar(self):
        self.mutex.lock()
        self.forcar = True
        self.mutex.unlock()

    def iniciar_auto(self):
        self.mutex.lock()
        self.auto = True
        self.forcar = True
        self.cycle = 0
        self.mutex.unlock()

    def parar_auto(self):
        self.mutex.lock()
        self.auto = False
        self.forcar = False
        self.cycle = 0
        self.mutex.unlock()

    def deve_escanear(self, db_reader=None) -> bool:
        self.mutex.lock()
        self.cycle += 1
        result = self.forcar
        if not result and self.auto:
            interval = self.interval
            if self.use_db_interval and db_reader:
                interval = db_reader(self.use_db_interval, self.interval)
            result = (self.cycle % interval == 0)
        if result:
            self.forcar = False
        self.mutex.unlock()
        return result


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
    put_ratio_atualizados = Signal(list)
    mpp_atualizados = Signal(list)
    mre_atualizados = Signal(list)
    mpp_status_changed = Signal(bool)
    integridade_params_verificada = Signal(list)

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
        self._monitor_put_ratio_uc = MonitorPutRatioUseCase(db_path)
        self._running = False
        self._paused = False
        self._interval_ms = 3000
        self._mostrar_tp_op = False
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()
        self._toggle_colar = StrategyToggle(interval=10)
        self._toggle_colar_cal = StrategyToggle(interval=3)
        self._toggle_box = StrategyToggle(interval=5, use_db_interval="box_scan_interval")
        self._toggle_put_ratio = StrategyToggle(interval=5)
        self._colar_cal_ativos: list[str] | None = None
        self._colar_cal_params: dict | None = None
        self._ultimo_dados_mercado: dict | None = None
        self._rtd_estava_stale: bool = False
        self._manutencao_cycle = 0
        self._rtd_reconnect_cycle = 0
        self._verificacao_integridade_feita = False

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

        fonte_nome = {"openfast": "Open Fast Socket", "profit": "Profit RTD", "fasttrade": "Fast Trade RTD", "mock": "Mock (Teste)"}.get(fonte, fonte)
        logger.info("MonitorWorker: iniciando fonte de dados: %s", fonte_nome)

        rtd = self._rtd_main
        if not rtd or not getattr(rtd, 'disponivel', False):
            if fonte == "openfast":
                delay_ms = self._ler_param_int("openfast_send_delay_ms", 1)
                rtd = criar_data_source("openfast", send_delay_ms=delay_ms)
            elif fonte == "mock":
                rtd = criar_data_source("mock", db_path=self.db_path)
            elif fonte == "fasttrade":
                throttle_ms = self._ler_param_int("rtd_throttle_ms", 200)
                rtd = criar_data_source("fasttrade", throttle_ms=throttle_ms)
            else:
                rtd = criar_data_source("profit")
            self._rtd_main = rtd
        self._mercado_provider = MercadoDataProvider(self.db_path, rtd)
        self._subscrever_futuros(rtd)
        if not getattr(rtd, 'disponivel', False) and hasattr(rtd, 'reconectar'):
            logger.info("MonitorWorker: tentativa rápida de reconexão...")
            if rtd.reconectar(max_attempts=2, delay_s=1.0):
                logger.info("MonitorWorker: fonte reconectada.")
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
                # 0. Manutenção primeiro — promove novas chaves ANTES do scan
                #    para instrumentos entrarem no mesmo ciclo (não no próximo)
                self._processar_manutencao()
                t0 = time.perf_counter()

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

                # 5. Varredura de Put Ratio Spread
                self._processar_put_ratio(rtd)
                t4b = time.perf_counter()

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

                dt_manut = t0 - t_start_cycle
                dt_monitor = t1 - t0
                dt_colar = t2 - t1
                dt_cal = t3 - t2
                dt_box = t4 - t3
                dt_put_ratio = t4b - t4
                dt_mpp = t6 - t4b
                dt_cycle = t6 - t_start_cycle

                n_inst = len(getattr(self._mercado_provider, '_chaves_com_book', set()))
                n_onda2 = len(getattr(self._mercado_provider, '_chaves_detalhes_completos', set()))
                self._profile_cycle = getattr(self, '_profile_cycle', 0) + 1
                with open(_profile_log_path(), "a") as pf:
                    pf.write(f"{self._profile_cycle}\t{dt_cycle:.4f}\t{dt_monitor:.4f}\t{dt_colar:.4f}\t"
                             f"{dt_cal:.4f}\t{dt_box:.4f}\t{dt_put_ratio:.4f}\t{dt_manut:.4f}\t{dt_mpp:.4f}\t"
                             f"{n_inst}\t{n_onda2}\n")

                # 7. Coleta Estatísticas do Motor
                self._emitir_estatisticas_engine(t_start_cycle)

                if not self._verificacao_integridade_feita:
                    self._verificar_integridade_params()
                    self._verificacao_integridade_feita = True

            except Exception as e:
                logger.exception("MonitorWorker: erro na varredura: %s", e)
                self.status_message.emit("Erro na varredura: {}".format(str(e)))

            self.msleep(self._interval_ms)

        rtd.desconectar()
        if com_initialized:
            import pythoncom
            pythoncom.CoUninitialize()
        logger.info("MonitorWorker: thread finalizada.")

    @property
    def market_data_source(self):
        if self._mercado_provider and hasattr(self._mercado_provider, 'source'):
            return self._mercado_provider.source
        return None

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
        terminou = self.wait(6000)
        if not terminou:
            source = self._obter_source()
            if source is not None and hasattr(source, 'desconectar'):
                source.desconectar()
                logger.info("MonitorWorker: forçou desconexão da fonte.")
        logger.info("MonitorWorker: parado.")

    def _obter_source(self):
        if self._rtd_main is not None:
            return self._rtd_main
        if self._mercado_provider is not None:
            return getattr(self._mercado_provider, 'source', None)
        return None

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

    def _verificar_integridade_params(self):
        try:
            from scripts.verificar_integridade_params import verificar as verificar_integridade
            divergencias = verificar_integridade(db_path=self.db_path)
            if divergencias:
                logger.warning(
                    "MonitorWorker: %d parâmetro(s) com divergência de integridade",
                    len(divergencias),
                )
                self.integridade_params_verificada.emit(divergencias)
        except Exception:
            logger.exception("MonitorWorker: erro ao verificar integridade dos parâmetros")

    def recarregar_parametros(self):
        self._monitor_uc.recarregar_parametros()
        self._monitor_vendidas_uc.recarregar_parametros()
        self._monitor_coberta_uc.recarregar_parametros()
        self._monitor_colares_uc.recarregar_parametros()
        self._monitor_colares_cal_uc.recarregar_parametros()
        self._monitor_box_uc.recarregar_parametros()
        self._monitor_put_ratio_uc.recarregar_parametros()
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
        self._toggle_colar.solicitar()

    def iniciar_auto_colar(self):
        self._toggle_colar.iniciar_auto()

    def parar_auto_colar(self):
        self._toggle_colar.parar_auto()

    def solicitar_varredura_colar_cal(self):
        self._toggle_colar_cal.solicitar()

    def iniciar_auto_colar_cal(self, ativos: list[str] | None = None, params: dict | None = None):
        self._colar_cal_ativos = ativos
        self._colar_cal_params = params
        self._toggle_colar_cal.iniciar_auto()

    def parar_auto_colar_cal(self):
        self._toggle_colar_cal.parar_auto()

    def iniciar_auto_box(self):
        self._toggle_box.iniciar_auto()

    def parar_auto_box(self):
        self._toggle_box.parar_auto()

    def iniciar_auto_put_ratio(self):
        self._toggle_put_ratio.iniciar_auto()

    def parar_auto_put_ratio(self):
        self._toggle_put_ratio.parar_auto()

    def set_mostrar_tp_op(self, mostrar: bool):
        self._mostrar_tp_op = mostrar

    def _processar_monitor_geral(self, rtd):
        t6_inicio = time.time()
        dados_mercado = self._mercado_provider.capturar_dados_mercado()
        self._ultimo_dados_mercado = dados_mercado
        if not dados_mercado:
            return

        # Pré-processamento compartilhado: estruturas comuns a todos os consumers
        chaves = list(dados_mercado.keys())
        chaves_parsed = [tuple(k.split("|", 1)) for k in chaves]
        inst_repo = InstrumentoRepository(self.db_path)
        inst_map = inst_repo.get_all_mapped()

        resultados = self._monitor_uc.varrer(dados_mercado,
            inst_map=inst_map, chaves=chaves, chaves_parsed=chaves_parsed,
            pipeline_tracker=PipelineTracker())
        stale_trace.log_t6("monitor_geral_captura", time.time() - t6_inicio)

        if not self._mostrar_tp_op:
            resultados = [r for r in resultados
                          if not (hasattr(r, 'classificacao')
                                  and r.classificacao == 'TP.Op')]

        self.oportunidades_atualizadas.emit(resultados)
        stale_trace.log_t6("monitor_geral_oportunidades_emit", time.time() - t6_inicio)

        # Box/SBTH Vendido
        vendidas = self._monitor_vendidas_uc.varrer(dados_mercado,
            inst_map=inst_map, chaves=chaves, chaves_parsed=chaves_parsed,
            pipeline_tracker=PipelineTracker())
        stale_trace.log_t6("monitor_geral_vendidas_varrer", time.time() - t6_inicio)
        if not self._mostrar_tp_op:
            vendidas = [r for r in vendidas if r.viavel]
        self.oportunidades_vendidas_atualizadas.emit(vendidas)
        stale_trace.log_t6("monitor_geral_vendidas_emit", time.time() - t6_inicio)

        # Venda Coberta (Vendida + Comprada)
        coberta_vendida = self._monitor_coberta_uc.varrer(dados_mercado,
            inst_map=inst_map, chaves=chaves, chaves_parsed=chaves_parsed,
            pipeline_tracker=PipelineTracker())
        stale_trace.log_t6("monitor_geral_coberta_vendida", time.time() - t6_inicio)
        coberta_comprada = self._monitor_coberta_uc.varrer_comprada(dados_mercado,
            inst_map=inst_map, chaves=chaves, chaves_parsed=chaves_parsed)
        stale_trace.log_t6("monitor_geral_comprada", time.time() - t6_inicio)
        coberta = coberta_vendida + coberta_comprada
        if not self._mostrar_tp_op:
            coberta = [r for r in coberta if r.viavel]
        coberta.sort(key=lambda o: (not o.viavel, -o.pct_cdi))
        stale_trace.log_t6("monitor_geral_sort", time.time() - t6_inicio)
        self.oportunidades_coberta_atualizadas.emit(coberta)
        stale_trace.log_t6("monitor_geral_coberta_emit", time.time() - t6_inicio)

        self._snapshot_pipeline()
        stale_trace.log_t6("monitor_geral_snapshot", time.time() - t6_inicio)
        stale_trace.log_t6("monitor_geral_total", time.time() - t6_inicio)

    def _snapshot_pipeline(self):
        self._pipeline_monitor = getattr(self._monitor_uc, '_ultimo_pipeline', None)
        self._pipeline_vendidas = getattr(self._monitor_vendidas_uc, '_ultimo_pipeline', None)
        self._pipeline_coberta = getattr(self._monitor_coberta_uc, '_ultimo_pipeline', None)

    def _processar_colares(self, rtd):
        if not self._toggle_colar.deve_escanear():
            return

        t6_colar = time.time()
        dados_md = getattr(self, '_ultimo_dados_mercado', None)
        if not dados_md or len(dados_md) < 50:
            return
        tracker = PipelineTracker()
        resultados = self._monitor_colares_uc.varrer(None, dados_mercado=dados_md, pipeline_tracker=tracker)
        try:
            otimizadas = self._processar_otimizado(resultados, tipo_estrategia="Protetivo")
            if otimizadas:
                resultados.extend(otimizadas)
        except Exception:
            logger.exception("Erro pós-processamento otimizado colar")
        stale_trace.log_t6("COLAR_total", time.time() - t6_colar)
        self.colares_atualizados.emit(resultados)

    def _processar_colar_calendario(self, rtd):
        if not self._toggle_colar_cal.deve_escanear():
            return

        t6_cal = time.time()
        ativos = self._colar_cal_ativos
        params = self._colar_cal_params

        dados_md = getattr(self, '_ultimo_dados_mercado', None)
        tracker = PipelineTracker()
        resultados = self._monitor_colares_cal_uc.varrer(rtd, dados_md, params, ativos, pipeline_tracker=tracker)

        try:
            if resultados:
                otimizadas = self._processar_otimizado(resultados, pipeline_tracker=tracker)
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

        stale_trace.log_t6("COLAR_CAL_total", time.time() - t6_cal)
        self.colares_calendario_atualizados.emit(resultados)

    def _processar_otimizado(self, resultados: list, tipo_estrategia: str = "Calendario", pipeline_tracker: PipelineTracker | None = None) -> list:
        from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3
        from src.domain.services.calculadora_colar import ResultadoColar, TipoColar
        ui_results: list = []
        repo = HistoricoSimulacoesRepository(self.db_path)
        taxa_cdi = float(ParametroRepository(self.db_path).get_by_chave("taxa_cdi").valor)
        otimizado_desvios_sigma = self._ler_param_float("otimizado_desvios_sigma", 2.2)
        otimizado_sigma_rendimento = self._ler_param_float("otimizado_sigma_rendimento", 2.0)
        otimizado_ratio_put_min = self._ler_param_float("otimizado_ratio_put_min", 0.80)
        otimizado_ratio_max = self._ler_param_float("otimizado_ratio_max", 1.30)
        otimizado_ratio_put_step = self._ler_param_float("otimizado_ratio_put_step", 0.10)
        emol = self._ler_param_float("taxa_emolumento_pct", 0.00025)
        liq = self._ler_param_float("taxa_liquidacao_pct", 0.000275)
        ir = self._ler_param_float("taxa_ir_pct", 0.15)
        custos_b3_calc = CalculadoraCustosB3(emol, liq, ir)

        n_sigma_protecao = self._ler_param_float("n_sigma_protecao", 2.0)
        limite_protecao_pct = self._ler_param_float("limite_protecao_pct", 0.35)
        limite_protecao_pct_rendimento = self._ler_param_float("limite_protecao_pct_rendimento", 0.20)
        limite_protecao_pct_plato = self._ler_param_float("limite_protecao_pct_plato", 0.45)
        limite_protecao_pct_protecao = self._ler_param_float("limite_protecao_pct_protecao", 0.70)
        razao_convexidade_max = self._ler_param_float("razao_convexidade_max", 1.5)
        spread_maximo_pct = self._ler_param_float("spread_maximo_pct", 0.20)
        calda_preco_min_opcao = self._ler_param_float("calda_preco_min_opcao", 0.01)
        cab_minimo_protecao = int(self._ler_param_float("cab_minimo_protecao", 1))
        fator_seguranca_liquidez = self._ler_param_float("fator_seguranca_liquidez", 0.2)
        bwb_modo = self._ler_param_str("bwb_modo", "simples")

        c_entrada = len(resultados)
        c_nao_viavel = 0
        c_sem_variantes = 0
        c_variantes_geradas = 0
        c_filtro_cdi = 0
        c_montadas = 0

        for r in resultados:
            if not r.viavel:
                c_nao_viavel += 1
                continue
            if tipo_estrategia == "Calendario":
                if r.tipo != TipoColarCalendario.NEUTRO:
                    continue
                dte_call = r.dte_call
                dte_put = r.dte_put
                pnl_base = r.pnl_projetado
                cap_base = r.capital_empregado
            else:
                if r.tipo != TipoColar.TRADICIONAL:
                    continue
                dte_call = r.dias
                dte_put = r.dias
                pnl_base = r.preco_ativo * r.qtd_acao - r.custo_liquido
                cap_base = r.preco_compra * r.qtd_acao

            variantes = CalculadoraCaudaAssincrona.processar_otimizado(
                preco_ativo=r.preco_ativo,
                strike_call=r.strike_call,
                strike_put=r.strike_put,
                premio_call=r.premio_call,
                premio_put=r.premio_put,
                dte_call=dte_call,
                ativo=r.ativo,
                iv_call_pct=r.iv_call,
                pnl_projetado_base=pnl_base,
                capital_empregado_base=cap_base,
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
                dte_put=dte_put,
                qtd_acao=r.qtd_acao,
                vencimento_call=r.vencimento_call.isoformat() if getattr(r, 'vencimento_call', None) else None,
                vencimento_put=r.vencimento_put.isoformat() if getattr(r, 'vencimento_put', None) else None,
            )
            if not variantes:
                c_sem_variantes += 1
                continue

            premio_risco_chave = "premio_risco_colar_calendario" if tipo_estrategia == "Calendario" else "premio_risco_colar"
            premio_risco = self._ler_param_float(premio_risco_chave, 0.9)
            registros = []
            c_variantes_geradas += len(variantes)
            for v in variantes:
                if v.estagio != "Base" and v.pct_cdi_com_ratio < max(r.pct_cdi, premio_risco):
                    c_filtro_cdi += 1
                    continue

                candidatos_call, candidatos_put = self._resolver_strikes_protecao(
                    v, n_sigma_protecao, cab_minimo_protecao
                )

                protecao = CalculadoraProtecaoCauda.avaliar(
                    resultado=v,
                    strikes_call_candidatos=candidatos_call,
                    strikes_put_candidatos=candidatos_put,
                    qtd_acao=r.qtd_acao,
                    n_sigma=n_sigma_protecao,
                    limite_protecao_pct=limite_protecao_pct,
                    limite_protecao_pct_rendimento=limite_protecao_pct_rendimento,
                    limite_protecao_pct_plato=limite_protecao_pct_plato,
                    limite_protecao_pct_protecao=limite_protecao_pct_protecao,
                    razao_convexidade_max=razao_convexidade_max,
                    spread_maximo_pct=spread_maximo_pct,
                    taxa_cdi=taxa_cdi,
                    calda_preco_min_opcao=calda_preco_min_opcao,
                    cab_minimo=cab_minimo_protecao,
                    fator_seguranca_liquidez=fator_seguranca_liquidez,
                    pipeline_tracker=pipeline_tracker,
                    bwb_modo=bwb_modo,
                )

                if protecao is None:
                    protecao_campos = {
                        "lado_protegido": "nenhum",
                        "naked_call_frac": 0.0,
                        "naked_put_gap": 0.0,
                        "strike_protecao_call": None,
                        "strike_protecao_put": None,
                        "premio_ask_protecao_call": None,
                        "premio_ask_protecao_put": None,
                        "qtd_protecao_call": 0,
                        "qtd_protecao_put": 0,
                        "custo_protecao_call": 0.0,
                        "custo_protecao_put": 0.0,
                        "custo_protecao_total": 0.0,
                        "pnl_liquido_pos_protecao": 0.0,
                        "viavel": 0,
                        "strikes_bwb_call": None,
                        "strikes_bwb_put": None,
                        "premios_bwb_call": None,
                        "premios_bwb_put": None,
                        "custo_borboleta_call": 0.0,
                        "custo_borboleta_put": 0.0,
                        "lotes_bwb_call": 0,
                        "lotes_bwb_put": 0,
                        "razao_convexidade_call": 1.0,
                        "razao_convexidade_put": 1.0,
                        "cod_prot_call": None,
                        "cod_prot_put": None,
                        "premio_book_call": 0.0,
                        "premio_book_put": 0.0,
                        "score_ev": 0.0,
                        "score_ev_pct": 0.0,
                        "zonas_ev_json": None,
                    }
                else:
                    protecao_campos = {
                        "lado_protegido": protecao.lado_protegido,
                        "naked_call_frac": protecao.naked_call_frac,
                        "naked_put_gap": protecao.naked_put_gap,
                        "strike_protecao_call": protecao.strike_protecao_call,
                        "strike_protecao_put": protecao.strike_protecao_put,
                        "premio_ask_protecao_call": protecao.premio_ask_call,
                        "premio_ask_protecao_put": protecao.premio_ask_put,
                        "qtd_protecao_call": protecao.qtd_protecao_call,
                        "qtd_protecao_put": protecao.qtd_protecao_put,
                        "custo_protecao_call": protecao.custo_protecao_call,
                        "custo_protecao_put": protecao.custo_protecao_put,
                        "custo_protecao_total": protecao.custo_protecao_total,
                        "pnl_liquido_pos_protecao": protecao.pnl_liquido_pos_protecao if protecao.lado_protegido != "nenhum" else 0.0,
                        "viavel": 1 if protecao.viavel else 0,
                        "strikes_bwb_call": protecao.strikes_bwb_call,
                        "strikes_bwb_put": protecao.strikes_bwb_put,
                        "premios_bwb_call": protecao.premios_bwb_call,
                        "premios_bwb_put": protecao.premios_bwb_put,
                        "custo_borboleta_call": protecao.custo_borboleta_call,
                        "custo_borboleta_put": protecao.custo_borboleta_put,
                        "lotes_bwb_call": protecao.lotes_bwb_call,
                        "lotes_bwb_put": protecao.lotes_bwb_put,
                        "razao_convexidade_call": protecao.razao_convexidade_call,
                        "razao_convexidade_put": protecao.razao_convexidade_put,
                        "cod_prot_call": getattr(protecao, 'cod_prot_call', None),
                        "cod_prot_put": getattr(protecao, 'cod_prot_put', None),
                        "premio_book_call": getattr(protecao, 'premio_book_call', 0.0) or 0.0,
                        "premio_book_put": getattr(protecao, 'premio_book_put', 0.0) or 0.0,
                        "score_ev": protecao.score_ev,
                        "score_ev_pct": protecao.score_ev_pct,
                        "zonas_ev_json": protecao.zonas_ev_json,
                    }

                n = v.ratio_call
                m = v.ratio_put
                custo_b3_variante = (
                    custos_b3_calc.custos_opcao(r.premio_call, n_pernas=1, ida_e_volta=True) * n
                    + custos_b3_calc.custos_opcao(r.premio_put, n_pernas=1, ida_e_volta=True) * m
                    + custos_b3_calc.custos_stock(r.preco_compra or r.preco_ativo, n_acoes=r.qtd_acao)
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
                    "cod_call": getattr(r, 'cod_call', None) or getattr(r, 'codigo_call', None),
                    "cod_put": getattr(r, 'cod_put', None) or getattr(r, 'codigo_put', None),
                    "vencimento_call": (r.vencimento_call.isoformat() if hasattr(r, 'vencimento_call') and hasattr(r.vencimento_call, 'isoformat') else getattr(r, 'vencimento_call', None)),
                    "vencimento_put": (r.vencimento_put.isoformat() if hasattr(r, 'vencimento_put') and hasattr(r.vencimento_put, 'isoformat') else getattr(r, 'vencimento_put', None)),
                    "dte_put": getattr(r, 'dte_put', None),
                    "dte_extra": getattr(r, 'dte_extra', None),
                    "iv_put": getattr(r, 'iv_put', None),
                    "iv_rank_call": getattr(r, 'iv_rank_call', None),
                    "iv_rank_put": getattr(r, 'iv_rank_put', None),
                    "net_credito": getattr(r, 'net_credito', None),
                    "capital_empregado": getattr(r, 'capital_empregado', None),
                    "pnl_projetado": v.pnl_com_ratio,
                    "pct_retorno": getattr(r, 'pct_retorno', None),
                    "pct_cdi_liquido": getattr(r, 'pct_cdi_liquido', None),
                    "custo_b3": getattr(r, 'custo_b3', None),
                    "custo_ir": getattr(r, 'custo_ir', None),
                    "theta_liquido": getattr(r, 'theta_liquido', None),
                    "delta_total": getattr(r, 'delta_total', None),
                    "vega_liquido": getattr(r, 'vega_liquido', None),
                    "valor_put_venc_call": getattr(r, 'valor_put_venc_call', None),
                    "pop_upside": getattr(r, 'pop_upside', None),
                    "pop_downside": getattr(r, 'pop_downside', None),
                    "score": getattr(r, 'score', None),
                    "score_iv": getattr(r, 'score_iv', None),
                    "tipo_estrategia": tipo_estrategia,
                    "is_otimizado": 1,
                    **protecao_campos,
                })

                if v.estagio == "Base":
                    continue

                if tipo_estrategia == "Calendario":
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
                        custo_b3=round(custo_b3_variante, 4),
                        custo_ir=r.custo_ir,
                        pct_cdi_liquido=r.pct_cdi_liquido,
                        score=round(r.score, 4),
                        risco_max=r.risco_max,
                        iv_rank=r.iv_rank,
                        iv_rank_call=r.iv_rank_call,
                        iv_rank_put=r.iv_rank_put,
                        vega_call=r.vega_call,
                        vega_put=r.vega_put,
                        vega_liquido=r.vega_liquido,
                        gamma_call=r.gamma_call,
                        gamma_put=r.gamma_put,
                        score_iv=r.score_iv,
                        preco_compra=r.preco_compra,
                        be_baixa=v.breakeven_esquerdo,
                        be_alta=v.breakeven_direito,
                        be_baixa_intrinseco=r.be_baixa_intrinseco,
                        be_alta_intrinseco=r.be_alta_intrinseco,
                        ratio_call=v.ratio_call,
                        ratio_put=v.ratio_put,
                        is_otimizado=True,
                        estagio_otimizado=v.estagio,
                        detectado_em=r.detectado_em,
                        qtd_acao=r.qtd_acao,
                        qtd_call=r.qtd_call,
                        qtd_put=r.qtd_put,
                        lado_protegido=protecao_campos.get("lado_protegido"),
                        custo_protecao_total=protecao_campos.get("custo_protecao_total", 0.0),
                        pnl_liquido_pos_protecao=protecao_campos.get("pnl_liquido_pos_protecao", 0.0),
                        strike_protecao_call=protecao_campos.get("strike_protecao_call"),
                        strike_protecao_put=protecao_campos.get("strike_protecao_put"),
                        qtd_protecao_call=protecao_campos.get("qtd_protecao_call", 0),
                        qtd_protecao_put=protecao_campos.get("qtd_protecao_put", 0),
                        custo_protecao_call=protecao_campos.get("custo_protecao_call", 0.0),
                        custo_protecao_put=protecao_campos.get("custo_protecao_put", 0.0),
                        viavel_protecao=bool(protecao_campos.get("viavel", 0)),
                        strikes_bwb_call=protecao_campos.get("strikes_bwb_call"),
                        strikes_bwb_put=protecao_campos.get("strikes_bwb_put"),
                        premios_bwb_call=protecao_campos.get("premios_bwb_call"),
                        premios_bwb_put=protecao_campos.get("premios_bwb_put"),
                        custo_borboleta_call=protecao_campos.get("custo_borboleta_call", 0.0),
                        custo_borboleta_put=protecao_campos.get("custo_borboleta_put", 0.0),
                        lotes_bwb_call=protecao_campos.get("lotes_bwb_call", 0),
                        lotes_bwb_put=protecao_campos.get("lotes_bwb_put", 0),
                        score_ev=protecao_campos.get("score_ev", 0.0),
                        score_ev_pct=protecao_campos.get("score_ev_pct", 0.0),
                        zonas_ev_json=protecao_campos.get("zonas_ev_json"),
                    )
                else:
                    novo = ResultadoColar(
                        ativo=r.ativo,
                        vencimento=r.vencimento,
                        dias=r.dias,
                        strike_put=r.strike_put,
                        strike_call=r.strike_call,
                        cod_put=r.cod_put,
                        cod_call=r.cod_call,
                        preco_ativo=r.preco_ativo,
                        premio_put=r.premio_put,
                        premio_call=r.premio_call,
                        custo_liquido=r.custo_liquido,
                        pior_retorno=r.pior_retorno,
                        melhor_retorno=r.melhor_retorno,
                        pct_ganho=r.pct_ganho,
                        pct_cdi=v.pct_cdi_com_ratio,
                        pct_cdi_melhor=r.pct_cdi_melhor,
                        tipo=r.tipo,
                        risco_leilao=r.risco_leilao,
                        viavel=True,
                        em_leilao=r.em_leilao,
                        custo_b3=round(custo_b3_variante, 4),
                        custo_ir=r.custo_ir,
                        custo_ir_melhor=r.custo_ir_melhor,
                        pct_cdi_liquido=r.pct_cdi_liquido,
                        pct_cdi_melhor_liquido=r.pct_cdi_melhor_liquido,
                        preco_compra=r.preco_compra,
                        iv_call=r.iv_call,
                        iv_put=r.iv_put,
                        pop_upside=r.pop_upside,
                        pop_downside=r.pop_downside,
                        score=0.0,
                        detectado_em=r.detectado_em,
                        qtd_acao=r.qtd_acao,
                        qtd_call=r.qtd_call,
                        qtd_put=r.qtd_put,
                        is_otimizado=True,
                        estagio_otimizado=v.estagio,
                        ratio_call=v.ratio_call,
                        ratio_put=v.ratio_put,
                        id_chassi=v.id_chassi,
                    )
                ui_results.append(novo)
                c_montadas += 1

                if tipo_estrategia == "Calendario":
                    tail = None
                    try:
                        tail = self._selecionar_tail_protect(
                            ativo=r.ativo,
                            vencimento_call=r.vencimento_call.isoformat() if getattr(r, 'vencimento_call', None) else None,
                            vencimento_put=r.vencimento_put.isoformat() if getattr(r, 'vencimento_put', None) else None,
                            preco_ativo=r.preco_ativo,
                            iv_call=r.iv_call / 100.0 if r.iv_call and r.iv_call > 1 else r.iv_call,
                            iv_put=r.iv_put / 100.0 if r.iv_put and r.iv_put > 1 else r.iv_put,
                            ratio_call=v.ratio_call,
                            ratio_put=v.ratio_put,
                            premio_call=r.premio_call,
                            premio_put=r.premio_put,
                            qtd_acao=r.qtd_acao,
                            estagio=v.estagio,
                            dte_call=r.dte_call,
                            dte_put=r.dte_put if hasattr(r, 'dte_put') else r.dte_call + (r.dte_extra if hasattr(r, 'dte_extra') else 0),
                            r_cont=math.log(1 + taxa_cdi),
                        )
                    except Exception:
                        logger.debug("Tail protect fallback falhou para %s", r.ativo, exc_info=True)

                    if tail and (tail.get("call") or tail.get("put")):
                        custo_tail = (tail.get("call") or {}).get("custo_total", 0) + \
                                     (tail.get("put") or {}).get("custo_total", 0)
                        pnl_tail = v.pnl_com_ratio - custo_tail
                        cdi_per_tail = (1 + taxa_cdi) ** (dc_to_du(None, None, r.dte_call) / 252) - 1
                        cap_tail = abs(r.preco_ativo * r.qtd_acao + r.premio_put * r.qtd_acao * v.ratio_put - r.premio_call * r.qtd_acao * v.ratio_call)
                        cdi_tail = (pnl_tail / cap_tail) / cdi_per_tail if cdi_per_tail > 0 and cap_tail > 0 else 0.0

                        tail_call = tail.get("call") or {}
                        tail_put = tail.get("put") or {}

                        # Registro no banco
                        reg_tail = {
                            "id_chassi": v.id_chassi,
                            "estagio": v.estagio + " +Tail",
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
                            "pct_cdi": cdi_tail,
                            "qtd_acao": r.qtd_acao,
                            "premio_call": r.premio_call,
                            "premio_put": r.premio_put,
                            "preco_compra": r.preco_compra or r.preco_ativo,
                            "cod_call": getattr(r, 'cod_call', None),
                            "cod_put": getattr(r, 'cod_put', None),
                            "vencimento_call": str(r.vencimento_call) if getattr(r, 'vencimento_call', None) else None,
                            "vencimento_put": str(r.vencimento_put) if getattr(r, 'vencimento_put', None) else None,
                            "dte_put": getattr(r, 'dte_put', None),
                            "dte_extra": getattr(r, 'dte_extra', None),
                            "iv_put": getattr(r, 'iv_put', None),
                            "iv_rank_call": getattr(r, 'iv_rank_call', None),
                            "iv_rank_put": getattr(r, 'iv_rank_put', None),
                            "net_credito": getattr(r, 'net_credito', None),
                            "capital_empregado": cap_tail,
                            "pnl_projetado": pnl_tail,
                            "pct_retorno": getattr(r, 'pct_retorno', None),
                            "pct_cdi_liquido": getattr(r, 'pct_cdi_liquido', None),
                            "custo_b3": getattr(r, 'custo_b3', None),
                            "custo_ir": getattr(r, 'custo_ir', None),
                            "theta_liquido": getattr(r, 'theta_liquido', None),
                            "delta_total": getattr(r, 'delta_total', None),
                            "vega_liquido": getattr(r, 'vega_liquido', None),
                            "valor_put_venc_call": getattr(r, 'valor_put_venc_call', None),
                            "pop_upside": getattr(r, 'pop_upside', None),
                            "pop_downside": getattr(r, 'pop_downside', None),
                            "score": getattr(r, 'score', None),
                            "score_iv": getattr(r, 'score_iv', None),
                            "tipo_estrategia": tipo_estrategia,
                            "is_otimizado": 1,
                            "lado_protegido": "call" if tail_call else ("put" if tail_put else "nenhum"),
                            "naked_call_frac": max(0.0, v.ratio_call - 1.0),
                            "naked_put_gap": max(0.0, 1.0 - v.ratio_put),
                            "strike_protecao_call": tail_call.get("strike"),
                            "strike_protecao_put": tail_put.get("strike"),
                            "premio_ask_protecao_call": tail_call.get("premio_book"),
                            "premio_ask_protecao_put": tail_put.get("premio_book"),
                            "qtd_protecao_call": r.qtd_acao,
                            "qtd_protecao_put": r.qtd_acao,
                            "custo_protecao_call": tail_call.get("custo_total", 0.0),
                            "custo_protecao_put": tail_put.get("custo_total", 0.0),
                            "custo_protecao_total": custo_tail,
                            "pnl_liquido_pos_protecao": pnl_tail,
                            "viavel": 1,
                            "cod_prot_call": tail_call.get("codigo"),
                            "cod_prot_put": tail_put.get("codigo"),
                            "premio_book_call": tail_call.get("premio_book", 0.0),
                            "premio_book_put": tail_put.get("premio_book", 0.0),
                            "strikes_bwb_call": None,
                            "strikes_bwb_put": None,
                            "premios_bwb_call": None,
                            "premios_bwb_put": None,
                            "custo_borboleta_call": 0.0,
                            "custo_borboleta_put": 0.0,
                            "lotes_bwb_call": 0,
                            "lotes_bwb_put": 0,
                            "razao_convexidade_call": 1.0,
                            "razao_convexidade_put": 1.0,
                        }

                        ev_tail = {"score_ev": 0.0, "score_ev_pct": 0.0}
                        zonas_ev_json_tail = None
                        logger.debug("Tail E[PnL] iniciando para %s %s", v.ativo, v.estagio)
                        try:
                            prot_tail = ResultadoProtecaoCauda(
                                id_chassi=v.id_chassi,
                                ativo=v.ativo,
                                lado_protegido="call" if tail_call else ("put" if tail_put else "nenhum"),
                                naked_call_frac=max(0.0, v.ratio_call - 1.0),
                                naked_put_gap=max(0.0, 1.0 - v.ratio_put),
                                strike_protecao_call=tail_call.get("strike") if tail_call else None,
                                strike_protecao_put=tail_put.get("strike") if tail_put else None,
                                premio_ask_call=tail_call.get("premio_book") if tail_call else None,
                                premio_ask_put=tail_put.get("premio_book") if tail_put else None,
                                qtd_protecao_call=r.qtd_acao if tail_call else 0,
                                qtd_protecao_put=r.qtd_acao if tail_put else 0,
                                custo_protecao_call=tail_call.get("custo_total", 0.0) if tail_call else 0.0,
                                custo_protecao_put=tail_put.get("custo_total", 0.0) if tail_put else 0.0,
                                custo_protecao_total=custo_tail,
                                pnl_sem_protecao=v.pnl_com_ratio,
                                pnl_liquido_pos_protecao=pnl_tail,
                                viavel_call=bool(tail_call),
                                viavel_put=bool(tail_put),
                                viavel=bool(tail_call or tail_put),
                            )
                            ev_tail = CalculadoraProtecaoCauda._calcular_score_probabilistico(
                                resultado=v, protecao=prot_tail, qtd_acao=r.qtd_acao, taxa_cdi=taxa_cdi,
                            )
                            import json
                            zonas_ev_json_tail = json.dumps({
                                "p": [ev_tail.get("p_a", 0), ev_tail.get("p_b", 0), ev_tail.get("p_c", 0), ev_tail.get("p_d", 0)],
                                "ev": [ev_tail.get("ev_a", 0), ev_tail.get("ev_b", 0), ev_tail.get("ev_c", 0), ev_tail.get("ev_d", 0)],
                            })
                        except Exception:
                            logger.exception("Erro ao calcular E[PnL] para Tail")
                            pass

                        reg_tail["score_ev"] = ev_tail.get("score_ev", 0.0)
                        reg_tail["score_ev_pct"] = ev_tail.get("score_ev_pct", 0.0)
                        reg_tail["zonas_ev_json"] = zonas_ev_json_tail
                        registros.append(reg_tail)

                        # Variante na UI
                        novo_tail = ResultadoColarCalendario(
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
                            pnl_projetado=round(pnl_tail, 4),
                            capital_empregado=cap_tail,
                            pct_retorno=0.0,
                            pct_cdi=cdi_tail,
                            delta_total=r.delta_total,
                            theta_call=r.theta_call,
                            theta_put=r.theta_put,
                            theta_liquido=r.theta_liquido,
                            viavel=True,
                            tipo=r.tipo,
                            r=taxa_cdi,
                            custo_b3=round(custo_b3_variante, 4),
                            custo_ir=r.custo_ir,
                            pct_cdi_liquido=r.pct_cdi_liquido,
                            score=round(r.score, 4),
                            risco_max=r.risco_max,
                            iv_rank=r.iv_rank,
                            iv_rank_call=r.iv_rank_call,
                            iv_rank_put=r.iv_rank_put,
                            vega_call=r.vega_call,
                            vega_put=r.vega_put,
                            vega_liquido=r.vega_liquido,
                            gamma_call=r.gamma_call,
                            gamma_put=r.gamma_put,
                            score_iv=r.score_iv,
                            preco_compra=r.preco_compra,
                            be_baixa=r.be_baixa,
                            be_alta=r.be_alta,
                            be_baixa_intrinseco=r.be_baixa_intrinseco,
                            be_alta_intrinseco=r.be_alta_intrinseco,
                            ratio_call=v.ratio_call,
                            ratio_put=v.ratio_put,
                            is_otimizado=True,
                            estagio_otimizado=v.estagio + " +Tail",
                            detectado_em=r.detectado_em,
                            qtd_acao=r.qtd_acao,
                            qtd_call=r.qtd_call,
                            qtd_put=r.qtd_put,
                            cod_prot_call=tail_call.get("codigo"),
                            cod_prot_put=tail_put.get("codigo"),
                            premio_book_call=tail_call.get("premio_book", 0.0),
                            premio_book_put=tail_put.get("premio_book", 0.0),
                            strike_protecao_call=tail_call.get("strike"),
                            strike_protecao_put=tail_put.get("strike"),
                            custo_protecao_call=tail_call.get("custo_total", 0.0),
                            custo_protecao_put=tail_put.get("custo_total", 0.0),
                            custo_protecao_total=custo_tail,
                            pnl_liquido_pos_protecao=pnl_tail,
                            lado_protegido="call" if tail_call else ("put" if tail_put else "nenhum"),
                            viavel_protecao=True,
                            qtd_protecao_call=r.qtd_acao if tail_call else 0,
                            qtd_protecao_put=r.qtd_acao if tail_put else 0,
                            score_ev=ev_tail.get("score_ev", 0.0),
                            score_ev_pct=ev_tail.get("score_ev_pct", 0.0),
                            zonas_ev_json=zonas_ev_json_tail,
                        )
                        ui_results.append(novo_tail)
                        c_montadas += 1

            if registros:
                repo.salvar_lote(registros)

        if pipeline_tracker is not None:
            pipeline_tracker.add_stage(
                "14a. Entrada (viáveis do varrer)",
                c_entrada, c_entrada - c_nao_viavel,
                f"{c_nao_viavel} já marcadas como inviáveis"
            )
            entrou_otim = c_entrada - c_nao_viavel
            pipeline_tracker.add_stage(
                "14b. Entrada otimização (todos os viáveis)",
                c_entrada, entrou_otim,
                f"{entrou_otim} collares elegíveis"
            )
            msg_stress = "ok" if c_sem_variantes == 0 else f"{c_sem_variantes} reprovadas: PnL negativo a ±{otimizado_desvios_sigma}σ"
            pipeline_tracker.add_stage(
                "14c. Stress ±2.2σ (PnL > 0 nos extremos)",
                entrou_otim, entrou_otim - c_sem_variantes,
                msg_stress
            )
            pipeline_tracker.add_stage(
                "14d. Piso de CDI (variantes não-Base)",
                c_variantes_geradas, c_variantes_geradas - c_filtro_cdi,
                f"{c_filtro_cdi} descartadas: %CDI abaixo do mínimo exigido" if c_filtro_cdi else "todas passaram"
            )
            pipeline_tracker.add_stage(
                "14e. Montagem final (→ tabela)",
                c_variantes_geradas - c_filtro_cdi, c_montadas,
                f"{c_montadas} variantes emitidas" if c_montadas else "nenhuma montada"
            )

        return ui_results

    def _processar_box_4p(self, rtd):
        if not self._toggle_box.deve_escanear(db_reader=self._ler_param_int):
            return

        t6_box = time.time()
        tracker = PipelineTracker()
        resultados = self._monitor_box_uc.varrer(rtd, pipeline_tracker=tracker)
        stale_trace.log_t6("BOX4P_varrer", time.time() - t6_box)
        resultados = self._monitor_box_uc.confirmar_resultados(rtd, resultados)
        stale_trace.log_t6("BOX4P_total", time.time() - t6_box)
        self.boxes_atualizados.emit(resultados)

    def _processar_put_ratio(self, rtd):
        if not self._toggle_put_ratio.deve_escanear():
            return

        t6_pr = time.time()
        tracker = PipelineTracker()
        resultados = self._monitor_put_ratio_uc.varrer(rtd, pipeline_tracker=tracker)
        stale_trace.log_t6("PUT_RATIO_varrer", time.time() - t6_pr)
        resultados = self._monitor_put_ratio_uc.confirmar_resultados(rtd, resultados)
        stale_trace.log_t6("PUT_RATIO_total", time.time() - t6_pr)
        self.put_ratio_atualizados.emit(resultados)

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

    def _subscrever_futuros(self, rtd):
        from datetime import date
        from src.domain.services.market_data_source import FieldName
        if not hasattr(rtd, 'registrar_topico'):
            return
        hoje = date.today()
        a, m = hoje.year, hoje.month
        _mc = {1:"F",2:"G",3:"H",4:"J",5:"K",6:"M",7:"N",8:"Q",9:"U",10:"V",11:"X",12:"Z"}
        extras = ["IBOV", "PETR4"]
        for pref in ("WIN","WDO","BCT","IOF"):
            extras.append(pref.lower())
            for am in ((a,m),(a+1 if m==12 else a,1 if m==12 else m+1)):
                extras.append(f"{pref.lower()}{_mc[am[1]].lower()}{str(am[0])[-2:]}")
        for cod in extras:
            for f in (FieldName.LAST_PRICE, FieldName.BID, FieldName.ASK):
                rtd.registrar_topico(cod, f)
        logger.info("Subscrição futuros+IBOV+PETR4 enviada: %s", extras)

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
            t6_mpp = time.time()
            resultados_box, recomendacoes = self._monitor_mpp_uc.calcular_instantaneo(rtd)
            stale_trace.log_t6("MPP_calcular", time.time() - t6_mpp)
            self.mpp_atualizados.emit(resultados_box)
            self.mre_atualizados.emit(recomendacoes)
        except Exception as e:
            logger.error(f"Erro no MPP: {e}")

    def _resolver_strikes_protecao(self, resultado: ResultadoCaudaAssincrona, n_sigma: float,
                                     cab_minimo: int) -> tuple[list[dict], list[dict]]:
        s_target_call = resultado.preco_ativo * (1.0 + n_sigma * resultado.sigma_periodo)
        s_target_put = resultado.preco_ativo * (1.0 - n_sigma * resultado.sigma_periodo)

        from src.domain.services.market_data_source import FieldName
        from src.infrastructure.persistence.database import get_connection

        source = self._mercado_provider.source if self._mercado_provider else None
        fonte = self._ler_param_str("fonte_market_data", "profit")
        eh_openfast = fonte == "openfast"

        conn = get_connection(self.db_path)
        try:
            venc_call = getattr(resultado, 'vencimento_call', None)
            venc_put = getattr(resultado, 'vencimento_put', None)

            if venc_call:
                rows_call = conn.execute(
                    "SELECT cod_call FROM instrumentos_base WHERE ativo = ? AND vencimento = ?",
                    (resultado.ativo, venc_call)
                ).fetchall()
            else:
                rows_call = conn.execute(
                    "SELECT cod_call FROM instrumentos_base WHERE ativo = ?",
                    (resultado.ativo,)
                ).fetchall()

            if venc_put:
                rows_put = conn.execute(
                    "SELECT cod_put FROM instrumentos_base WHERE ativo = ? AND vencimento = ?",
                    (resultado.ativo, venc_put)
                ).fetchall()
            else:
                rows_put = conn.execute(
                    "SELECT cod_put FROM instrumentos_base WHERE ativo = ?",
                    (resultado.ativo,)
                ).fetchall()
        finally:
            conn.close()

        codigos_call = set()
        codigos_put = set()
        for row in rows_call:
            if row["cod_call"]:
                codigos_call.add(row["cod_call"])
        for row in rows_put:
            if row["cod_put"]:
                codigos_put.add(row["cod_put"])

        if source and source.disponivel:
            for cod in codigos_call | codigos_put:
                source.registrar_topico(cod, FieldName.STRIKE)
                source.registrar_topico(cod, FieldName.ASK)
                source.registrar_topico(cod, FieldName.BID)
                source.registrar_topico(cod, FieldName.VOL_ASK)
                source.registrar_topico(cod, FieldName.VOL_BID)
            if eh_openfast:
                bwb_key = (resultado.ativo, getattr(resultado, 'vencimento_call', ''))
                if not hasattr(self, '_bwb_pre_registered'):
                    self._bwb_pre_registered: set[tuple] = set()
                if bwb_key not in self._bwb_pre_registered:
                    logger.info("BWB: %d call + %d put codes registrados, aguardando push...",
                                len(codigos_call), len(codigos_put))
                    time.sleep(2.0)
                    self._bwb_pre_registered.add(bwb_key)
                com_strike = com_ask = com_vol = 0
                total = len(codigos_call) + len(codigos_put)
                for cod in codigos_call | codigos_put:
                    s = source.ler_campo_cache(cod, FieldName.STRIKE)
                    a = source.ler_campo_cache(cod, FieldName.ASK)
                    va = source.ler_campo_cache(cod, FieldName.VOL_ASK)
                    if s and s > 0:
                        com_strike += 1
                    if a and a > 0:
                        com_ask += 1
                    if va and va > 0:
                        com_vol += 1
                logger.info("BWB: strike=%d/%d ask=%d/%d vol=%d/%d apos espera",
                            com_strike, total, com_ask, total, com_vol, total)

        def _coletar_lado(codigos: set[str], strike_filtro, campos_dados, eh_call: bool) -> list[dict]:
            lado = "call" if eh_call else "put"
            n_total = len(codigos)
            n_com_strike_ask = 0
            n_na_direcao = 0
            candidatos = []
            for cod in sorted(codigos):
                strike = 0.0
                ask = 0.0
                vol_ask = 0
                vol_bid = 0
                if source and source.disponivel and hasattr(source, "ler_campos"):
                    try:
                        dados = source.ler_campos(cod, FieldName.STRIKE, FieldName.ASK,
                                                   FieldName.BID,
                                                   FieldName.VOL_ASK, FieldName.VOL_BID,
                                                   FieldName.BOOK_HEADER) or {}
                    except Exception:
                        dados = {}
                    strike = dados.get(FieldName.STRIKE) or 0.0
                    ask = dados.get(FieldName.ASK) or 0.0
                    bid = dados.get(FieldName.BID) or 0.0
                    vol_ask = dados.get(FieldName.VOL_ASK) or 0
                    vol_bid = dados.get(FieldName.VOL_BID) or 0
                if not strike or strike <= 0 or ask <= 0:
                    continue
                n_com_strike_ask += 1
                if eh_call and strike < s_target_call:
                    continue
                if not eh_call and strike > s_target_put:
                    continue
                n_na_direcao += 1
                if eh_openfast:
                    if vol_ask <= 0 and vol_bid <= 0:
                        vol_ask = 1
                        vol_bid = 1
                    cab = vol_ask
                else:
                    cab = max(vol_ask, 0)
                if cab < cab_minimo:
                    logger.debug("BWB _coletar [%s]: %s K=%.2f descartado cab=%d < min=%d [va=%d vb=%d]",
                                 lado, cod, strike, cab, cab_minimo, vol_ask, vol_bid)
                    continue
                candidatos.append({
                    "strike": strike,
                    "premio_ask": ask,
                    "premio_bid": bid,
                    "vol_ask": vol_ask,
                    "vol_bid": vol_bid,
                })
            logger.info("BWB _coletar [%s]: total=%d strike+ask=%d direcao=%d final=%d target=%.2f",
                        lado, n_total, n_com_strike_ask, n_na_direcao, len(candidatos),
                        s_target_call if eh_call else s_target_put)
            return candidatos

        calls = _coletar_lado(codigos_call, s_target_call, {}, True)
        calls.sort(key=lambda x: x["strike"])
        puts = _coletar_lado(codigos_put, s_target_put, {}, False)
        puts.sort(key=lambda x: x["strike"], reverse=True)

        return calls[:15], puts[:15]

    def _selecionar_tail_protect(self, ativo: str, vencimento_call: str, vencimento_put: str,
                                  preco_ativo: float, iv_call: float, iv_put: float,
                                  ratio_call: float, ratio_put: float,
                                  premio_call: float, premio_put: float,
                                  qtd_acao: int, estagio: str,
                                  dte_call: int, dte_put: int,
                                  r_cont: float) -> dict:
        resultado = {"call": None, "put": None}

        if ratio_call <= 1.0 and ratio_put >= 1.0:
            return resultado

        extra = (ratio_call - 1.0) * qtd_acao * premio_call if ratio_call > 1.0 else 0.0
        extra_put = (1.0 - ratio_put) * qtd_acao * premio_put if ratio_put < 1.0 else 0.0

        pct = 0.40
        orcamento = extra * pct
        orcamento_put = extra_put * pct

        from src.domain.services.market_data_source import FieldName
        from src.infrastructure.persistence.database import get_connection

        source = self._mercado_provider.source if self._mercado_provider else None
        if not source or not source.disponivel:
            return resultado

        conn = get_connection(self.db_path)
        try:
            rows_call = conn.execute(
                "SELECT cod_call FROM instrumentos_base WHERE ativo = ? AND vencimento = ?",
                (ativo, vencimento_call)
            ).fetchall() if vencimento_call and ratio_call > 1.0 else []
            rows_put = conn.execute(
                "SELECT cod_put FROM instrumentos_base WHERE ativo = ? AND vencimento = ?",
                (ativo, vencimento_put)
            ).fetchall() if vencimento_put and ratio_put < 1.0 else []
        finally:
            conn.close()

        todos_codigos = set()
        for row in rows_call:
            if row["cod_call"]:
                todos_codigos.add(row["cod_call"])
        for row in rows_put:
            if row["cod_put"]:
                todos_codigos.add(row["cod_put"])

        if not todos_codigos:
            return resultado

        for cod in todos_codigos:
            source.registrar_topico(cod, FieldName.STRIKE)
            source.registrar_topico(cod, FieldName.ASK)
            source.registrar_topico(cod, FieldName.VOL_ASK)
            source.registrar_topico(cod, FieldName.VOL_BID)

        fonte = self._ler_param_str("fonte_market_data", "profit")
        if fonte == "openfast":
            import time
            time.sleep(2.0)

        source.refresh(3000)

        for codigo, eh_call, orc, iv, dte, rows in [
            ("call", True, orcamento, iv_call, dte_call, rows_call),
            ("put", False, orcamento_put, iv_put, dte_put, rows_put),
        ]:
            if orc <= 0:
                continue

            candidatos = []
            for row in rows:
                cod = row["cod_call"] if eh_call else row["cod_put"]
                if not cod:
                    continue
                try:
                    dados = source.ler_campos(cod, FieldName.STRIKE, FieldName.ASK) or {}
                except Exception:
                    continue
                strike = dados.get(FieldName.STRIKE) or 0.0
                ask = dados.get(FieldName.ASK) or 0.0
                if not strike or strike <= 0 or ask <= 0:
                    continue
                if eh_call and strike <= preco_ativo:
                    continue
                if not eh_call and strike >= preco_ativo:
                    continue
                if ask * qtd_acao > orc * 1.5:
                    continue
                s_tail = preco_ativo * (1.30 if eh_call else 0.70)
                payoff = max(s_tail - strike, 0) if eh_call else max(strike - s_tail, 0)
                candidatos.append({
                    "codigo": cod, "strike": strike, "ask": ask,
                    "custo_total": ask * qtd_acao,
                    "payoff": payoff,
                    "score": payoff / ask if ask > 0 else 0,
                })

            if not candidatos:
                continue

            melhor = max(candidatos, key=lambda c: c["score"])

            label = "call" if eh_call else "put"
            resultado[label] = {
                "codigo": melhor["codigo"],
                "strike": round(melhor["strike"], 2),
                "premio_book": round(melhor["ask"], 4),
                "custo_total": round(melhor["custo_total"], 2),
                "score": round(melhor["score"], 2),
                "payoff": round(melhor["payoff"], 4),
            }

        return resultado

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


