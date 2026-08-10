"""Testes dos campos de origem da cotação (ts/idade_origem_ativo) nos DTOs."""
from datetime import date, datetime

from src.application.dtos.dtos import OportunidadeMonitor
from src.application.dtos.dtos_vendida import OportunidadeVendida
from src.application.dtos.dtos_venda_coberta import OportunidadeVendaCoberta


def _naive_utc(**kw):
    return datetime(2026, 8, 10, 13, 0, 0, **kw)


def _monitor(ativo="PETR4", **kw):
    base = dict(
        instrumento_id=1, ativo=ativo, strike=18.0, vencimento=date(2026, 9, 10),
        dias=30, cod_put="PETRG180", cod_call="PETRH180", tipo_opcao="A",
    )
    base.update(kw)
    return OportunidadeMonitor(**base)


def _vendida(ativo="PETR4"):
    return OportunidadeVendida(
        ativo=ativo, strike=18.0, vencimento=date(2026, 9, 10), dias=30,
        cod_put="PETRG180", cod_call="PETRH180", tipo_opcao="A",
        classificacao="BOX_VENDIDO", recebimento=0.5, pct_ganho=0.02,
        pct_cdi=1.5, viavel=True, em_leilao=False,
    )


def _coberta(ativo="PETR4"):
    return OportunidadeVendaCoberta(
        ativo=ativo, strike=18.0, vencimento=date(2026, 9, 10), dias=30,
        cod_put="PETRG180", cod_call="PETRH180", tipo_opcao="A",
    )


class TestOportunidadeMonitorOrigem:
    def test_label_origem_vazio_sem_idade(self):
        dto = _monitor()
        assert dto.label_origem == ""

    def test_label_origem_decimal_curta(self):
        dto = _monitor(idade_origem_ativo=2.5)
        assert dto.label_origem == "origem 2.5s"

    def test_label_origem_inteira(self):
        dto = _monitor(idade_origem_ativo=45.0)
        assert dto.label_origem == "origem 45s atrás"

    def test_label_detectado_com_origem(self):
        dto = _monitor(
            detectado_em=_naive_utc(),
            idade_origem_ativo=3.0,
        )
        label = dto.label_detectado
        assert label.startswith("10/08/2026")
        assert "(origem 3.0s)" in label

    def test_label_detectado_sem_origem(self):
        dto = _monitor(
            detectado_em=_naive_utc(),
        )
        assert dto.label_detectado == "10/08/2026 10:00:00"


class TestOportunidadeVendidaOrigem:
    def test_label_origem(self):
        dto = _vendida()
        dto.idade_origem_ativo = 12.0
        assert dto.label_origem == "origem 12s atrás"

    def test_label_detectado_com_origem(self):
        dto = _vendida()
        dto.detectado_em = _naive_utc()
        dto.idade_origem_ativo = 1.2
        assert "(origem 1.2s)" in dto.label_detectado


class TestOportunidadeVendaCobertaOrigem:
    def test_label_origem(self):
        dto = _coberta()
        dto.idade_origem_ativo = 9.0
        assert dto.label_origem == "origem 9.0s"

    def test_label_detectado_com_origem(self):
        dto = _coberta()
        dto.detectado_em = _naive_utc()
        dto.idade_origem_ativo = 5.0
        assert "(origem 5.0s)" in dto.label_detectado