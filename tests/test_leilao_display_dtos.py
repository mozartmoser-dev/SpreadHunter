"""Leilao por perna nas oportunidades Vendidas e Venda Coberta.

leilao_display exibe triangulo + combinacao por perna (ex.: '⚠ Leilão PUT'),
com fallback '⚠ LEILAO' quando nao ha status. Tambem cobre a tolerancia
ao artefato de encoding 'Leil?o' do servidor OpenFast.
"""

from datetime import date

from src.application.dtos.dtos import montar_leilao_label
from src.application.dtos.dtos_venda_coberta import OportunidadeVendaCoberta
from src.application.dtos.dtos_vendida import OportunidadeVendida


def _vendida(status_put="aberto", status_call="aberto", status_ativo="aberto", em_leilao=True):
    return OportunidadeVendida(
        ativo="PETR4",
        strike=30.0,
        vencimento=date(2026, 9, 18),
        dias=29,
        cod_put="P",
        cod_call="C",
        tipo_opcao="E",
        classificacao="BOX_VENDIDO",
        recebimento=1.5,
        pct_ganho=0.01,
        pct_cdi=2.5,
        viavel=True,
        em_leilao=em_leilao,
        status_put=status_put,
        status_call=status_call,
        status_ativo=status_ativo,
    )


def _coberta(status_put="aberto", status_call="aberto", status_ativo="aberto", em_leilao=True):
    return OportunidadeVendaCoberta(
        ativo="PETR4",
        strike=30.0,
        vencimento=date(2026, 9, 18),
        dias=29,
        cod_put="P",
        cod_call="C",
        tipo_opcao="E",
        em_leilao=em_leilao,
        status_put=status_put,
        status_call=status_call,
        status_ativo=status_ativo,
    )


class TestVendidaLeilaoDisplay:
    def test_vazio_sem_leilao(self):
        assert _vendida(em_leilao=False).leilao_display == ""

    def test_fallback_sem_status(self):
        assert _vendida(status_put="aberto", status_call="aberto", status_ativo="aberto").leilao_display == "\u26a0 LEILAO"

    def test_put(self):
        assert _vendida(status_put="Leilão").leilao_display == "\u26a0 Leilão PUT"

    def test_combinacao_todas(self):
        o = _vendida(status_put="Leilão", status_call="Leilão", status_ativo="Leilão")
        assert o.leilao_display == "\u26a0 Leilão Ativo + PUT + CALL"

    def test_artefato_encoding(self):
        assert _vendida(status_ativo="Leil?o").leilao_display == "\u26a0 Leilão Ativo"


class TestVendaCobertaLeilaoDisplay:
    def test_vazio_sem_leilao(self):
        assert _coberta(em_leilao=False).leilao_display == ""

    def test_fallback_sem_status(self):
        assert _coberta(status_put="aberto", status_call="aberto", status_ativo="aberto").leilao_display == "\u26a0 LEILAO"

    def test_put(self):
        assert _coberta(status_put="Leilão").leilao_display == "\u26a0 Leilão PUT"

    def test_combinacao_todas(self):
        o = _coberta(status_put="Leilão", status_call="Leilão", status_ativo="Leilão")
        assert o.leilao_display == "\u26a0 Leilão Ativo + PUT + CALL"

    def test_artefato_encoding(self):
        assert _coberta(status_call="Leil?o").leilao_display == "\u26a0 Leilão CALL"


class TestMontarLeilaoLabel:
    def test_tudo_aberto_vazio(self):
        assert montar_leilao_label("aberto", "aberto", "aberto") == ""

    def test_sem_status_vazio(self):
        assert montar_leilao_label(None, "", None) == ""

    def test_precomposed_decomposto(self):
        assert montar_leilao_label("Leil\u00e3o", "aberto", "aberto") == "Leilão Ativo"

    def test_artefato_question(self):
        assert montar_leilao_label("Leil?o", "aberto", "aberto") == "Leilão Ativo"

    def test_fechado(self):
        assert montar_leilao_label("aberto", "Fechado", "aberto") == "PUT: Fechado"

    def test_misto_leilao_e_outros(self):
        assert montar_leilao_label("Leilão", "Fechado", "aberto") == "Leilão Ativo + PUT: Fechado"