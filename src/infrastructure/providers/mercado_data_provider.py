import logging
import os
import time
from datetime import date
from PySide6.QtCore import QMutex

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.market_data_source import FieldName, MarketDataSource, OPENFAST_FIELD_STR
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
from src.infrastructure.providers import stale_trace

logger = logging.getLogger(__name__)


class MercadoDataProvider:
    SEM_BOOK_SKIP_CYCLES = 6
    SEM_ATIVO_SKIP_CYCLES = 10
    _GIL_YIELD_INTERVAL = 100

    _CAMPOS_PUT = [FieldName.STRIKE, FieldName.ASK, FieldName.BID,
                   FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_ASK, FieldName.VOL_BID]
    _CAMPOS_CALL = [FieldName.STRIKE, FieldName.ASK, FieldName.BID,
                    FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_BID, FieldName.VOL_ASK]

    def __init__(self, db_path=None, source: MarketDataSource | None = None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.source = source
        self._registrado = False
        self._registro_idx = 0
        self._ativos_registrados: set[str] = set()
        self._chaves_registradas: set[str] = set()
        self._chaves_com_book: set[str] = set()
        self._chaves_detalhes_completos: set[str] = set()
        self._sem_ativo_skip: dict[str, int] = {}
        self._precos_ativo_cache: dict[str, float] = {}
        self._precos_ativo_cache_ts: dict[str, float] = {}
        self._scan_count = 0
        self._total_instrumentos_cache: int = 0
        self._ultimo_refresh_timestamp: float = 0.0
        self._ciclos_sem_dados: int = 0
        self._lock = QMutex()
        self._registro_remaining_idx: int = 0
        self._background_offset: int = 0
        self._sem_book_skip: dict[str, int] = {}
        self._MAX_SEM_BOOK_SKIP = 10
        self._prioridade_set: set[str] = self._carregar_prioridades()
        self._prioridade_salva: set[str] = set()
        self._caminho_prioridade = self._resolver_caminho_prioridade()
        self._cab_anterior: dict[str, tuple[float | None, float | None]] = {}
        self._dados_cache: dict[str, dict] = {}
        self._strike_cache: dict[str, float] = {}  # cache opcional (nao usado atualmente)
        self._onda2_dte_min: int = 7
        self._onda2_dte_max: int = 180
        self._filtro_semanal: bool = False
        self._chaves_semanais_excluidas: set[str] = set()
        self._inst_map_cache: dict | None = None
        self._inst_map_cache_time: float = 0.0
        self._INST_MAP_CACHE_TTL: float = 30.0
        self._cont_stale_skip = 0
        self._cont_stale_skip_ciclo = 0
        self._assinar_timestamp_openfast = False
        self._stale_sinal_s = 30.0
        self.recarregar_parametros()

    def _resolver_caminho_prioridade(self) -> str:
        if self.db_path:
            base = os.path.splitext(str(self.db_path))[0]
            return os.path.abspath(base + "_prioridade.json")
        return os.path.abspath("rtd_prioridade.json")

    def _campo_stale(self, codigo: str, campo: FieldName) -> bool:
        """True se a fonte expõe frescor e o campo está fora da janela.

        Para feed push change-driven (OpenFast), o valor presente no cache é a
        cotação atual (sem push = não mudou — manual SQT §6). O gate de idade
        é irrelevante aqui: a saúde é garantida por ``disponivel`` (SYN <= 20s)
        e pela limpeza do cache na desconexão/reconexão/watchdog. Nunca marca
        stale por idade; ausência é tratada como None nos fluxos downstream.
        """
        if getattr(self.source, 'suporta_push', False):
            return False
        is_stale = getattr(self.source, 'is_stale_campo', None)
        if is_stale is None:
            return False
        try:
            return bool(is_stale(codigo, campo))
        except Exception:
            return False

    def _ler_campo_cache(self, codigo: str, campo: FieldName) -> float | None:
        """Leitura de campo com a semântica de frescor da fonte.

        Feed push change-driven e disponível: valor presente = cotação atual
        (sem push = não mudou), portanto ``allow_stale=True``. Polling mantém
        o contrato original (idade vale, pois não há push).
        """
        try:
            if getattr(self.source, 'suporta_push', False) and getattr(self.source, 'disponivel', True):
                return self.source.ler_campo_cache(codigo, campo, allow_stale=True)
        except Exception:
            pass
        return self.source.ler_campo_cache(codigo, campo)

    def _ler_campos(self, codigo: str, *campos: FieldName) -> dict[FieldName, float | None]:
        try:
            if getattr(self.source, 'suporta_push', False) and getattr(self.source, 'disponivel', True):
                return self.source.ler_campos(codigo, *campos, allow_stale=True)
        except Exception:
            pass
        return self.source.ler_campos(codigo, *campos)

    def _preco_ativo_cache_fresco(self, ativo: str) -> float | None:
        """Fallback de preço do ativo apenas se dentro da janela de frescor.

        Valor cacheado com idade > stale_campo_s é tratado como inexistente:
        nunca devolve preço velho para alimentar cálculo (C2)."""
        try:
            janela = float(getattr(self.source, 'stale_campo_s', 15.0))
        except (TypeError, ValueError):
            janela = 15.0
        p = self._precos_ativo_cache.get(ativo)
        if not p:
            return None
        ts = self._precos_ativo_cache_ts.get(ativo, 0.0)
        if ts and (time.time() - ts) > janela:
            self._precos_ativo_cache.pop(ativo, None)
            self._precos_ativo_cache_ts.pop(ativo, None)
            return None
        return p

    def _armazenar_preco_ativo(self, ativo: str, preco: float) -> None:
        self._precos_ativo_cache[ativo] = preco
        self._precos_ativo_cache_ts[ativo] = time.time()

    def _fonte_controla_frescor(self) -> bool:
        return getattr(self.source, 'is_stale_campo', None) is not None

    def _anotar_frescor(self, entry: dict, inst) -> None:
        entry.setdefault("stale", False)
        entry.setdefault("ts_ativo_ask", self._ts_fonte(inst.ativo, FieldName.ASK))
        entry.setdefault("ts_ativo_bid", self._ts_fonte(inst.ativo, FieldName.BID))
        entry.setdefault("ts_put_ask", self._ts_fonte(inst.cod_put, FieldName.ASK))
        entry.setdefault("ts_call_bid", self._ts_fonte(inst.cod_call, FieldName.BID))
        entry.setdefault("feed_state", self._feed_fonte())
        entry.setdefault("subscription_generation", self._geracao_fonte())
        entry.setdefault("ts_origem_ativo", self._origem_fonte(inst.ativo))
        entry.setdefault("ts_time_ativo", self._time_fonte(inst.ativo))
        entry.setdefault("ts_timeng_ativo", self._timeng_fonte(inst.ativo))
        if entry.get("ts_origem_ativo") is not None and "idade_origem_ativo" not in entry:
            origem = entry["ts_origem_ativo"]
            if origem >= 1_000_000_000 and origem <= time.time() + 3600:
                entry["idade_origem_ativo"] = time.time() - origem

    def _origem_fonte(self, codigo: str) -> float | None:
        try:
            return self.source.get_ts_origem(codigo)
        except Exception:
            return None

    def _time_fonte(self, codigo: str) -> float | None:
        try:
            return self.source.get_ts_time(codigo)
        except Exception:
            return None

    def _timeng_fonte(self, codigo: str) -> float | None:
        try:
            return self.source.get_ts_timeng(codigo)
        except Exception:
            return None

    def _idade_origem_fonte(self, codigo: str) -> float | None:
        try:
            return self.source.get_idade_origem(codigo)
        except Exception:
            return None

    def _trace_t5_ciclo(self) -> None:
        if not stale_trace.enabled() or not getattr(self.source, "suporta_push", False):
            return
        campo_por_nome = {nome: campo for campo, nome in OPENFAST_FIELD_STR.items()}
        for codigo, nome in stale_trace.traced_keys():
            campo = campo_por_nome.get(nome)
            if campo is None:
                continue
            valor = self.source.ler_campo_cache(codigo, campo, allow_stale=True)
            if valor is None:
                continue
            idade = self.source.get_idade_campo(codigo, campo)
            stale = self.source.is_stale_campo(codigo, campo)
            stale_trace.log_t5(codigo, nome, valor, idade, stale)

    def _ts_fonte(self, codigo: str, campo: FieldName) -> float | None:
        try:
            return self.source.get_ts_campo(codigo, campo)
        except Exception:
            return None

    def _feed_fonte(self) -> str:
        return str(getattr(self.source, 'feed_state', ''))

    def _geracao_fonte(self):
        return getattr(self.source, 'subscription_generation', 0)

    def _carregar_prioridades(self) -> set[str]:
        try:
            import json
            path = self._resolver_caminho_prioridade() if self.db_path else "rtd_prioridade.json"
            logger.info("Procurando prioridades em: %s", path)
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    logger.info("Prioridades carregadas: %d instrumentos", len(data))
                    return set(data)
                else:
                    logger.warning("Prioridades: formato inesperado (%s)", type(data).__name__)
            else:
                logger.info("Prioridades: arquivo nao encontrado")
        except Exception as e:
            logger.warning("Erro ao carregar prioridades: %s", e)
        return set()

    def _salvar_prioridades(self):
        try:
            import json
            chaves = list(self._dados_cache.keys()) + list(self._chaves_com_book - self._dados_cache.keys())
            with open(self._caminho_prioridade, "w") as f:
                json.dump(chaves, f)
            self._prioridade_salva = set(chaves)
        except Exception as e:
            logger.warning("Erro ao salvar prioridades: %s", e)

    def recarregar_instrumentos(self):
        """Limpa as flags de cache e força o re-registro dos instrumentos no RTD."""
        self._lock.lock()
        try:
            self._registrado = False
            self._registro_idx = 0
            self._registro_remaining_idx = 0
            self._ativos_registrados.clear()
            self._chaves_registradas.clear()
            self._chaves_com_book.clear()
            self._chaves_detalhes_completos.clear()
            self._sem_ativo_skip.clear()
            self._sem_book_skip.clear()
            self._precos_ativo_cache.clear()
            self._precos_ativo_cache_ts.clear()
            self._cab_anterior.clear()
            self._dados_cache.clear()
            self._chaves_semanais_excluidas.clear()
            self._invalidar_cache_inst_map()
            self.recarregar_parametros()
            logger.info("MercadoDataProvider: recarregamento de instrumentos agendado.")
        finally:
            self._lock.unlock()

    def recarregar_parametros(self):
        if not hasattr(self, '_param_repo_cache'):
            from src.infrastructure.persistence.repositories.repositories import ParametroRepository
            self._param_repo_cache = ParametroRepository(self.db_path)
        repo = self._param_repo_cache
        repo.invalidate_cache()
        
        p_ci = repo.get_by_chave("perf_carga_inteligente")
        self._carga_inteligente_habilitada = bool(p_ci.valor) if p_ci else True
        
        p_min = repo.get_by_chave("perf_range_min")
        self._range_min = (p_min.valor / 100.0) if p_min else -0.5
        
        p_max = repo.get_by_chave("perf_range_max")
        self._range_max = (p_max.valor / 100.0) if p_max else 0.5
        
        p_meses = repo.get_by_chave("perf_limite_meses")
        self._limite_meses = int(p_meses.valor) if p_meses else 0
        
        p_dias_min = repo.get_by_chave("perf_dias_minimos")
        self._dias_minimos = int(p_dias_min.valor) if p_dias_min else 0
        p_onda2_min = repo.get_by_chave("onda2_dte_min")
        self._onda2_dte_min = int(p_onda2_min.valor) if p_onda2_min else 7
        p_onda2_max = repo.get_by_chave("onda2_dte_max")
        self._onda2_dte_max = int(p_onda2_max.valor) if p_onda2_max else 180
        p_rtd = repo.get_by_chave("rtd_refresh_timeout_ms")
        self._rtd_refresh_timeout_ms = int(p_rtd.valor) if p_rtd else 5000
        
        p_fs = repo.get_by_chave("perf_filtro_semanal")
        self._filtro_semanal = bool(p_fs.valor) if p_fs else False
        
        p_tso = repo.get_by_chave("assinar_timestamp_openfast")
        self._assinar_timestamp_openfast = bool(p_tso.valor) if p_tso else False
        
        p_si = repo.get_by_chave("stale_sinal_s")
        self._stale_sinal_s = float(p_si.valor) if p_si else 30.0
        
        # Se houve mudança em parâmetros que afetam a carga, agendamos uma revisão de carga
        if self._registrado:
            # Reseta flags para re-escancar o banco, mas MANTÉM tudo o que já estava registrado
            self._registrado = False
            self._registro_idx = 0
            # Limpa cache de preços + books + Onda 2 para forçar re-detecção completa
            self._precos_ativo_cache.clear()
            self._precos_ativo_cache_ts.clear()
            self._chaves_com_book.clear()
            self._chaves_detalhes_completos.clear()
            self._cab_anterior.clear()
            self._dados_cache.clear()
            logger.info("MercadoDataProvider: Parametros alterados. Revisão de carga agendada em background.")
        
        logger.info("MercadoDataProvider: Parametros de performance atualizados.")

    def _get_inst_map(self) -> dict:
        ahora = time.time()
        if self._inst_map_cache is None or (ahora - self._inst_map_cache_time) > self._INST_MAP_CACHE_TTL:
            self._inst_map_cache = self.inst_repo.get_all_mapped()
            self._inst_map_cache_time = ahora
        return self._inst_map_cache

    def _invalidar_cache_inst_map(self):
        self._inst_map_cache = None
        self._inst_map_cache_time = 0.0

    def _campos_timestamp_openfast(self, codigo: str) -> list[tuple[str, FieldName]]:
        """Campos de origem (TIME/TIMENEG) do OpenFast quando habilitado.

        Diagnóstico apenas: mede a idade real da cotação no protocolo, sem
        reescrever _cache_ts (frescor de entrega) da fonte.
        """
        if not self._assinar_timestamp_openfast or not self._fonte_controla_frescor():
            return []
        return [
            (codigo.upper(), FieldName.TIMENEG),
            (codigo.upper(), FieldName.TIME),
        ]

    def _registrar_ativos_prioritarios(self, instrumentos: list[InstrumentoOpcional]):
        """Registra apenas os ativos (underlyings) para obter preços de referência rápido."""
        rtd = self.source
        t0 = time.perf_counter()
        registros: list[tuple[str, FieldName]] = []
        for inst in instrumentos:
            if inst.ativo not in self._ativos_registrados:
                registros += [
                    (inst.ativo, FieldName.LAST_PRICE),
                    (inst.ativo, FieldName.ASK),
                    (inst.ativo, FieldName.BID),
                    (inst.ativo, FieldName.STATUS),
                ]
                registros += self._campos_timestamp_openfast(inst.ativo)
                self._ativos_registrados.add(inst.ativo)
        if registros:
            self._flush_buffer(registros)
            logger.info("RTD: %d ativos registrados prioritariamente em %.2fs (%d registros).",
                         len(registros) // 4, time.perf_counter() - t0, len(registros))

    def _registrar_detalhes_completos(self, inst: InstrumentoOpcional, registros_acum: list | None = None):
        """Registra todos os campos de um instrumento quando detectamos liquidez."""
        key = f"{inst.ativo}|{inst.cod_put}"
        if key in self._chaves_detalhes_completos:
            return
        
        rtd = self.source
        # Feed push (OpenFast): strike canônico vem do banco (OptionsChain via
        # inst.strike) — assinar PEX/STRIKE é tráfego morto (~metade do socket).
        if getattr(rtd, 'suporta_push', False):
            campos_put = [c for c in self._CAMPOS_PUT
                          if c != FieldName.BOOK_HEADER and c != FieldName.STRIKE]
            campos_call = [c for c in self._CAMPOS_CALL
                           if c != FieldName.BOOK_HEADER and c != FieldName.STRIKE]
        else:
            campos_put = [c for c in self._CAMPOS_PUT if c != FieldName.BOOK_HEADER]
            campos_call = [c for c in self._CAMPOS_CALL if c != FieldName.BOOK_HEADER]
        registros = [
            (inst.cod_put, campo) for campo in campos_put
        ] + [
            (inst.cod_call, campo) for campo in campos_call
        ] + [
            (inst.cod_put, FieldName.STATUS),
            (inst.cod_call, FieldName.STATUS),
        ]
        if registros_acum is not None:
            registros_acum.extend(registros)
        else:
            rtd.registrar_lista(registros)
        
        self._chaves_detalhes_completos.add(key)
        logger.debug("RTD: Detalhes completos registrados para %s (Liquidez detectada)", key)

        preco = rtd.ler_campo_cache(inst.ativo, FieldName.ASK)
        if preco and preco > 0:
            self._armazenar_preco_ativo(inst.ativo, preco)
            logger.debug("RTD: preco_ativo %s=%.2f forçado com sucesso", inst.ativo, preco)

    def _deve_pular_instrumento(self, inst: InstrumentoOpcional) -> bool:
        if not self._carga_inteligente_habilitada:
            return False
        hoje = date.today()
        if self._dias_minimos > 0 and inst.vencimento:
            if (inst.vencimento - hoje).days < self._dias_minimos:
                return True
        if self._limite_meses > 0 and inst.vencimento:
            if (inst.vencimento - hoje).days > (self._limite_meses * 30):
                return True
        return False

    def _deve_pular_por_strike(self, inst: InstrumentoOpcional) -> bool:
        if not self._carga_inteligente_habilitada or not (self._range_min < 0 or self._range_max > 0):
            return False
        strike_val = inst.strike if inst.strike else self.source.ler_campo_cache(inst.cod_put, FieldName.STRIKE)
        if not strike_val or strike_val <= 0:
            return False
        preco = self.source.ler_campo_cache(inst.ativo, FieldName.ASK)
        if not preco or preco <= 0:
            return False
        ratio = (strike_val / preco) - 1
        return ratio < self._range_min or ratio > self._range_max

    def _registrar_instrumento(self, inst: InstrumentoOpcional, registros_acum: list | None = None):
        rtd = self.source
        key = f"{inst.ativo}|{inst.cod_put}"
        if key in self._chaves_registradas or key in self._chaves_semanais_excluidas:
            return False

        if self._filtro_semanal:
            cod = inst.cod_put or inst.cod_call
            if cod and len(cod) >= 2 and cod[-2].upper() == "W":
                self._chaves_semanais_excluidas.add(key)
                return False

        if self._deve_pular_instrumento(inst):
            self._chaves_registradas.add(key)
            return False

        # Assinatura de STRIKE (PEX) apenas para fontes COM (RTD). Em feed
        # push (OpenFAST) o strike canônico vem do banco (inst.strike via
        # OptionsChain API) — assinar PEX é tráfego morto no socket.
        if getattr(rtd, 'suporta_push', False):
            registros: list[tuple[str, FieldName]] = []
        else:
            registros = [
                (inst.cod_put, FieldName.STRIKE),
                (inst.cod_call, FieldName.STRIKE),
            ]

        # Correção de strike apenas para fontes COM (RTD), onde o dado RTD
        # pode ter ajustes pós-mercado (ex-dividendo). Para push-based
        # (OpenFAST), o strike do banco (OptionsChain API) é a fonte canônica.
        if not getattr(rtd, 'suporta_push', False):
            strike_db = inst.strike
            for cod_opcao in (inst.cod_put, inst.cod_call):
                strike_rtd = rtd.ler_campo_cache(cod_opcao, FieldName.STRIKE)
                if strike_rtd and strike_rtd > 0 and strike_db and strike_db > 0:
                    strike_final = min(strike_db, strike_rtd)
                    if strike_final < strike_rtd:
                        logger.info(
                            "Strike corrigido %s: DB=%.2f RTD=%.2f -> %.2f",
                            cod_opcao, strike_db, strike_rtd, strike_final,
                        )
                        rtd_raw = getattr(rtd, '_rtd', None)
                        if rtd_raw is not None and hasattr(rtd_raw, '_topic_id'):
                            tid = rtd_raw._topic_id(cod_opcao, "PEX")
                            with rtd_raw._lock:
                                rtd_raw._valores[tid] = strike_final
                        else:
                            rtd.invalidar_cache(cod_opcao, FieldName.STRIKE)
                            rtd.registrar_topico(cod_opcao, FieldName.STRIKE)
                        self._strike_cache[cod_opcao] = strike_final
                elif strike_db and strike_db > 0:
                    strike_final = strike_db
                    rtd_raw = getattr(rtd, '_rtd', None)
                    if rtd_raw is not None and hasattr(rtd_raw, '_topic_id'):
                        tid = rtd_raw._topic_id(cod_opcao, "PEX")
                        with rtd_raw._lock:
                            rtd_raw._valores[tid] = strike_final
                    else:
                        rtd.invalidar_cache(cod_opcao, FieldName.STRIKE)
                        rtd.registrar_topico(cod_opcao, FieldName.STRIKE)

        if not self._deve_pular_por_strike(inst):
            registros += [
                (inst.cod_put, FieldName.BOOK_HEADER),
                (inst.cod_call, FieldName.BOOK_HEADER),
                (inst.cod_put, FieldName.ASK),
                (inst.cod_put, FieldName.BID),
                (inst.cod_put, FieldName.VOL_ASK),
                (inst.cod_put, FieldName.VOL_BID),
                (inst.cod_put, FieldName.QTD_LAST),
                (inst.cod_put, FieldName.STATUS),
                (inst.cod_call, FieldName.ASK),
                (inst.cod_call, FieldName.BID),
                (inst.cod_call, FieldName.VOL_ASK),
                (inst.cod_call, FieldName.VOL_BID),
                (inst.cod_call, FieldName.QTD_LAST),
                (inst.cod_call, FieldName.STATUS),
            ]

        if inst.ativo not in self._ativos_registrados:
            registros += [
                (inst.ativo, FieldName.LAST_PRICE),
                (inst.ativo, FieldName.ASK),
                (inst.ativo, FieldName.BID),
                (inst.ativo, FieldName.STATUS),
            ]
            registros += self._campos_timestamp_openfast(inst.ativo)
            self._ativos_registrados.add(inst.ativo)

        if registros_acum is not None:
            registros_acum.extend(registros)
        else:
            rtd.registrar_lista(registros)
        self._chaves_registradas.add(key)
        self._chaves_com_book.add(key)
        return True

    def _flush_buffer(self, buffer: list, max_chunk: int = 1000):
        if not buffer:
            return
        if not getattr(self.source, 'disponivel', True):
            buffer.clear()
            return
        t0 = time.perf_counter()
        n = len(buffer)
        for i in range(0, n, max_chunk):
            chunk = buffer[i:i + max_chunk]
            self.source.registrar_lista(chunk)
        buffer.clear()
        dt = time.perf_counter() - t0
        if dt > 0.1:
            logger.debug("_flush_buffer: %d registros em %.2fs", n, dt)

    def _registrar_batch_inteligente(self, instrumentos: list[InstrumentoOpcional], batch_size: int = 2000) -> list[tuple[str, FieldName]]:
        if self._registrado:
            return []

        t0 = time.perf_counter()
        start_idx = self._registro_idx
        end_idx = min(start_idx + batch_size, len(instrumentos))
        
        count_processados = 0
        count_pulas = 0
        registros_acum: list[tuple[str, FieldName]] = []

        for i in range(start_idx, end_idx):
            inst = instrumentos[i]
            if self._registrar_instrumento(inst, registros_acum):
                count_processados += 1
            else:
                count_pulas += 1

        self._registro_idx = end_idx

        if self._registro_idx >= len(instrumentos):
            self._registrado = True
            logger.info("RTD: Onda 1 (Cabeçalhos) concluída. %d monitorados. (Pulos: %d)",
                         len(self._chaves_registradas), count_pulas)
        else:
            logger.info("RTD: Lote Onda 1 %d/%d (Registros: %d) em %.2fs.",
                         self._registro_idx, len(instrumentos), count_processados, time.perf_counter() - t0)

        return registros_acum

    def _registrar_novos_entrantes(self) -> list[tuple[str, FieldName]]:
        instrumentos = self.inst_repo.get_all()
        instrumentos.sort(key=lambda i: i.vencimento)
        total = len(instrumentos)
        if self._registro_remaining_idx >= total:
            self._registro_remaining_idx = self._background_offset

        batch = 2000
        start = self._registro_remaining_idx
        end = min(start + batch, total)
        count = 0
        registros_acum: list[tuple[str, FieldName]] = []

        for i in range(start, end):
            inst = instrumentos[i]
            if self._registrar_instrumento(inst, registros_acum):
                count += 1

        self._registro_remaining_idx = end
        if count > 0:
            logger.info("Background scan: %d novos instrumentos registrados", count)
        if self._registro_remaining_idx >= total:
            self._registro_remaining_idx = 0
            logger.info("Background scan: ciclo completo. Total monitorados: %d", len(self._chaves_registradas))

        return registros_acum

    def capturar_dados_mercado(self) -> dict[str, dict]:
        if not self.source.disponivel:
            logger.warning("RTD nao disponivel — retornando dados vazios.")
            return {}

        self._lock.lock()
        try:
            try:
                # Mock source: atalho direto, sem scan
                if getattr(self.source, 'is_mock', False):
                    instrumentos = self.inst_repo.get_all()
                    from src.infrastructure.providers.mock_market_data import MockMarketDataProvider
                    mock_provider = MockMarketDataProvider(preco_base=18.0)
                    dados = mock_provider.gerar_dados_para_instrumentos(instrumentos)
                    if dados:
                        self._chaves_com_book = set(dados.keys())
                        self._chaves_detalhes_completos = set(dados.keys())
                        self._chaves_registradas = set(dados.keys())
                        self._registrado = True
                        self._ativos_registrados = {k.split("|")[0] for k in dados}
                        self.source.popular_cache(dados)
                    return dados

                t_reg = time.perf_counter()
                # Carrega a lista completa do banco apenas quando necessário
                # (evita ler 52k linhas do SQLite a cada ciclo)
                if not self._registrado or not self._ativos_registrados:
                    instrumentos = self.inst_repo.get_all()
                    instrumentos.sort(key=lambda i: i.vencimento)
                    self._total_instrumentos_cache = len(instrumentos)

                    # Primeiro ciclo: registra apenas ativos para pegar preços base
                    if not self._ativos_registrados:
                        self._registrar_ativos_prioritarios(instrumentos)

                    # Onda 1
                    if not self._registrado:
                        if self._prioridade_set:
                            prio = [inst for inst in instrumentos if f"{inst.ativo}|{inst.cod_put}" in self._prioridade_set or inst.cod_put in self._prioridade_set]
                            regs = self._registrar_batch_inteligente(prio, batch_size=2000)
                            self._flush_buffer(regs)
                            if self._registrado:
                                self._background_offset = len(prio)
                                self._registro_remaining_idx = len(prio)
                                logger.info("Onda 1 prioritária concluída: %d instrumentos monitorados. Background scan ativo para novos entrantes.", len(self._chaves_registradas))
                        else:
                            regs = self._registrar_batch_inteligente(instrumentos, batch_size=2000)
                            self._flush_buffer(regs)
                # Força refresh logo após Onda 1 completa pra garantir dados reais do servidor
                if self._registrado and not getattr(self, '_refresh_pos_onda1', False):
                    self._refresh_pos_onda1 = True
                    logger.info("Onda 1 concluída — forçando refresh inicial...")
                    try:
                        self.source.refresh(self._rtd_refresh_timeout_ms)
                    except Exception:
                        pass
                t_registro = time.perf_counter() - t_reg

                t0 = time.perf_counter()
                mudancas: dict = {}
                try:
                    mudancas = self.source.refresh(self._rtd_refresh_timeout_ms) or {}
                except Exception as e:
                    logger.error("RTD refresh escapou: %s", e, exc_info=True)
                    return {}
                t_refresh = time.perf_counter() - t0

                suporta_push = getattr(self.source, 'suporta_push', False)
                suporta_cab_skip = getattr(self.source, 'suporta_cab_skip', False)
                cab_skip_habilitado = not suporta_push and suporta_cab_skip

                t_scan0 = time.perf_counter()
                self._scan_count += 1
                self._ultimo_refresh_timestamp = time.time()

                dados_mercado: dict[str, dict] = {}
                sem_ativo_atual: dict[str, int] = {}
                t_onda2_detalhes = 0.0
                t_onda1_basico = 0.0
                t_cab_cache = 0.0
                t_status = 0.0
                count_onda2 = 0
                count_onda1 = 0
                count_cab_skip = 0
                count_sem_preco = 0
                count_sem_dados_rtd = 0
                logger.debug("Varredura: _chaves_com_book=%d _chaves_detalhes=%d",
                             len(self._chaves_com_book), len(self._chaves_detalhes_completos))

                t_inst_map = time.perf_counter()
                inst_map = self._get_inst_map()
                t_inst_map = time.perf_counter() - t_inst_map

                # Pré-computa set de códigos que mudaram (push-based)
                codigos_mudados: set[str] | None = None
                if suporta_push and mudancas:
                    codigos_mudados = {ch.split("|")[0] for ch in mudancas}

                for i_scan, key in enumerate(list(self._chaves_com_book)):
                    if i_scan % self._GIL_YIELD_INTERVAL == 0:
                        time.sleep(0)
                    if "|" not in key:
                        continue
                    ativo, cod_put = key.split("|", 1)
                    inst = inst_map.get((ativo, cod_put))
                    if not inst:
                        continue

                    # Gate de frescor: se a fonte expõe is_stale_campo, qualquer perna
                    # crítica fora da janela bloqueia o cálculo neste ciclo.
                    if self._fonte_controla_frescor():
                        criticos = [
                            (inst.ativo, FieldName.ASK), (inst.ativo, FieldName.BID),
                            (inst.cod_put, FieldName.ASK), (inst.cod_put, FieldName.BID),
                            (inst.cod_call, FieldName.ASK), (inst.cod_call, FieldName.BID),
                        ]
                        if any(self._campo_stale(codigo, campo) for codigo, campo in criticos):
                            stale_trace.log_evento("stale_skip", f"{ativo}|{cod_put}")
                            self._cont_stale_skip += 1
                            self._cont_stale_skip_ciclo += 1
                            continue

                    if key in self._chaves_detalhes_completos:
                        t0_onda2 = time.perf_counter()

                        # CAB skip (Profit RTD) ou dirty keys (Open Fast)
                        if cab_skip_habilitado:
                            cab_put = self.source.ler_campo_cache(inst.cod_put, FieldName.BOOK_HEADER)
                            cab_call = self.source.ler_campo_cache(inst.cod_call, FieldName.BOOK_HEADER)
                            cab_prev = self._cab_anterior.get(key)
                            cab_mudou = cab_prev is None or cab_prev[0] != cab_put or cab_prev[1] != cab_call
                        elif suporta_push:
                            tem_mudanca = (
                                codigos_mudados is None
                                or inst.ativo in codigos_mudados
                                or inst.cod_put in codigos_mudados
                                or inst.cod_call in codigos_mudados
                            )
                            cab_mudou = tem_mudanca
                            cab_put = cab_call = None
                        else:
                            cab_mudou = True
                            cab_put = cab_call = None

                        if not cab_mudou and key in self._dados_cache:
                            t0_status = time.perf_counter()
                            entry = self._dados_cache[key]
                            entry["status_put"] = self.source.ler_status_cache(inst.cod_put)
                            entry["status_call"] = self.source.ler_status_cache(inst.cod_call)
                            entry["status_ativo"] = self.source.ler_status_cache(inst.ativo)
                            entry["em_leilao"] = not (
                                entry["status_put"].lower() == "aberto"
                                and entry["status_call"].lower() == "aberto"
                                and entry["status_ativo"].lower() == "aberto"
                            )
                            # Batch reads: 1 lock por símbolo em vez de 1 por campo
                            c_ativo = self._ler_campos(inst.ativo, FieldName.ASK, FieldName.BID)
                            c_put = self._ler_campos(inst.cod_put, FieldName.ASK, FieldName.BID, FieldName.VOL_ASK, FieldName.QTD_LAST)
                            c_call = self._ler_campos(inst.cod_call, FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.QTD_LAST)
                            p_ativo = c_ativo.get(FieldName.ASK)
                            if p_ativo is not None and p_ativo > 0:
                                entry["preco_ativo"] = p_ativo
                                entry["of_venda_ativo"] = p_ativo
                                self._armazenar_preco_ativo(inst.ativo, p_ativo)
                            else:
                                p_ativo = self._preco_ativo_cache_fresco(inst.ativo)
                                if p_ativo:
                                    entry["preco_ativo"] = p_ativo
                                    entry["of_venda_ativo"] = p_ativo
                                else:
                                    entry["stale"] = True
                                    self._cont_stale_skip += 1
                                    self._cont_stale_skip_ciclo += 1
                                    self._dados_cache.pop(key, None)
                                    continue
                            of_compra = c_ativo.get(FieldName.BID) or 0.0
                            if of_compra > p_ativo or of_compra <= 0:
                                of_compra = 0.0
                            entry["of_compra_ativo"] = of_compra
                            of_v_put = c_put.get(FieldName.ASK)
                            if of_v_put is not None:
                                entry["of_venda_put"] = of_v_put
                                entry["premio_put"] = of_v_put
                            of_c_put = c_put.get(FieldName.BID)
                            if of_c_put is not None:
                                entry["of_compra_put"] = of_c_put
                            vov = c_put.get(FieldName.VOL_ASK)
                            if vov is not None:
                                entry["vov_put"] = vov
                            qul_p = c_put.get(FieldName.QTD_LAST)
                            if qul_p is not None:
                                entry["qul_put"] = qul_p
                            of_c_call = c_call.get(FieldName.BID)
                            if of_c_call is not None:
                                entry["of_compra_call"] = of_c_call
                                entry["premio_call"] = of_c_call
                            of_v_call = c_call.get(FieldName.ASK)
                            if of_v_call is not None:
                                entry["of_venda_call"] = of_v_call
                            voc = c_call.get(FieldName.VOL_BID)
                            if voc is not None:
                                entry["voc_call"] = voc
                            qul_c = c_call.get(FieldName.QTD_LAST)
                            if qul_c is not None:
                                entry["qul_call"] = qul_c
                            t_status += time.perf_counter() - t0_status
                            entry["ts_ativo_ask"] = self.source.get_ts_campo(inst.ativo, FieldName.ASK)
                            entry["ts_ativo_bid"] = self.source.get_ts_campo(inst.ativo, FieldName.BID)
                            self._anotar_frescor(entry, inst)
                            dados_mercado[key] = entry
                            count_cab_skip += 1
                            continue

                        if cab_skip_habilitado:
                            self._cab_anterior[key] = (cab_put, cab_call)

                        preco_ativo_rtd = self._ler_campo_cache(inst.ativo, FieldName.ASK)
                        if preco_ativo_rtd is not None and preco_ativo_rtd > 0:
                            preco_ativo = preco_ativo_rtd
                            self._armazenar_preco_ativo(inst.ativo, preco_ativo)
                        else:
                            preco_ativo = self._preco_ativo_cache_fresco(inst.ativo)

                        if not preco_ativo or preco_ativo <= 0:
                            if key in self._dados_cache:
                                self._dados_cache[key]["stale"] = True
                                self._dados_cache.pop(key, None)
                            if inst.ativo in self._sem_ativo_skip:
                                count_sem_preco += 1
                                continue
                            sem_ativo_atual[inst.ativo] = self.SEM_ATIVO_SKIP_CYCLES
                            count_sem_preco += 1
                            continue

                        dados_rtd = self._ler_instrumento_cache(inst, preco_ativo)
                        if dados_rtd:
                            entry = dados_rtd.to_dados_mercado()
                            entry["ts_ativo_ask"] = self.source.get_ts_campo(inst.ativo, FieldName.ASK)
                            entry["ts_ativo_bid"] = self.source.get_ts_campo(inst.ativo, FieldName.BID)
                            self._anotar_frescor(entry, inst)
                            entry["ts_scan"] = time.time()
                            entry["onda"] = 2
                            dados_mercado[key] = entry
                            self._dados_cache[key] = entry
                        else:
                            count_sem_dados_rtd += 1
                            self._dados_cache.pop(key, None)
                        t_onda2_detalhes += time.perf_counter() - t0_onda2
                        count_onda2 += 1
                        continue

                    # Onda 1: dados basicos para collars (strike + OCP/OVD)
                    t0_onda1 = time.perf_counter()
                    if getattr(self.source, 'suporta_push', False):
                        strike_put = inst.strike
                        if strike_put is None:
                            logger.warning(
                                "Strike não encontrado no banco para %s/%s — descartando",
                                inst.cod_put, inst.cod_call,
                            )
                    else:
                        strike_put = self.source.ler_campo_cache(inst.cod_put, FieldName.STRIKE)
                        if not strike_put or strike_put <= 0:
                            strike_put = self.source.ler_campo_cache(inst.cod_call, FieldName.STRIKE)
                    if not strike_put or strike_put <= 0:
                        continue
                    # Skip da Onda 1 (push-based): se ativo, PUT e CALL não mudaram,
                    # a entry pode ser reutilizada do _dados_cache no pós-loop.
                    if suporta_push and codigos_mudados is not None:
                        perna_mudou = (
                            (inst.ativo in codigos_mudados)
                            or (inst.cod_put in codigos_mudados)
                            or (inst.cod_call in codigos_mudados)
                        )
                        if not perna_mudou and key in self._dados_cache:
                            continue
                    # Batch reads: 1 lock por símbolo (put, call, ativo) em vez
                    # de 1 lock por campo — reduz contenção com a thread leitora.
                    c_put_onda1 = self._ler_campos(inst.cod_put, FieldName.ASK, FieldName.BID,
                                                   FieldName.VOL_ASK, FieldName.QTD_LAST)
                    c_call_onda1 = self._ler_campos(inst.cod_call, FieldName.ASK, FieldName.BID,
                                                    FieldName.VOL_BID, FieldName.QTD_LAST)
                    c_ativo_onda1 = self._ler_campos(inst.ativo, FieldName.ASK, FieldName.BID)
                    ocp = c_call_onda1.get(FieldName.BID)
                    ovd = c_put_onda1.get(FieldName.ASK)
                    preco_ativo_rtd = c_ativo_onda1.get(FieldName.ASK)
                    if preco_ativo_rtd is not None and preco_ativo_rtd > 0:
                        preco_ativo = preco_ativo_rtd
                        self._armazenar_preco_ativo(inst.ativo, preco_ativo)
                    else:
                        preco_ativo = self._preco_ativo_cache_fresco(inst.ativo)
                    if not preco_ativo or preco_ativo <= 0:
                        if key in self._dados_cache:
                            self._dados_cache[key]["stale"] = True
                            self._dados_cache.pop(key, None)
                        continue
                    bid_ativo = c_ativo_onda1.get(FieldName.BID) or 0.0
                    if bid_ativo > preco_ativo or bid_ativo <= 0:
                        bid_ativo = 0.0
                    ts_ask = self.source.get_ts_campo(inst.ativo, FieldName.ASK)
                    ts_bid = self.source.get_ts_campo(inst.ativo, FieldName.BID)
                    entry = {
                        "preco_ativo": preco_ativo,
                        "strike_rtd": strike_put,
                        "of_compra_ativo": bid_ativo,
                        "of_venda_ativo": preco_ativo,
                        "of_compra_call": ocp or 0.0,
                        "of_venda_put": ovd or 0.0,
                        "premio_call": ocp or 0.0,
                        "premio_put": ovd or 0.0,
                        "of_compra_put": c_put_onda1.get(FieldName.BID) or 0.0,
                        "of_venda_call": c_call_onda1.get(FieldName.ASK) or 0.0,
                        "qul_put": c_put_onda1.get(FieldName.QTD_LAST) or 0.0,
                        "qul_call": c_call_onda1.get(FieldName.QTD_LAST) or 0.0,
                        "vov_put": c_put_onda1.get(FieldName.VOL_ASK) or 0.0,
                        "voc_call": c_call_onda1.get(FieldName.VOL_BID) or 0.0,
                        "em_leilao": False,
                        "status_put": self.source.ler_status_cache(inst.cod_put) or "aberto",
                        "status_call": self.source.ler_status_cache(inst.cod_call) or "aberto",
                        "status_ativo": self.source.ler_status_cache(inst.ativo) or "aberto",
                        "ts_ativo_ask": ts_ask,
                        "ts_ativo_bid": ts_bid,
                    }
                    self._anotar_frescor(entry, inst)
                    entry["ts_scan"] = time.time()
                    entry["onda"] = 1
                    dados_mercado[key] = entry
                    self._dados_cache[key] = entry
                    t_onda1_basico += time.perf_counter() - t0_onda1
                    count_onda1 += 1

                # Pós-processamento: preenche entries que não mudaram com
                # shallow copy do _dados_cache (em_leilao=False = Onda 1 normal).
                for key, cached in self._dados_cache.items():
                    if cached.get("stale") is True:
                        continue
                    if key not in dados_mercado and key in self._chaves_com_book:
                        entry = dict(cached)
                        entry["em_leilao"] = False
                        dados_mercado[key] = entry

                t_varredura = time.perf_counter() - t_scan0
                self._sem_ativo_skip = sem_ativo_atual
                self._trace_t5_ciclo()

                if dados_mercado:
                    self._ciclos_sem_dados = 0
                else:
                    self._ciclos_sem_dados += 1
                t_total = time.perf_counter() - t0
                if count_sem_preco > 0 or count_sem_dados_rtd > 0:
                    logger.debug(
                        "Varredura: sem_preco=%d sem_dados_rtd=%d "
                        "chaves_com_book=%d",
                        count_sem_preco, count_sem_dados_rtd,
                        len(self._chaves_com_book),
                    )
                logger.info(
                    "Varredura(%s): monitor=%d book=%d | "
                    "reg=%.3f ref=%.3f var=%.3f total=%.3f | "
                    "inst_map=%.3f | "
                    "onda2=%d(%.3f) onda1=%d(%.3f) cab_skip=%d status=%.3f",
                    "G" if (self._scan_count % 10 == 0) else "F",
                    len(self._chaves_registradas), len(dados_mercado),
                    t_registro, t_refresh, t_varredura, t_total,
                    t_inst_map,
                    count_onda2, t_onda2_detalhes,
                    count_onda1, t_onda1_basico,
                    count_cab_skip, t_status,
                )

                if self._cont_stale_skip_ciclo > 0:
                    logger.warning(
                        "OF STALE: %d entries com perna fora da janela (%ss) não "
                        "alimentaram a calculadora neste ciclo — acumulado=%d "
                        "no_new_update=%d (ciclo #%d)",
                        self._cont_stale_skip_ciclo,
                        getattr(self.source, 'stale_campo_s', '?'),
                        self._cont_stale_skip,
                        getattr(self.source, 'cont_no_new_update', 0),
                        self._scan_count,
                    )
                    self._cont_stale_skip_ciclo = 0

                return dados_mercado
            except Exception as e:
                logger.error("capturar_dados_mercado: erro inesperado: %s", e, exc_info=True)
                return {}
        finally:
            self._lock.unlock()

    def fazer_manutencao(self):
        """Detecta novos books, registra Onda 2, background scan e salva prioridades.
        Executado externamente (MonitorWorker), fora da varredura principal."""
        buffer_onda2: list[tuple[str, FieldName]] = []

        self._lock.lock()
        try:
            inst_map = self._get_inst_map()
            sem_detalhes = self._chaves_registradas - self._chaves_detalhes_completos
            count_reg = 0
            MAX_REG_ONDA2 = 500

            # Atualiza contadores de skip e filtra apenas os que devem ser verificados
            for key in list(self._sem_book_skip):
                self._sem_book_skip[key] -= 1
                if self._sem_book_skip[key] <= 0:
                    del self._sem_book_skip[key]

            for i_manu, key in enumerate(list(sem_detalhes)):
                if i_manu % self._GIL_YIELD_INTERVAL == 0:
                    time.sleep(0)
                if "|" not in key:
                    continue
                if key in self._sem_book_skip:
                    continue
                ativo, cod_put = key.split("|", 1)
                inst = inst_map.get((ativo, cod_put))
                if not inst:
                    continue
                # Usa OVD (ask da put) e OCP (bid da call) como sinais de liquidez.
                # CAB isolado não é confiável para opções B3 (retorna > 0 mesmo sem book ativo).
                # Para OpenFAST (push-based), CAB não existe — usar call BID como proxy.
                c_put = self.source.ler_campos(inst.cod_put, FieldName.ASK, FieldName.BOOK_HEADER)
                c_call = self.source.ler_campos(inst.cod_call, FieldName.BID, FieldName.ASK, FieldName.BOOK_HEADER)
                ovd_put = c_put.get(FieldName.ASK)
                ocp_call = c_call.get(FieldName.BID)
                ovd_call = c_call.get(FieldName.ASK)
                cab_put = c_put.get(FieldName.BOOK_HEADER)
                cab_call = c_call.get(FieldName.BOOK_HEADER)
                tem_negocio = (
                    (ovd_put is not None and ovd_put > 0)
                    or (ovd_call is not None and ovd_call > 0)
                    or (ocp_call is not None and ocp_call > 0)
                )
                tem_book = ((cab_put is not None and cab_put > 0)
                            or (cab_call is not None and cab_call > 0))
                if not (tem_negocio or tem_book):
                    self._sem_book_skip[key] = self._MAX_SEM_BOOK_SKIP
                    continue
                if tem_negocio or tem_book:
                    self._chaves_com_book.add(key)
                    dte = inst.dias_ate_vencimento or 0
                    if self._onda2_dte_min <= dte <= self._onda2_dte_max and count_reg < MAX_REG_ONDA2:
                        self._registrar_detalhes_completos(inst, buffer_onda2)
                        count_reg += 1
                        if count_reg >= MAX_REG_ONDA2:
                            break
        finally:
            self._lock.unlock()

        # Flush fora do lock — chamadas COM ConnectData lentas (5k+ chamadas, 2-10ms cada)
        if buffer_onda2:
            self._flush_buffer(buffer_onda2)

        # Prioridades e background scan precisam do lock
        buffer_bg: list[tuple[str, FieldName]] = []
        self._lock.lock()
        try:
            if self._prioridade_set:
                buffer_bg = self._registrar_novos_entrantes()
            if self._chaves_com_book and self._chaves_com_book != self._prioridade_salva:
                self._salvar_prioridades()
        finally:
            self._lock.unlock()

        # Flush do background scan fora do lock (COM ConnectData lento)
        if buffer_bg:
            self._flush_buffer(buffer_bg)

    def get_engine_stats(self) -> dict:
        """Retorna contagens internas para o Dashboard de Performance."""
        self._lock.lock()
        try:
            agora = time.time()
            segundos_desde_refresh = int(agora - self._ultimo_refresh_timestamp) if self._ultimo_refresh_timestamp > 0 else -1
            dados_stale = self._ciclos_sem_dados > 3 or segundos_desde_refresh > 30
            return {
                "total": self._total_instrumentos_cache,
                "onda1": len(self._chaves_registradas),
                "onda2": len(self._chaves_detalhes_completos),
                "registrado": self._registrado,
                "progresso_idx": len(self._chaves_registradas),
                "dados_stale": dados_stale,
                "ultimo_refresh_ha_segundos": segundos_desde_refresh,
                "ciclos_sem_dados": self._ciclos_sem_dados,
                "stale_skip": self._cont_stale_skip,
                "no_new_update": getattr(self.source, 'cont_no_new_update', 0),
            }
        finally:
            self._lock.unlock()

    def _ler_instrumento_cache(self, inst: InstrumentoOpcional, preco_ativo: float | None) -> DadosRTDInstrumento | None:
        rtd = self.source

        # Batch reads: 1 lock por símbolo em vez de 1 por campo
        c_put = self._ler_campos(inst.cod_put,
            FieldName.ASK, FieldName.BID, FieldName.STRIKE,
            FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_ASK)
        c_call = self._ler_campos(inst.cod_call,
            FieldName.ASK, FieldName.BID, FieldName.STRIKE,
            FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_BID)
        c_ativo = self._ler_campos(inst.ativo, FieldName.ASK, FieldName.BID)

        of_venda_put = c_put.get(FieldName.ASK)
        of_compra_put = c_put.get(FieldName.BID)
        of_venda_call = c_call.get(FieldName.ASK)
        of_compra_call = c_call.get(FieldName.BID)

        if not of_venda_put and not of_compra_put and not of_venda_call and not of_compra_call:
            return None

        strike_rtd = inst.strike if getattr(rtd, 'suporta_push', False) else None
        if not strike_rtd or strike_rtd <= 0:
            strike_rtd = c_put.get(FieldName.STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            strike_rtd = c_call.get(FieldName.STRIKE)

        if not strike_rtd or strike_rtd <= 0:
            return None

        of_venda_ativo = c_ativo.get(FieldName.ASK)
        of_compra_ativo = c_ativo.get(FieldName.BID)

        status_put = rtd.ler_status_cache(inst.cod_put)
        status_call = rtd.ler_status_cache(inst.cod_call)
        status_ativo = rtd.ler_status_cache(inst.ativo)

        return DadosRTDInstrumento(
            ativo=inst.ativo,
            cod_put=inst.cod_put,
            cod_call=inst.cod_call,
            preco_ativo=preco_ativo,
            strike=strike_rtd,
            vencimento_rtd=inst.vencimento.isoformat(),
            of_compra_ativo=of_compra_ativo,
            of_venda_ativo=of_venda_ativo,
            of_venda_put=of_venda_put,
            of_compra_put=of_compra_put,
            of_venda_call=of_venda_call,
            of_compra_call=of_compra_call,
            status_put=status_put,
            status_call=status_call,
            status_ativo=status_ativo,
            cab_put=c_put.get(FieldName.BOOK_HEADER),
            qul_put=c_put.get(FieldName.QTD_LAST),
            vov_put=c_put.get(FieldName.VOL_ASK),
            cab_call=c_call.get(FieldName.BOOK_HEADER),
            qul_call=c_call.get(FieldName.QTD_LAST),
            voc_call=c_call.get(FieldName.VOL_BID),
        )
