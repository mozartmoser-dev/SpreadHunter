import logging
import time
import os
import psutil

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.application.use_cases.monitor_colares import MonitorColaresUseCase
from src.application.use_cases.monitor_colares_calendario import MonitorColaresCalendarioUseCase
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.application.dtos.dtos import EngineStatsDTO

logger = logging.getLogger(__name__)


class MonitorWorker(QThread):
    oportunidades_atualizadas = pyqtSignal(list)
    status_message = pyqtSignal(str)
    rtd_status = pyqtSignal(bool)
    engine_stats_updated = pyqtSignal(object)
    colares_atualizados = pyqtSignal(list)
    colares_calendario_atualizados = pyqtSignal(list)

    def __init__(self, db_path: str, rtd: RTDProfit, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self._rtd_main = rtd
        self._mercado_provider = None
        self._monitor_uc = MonitorOportunidadesUseCase(db_path)
        self._monitor_colares_uc = MonitorColaresUseCase(db_path)
        self._monitor_colares_cal_uc = MonitorColaresCalendarioUseCase(db_path)
        self._running = False
        self._paused = False
        self._interval_ms = 2500
        self._mostrar_tp_op = False
        self._colar_cycle = 0
        self._colar_interval = 24
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

        # Nível 2: Forca refresh RTD para ativos ex-dividendo do dia
        self._verificar_e_forcar_refresh_ex_dividendo()

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

                # Varredura de Colares (auto a cada ~60s quando ativado, ou sob demanda)
                forcar = False
                self._colar_mutex.lock()
                if self._forcar_colar:
                    forcar = True
                    self._forcar_colar = False
                colar_auto = self._colar_auto
                self._colar_mutex.unlock()

                deve_escanear = forcar
                if colar_auto:
                    self._colar_cycle += 1
                    if self._colar_cycle >= self._colar_interval:
                        deve_escanear = True
                        self._colar_cycle = 0

                if deve_escanear:
                    try:
                        self.status_message.emit("🔄 Varredura de colares em andamento...")
                        colar_results = self._monitor_colares_uc.varrer(rtd)
                        n = len(colar_results)
                        self.status_message.emit(f"✅ Colares: {n} viáveis" if n else "✅ Colares: nenhum viável no momento")
                        self.colares_atualizados.emit(colar_results)
                    except Exception as e:
                        logger.error("Colar scan error: %s", e)

                # Varredura de Collar Calendário
                forcar_cal = False
                colar_cal_ativos: list[str] | None = None
                colar_cal_params: dict | None = None
                self._colar_cal_mutex.lock()
                if self._forcar_colar_cal:
                    forcar_cal = True
                    self._forcar_colar_cal = False
                colar_cal_auto = self._colar_cal_auto
                colar_cal_ativos = self._colar_cal_ativos
                colar_cal_params = self._colar_cal_params
                self._colar_cal_mutex.unlock()

                deve_escanear_cal = forcar_cal
                if colar_cal_auto:
                    self._colar_cal_cycle += 1
                    if self._colar_cal_cycle >= self._colar_cal_interval:
                        deve_escanear_cal = True
                        self._colar_cal_cycle = 0

                if deve_escanear_cal:
                    try:
                        self.status_message.emit("🔄 Varredura de collar calendario...")
                        cal_results = self._monitor_colares_cal_uc.varrer(rtd, params=colar_cal_params, ativos=colar_cal_ativos)
                        n = len(cal_results)
                        self.status_message.emit(f"✅ Collar Cal: {n} viaveis" if n else "✅ Collar Cal: nenhum viavel")
                        self.colares_calendario_atualizados.emit(cal_results)
                    except Exception as e:
                        logger.error("Collar Cal scan error: %s", e)

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
        self._monitor_colares_uc.recarregar_parametros()
        self._monitor_colares_cal_uc.recarregar_parametros()
        if self._mercado_provider:
            self._mercado_provider.recarregar_parametros()

    def recarregar_instrumentos(self):
        from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
        InstrumentoRepository.invalidate_cache()
        if self._mercado_provider:
            self._mercado_provider.recarregar_instrumentos()

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
        self._colar_cal_cycle = 0
        self._colar_cal_mutex.unlock()

    def set_mostrar_tp_op(self, mostrar: bool):
        self._mostrar_tp_op = mostrar

    def _verificar_e_forcar_refresh_ex_dividendo(self):
        """Nível 2: Verifica ativos ex-dividendo do dia e força refresh RTD."""
        try:
            from src.infrastructure.persistence.repositories.repositories import DividendoRepository
            from datetime import date

            div_repo = DividendoRepository(self.db_path)
            divs_hoje = div_repo.get_ex_hoje()

            if divs_hoje:
                ativos_ex = list(set(d["ativo"] for d in divs_hoje))
                self.status_message.emit(
                    f"⚠️ Dia ex de dividendo: {', '.join(ativos_ex)} — Forcando refresh RTD..."
                )
                self._mercado_provider.forcar_refresh_ex_dividendo(ativos_ex)
                self.status_message.emit("Refresh RTD ex-dividendo concluído.")
            else:
                logger.info("Nenhum ativo ex-dividendo detectado hoje.")
        except Exception as e:
            logger.warning("Erro ao verificar ex-dividendo: %s", e)
