import logging
from datetime import date

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.infrastructure.importers.excel_importer import extrair_strike
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
from src.infrastructure.providers.rtd_config import (
    RTD_CAMPO_ULTIMO_PRECO, RTD_CAMPO_STRIKE, RTD_CAMPO_VENCIMENTO,
    RTD_CAMPO_OFERTA_VENDA, RTD_CAMPO_OFERTA_COMPRA,
    RTD_CAMPO_CABECALHO_BOOK, RTD_CAMPO_QTDE_ULT_NEG,
    RTD_CAMPO_VOL_VENDA, RTD_CAMPO_VOL_COMPRA,
    DadosRTDInstrumento,
)
from src.infrastructure.providers.rtd_profit import RTDProfit

logger = logging.getLogger(__name__)


class MercadoDataProvider:
    def __init__(self, db_path=None, rtd: RTDProfit | None = None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.rtd = rtd or RTDProfit()

    def capturar_dados_mercado(self) -> dict[str, dict]:
        if not self.rtd.disponivel:
            logger.warning("RTD nao disponivel — retornando dados vazios.")
            return {}

        instrumentos = self.inst_repo.get_all()
        logger.info("capturar_dados_mercado: %d instrumentos na base.", len(instrumentos))
        precos_ativo_cache: dict[str, float | None] = {}
        dados_mercado: dict[str, dict] = {}

        for inst in instrumentos:
            key = inst.cod_put
            if key in dados_mercado:
                continue

            preco_ativo = precos_ativo_cache.get(inst.ativo)
            if preco_ativo is None:
                preco_ativo = self.rtd.ler_campo(inst.ativo, RTD_CAMPO_ULTIMO_PRECO)
                precos_ativo_cache[inst.ativo] = preco_ativo

            if not preco_ativo or preco_ativo <= 0:
                logger.debug("Sem preco para ativo %s — pulando.", inst.ativo)
                continue

            dados_rtd = self._ler_instrumento(inst, preco_ativo)
            if dados_rtd and dados_rtd.preco_ativo and dados_rtd.preco_ativo > 0:
                dados_mercado[key] = dados_rtd.to_dados_mercado()
                logger.debug("OK: %s | strike=%s ovd_put=%s ocp_call=%s", key, dados_rtd.strike, dados_rtd.of_venda_put, dados_rtd.of_compra_call)
            else:
                logger.debug("Sem dados RTD para %s (put=%s call=%s)", inst.cod_put, inst.cod_put, inst.cod_call)

        logger.info("MercadoDataProvider: %d chaves com dados de mercado (de %d instrumentos).", len(dados_mercado), len(instrumentos))
        return dados_mercado

    def _ler_instrumento(self, inst: InstrumentoOpcional, preco_ativo: float | None) -> DadosRTDInstrumento | None:
        rtd = self.rtd

        strike_rtd = rtd.ler_campo(inst.cod_put, RTD_CAMPO_STRIKE)
        if strike_rtd is None or strike_rtd <= 0:
            strike_rtd = rtd.ler_campo(inst.cod_call, RTD_CAMPO_STRIKE)
        if strike_rtd is None or strike_rtd <= 0:
            strike_rtd = extrair_strike(inst.cod_put)
        if strike_rtd is None or strike_rtd <= 0:
            strike_rtd = extrair_strike(inst.cod_call)

        of_venda_put = rtd.ler_campo(inst.cod_put, RTD_CAMPO_OFERTA_VENDA)
        of_compra_put = rtd.ler_campo(inst.cod_put, RTD_CAMPO_OFERTA_COMPRA)
        of_venda_call = rtd.ler_campo(inst.cod_call, RTD_CAMPO_OFERTA_VENDA)
        of_compra_call = rtd.ler_campo(inst.cod_call, RTD_CAMPO_OFERTA_COMPRA)

        if not of_venda_put and not of_compra_put and not of_venda_call and not of_compra_call:
            return None

        status_put = rtd.ler_status(inst.cod_put) or "Aberto"
        status_call = rtd.ler_status(inst.cod_call) or "Aberto"
        status_ativo = rtd.ler_status(inst.ativo) or "Aberto"

        cab_put = rtd.ler_campo(inst.cod_put, RTD_CAMPO_CABECALHO_BOOK)
        qul_put = rtd.ler_campo(inst.cod_put, RTD_CAMPO_QTDE_ULT_NEG)
        vov_put = rtd.ler_campo(inst.cod_put, RTD_CAMPO_VOL_VENDA)
        cab_call = rtd.ler_campo(inst.cod_call, RTD_CAMPO_CABECALHO_BOOK)
        qul_call = rtd.ler_campo(inst.cod_call, RTD_CAMPO_QTDE_ULT_NEG)
        voc_call = rtd.ler_campo(inst.cod_call, RTD_CAMPO_VOL_COMPRA)

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
            cab_put=cab_put,
            qul_put=qul_put,
            vov_put=vov_put,
            cab_call=cab_call,
            qul_call=qul_call,
            voc_call=voc_call,
        )
