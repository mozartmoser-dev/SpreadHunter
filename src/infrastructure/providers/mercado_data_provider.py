import logging
import os
import time
from datetime import date
from PySide6.QtCore import QMutex

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.market_data_source import FieldName, MarketDataSource
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
from src.infrastructure.providers.rtd_config import DadosRTDInstrumento

logger = logging.getLogger(__name__)


class MercadoDataProvider:
    SEM_BOOK_SKIP_CYCLES = 6
    SEM_ATIVO_SKIP_CYCLES = 10
    _GIL_YIELD_INTERVAL = 100

    _CAMPOS_PUT = [FieldName.STRIKE, FieldName.ASK, FieldName.BID,
                   FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_ASK, FieldName.VOL_BID]
    _CAMPOS_CALL = [FieldName.STRIKE, FieldName.ASK, FieldName.BID,
                    FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_BID]

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
        self._inst_map_cache: dict | None = None
        self._inst_map_cache_time: float = 0.0
        self._INST_MAP_CACHE_TTL: float = 30.0
        self.recarregar_parametros()

    def _resolver_caminho_prioridade(self) -> str:
        if self.db_path:
            base = os.path.splitext(str(self.db_path))[0]
            return os.path.abspath(base + "_prioridade.json")
        return os.path.abspath("rtd_prioridade.json")

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
            self._cab_anterior.clear()
            self._dados_cache.clear()
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
        
        # Se houve mudança em parâmetros que afetam a carga, agendamos uma revisão de carga
        if self._registrado:
            # Reseta flags para re-escancar o banco, mas MANTÉM tudo o que já estava registrado
            self._registrado = False
            self._registro_idx = 0
            # Limpa cache de preços + books + Onda 2 para forçar re-detecção completa
            self._precos_ativo_cache.clear()
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
        registros = [
            (inst.cod_put, campo) for campo in self._CAMPOS_PUT
            if campo != FieldName.BOOK_HEADER
        ] + [
            (inst.cod_call, campo) for campo in self._CAMPOS_CALL
            if campo != FieldName.BOOK_HEADER
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
            self._precos_ativo_cache[inst.ativo] = preco
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
        if key in self._chaves_registradas:
            return False

        if self._deve_pular_instrumento(inst):
            self._chaves_registradas.add(key)
            return False

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
                        if rtd_raw is not None:
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
                    if rtd_raw is not None:
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
                (inst.cod_call, FieldName.BID),
            ]

        if inst.ativo not in self._ativos_registrados:
            registros += [
                (inst.ativo, FieldName.LAST_PRICE),
                (inst.ativo, FieldName.ASK),
                (inst.ativo, FieldName.BID),
                (inst.ativo, FieldName.STATUS),
            ]
            self._ativos_registrados.add(inst.ativo)

        if registros_acum is not None:
            registros_acum.extend(registros)
        else:
            rtd.registrar_lista(registros)
        self._chaves_registradas.add(key)
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
                            c_ativo = self.source.ler_campos(inst.ativo, FieldName.ASK, FieldName.BID)
                            c_put = self.source.ler_campos(inst.cod_put, FieldName.ASK, FieldName.BID, FieldName.VOL_ASK, FieldName.QTD_LAST)
                            c_call = self.source.ler_campos(inst.cod_call, FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.QTD_LAST)
                            p_ativo = c_ativo.get(FieldName.ASK)
                            if p_ativo is not None and p_ativo > 0:
                                entry["preco_ativo"] = p_ativo
                                entry["of_venda_ativo"] = p_ativo
                                self._precos_ativo_cache[inst.ativo] = p_ativo
                            else:
                                p_ativo = self._precos_ativo_cache.get(inst.ativo)
                                if p_ativo:
                                    entry["preco_ativo"] = p_ativo
                                    entry["of_venda_ativo"] = p_ativo
                            of_compra = c_ativo.get(FieldName.BID)
                            if of_compra is not None:
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
                            dados_mercado[key] = entry
                            count_cab_skip += 1
                            continue

                        if cab_skip_habilitado:
                            self._cab_anterior[key] = (cab_put, cab_call)

                        preco_ativo_rtd = self.source.ler_campo_cache(inst.ativo, FieldName.ASK)
                        if preco_ativo_rtd is not None and preco_ativo_rtd > 0:
                            preco_ativo = preco_ativo_rtd
                            self._precos_ativo_cache[inst.ativo] = preco_ativo
                        else:
                            preco_ativo = self._precos_ativo_cache.get(inst.ativo)

                        if not preco_ativo or preco_ativo <= 0:
                            if inst.ativo in self._sem_ativo_skip:
                                count_sem_preco += 1
                                continue
                            sem_ativo_atual[inst.ativo] = self.SEM_ATIVO_SKIP_CYCLES
                            count_sem_preco += 1
                            continue

                        dados_rtd = self._ler_instrumento_cache(inst, preco_ativo)
                        if dados_rtd:
                            entry = dados_rtd.to_dados_mercado()
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
                    ocp = self.source.ler_campo_cache(inst.cod_call, FieldName.BID)
                    ovd = self.source.ler_campo_cache(inst.cod_put, FieldName.ASK)
                    if not ocp:
                        continue
                    preco_ativo_rtd = self.source.ler_campo_cache(inst.ativo, FieldName.ASK)
                    if preco_ativo_rtd is not None and preco_ativo_rtd > 0:
                        preco_ativo = preco_ativo_rtd
                        self._precos_ativo_cache[inst.ativo] = preco_ativo
                    else:
                        preco_ativo = self._precos_ativo_cache.get(inst.ativo)
                    if not preco_ativo or preco_ativo <= 0:
                        continue
                    entry = {
                        "preco_ativo": preco_ativo,
                        "strike_rtd": strike_put,
                        "of_compra_ativo": self.source.ler_campo_cache(inst.ativo, FieldName.BID) or 0.0,
                        "of_venda_ativo": preco_ativo,
                        "of_compra_call": ocp,
                        "of_venda_put": ovd,
                        "premio_call": ocp,
                        "premio_put": ovd,
                        "of_compra_put": self.source.ler_campo_cache(inst.cod_put, FieldName.BID) or 0.0,
                        "of_venda_call": self.source.ler_campo_cache(inst.cod_call, FieldName.ASK) or 0.0,
                        "qul_put": 0,
                        "qul_call": 0,
                        "vov_put": 0,
                        "voc_call": 0,
                        "em_leilao": False,
                        "status_put": self.source.ler_status_cache(inst.cod_put) or "aberto",
                        "status_call": self.source.ler_status_cache(inst.cod_call) or "aberto",
                        "status_ativo": self.source.ler_status_cache(inst.ativo) or "aberto",
                    }
                    dados_mercado[key] = entry
                    t_onda1_basico += time.perf_counter() - t0_onda1
                    count_onda1 += 1

                t_varredura = time.perf_counter() - t_scan0
                self._sem_ativo_skip = sem_ativo_atual

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
            }
        finally:
            self._lock.unlock()

    def _ler_instrumento_cache(self, inst: InstrumentoOpcional, preco_ativo: float | None) -> DadosRTDInstrumento | None:
        rtd = self.source

        # Batch reads: 1 lock por símbolo em vez de 1 por campo
        c_put = rtd.ler_campos(inst.cod_put,
            FieldName.ASK, FieldName.BID, FieldName.STRIKE,
            FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_ASK)
        c_call = rtd.ler_campos(inst.cod_call,
            FieldName.ASK, FieldName.BID, FieldName.STRIKE,
            FieldName.BOOK_HEADER, FieldName.QTD_LAST, FieldName.VOL_BID)
        c_ativo = rtd.ler_campos(inst.ativo, FieldName.ASK, FieldName.BID)

        of_venda_put = c_put.get(FieldName.ASK)
        of_compra_put = c_put.get(FieldName.BID)
        of_venda_call = c_call.get(FieldName.ASK)
        of_compra_call = c_call.get(FieldName.BID)

        if not of_venda_put and not of_compra_put and not of_venda_call and not of_compra_call:
            return None

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
