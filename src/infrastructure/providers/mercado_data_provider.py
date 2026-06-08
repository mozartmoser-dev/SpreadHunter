import logging
import time
from datetime import date
from PyQt5.QtCore import QMutex

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
        self._lock = QMutex()
        self.recarregar_parametros()

    def recarregar_instrumentos(self):
        """Limpa as flags de cache e força o re-registro dos instrumentos no RTD."""
        self._lock.lock()
        try:
            self._registrado = False
            self._registro_idx = 0
            self._ativos_registrados.clear()
            self._chaves_registradas.clear()
            self._chaves_com_book.clear()
            self._chaves_detalhes_completos.clear()
            self._sem_ativo_skip.clear()
            self._precos_ativo_cache.clear()
            self.recarregar_parametros()
            logger.info("MercadoDataProvider: recarregamento de instrumentos agendado.")
        finally:
            self._lock.unlock()

    def recarregar_parametros(self):
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        repo = ParametroRepository(self.db_path)
        
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
        
        # Se houve mudança em parâmetros que afetam a carga, agendamos uma revisão de carga
        if self._registrado:
            # Ao resetar apenas estas duas flags, o sistema re-escaneia o banco em background
            # mas MANTÉM tudo o que já estava registrado (não desconecta nada).
            self._registrado = False
            self._registro_idx = 0
            # Limpa o cache de preços para forçar leitura limpa
            self._precos_ativo_cache.clear()
            self._chaves_com_book.clear()
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
                count += 1

        if count > 0:
            logger.info("RTD: Refresh forcado para %d instrumentos de %d ativos ex-dividendo.", count, len(ativos_registrados))

    def _registrar_batch_inteligente(self, instrumentos: list[InstrumentoOpcional], batch_size: int = 2000):
        if self._registrado:
            return

        rtd = self.rtd
        t0 = time.perf_counter()
        start_idx = self._registro_idx
        end_idx = min(start_idx + batch_size, len(instrumentos))
        
        count_processados = 0
        count_pulas = 0

        for i in range(start_idx, end_idx):
            inst = instrumentos[i]
            key = inst.cod_put
            
            if key in self._chaves_registradas:
                continue

            # Filtros de Proximidade (Carga Inteligente)
            if self._carga_inteligente_habilitada:
                hoje = date.today()
                if self._dias_minimos > 0 and inst.vencimento:
                    if (inst.vencimento - hoje).days < self._dias_minimos:
                        count_pulas += 1
                        continue
                if self._limite_meses > 0 and inst.vencimento:
                    if (inst.vencimento - hoje).days > (self._limite_meses * 30):
                        count_pulas += 1
                        continue

            # ONDA 1: Registra o strike e o cabeçalho para detecção (sempre, independente da Carga Inteligente)
            rtd.registrar_topico(inst.cod_put, RTD_CAMPO_STRIKE)
            rtd.registrar_topico(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK)
            rtd.registrar_topico(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK)
            
            if inst.ativo not in self._ativos_registrados:
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_OFERTA_VENDA)
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_OFERTA_COMPRA)
                rtd.registrar_status(inst.ativo)
                self._ativos_registrados.add(inst.ativo)
            
            self._chaves_registradas.add(key)
            count_processados += 1

        self._registro_idx = end_idx

        if self._registro_idx >= len(instrumentos):
            self._registrado = True
            logger.info("RTD: Onda 1 (Cabeçalhos) concluída. %d monitorados. (Pulos: %d)",
                         len(self._chaves_registradas), count_pulas)
        else:
            logger.info("RTD: Lote Onda 1 %d/%d (Registros: %d) em %.2fs.",
                         self._registro_idx, len(instrumentos), count_processados, time.perf_counter() - t0)

    def capturar_dados_mercado(self) -> dict[str, dict]:
        if not self.rtd.disponivel:
            logger.warning("RTD nao disponivel — retornando dados vazios.")
            return {}

        self._lock.lock()
        try:
            # Carrega a lista completa do banco apenas quando necessário
            # (evita ler 52k linhas do SQLite a cada ciclo)
            if not self._registrado or not self._ativos_registrados:
                instrumentos = self.inst_repo.get_all()
                self._total_instrumentos_cache = len(instrumentos)
                
                # Primeiro ciclo: registra apenas ativos para pegar preços base
                if not self._ativos_registrados:
                    self._registrar_ativos_prioritarios(instrumentos)

                # Registro em lotes com filtro de proximidade
                if not self._registrado:
                    self._registrar_batch_inteligente(instrumentos, batch_size=2000)

            t0 = time.perf_counter()
            self.rtd.refresh()
            self._scan_count += 1
            
            # Ciclo Global a cada 5 rodadas
            is_global_scan = (self._scan_count % 5 == 0)
            
            if self._scan_count % 10 == 0:
                self._precos_ativo_cache.clear()

            dados_mercado: dict[str, dict] = {}
            sem_ativo_atual: dict[str, int] = {}
            
            count_reg_onda2 = 0
            MAX_REG_ONDA2_PER_CYCLE = 500
            
            inst_map = self.inst_repo.get_all_mapped()
            chaves_alvo = self._chaves_registradas if is_global_scan else self._chaves_com_book

            for key in list(chaves_alvo):
                inst = inst_map.get(key)
                if not inst:
                    continue

                # 1. Se já temos detalhes completos, tentamos ler
                if key in self._chaves_detalhes_completos:
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
                        dados_mercado[key] = dados_rtd.to_dados_mercado()
                        self._chaves_com_book.add(key)
                    else:
                        if key in self._chaves_com_book:
                            self._chaves_com_book.remove(key)
                    continue

                # 2. Senão, checamos se ele "acordou" (tem book) para registrar na Onda 2
                cab_put = self.rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK)
                cab_call = self.rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK)
                
                if (cab_put and cab_put > 0) or (cab_call and cab_call > 0):
                    self._chaves_com_book.add(key)
                    dte = inst.dias_ate_vencimento or 0
                    if not (7 <= dte <= 180):
                        continue
                    if count_reg_onda2 < MAX_REG_ONDA2_PER_CYCLE:
                        self._registrar_detalhes_completos(inst)
                        count_reg_onda2 += 1

            self._sem_ativo_skip = sem_ativo_atual
            logger.info("Varredura (%s): %d monitored, %d with book in %.2fs",
                         "Global" if is_global_scan else "Fast",
                         len(self._chaves_registradas), len(dados_mercado),
                         time.perf_counter() - t0)
            return dados_mercado
        finally:
            self._lock.unlock()

    def get_engine_stats(self) -> dict:
        """Retorna contagens internas para o Dashboard de Performance."""
        self._lock.lock()
        try:
            return {
                "total": self._total_instrumentos_cache,
                "onda1": len(self._chaves_registradas),
                "onda2": len(self._chaves_detalhes_completos),
                "registrado": self._registrado,
                "progresso_idx": self._registro_idx
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

        status_put = rtd.ler_status_cache(inst.cod_put) or "Aberto"
        status_call = rtd.ler_status_cache(inst.cod_call) or "Aberto"
        status_ativo = rtd.ler_status_cache(inst.ativo) or "Aberto"

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
