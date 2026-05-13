import logging
import time

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.infrastructure.importers.excel_importer import extrair_strike
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
        self._sem_book_skip: dict[str, int] = {}
        self._sem_ativo_skip: dict[str, int] = {}
        self._precos_ativo_cache: dict[str, float] = {}
        self._scan_count = 0

    def _registrar_todos(self, instrumentos: list[InstrumentoOpcional]):
        rtd = self.rtd
        ativos_registrados: set[str] = set()
        t0 = time.perf_counter()

        for inst in instrumentos:
            for campo in self._CAMPOS_PUT:
                rtd.registrar_topico(inst.cod_put, campo)
            for campo in self._CAMPOS_CALL:
                rtd.registrar_topico(inst.cod_call, campo)
            rtd.registrar_status(inst.cod_put)
            rtd.registrar_status(inst.cod_call)
            if inst.ativo not in ativos_registrados:
                rtd.registrar_topico(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                rtd.registrar_status(inst.ativo)
                ativos_registrados.add(inst.ativo)

        self._registrado = True
        logger.info("RTD: %d topicos registrados em %.2fs.",
                     len(rtd._topic_map), time.perf_counter() - t0)

    def capturar_dados_mercado(self) -> dict[str, dict]:
        if not self.rtd.disponivel:
            logger.warning("RTD nao disponivel — retornando dados vazios.")
            return {}

        instrumentos = self.inst_repo.get_all()
        logger.info("capturar_dados_mercado: %d instrumentos na base.", len(instrumentos))

        if not self._registrado:
            self._registrar_todos(instrumentos)

        t0 = time.perf_counter()
        self.rtd.refresh()
        self._scan_count += 1
        if self._scan_count % 10 == 0:
            self._precos_ativo_cache.clear()

        dados_mercado: dict[str, dict] = {}
        sem_book_atual: dict[str, int] = {}
        sem_ativo_atual: dict[str, int] = {}

        for inst in instrumentos:
            key = inst.cod_put
            if key in dados_mercado:
                continue

            skip_ativo = self._sem_ativo_skip.get(inst.ativo, 0)
            if skip_ativo > 0:
                sem_ativo_atual[inst.ativo] = skip_ativo - 1
                continue

            preco_ativo = self._precos_ativo_cache.get(inst.ativo)
            if preco_ativo is None:
                preco_ativo = self.rtd.ler_campo_cache(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                if not preco_ativo or preco_ativo <= 0:
                    preco_ativo = self.rtd.ler_campo(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                    if not preco_ativo or preco_ativo <= 0:
                        sem_ativo_atual[inst.ativo] = self.SEM_ATIVO_SKIP_CYCLES
                        continue
                self._precos_ativo_cache[inst.ativo] = preco_ativo

            skip = self._sem_book_skip.get(key, 0)
            if skip > 0:
                self._sem_book_skip[key] = skip - 1
                sem_book_atual[key] = skip - 1
                continue

            dados_rtd = self._ler_instrumento_cache(inst, preco_ativo)
            if dados_rtd and dados_rtd.preco_ativo and dados_rtd.preco_ativo > 0:
                dados_mercado[key] = dados_rtd.to_dados_mercado()
            else:
                sem_book_atual[key] = self.SEM_BOOK_SKIP_CYCLES

        self._sem_book_skip = sem_book_atual
        self._sem_ativo_skip = sem_ativo_atual
        logger.info("MercadoDataProvider: %d chaves (de %d) em %.2fs. pulados=%d sem_ativo=%d",
                     len(dados_mercado), len(instrumentos), time.perf_counter() - t0,
                     len(sem_book_atual), len(sem_ativo_atual))
        return dados_mercado

    def _ler_instrumento_cache(self, inst: InstrumentoOpcional, preco_ativo: float | None) -> DadosRTDInstrumento | None:
        rtd = self.rtd

        of_venda_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_VENDA)
        of_compra_put = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_OFERTA_COMPRA)
        of_venda_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_VENDA)
        of_compra_call = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_OFERTA_COMPRA)

        if not of_venda_put and not of_compra_put and not of_venda_call and not of_compra_call:
            return None

        strike_rtd = rtd.ler_campo_cache(inst.cod_put, RTD_CAMPO_STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            strike_rtd = rtd.ler_campo_cache(inst.cod_call, RTD_CAMPO_STRIKE)
        if not strike_rtd or strike_rtd <= 0:
            strike_rtd = extrair_strike(inst.cod_put) or extrair_strike(inst.cod_call)

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
