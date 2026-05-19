import logging
from typing import Optional

from src.infrastructure.providers.rtd_config import RTD_SERVIDOR, rtd_topico

logger = logging.getLogger(__name__)


class RTDProfit:
    def __init__(self):
        self.disponivel = False
        self._rtd = None
        import random
        # Começa com um número dinâmico e aleatório alto para evitar colisão de IDs 
        # de tópicos com execuções anteriores que possam ter ficado ativas no servidor RTD do Profit
        self._topic_counter = random.randint(100000, 20000000)
        self._topic_map: dict[str, int] = {}
        self._topic_reverse: dict[int, str] = {}
        self._valores: dict[int, object] = {}
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
            tid = self._topic_counter
            self._topic_map[chave] = tid
            self._topic_reverse[tid] = chave
        return self._topic_map[chave]

    def registrar_topico(self, codigo: str, campo: str) -> int:
        tid = self._topic_id(codigo, campo)
        if tid not in self._valores:
            try:
                topico = rtd_topico(codigo)
                resultado = self._rtd.ConnectData(tid, [topico, campo], True)
                valor = resultado[0] if isinstance(resultado, tuple) else resultado
                self._valores[tid] = valor
            except Exception:
                self._valores[tid] = None
        return tid

    def registrar_status(self, codigo: str) -> int:
        tid = self._topic_id(codigo, "EST")
        if tid not in self._valores:
            try:
                resultado = self._rtd.ConnectData(tid, [codigo, "EST"], True)
                valor = resultado[0] if isinstance(resultado, tuple) else resultado
                self._valores[tid] = valor
            except Exception:
                self._valores[tid] = None
        return tid

    def refresh(self) -> dict[str, object]:
        if not self.disponivel or self._rtd is None:
            return {}
        try:
            resultado = self._rtd.RefreshData(0)
        except Exception as e:
            logger.debug("RTD RefreshData erro: %s", e)
            return {}
        if isinstance(resultado, int):
            return {}
        try:
            data, update_count = resultado[0], resultado[1]
            update_count = int(update_count)
        except Exception:
            return {}
        if update_count == 0:
            return {}

        try:
            topics = data[0]
            values = data[1]
        except Exception:
            logger.debug("RTD: RefreshData format unexpected (no values array).")
            return {}

        mudancas: dict[str, object] = {}
        # Itera sobre os tópicos atualizados e seus respectivos valores
        for i in range(min(len(topics), len(values), update_count)):
            try:
                raw_tid = topics[i]
                tid = int(raw_tid[0]) if isinstance(raw_tid, (tuple, list)) else int(raw_tid)
                
                valor = values[i]
                if isinstance(valor, (tuple, list)):
                    valor = valor[0]
                
                self._valores[tid] = valor
                chave = self._topic_reverse.get(tid)
                if chave:
                    mudancas[chave] = valor
            except (ValueError, TypeError, IndexError):
                continue
                
        return mudancas

    def ler_campo_cache(self, codigo: str, campo: str) -> Optional[float]:
        chave = "{}|{}".format(codigo, campo)
        tid = self._topic_map.get(chave)
        if tid is None:
            return None
        valor = self._valores.get(tid)
        if valor is None:
            return None
        try:
            v = float(str(valor).replace(",", "."))
            return v if v > 0 else None
        except (ValueError, TypeError):
            return None

    def ler_status_cache(self, codigo: str) -> str:
        chave = "{}|EST".format(codigo)
        tid = self._topic_map.get(chave)
        if tid is None:
            return ""
        valor = self._valores.get(tid)
        if valor is None:
            return ""
        return str(valor).strip()

    def ler_campo(self, codigo: str, campo: str) -> Optional[float]:
        if not self.disponivel or self._rtd is None:
            return None
        try:
            topico = rtd_topico(codigo)
            tid = self._topic_id(codigo, campo)
            resultado = self._rtd.ConnectData(tid, [topico, campo], False)
            valor = resultado[0] if isinstance(resultado, tuple) else resultado
            if valor is None:
                return None
            v = float(str(valor).replace(",", "."))
            return v if v > 0 else None
        except Exception:
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
