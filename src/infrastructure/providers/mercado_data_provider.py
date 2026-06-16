import logging
import time
from datetime import date
from PySide6.QtCore import QMutex

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.infrastructure.importers.excel_importer import extrair_strike, sanitizar_strike
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
from src.infrastructure.providers.rtd_config import (
    RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_STRIKE,
    RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
    RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_QTDE_ULT_NEG,
    RTD_CAMPO_VOL_VENDA, RTD_CAMPO_VOL_COMPRA,
    DadosRTDInstrumento,
)
from src.infrastructure.providers.rtd_profit import RTDProfit

logger = logging.getLogger(__name__)


class MercadoDataProvider:
    SEM_BOOK_SKIP_CYCLES = 6
    SEM_ATIVO_SKIP_CYCLES = 10

    _CAMPOS_PUT = [RTD_CAMPO_STRIKE, RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
                   RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_QTDE_ULT_NEG, RTD_CAMPO_VOL_VENDA]
    _CAMPOS_CALL = [RTD_CAMPO_STRIKE, RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
                    RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_QTDE_ULT_NEG, RTD_CAMPO_VOL_COMPRA]

    def __init__(self, db_path=None, rtd: RTDProfit | None = None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.rtd = rtd or RTDProfit()
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
        self._prioridade_set: set[str] = self._carregar_prioridades()
        self._prioridade_salva: set[str] = set()
        self._caminho_prioridade = self._resolver_caminho_prioridade()
        self._cab_anterior: dict[str, tuple[float | None, float | None]] = {}
        self._dados_cache: dict[str, dict] = {}
        self._onda2_dte_min: int = 7
        self._onda2_dte_max: int = 180
        self.recarregar_parametros()

    def _resolver_caminho_prioridade(self) -> str:
        if self.db_path:
            import os
            base = os.path.splitext(str(self.db_path))[0]
            return os.path.abspath(base + "_prioridade.json")
        return os.path.abspath("rtd_prioridade.json")

    def _carregar_prioridades(self) -> set[str]:
        try:
            import json, os
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
            # Salva apenas quem tem dados reais de mercado (passou _ler_instrumento_cache)
            chaves = list(self._dados_cache.keys())
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
            self._precos_ativo_cache.clear()
            self._cab_anterior.clear()
            self._dados_cache.clear()
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

    def _registrar_ativos_prioritarios(self, instrumentos: list[InstrumentoOpcional]):
        """Registra apenas os ativos (underlyings) para obter preços de referência rápido."""
        rtd = self.rtd
        t0 = time.perf_counter()
        count = 0
        for inst in instrumentos:
            if inst.ativo not in self._ativos_registrados:
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_OFERTA_VENDA)
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_OFERTA_COMPRA)
                rtd.registrar_status(inst.ativo)
                self._ativos_registrados.add(inst.ativo)
                count += 1
        if count > 0:
            logger.info("RTD: %d ativos registrados prioritariamente em %.2fs.", count, time.perf_counter() - t0)

    def _registrar_detalhes_completos(self, inst: InstrumentoOpcional):
        """Registra todos os campos de um instrumento quando detectamos liquidez."""
        key = inst.cod_put
        if key in self._chaves_detalhes_completos:
            return
        
        rtd = self.rtd
        # Campos de PUT
        for campo in self._CAMPOS_PUT:
            if campo != RTD_CAMPO_CABECALHO_BOOK: # Já registrado na onda 1
                rtd.registrar_topico(inst.cod_put, campo)
        # Campos de CALL
        for campo in self._CAMPOS_CALL:
            if campo != RTD_CAMPO_CABECALHO_BOOK:
                rtd.registrar_topico(inst.cod_call, campo)
        
        rtd.registrar_status(inst.cod_put)
        rtd.registrar_status(inst.cod_call)
        
        self._chaves_detalhes_completos.add(key)
        logger.debug("RTD: Detalhes completos registrados para %s (Liquidez detectada)", key)

    def forcar_refresh_ex_dividendo(self, ativos_ex: list[str]):
        """Forca registro completo (Wave 2) para ativos em dia ex-dividendo.
        Invalida o cache RTD e re-registra todos os topicos para garantir
        que o sistema busque dados frescos do servidor, essencial para
        capturar ajustes de strike e preco pos-dividendo."""
        if not ativos_ex or not self.rtd.disponivel:
            return

        inst_map = self.inst_repo.get_all_mapped()
        ativos_registrados = set()
        count = 0

        for key, inst in inst_map.items():
            if inst.ativo in ativos_ex and inst.ativo not in ativos_registrados:
                for campo in (RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA):
                    self.rtd.invalidar_cache(inst.ativo, campo)
                    self.rtd.registrar_topico(inst.ativo, campo)
                self.rtd.invalidar_cache(inst.ativo, "EST")
                self.rtd.registrar_status(inst.ativo)
                ativos_registrados.add(inst.ativo)

            if inst.ativo in ativos_ex:
                campos_put = [RTD_CAMPO_STRIKE, RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
                              RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_QTDE_ULT_NEG, RTD_CAMPO_VOL_VENDA]
                campos_call = [RTD_CAMPO_STRIKE, RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
                               RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_QTDE_ULT_NEG, RTD_CAMPO_VOL_COMPRA]

                for campo in campos_put:
                    self.rtd.invalidar_cache(inst.cod_put, campo)
                    self.rtd.registrar_topico(inst.cod_put, campo)
                for campo in campos_call:
                    self.rtd.invalidar_cache(inst.cod_call, campo)
                    self.rtd.registrar_topico(inst.cod_call, campo)

                self.rtd.invalidar_cache(inst.cod_put, "EST")
                self.rtd.registrar_status(inst.cod_put)
                self.rtd.invalidar_cache(inst.cod_call, "EST")
                self.rtd.registrar_status(inst.cod_call)
                
                self._chaves_registradas.add(key)
                self._chaves_detalhes_completos.add(key)
                self._chaves_com_book.add(key)
                self._cab_anterior.pop(key, None)
                self._dados_cache.pop(key, None)
                count += 1

        if count > 0:
            logger.info("RTD: Refresh forcado para %d instrumentos de %d ativos ex-dividendo.", count, len(ativos_registrados))

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
        strike_val = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_STRIKE)
        if not strike_val or strike_val <= 0:
            return False
        preco = self.rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
        if not preco or preco <= 0:
            return False
        ratio = (strike_val / preco) - 1
        return ratio < self._range_min or ratio > self._range_max

    def _registrar_instrumento(self, inst: InstrumentoOpcional):
        rtd = self.rtd
        key = inst.cod_put
        if key in self._chaves_registradas:
            return False

        if self._deve_pular_instrumento(inst):
            self._chaves_registradas.add(key)
            return False

        rtd.registrar_topico(inst.cod_put, RTD_CAMPO_STRIKE)
        rtd.registrar_topico(inst.cod_call, RTD_CAMPO_STRIKE)

        if not self._deve_pular_por_strike(inst):
            rtd.registrar_topico(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK)
            rtd.registrar_topico(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK)
            rtd.registrar_topico(inst.cod_put, RTD_CAMPO_OFERTA_VENDA)
            rtd.registrar_topico(inst.cod_call, RTD_CAMPO_OFERTA_COMPRA)

        if inst.ativo not in self._ativos_registrados:
            rtd.registrar_topico(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
            rtd.registrar_topico(inst.ativo, RTD_CAMPO_OFERTA_VENDA)
            rtd.registrar_topico(inst.ativo, RTD_CAMPO_OFERTA_COMPRA)
            rtd.registrar_status(inst.ativo)
            self._ativos_registrados.add(inst.ativo)

        self._chaves_registradas.add(key)
        return True

    def _registrar_batch_inteligente(self, instrumentos: list[InstrumentoOpcional], batch_size: int = 2000):
        if self._registrado:
            return

        t0 = time.perf_counter()
        start_idx = self._registro_idx
        end_idx = min(start_idx + batch_size, len(instrumentos))
        
        count_processados = 0
        count_pulas = 0

        for i in range(start_idx, end_idx):
            inst = instrumentos[i]
            if self._registrar_instrumento(inst):
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

    def _registrar_novos_entrantes(self):
        instrumentos = self.inst_repo.get_all()
        total = len(instrumentos)
        if self._registro_remaining_idx >= total:
            self._registro_remaining_idx = self._background_offset

        batch = 500
        start = self._registro_remaining_idx
        end = min(start + batch, total)
        count = 0

        for i in range(start, end):
            inst = instrumentos[i]
            if self._registrar_instrumento(inst):
                count += 1

        self._registro_remaining_idx = end
        if count > 0:
            logger.info("Background scan: %d novos instrumentos registrados", count)
        if self._registro_remaining_idx >= total:
            self._registro_remaining_idx = self._background_offset
            logger.info("Background scan: ciclo completo. Total monitorados: %d", len(self._chaves_registradas))

    def capturar_dados_mercado(self) -> dict[str, dict]:
        if not self.rtd.disponivel:
            logger.warning("RTD nao disponivel — retornando dados vazios.")
            return {}

        self._lock.lock()
        try:
            try:
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
                            prio = [inst for inst in instrumentos if inst.cod_put in self._prioridade_set]
                            self._registrar_batch_inteligente(prio, batch_size=2000)
                            if self._registrado:
                                self._background_offset = len(prio)
                                self._registro_remaining_idx = len(prio)
                                logger.info("Onda 1 prioritária concluída: %d instrumentos monitorados. Background scan ativo para novos entrantes.", len(self._chaves_registradas))
                        else:
                            self._registrar_batch_inteligente(instrumentos, batch_size=2000)
                # Força refresh logo após Onda 1 completa pra garantir dados reais do servidor
                if self._registrado and not getattr(self, '_refresh_pos_onda1', False):
                    self._refresh_pos_onda1 = True
                    logger.info("Onda 1 concluída — forçando refresh inicial...")
                    try:
                        self.rtd.refresh(self._rtd_refresh_timeout_ms)
                    except Exception:
                        pass
                t_registro = time.perf_counter() - t_reg

                t0 = time.perf_counter()
                try:
                    self.rtd.refresh(self._rtd_refresh_timeout_ms)
                except Exception as e:
                    logger.error("RTD refresh escapou: %s", e, exc_info=True)
                    return {}
                t_refresh = time.perf_counter() - t0
                t_scan0 = time.perf_counter()
                self._scan_count += 1
                self._ultimo_refresh_timestamp = time.time()

                dados_mercado: dict[str, dict] = {}
                sem_ativo_atual: dict[str, int] = {}

                inst_map = self.inst_repo.get_all_mapped()

                for key in list(self._chaves_com_book):
                    inst = inst_map.get(key)
                    if not inst:
                        continue

                    if key in self._chaves_detalhes_completos:
                        cab_put = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK)
                        cab_call = self.rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK)
                        cab_prev = self._cab_anterior.get(key)
                        cab_mudou = cab_prev is None or cab_prev[0] != cab_put or cab_prev[1] != cab_call

                        if not cab_mudou and key in self._dados_cache:
                            entry = self._dados_cache[key]
                            entry["status_put"] = self.rtd.ler_status_cache(inst.cod_put)
                            entry["status_call"] = self.rtd.ler_status_cache(inst.cod_call)
                            entry["status_ativo"] = self.rtd.ler_status_cache(inst.ativo)
                            entry["em_leilao"] = not (
                                entry["status_put"].lower() == "aberto"
                                and entry["status_call"].lower() == "aberto"
                                and entry["status_ativo"].lower() == "aberto"
                            )
                            dados_mercado[key] = entry
                            continue

                        self._cab_anterior[key] = (cab_put, cab_call)

                        preco_ativo = self._precos_ativo_cache.get(inst.ativo)
                        if preco_ativo is None:
                            preco_ativo = self.rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                            if not preco_ativo or preco_ativo <= 0:
                                if inst.ativo in self._sem_ativo_skip:
                                    continue
                                sem_ativo_atual[inst.ativo] = self.SEM_ATIVO_SKIP_CYCLES
                                continue
                            self._precos_ativo_cache[inst.ativo] = preco_ativo

                        dados_rtd = self._ler_instrumento_cache(inst, preco_ativo)
                        if dados_rtd:
                            entry = dados_rtd.to_dados_mercado()
                            dados_mercado[key] = entry
                            self._dados_cache[key] = entry
                        else:
                            self._dados_cache.pop(key, None)
                        continue

                    # Onda 1: dados basicos para collars (strike + OCP/OVD)
                    strike_put = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_STRIKE)
                    if not strike_put or strike_put <= 0:
                        strike_put = self.rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_STRIKE)
                    if not strike_put or strike_put <= 0:
                        continue
                    ocp = self.rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_COMPRA)
                    ovd = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_VENDA)
                    if not ocp or not ovd:
                        continue
                    preco_ativo = self._precos_ativo_cache.get(inst.ativo)
                    if not preco_ativo or preco_ativo <= 0:
                        preco_ativo = self.rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                        if not preco_ativo or preco_ativo <= 0:
                            continue
                        self._precos_ativo_cache[inst.ativo] = preco_ativo
                    entry = {
                        "preco_ativo": preco_ativo,
                        "strike_rtd": strike_put,
                        "of_compra_call": ocp,
                        "of_venda_put": ovd,
                        "of_compra_put": self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_COMPRA) or 0.0,
                        "of_venda_call": self.rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_VENDA) or 0.0,
                        "qul_put": 0,
                        "qul_call": 0,
                        "vov_put": 0,
                        "voc_call": 0,
                        "em_leilao": False,
                        "status_put": self.rtd.ler_status_cache(inst.cod_put) or "aberto",
                        "status_call": self.rtd.ler_status_cache(inst.cod_call) or "aberto",
                        "status_ativo": self.rtd.ler_status_cache(inst.ativo) or "aberto",
                    }
                    dados_mercado[key] = entry

                t_varredura = time.perf_counter() - t_scan0
                self._sem_ativo_skip = sem_ativo_atual

                if dados_mercado:
                    self._ciclos_sem_dados = 0
                else:
                    self._ciclos_sem_dados += 1
                t_total = time.perf_counter() - t0 - t_registro
                logger.info("Varredura: %d monitored, %d with book | registro=%.3fs refresh=%.3fs scan=%.3fs total=%.3fs",
                             len(self._chaves_registradas), len(dados_mercado),
                             t_registro, t_refresh, t_varredura, t_total)
                return dados_mercado
            except Exception as e:
                logger.error("capturar_dados_mercado: erro inesperado: %s", e, exc_info=True)
                return {}
        finally:
            self._lock.unlock()

    def fazer_manutencao(self):
        """Detecta novos books, registra Onda 2, background scan e salva prioridades.
        Executado externamente (MonitorWorker), fora da varredura principal."""
        self._lock.lock()
        try:
            inst_map = self.inst_repo.get_all_mapped()
            sem_detalhes = self._chaves_registradas - self._chaves_detalhes_completos
            count_reg = 0
            MAX_REG_ONDA2 = 500

            for key in list(sem_detalhes):
                inst = inst_map.get(key)
                if not inst:
                    continue
                # Usa OVD (ask da put) como sinal primário de liquidez real.
                # CAB isolado não é confiável para opções B3 (retorna > 0 mesmo sem book ativo).
                ovd_put = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_VENDA)
                cab_put = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK)
                cab_call = self.rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK)
                tem_negocio = (ovd_put is not None and ovd_put > 0)
                tem_book = (cab_put is not None and cab_put > 0) or (cab_call is not None and cab_call > 0)
                if tem_negocio or tem_book:
                    self._chaves_com_book.add(key)
                    dte = inst.dias_ate_vencimento or 0
                    if self._onda2_dte_min <= dte <= self._onda2_dte_max and count_reg < MAX_REG_ONDA2:
                        self._registrar_detalhes_completos(inst)
                        count_reg += 1

            if self._prioridade_set:
                self._registrar_novos_entrantes()

            if self._chaves_com_book and self._chaves_com_book != self._prioridade_salva:
                self._salvar_prioridades()

            # NÃO limpa _precos_ativo_cache aqui — isso força re-leitura de todos os ativos
            # a cada ~5s, causando "no_preco" em massa. Staleness é gerenciada pelo RefreshData(0).
        finally:
            self._lock.unlock()

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
                "progresso_idx": self._registro_idx,
                "dados_stale": dados_stale,
                "ultimo_refresh_ha_segundos": segundos_desde_refresh,
                "ciclos_sem_dados": self._ciclos_sem_dados,
            }
        finally:
            self._lock.unlock()

    def _ler_instrumento_cache(self, inst: InstrumentoOpcional, preco_ativo: float | None) -> DadosRTDInstrumento | None:
        rtd = self.rtd

        of_venda_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_VENDA)
        of_compra_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_COMPRA)
        of_venda_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_VENDA)
        of_compra_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_COMPRA)

        if not of_venda_put and not of_compra_put and not of_venda_call and not of_compra_call:
            return None

        # Prioridade Única: RTD (Garantido pelo Profit)
        strike_rtd = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            strike_rtd = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_STRIKE)
        
        if not strike_rtd or strike_rtd <= 0:
            return None # Sem strike real, não calculamos para evitar erro

        of_venda_ativo = rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_OFERTA_VENDA)
        of_compra_ativo = rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_OFERTA_COMPRA)

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
            cab_put=rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK),
            qul_put=rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_QTDE_ULT_NEG),
            vov_put=rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_VOL_VENDA),
            cab_call=rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK),
            qul_call=rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_QTDE_ULT_NEG),
            voc_call=rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_VOL_COMPRA),
        )
