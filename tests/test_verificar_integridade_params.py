"""Testa o script de verificação de integridade de parâmetros.

Simula o incidente real do commit b9d7e9a (27/07/2026):
hardcoded=0.40, json=0.0099, banco=0.0099 → RED + YELLOW juntos."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.verificar_integridade_params import (
    verificar,
    _fator_divergencia,
    _eh_parametro_de_fracao,
    SEVERITY_FATOR,
)


def test_fator_divergencia_zero_referencia():
    assert _fator_divergencia(0.0, 0.0) == 0.0
    assert _fator_divergencia(0.01, 0.0) == 0.01
    assert _fator_divergencia(0.0, 0.01) == float("inf")


def test_fator_divergencia_normal():
    assert _fator_divergencia(0.0099, 0.40) == pytest.approx(40.40, abs=0.1)
    assert _fator_divergencia(0.40, 0.0099) == pytest.approx(40.40, abs=0.1)
    assert _fator_divergencia(0.40, 0.40) == 1.0
    assert _fator_divergencia(0.01, 0.20) == 20.0


def test_eh_parametro_de_fracao():
    assert _eh_parametro_de_fracao("limite_protecao_pct") is True
    assert _eh_parametro_de_fracao("fator_seguranca_liquidez") is True
    assert _eh_parametro_de_fracao("razao_convexidade_max") is True
    assert _eh_parametro_de_fracao("spread_maximo_pct") is True
    assert _eh_parametro_de_fracao("n_sigma_protecao") is True
    assert _eh_parametro_de_fracao("taxa_cdi") is False
    assert _eh_parametro_de_fracao("fonte_market_data") is False


class TestIncidenteRealB9d7e9a:
    """Recria o cenário real do commit b9d7e9a (27/07/2026).

    limite_protecao_pct: hardcoded=0.40, json=0.0099, banco=0.0099.
    Deve disparar RED (banco vs hardcoded) + YELLOW (json vs hardcoded).
    """

    @pytest.fixture
    def temp_db(self, tmp_path):
        import sqlite3
        db_path = tmp_path / "test_integridade.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE parametros_operacionais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                estrategia TEXT NOT NULL DEFAULT '',
                descricao TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "INSERT INTO parametros_operacionais (chave, valor) VALUES (?, ?)",
            ("limite_protecao_pct", "0.0099"),
        )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def mock_json(self, tmp_path):
        json_path = tmp_path / "parametros_default.json"
        data = {
            "parametros": [
                {
                    "chave": "limite_protecao_pct",
                    "valor": "0.0099",
                    "estrategia": "PROTECAO_CAUDA",
                    "descricao": "corrompido",
                }
            ]
        }
        json_path.write_text(json.dumps(data), encoding="utf-8")
        return json_path

    def test_reconstrucao_incidente(self, temp_db, mock_json):
        with (
            patch("scripts.verificar_integridade_params.JSON_PATH", mock_json),
            patch(
                "scripts.verificar_integridade_params._carregar_hardcoded",
                return_value={"limite_protecao_pct": 0.40},
            ),
        ):
            result = verificar(db_path=str(temp_db))

        assert len(result) == 1
        d = result[0]

        assert d["chave"] == "limite_protecao_pct"
        assert d["hardcoded"] == 0.40
        assert d["json"] == 0.0099
        assert d["banco"] == 0.0099

        assert "RED" in d["sinais"], f"Esperado RED (banco 0.0099 vs hardcoded 0.40), obtido {d['sinais']}"
        assert "YELLOW" in d["sinais"], f"Esperado YELLOW (json 0.0099 vs hardcoded 0.40), obtido {d['sinais']}"

        assert d["fator_banco_hardcoded"] > SEVERITY_FATOR
        assert d["fator_json_hardcoded"] > SEVERITY_FATOR


class TestSemDivergencia:
    def test_parametros_integrados_nao_dispara(self, tmp_path):
        import sqlite3
        db_path = tmp_path / "test_ok.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE parametros_operacionais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                estrategia TEXT NOT NULL DEFAULT '',
                descricao TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "INSERT INTO parametros_operacionais (chave, valor) VALUES (?, ?)",
            ("limite_protecao_pct", "0.40"),
        )
        conn.commit()
        conn.close()

        json_path = tmp_path / "parametros_default.json"
        data = {
            "parametros": [
                {"chave": "limite_protecao_pct", "valor": "0.40"}
            ]
        }
        json_path.write_text(json.dumps(data), encoding="utf-8")

        with (
            patch("scripts.verificar_integridade_params.JSON_PATH", json_path),
            patch(
                "scripts.verificar_integridade_params._carregar_hardcoded",
                return_value={"limite_protecao_pct": 0.40},
            ),
        ):
            result = verificar(db_path=str(db_path))

        assert len(result) == 0


class TestSomenteBancoFoiAlterado:
    """Usuário editou via UI para valor errado — só banco diverge."""

    def test_so_banco_diverge(self, tmp_path):
        import sqlite3
        db_path = tmp_path / "test_sobanco.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE parametros_operacionais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                estrategia TEXT NOT NULL DEFAULT '',
                descricao TEXT DEFAULT ''
            )
        """)
        conn.execute(
            "INSERT INTO parametros_operacionais (chave, valor) VALUES (?, ?)",
            ("limite_protecao_pct", "0.005"),
        )
        conn.commit()
        conn.close()

        json_path = tmp_path / "parametros_default.json"
        data = {
            "parametros": [
                {"chave": "limite_protecao_pct", "valor": "0.40"}
            ]
        }
        json_path.write_text(json.dumps(data), encoding="utf-8")

        with (
            patch("scripts.verificar_integridade_params.JSON_PATH", json_path),
            patch(
                "scripts.verificar_integridade_params._carregar_hardcoded",
                return_value={"limite_protecao_pct": 0.40},
            ),
        ):
            result = verificar(db_path=str(db_path))

        assert len(result) == 1
        assert "RED" in result[0]["sinais"]
        assert "YELLOW" not in result[0]["sinais"]
