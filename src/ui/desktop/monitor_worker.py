import logging
import time
import os
import psutil

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.application.use_cases.monitor_colares import MonitorColaresUseCase
from src.application.use_cases.monitor_colares_calendario import MonitorColaresCalendarioUseCase
from src.application.use_cases.monitor_box import MonitorBoxUseCase
from src.application.use_cases.mpp_use_case import MPPUseCase
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.domain.services.market_data_source import criar_data_source, MarketDataSource
from src.application.dtos.dtos import EngineStatsDTO

logger = logging.getLogger()


class MonitorWorker(QThread):
    oportunidades_atualizadas = Signal(list)
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
        fonte = self._ler_param_int("fonte_market_data", 0)
        usa_com = (fonte != 1)
        if usa_com:
            try:
                import pythoncom
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                com_initialized = True
                logger.info("COM inicializado para fonte de dados.")
            except ImportError:
                logger.warning("MonitorWorker: pythoncom não disponível. Thread rodará sem COM.")
                self.status_message.emit("Aviso: pythoncom ausente. RTD indisponível.")

        fonte_nome = "Open Fast Socket" if fonte == 1 else "Profit RTD"
        logger.info("MonitorWorker: iniciando fonte de dados: %s", fonte_nome)

        rtd = self._rtd_main
        if not rtd or not getattr(rtd, 'disponivel', False):
            rtd = criar_data_source("openfast" if fonte == 1 else "profit")
            if fonte == 1:
                delay_ms = self._ler_param_int("openfast_send_delay_ms", 1)
                rtd._send_delay_s = max(0.0, delay_ms / 1000.0)
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

    def recarregar_parametros(self):
        self._monitor_uc.recarregar_parametros()
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
            self.colares_calendario_atualizados.emit(resultados)

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

        # A cada ~60 min (144 ciclos de manutencao * 25s ≈ 3600s)
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


