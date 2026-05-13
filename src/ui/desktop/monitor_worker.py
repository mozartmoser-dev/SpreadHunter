import logging

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.infrastructure.providers.rtd_profit import RTDProfit

logger = logging.getLogger(__name__)


class MonitorWorker(QThread):
    oportunidades_atualizadas = pyqtSignal(list)
    status_message = pyqtSignal(str)
    rtd_status = pyqtSignal(bool)

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
        import pythoncom
        pythoncom.CoInitialize()

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
            except Exception as e:
                logger.error("MonitorWorker: erro na varredura: %s", e)
                self.status_message.emit("Erro na varredura: {}".format(str(e)))

            self.msleep(self._interval_ms)

        rtd.desconectar()
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

    def set_mostrar_tp_op(self, mostrar: bool):
        self._mostrar_tp_op = mostrar
