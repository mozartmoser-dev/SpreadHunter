import logging
import time
import os
import psutil

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.application.dtos.dtos import EngineStatsDTO

logger = logging.getLogger(__name__)


class MonitorWorker(QThread):
    oportunidades_atualizadas = pyqtSignal(list)
    status_message = pyqtSignal(str)
    rtd_status = pyqtSignal(bool)
    engine_stats_updated = pyqtSignal(object)

    def __init__(self, db_path: str, rtd: RTDProfit, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._rtd_main = rtd
        self._mercado_provider = None
        self._monitor_uc = MonitorOportunidadesUseCase(db_path)
        self._running = False
        self._paused = False
        self._interval_ms = 2500
        self._mostrar_tp_op = False
        self._mutex = QMutex()
        self._wait_condition = QWaitCondition()

    def run(self):
        com_initialized = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_initialized = True
        except ImportError:
            logger.warning("MonitorWorker: pythoncom não disponível. Thread rodará sem inicializar COM.")
            self.status_message.emit("Aviso: pythoncom ausente. RTD indisponível.")

        rtd = self._rtd_main
        if not rtd or not rtd.disponivel:
            rtd = RTDProfit()
        self._mercado_provider = MercadoDataProvider(self.db_path, rtd)
        self.rtd_status.emit(rtd.disponivel)

        self._running = True
        logger.info("MonitorWorker: thread iniciada (COM inicializado).")

        while self._running:
            if self._paused:
                self._mutex.lock()
                self._wait_condition.wait(self._mutex)
                self._mutex.unlock()
                if not self._running:
                    break

            try:
                t_start_cycle = time.perf_counter()
                dados_mercado = {}
                if rtd.disponivel:
                    dados_mercado = self._mercado_provider.capturar_dados_mercado()

                resultados = self._monitor_uc.varrer(dados_mercado)
                if not self._mostrar_tp_op:
                    resultados = [r for r in resultados if r.classificacao != "TP.Op"]
                self.oportunidades_atualizadas.emit(resultados)

                viaveis = sum(1 for r in resultados if r.viavel)
                self.status_message.emit(
                    "Varredura: {} oportunidades, {} viaveis".format(len(resultados), viaveis)
                )

                # Coleta Estatísticas do Motor
                t_end = time.perf_counter()
                scan_ms = int((t_end - t_start_cycle) * 1000)
                
                process = psutil.Process(os.getpid())
                cpu_pct = psutil.cpu_percent() # Simplificado
                mem_mb = process.memory_info().rss / 1024 / 1024
                
                e_stats = self._mercado_provider.get_engine_stats()
                
                stats_dto = EngineStatsDTO(
                    scan_time_ms=scan_ms,
                    cpu_pct=cpu_pct,
                    mem_mb=mem_mb,
                    total_instrumentos=e_stats["total"],
                    monitored_onda1=e_stats["onda1"],
                    monitored_onda2=e_stats["onda2"],
                    registrado=e_stats.get("registrado", False),
                    progresso_idx=e_stats.get("progresso_idx", 0)
                )
                self.engine_stats_updated.emit(stats_dto)
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

    def recarregar_parametros(self):
        self._monitor_uc.recarregar_parametros()
        if self._mercado_provider:
            self._mercado_provider.recarregar_parametros()

    def recarregar_instrumentos(self):
        from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
        InstrumentoRepository.invalidate_cache()
        if self._mercado_provider:
            self._mercado_provider.recarregar_instrumentos()

    def set_mostrar_tp_op(self, mostrar: bool):
        self._mostrar_tp_op = mostrar
