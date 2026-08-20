"""Proventos: fallback dadosdemercado cobre eventos que a StatusInvest perdeu.

Caso GGBR4: ex-dividendo 20/08/2026 real, mas a StatusInvest nao publicou o
evento (tabela parada em data_com 13/05/2026). A dadosdemercado.com.br tem o
evento. O provider mescla as duas fontes com dedup por (data_com, tipo).
"""

import requests

from src.infrastructure.providers.dividendos_statusinvest import DividendosStatusInvestProvider

STATUSINVEST_HTML = """
<table>
<tr><th>Tipo</th><th>Data Com</th><th>Pagamento</th><th>Valor</th></tr>
<tr><td>Dividendo</td><td>13/05/2026</td><td>09/06/2026</td><td>0,180000</td></tr>
<tr><td>Dividendo</td><td>10/03/2026</td><td>18/03/2026</td><td>0,100000</td></tr>
</table>
"""

DADOSMERCADO_HTML = """
<table class="normal-table">
<thead><tr><th>Tipo</th><th>Valor</th><th>Registro</th><th>Ex</th><th>Pagamento</th></tr></thead>
<tbody>
<tr><td>Dividendo</td><td>0,230000</td><td>19/08/2026</td><td>20/08/2026</td><td>11/09/2026</td></tr>
<tr><td>Dividendo</td><td>0,180000</td><td>13/05/2026</td><td>14/05/2026</td><td>09/06/2026</td></tr>
</tbody>
</table>
"""


class _FakeResp:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


def test_mescla_evento_faltante_na_statusinvest(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if "statusinvest" in url:
            return _FakeResp(STATUSINVEST_HTML)
        if "dadosdemercado" in url:
            return _FakeResp(DADOSMERCADO_HTML)
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    result = DividendosStatusInvestProvider().buscar_proventos("GGBR4")

    evento = [r for r in result if r["data_com"] == "2026-08-19"]
    assert len(evento) == 1
    assert evento[0]["tipo"] == "Dividendo"
    assert evento[0]["data_ex"] == "2026-08-20"
    assert evento[0]["data_pagamento"] == "2026-09-11"
    assert evento[0]["valor"] == 0.23
    assert evento[0]["fonte"] == "dadosdemercado"

    comuns = [r for r in result if r["data_com"] == "2026-05-13"]
    assert len(comuns) == 1
    assert comuns[0]["fonte"] == "statusinvest"


def test_mesclar_preenche_campo_faltante_e_deduplica():
    provider = DividendosStatusInvestProvider()
    status = [{
        "ativo": "GGBR4", "tipo": "Dividendo", "data_com": "2026-08-19",
        "data_ex": "2026-08-20", "data_pagamento": None, "valor": 0.23,
        "fonte": "statusinvest",
    }]
    dados = [{
        "ativo": "GGBR4", "tipo": "Dividendo", "data_com": "2026-08-19",
        "data_ex": "2026-08-20", "data_pagamento": "2026-09-11", "valor": 0.23,
        "fonte": "dadosdemercado",
    }]
    merged = provider._mesclar(status, dados)
    assert len(merged) == 1
    assert merged[0]["data_pagamento"] == "2026-09-11"
    assert merged[0]["fonte"] == "statusinvest"


def test_fallback_erro_nao_derruba_importacao(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if "statusinvest" in url:
            return _FakeResp(STATUSINVEST_HTML)
        raise RuntimeError("timeout dadosdemercado")

    monkeypatch.setattr(requests, "get", fake_get)
    result = DividendosStatusInvestProvider().buscar_proventos("GGBR4")
    assert len(result) == 2
    assert {r["fonte"] for r in result} == {"statusinvest"}