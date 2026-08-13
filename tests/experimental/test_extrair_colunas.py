import numpy as np
import pytest

from src.application.use_cases.experimental.extrair_colunas import (
    extrair,
    extrair_encadeado,
    extrair_passthrough,
    or_chain,
    or_default,
    strike_limpo,
)


class TestOrDefault:
    def test_valor_presente(self):
        assert or_default({"a": 5.0}, "a") == 5.0

    def test_ausente_usa_default(self):
        assert or_default({"b": 1.0}, "a", 7.0) == 7.0

    def test_zero_truthiness_vira_default(self):
        assert or_default({"a": 0.0}, "a", None) is None
        assert or_default({"a": 0.0}, "a") == 0.0


class TestOrChain:
    def test_boca_prioridade(self):
        m = {"vov_put_boca": 12.0, "vov_put": 3.0}
        assert or_chain(m, ["vov_put_boca", "vov_put"]) == 12.0

    def test_fallback_para_normal(self):
        m = {"vov_put_boca": 0.0, "vov_put": 3.0}
        assert or_chain(m, ["vov_put_boca", "vov_put"]) == 3.0

    def test_negativo_e_truthy(self):
        m = {"vov_put_boca": -1.0, "vov_put": 3.0}
        assert or_chain(m, ["vov_put_boca", "vov_put"]) == -1.0

    def test_todos_zero_usa_default(self):
        m = {"vov_put_boca": 0.0, "vov_put": 0.0}
        assert or_chain(m, ["vov_put_boca", "vov_put"]) == 0.0

    def test_ausente_vira_default(self):
        m = {"outro": 1.0}
        assert or_chain(m, ["vov_put_boca", "vov_put"], 9.0) == 9.0


class TestStrikeLimpo:
    def test_valido(self):
        assert strike_limpo({"strike_rtd": 44.5}) == 44.5

    def test_zero(self):
        assert strike_limpo({"strike_rtd": 0.0}) == 0.0

    def test_negativo(self):
        assert strike_limpo({"strike_rtd": -1.0}) == 0.0

    def test_ausente(self):
        assert strike_limpo({}) == 0.0


class TestExtrair:
    def test_extrai_float_com_fallback(self):
        dados = {"A|B": {"preco_ativo": 10.0, "vov_put": 0.0},
                 "C|D": {"preco_ativo": None, "vov_put": 5.0}}
        chaves = ["A|B", "C|D"]
        arr = extrair(chaves, dados, "preco_ativo")
        np.testing.assert_array_equal(arr, np.array([10.0, 0.0]))
        arr2 = extrair(chaves, dados, "vov_put")
        np.testing.assert_array_equal(arr2, np.array([0.0, 5.0]))

    def test_extrai_bool(self):
        dados = {"A|B": {"em_leilao": True}, "C|D": {}}
        arr = extrair(["A|B", "C|D"], dados, "em_leilao", default=False, dtype=bool)
        np.testing.assert_array_equal(arr, np.array([True, False]))


class TestExtrairEncadeado:
    def test_boca_vence(self):
        dados = {"A|B": {"voc_call_boca": 200.0, "voc_call": 50.0},
                 "C|D": {"voc_call_boca": 0.0, "voc_call": 60.0}}
        arr = extrair_encadeado(["A|B", "C|D"], dados, ["voc_call_boca", "voc_call"])
        np.testing.assert_array_equal(arr, np.array([200.0, 60.0]))


class TestExtrairPassthrough:
    def test_preserva_none(self):
        dados = {"A|B": {"ts_scan": 123.0}, "C|D": {}}
        assert extrair_passthrough(["A|B", "C|D"], dados, "ts_scan") == [123.0, None]

    def test_ts_ativo_ask(self):
        dados = {"A|B": {"ts_ativo_ask": 1.0}, "C|D": {"ts_ativo_ask": 2.0}}
        assert extrair_passthrough(["A|B", "C|D"], dados, "ts_ativo_ask") == [1.0, 2.0]