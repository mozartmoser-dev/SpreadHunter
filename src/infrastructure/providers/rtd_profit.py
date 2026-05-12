import logging
from typing import Optional

from src.infrastructure.providers.rtd_config import RTD_SERVIDOR, rtd_topico

logger = logging.getLogger(__name__)


class RTDProfit:
    def __init__(self):
        self.disponivel = False
        self._rtd = None
        self._topic_counter = 1000
        self._topic_map: dict[str, int] = {}
        self._conectar()

    def _conectar(self):
        try:
            import win32com.client
            import win32com.server.util

            srv = win32com.client.Dispatch(RTD_SERVIDOR)

            class _RTDCallback:
                _public_methods_ = ["UpdateNotify"]
                def UpdateNotify(self): pass

            iniciado = False
            for tentativa, cb in enumerate([
                win32com.server.util.wrap(_RTDCallback()),
                None,
            ]):
                try:
                    srv.ServerStart(cb)
                    iniciado = True
                    logger.info("RTD ServerStart OK (tentativa %d)", tentativa + 1)
                    break
                except Exception:
                    pass

            if not iniciado:
                logger.debug("RTD ServerStart falhou — tentando ConnectData mesmo assim.")

            self._rtd = srv
            self.disponivel = True
            logger.info("RTD do Profit Pro disponivel.")
        except ImportError:
            logger.warning("pywin32 nao instalado — rodando sem RTD.")
        except Exception as e:
            logger.warning("RTD indisponivel: %s", e)

    def _topic_id(self, codigo: str, campo: str) -> int:
        chave = "{}|{}".format(codigo, campo)
        if chave not in self._topic_map:
            self._topic_counter += 1
            self._topic_map[chave] = self._topic_counter
        return self._topic_map[chave]

    def ler_campo(self, codigo: str, campo: str) -> Optional[float]:
        if not self.disponivel or self._rtd is None:
            return None
        try:
            topico = rtd_topico(codigo)
            tid = self._topic_id(codigo, campo)
            resultado = self._rtd.ConnectData(tid, [topico, campo], False)
            valor = resultado[0] if isinstance(resultado, tuple) else resultado
            logger.debug("RTD ConnectData(%s, [%s, %s]) = %s", tid, topico, campo, valor)
            if valor is None:
                return None
            v = float(str(valor).replace(",", "."))
            return v if v > 0 else None
        except Exception as e:
            logger.debug("RTD erro ConnectData(%s, [%s, %s]): %s", tid, topico, campo, e)
            return None

    def ler_status(self, codigo: str) -> str:
        if not self.disponivel or self._rtd is None:
            return ""
        try:
            tid = self._topic_id(codigo, "EST")
            resultado = self._rtd.ConnectData(tid, [codigo, "EST"], False)
            valor = resultado[0] if isinstance(resultado, tuple) else resultado
            if valor is None:
                return ""
            return str(valor).strip()
        except Exception:
            return ""

    def desconectar(self):
        if not self.disponivel or self._rtd is None:
            return
        try:
            for tid in self._topic_map.values():
                self._rtd.DisconnectData(tid)
        except Exception:
            pass
