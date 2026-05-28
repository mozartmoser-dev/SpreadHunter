from dataclasses import dataclass


RTD_SERVIDOR = "rtdtrading.rtdserver"

RTD_CAMPO_ULTIMO_PRECO = "ULT"
RTD_CAMPO_STRIKE = "PEX"
RTD_CAMPO_VENCIMENTO = "VAL"
RTD_CAMPO_OFERTA_VENDA = "OVD"
RTD_CAMPO_OFERTA_COMPRA = "OCP"
RTD_CAMPO_STATUS = "EST"
RTD_CAMPO_CABECALHO_BOOK = "CAB"
RTD_CAMPO_QTDE_ULT_NEG = "QUL"
RTD_CAMPO_VOL_VENDA = "VOV"
RTD_CAMPO_VOL_COMPRA = "VOC"


def rtd_topico(codigo: str) -> str:
    return "{}_B_0".format(codigo)


@dataclass
class DadosRTDInstrumento:
    ativo: str
    cod_put: str
    cod_call: str
    preco_ativo: float | None
    strike: float | None
    vencimento_rtd: str | None
    of_compra_ativo: float | None
    of_venda_ativo: float | None
    of_venda_put: float | None
    of_compra_put: float | None
    of_venda_call: float | None
    of_compra_call: float | None
    status_put: str
    status_call: str
    status_ativo: str
    cab_put: float | None
    qul_put: float | None
    vov_put: float | None
    cab_call: float | None
    qul_call: float | None
    voc_call: float | None

    @property
    def premio_put(self) -> float:
        if self.of_venda_put and self.of_venda_put > 0:
            return self.of_venda_put
        if self.of_compra_put and self.of_compra_put > 0:
            return self.of_compra_put
        return 0.0

    @property
    def premio_call(self) -> float:
        if self.of_compra_call and self.of_compra_call > 0:
            return self.of_compra_call
        if self.of_venda_call and self.of_venda_call > 0:
            return self.of_venda_call
        return 0.0

    @property
    def em_leilao(self) -> bool:
        return not (
            self.status_put.lower() == "aberto"
            and self.status_call.lower() == "aberto"
            and self.status_ativo.lower() == "aberto"
        )

    def to_dados_mercado(self) -> dict:
        return {
            "preco_ativo": self.preco_ativo or 0.0,
            "strike_rtd": self.strike,
            "of_compra_ativo": self.of_compra_ativo or 0.0,
            "of_venda_ativo": self.of_venda_ativo or 0.0,
            "of_compra_put": self.of_compra_put or 0.0,
            "of_venda_put": self.of_venda_put or 0.0,
            "of_compra_call": self.of_compra_call or 0.0,
            "of_venda_call": self.of_venda_call or 0.0,
            "premio_put": self.premio_put,
            "premio_call": self.premio_call,
            "em_leilao": self.em_leilao,
            "status_put": self.status_put,
            "status_call": self.status_call,
            "status_ativo": self.status_ativo,
            "vov_put_boca": self.vov_put or 0.0,
            "voc_call_boca": self.voc_call or 0.0,
            "qul_put": self.qul_put or 0.0,
            "qul_call": self.qul_call or 0.0,
        }
