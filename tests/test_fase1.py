import sqlite3
import tempfile
from pathlib import Path
from datetime import date

from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    OportunidadeRepository,
    EstruturaRepository,
    PernaRepository,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.entities.oportunidade import Oportunidade, ClassificacaoOp
from src.domain.entities.estrutura_operacional import EstruturaOperacional, TipoEstrutura
from src.domain.entities.perna_operacao import PernaOperacao, Lado
from src.domain.entities.parametro_operacional import ParametroOperacional


import pytest


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = init_db(path)
    conn.close()
    return path


@pytest.fixture
def instrumento_repo(db_path):
    return InstrumentoRepository(db_path)


@pytest.fixture
def parametro_repo(db_path):
    return ParametroRepository(db_path)


@pytest.fixture
def oportunidade_repo(db_path):
    return OportunidadeRepository(db_path)


@pytest.fixture
def estrutura_repo(db_path):
    return EstruturaRepository(db_path)


@pytest.fixture
def perna_repo(db_path):
    return PernaRepository(db_path)


class TestInstrumentoOpcional:
    def test_dias_ate_vencimento(self):
        inst = InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date.today(), tipo_opcao=TipoOpcao.AMERICANA
        )
        assert inst.dias_ate_vencimento == 0

    def test_dias_ate_vencimento_futuro(self):
        from datetime import timedelta
        inst = InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date.today() + timedelta(days=20),
            tipo_opcao=TipoOpcao.AMERICANA
        )
        assert inst.dias_ate_vencimento == 20

    def test_tipo_opcao_values(self):
        assert TipoOpcao.AMERICANA.value == "A"
        assert TipoOpcao.EUROPEIA.value == "E"


class TestParametroOperacional:
    def test_defaults_contem_taxa_cdi(self):
        defaults = ParametroOperacional.defaults()
        chaves = [p.chave for p in defaults]
        assert "taxa_cdi" in chaves
        assert "premio_risco_box" in chaves
        assert "premio_risco_sbth" in chaves
        assert "premio_box_sintetico_call_itm" in chaves

    def test_valor_taxa_cdi(self):
        defaults = ParametroOperacional.defaults()
        cdi = next(p for p in defaults if p.chave == "taxa_cdi")
        assert cdi.valor == 0.1425


class TestOportunidade:
    def test_pct_ganho_sbth(self):
        op = Oportunidade(
            instrumento_id=1, preco_ativo=38.0, strike=38.0, dias=20,
            cdi_periodo=0.15, custo_sbth=100.0, pct_ganho_sbth=0.15,
            pct_cdi_sbth=1.0,
            custo_box=100.0, pct_ganho_box=0.20, pct_cdi_box=1.33,
            classificacao=ClassificacaoOp.BOX_1, operacao="BOX"
        )
        assert op.pct_ganho_sbth == 0.15

    def test_pct_ganho_box_zero_cost(self):
        op = Oportunidade(
            instrumento_id=1, preco_ativo=38.0, strike=38.0, dias=20,
            cdi_periodo=0.15, custo_sbth=0.0, pct_ganho_sbth=0.0,
            pct_cdi_sbth=0.0,
            custo_box=0.0, pct_ganho_box=0.0, pct_cdi_box=0.0,
            classificacao=ClassificacaoOp.BOX_1, operacao="BOX"
        )
        assert op.pct_ganho_box == 0.0


class TestInstrumentoRepository:
    def test_save_and_get(self, instrumento_repo):
        inst = InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date(2026, 6, 20), tipo_opcao=TipoOpcao.AMERICANA
        )
        saved = instrumento_repo.save(inst)
        assert saved.id is not None

        all_inst = instrumento_repo.get_all()
        assert len(all_inst) == 1
        assert all_inst[0].ativo == "PETR4"

    def test_get_by_ativo(self, instrumento_repo):
        instrumento_repo.save(InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date(2026, 6, 20), tipo_opcao=TipoOpcao.AMERICANA
        ))
        instrumento_repo.save(InstrumentoOpcional(
            ativo="VALE3", cod_put="VALEX80", cod_call="VALEZ80",
            vencimento=date(2026, 6, 20), tipo_opcao=TipoOpcao.AMERICANA
        ))

        result = instrumento_repo.get_by_ativo("PETR4")
        assert len(result) == 1
        assert result[0].ativo == "PETR4"


class TestParametroRepository:
    def test_seed_defaults(self, parametro_repo):
        parametro_repo.seed_defaults()
        cdi = parametro_repo.get_by_chave("taxa_cdi")
        assert cdi is not None
        assert cdi.valor == 0.1425

    def test_upsert(self, parametro_repo):
        parametro_repo.save(ParametroOperacional(
            chave="taxa_cdi", valor=0.1450, estrategia="GERAL", descricao="Taxa CDI"
        ))
        parametro_repo.save(ParametroOperacional(
            chave="taxa_cdi", valor=0.14, estrategia="GERAL", descricao="Taxa CDI"
        ))
        result = parametro_repo.get_by_chave("taxa_cdi")
        assert result.valor == 0.14

    def test_get_by_estrategia(self, parametro_repo):
        parametro_repo.seed_defaults()
        box_params = parametro_repo.get_by_estrategia("BOX")
        assert len(box_params) >= 1


class TestOportunidadeRepository:
    def test_save_and_get(self, oportunidade_repo, instrumento_repo):
        inst = instrumento_repo.save(InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date(2026, 6, 20), tipo_opcao=TipoOpcao.AMERICANA
        ))
        op = Oportunidade(
            instrumento_id=inst.id, preco_ativo=38.0, strike=38.0, dias=20,
            cdi_periodo=0.15, custo_sbth=100.0, pct_ganho_sbth=0.15,
            pct_cdi_sbth=1.0,
            custo_box=100.0, pct_ganho_box=0.20, pct_cdi_box=1.33,
            classificacao=ClassificacaoOp.BOX_1, operacao="BOX",
            snapshot_mercado={"liq_put_x_lote": 500, "em_leilao": False}
        )
        saved = oportunidade_repo.save(op)
        assert saved.id is not None

        all_ops = oportunidade_repo.get_all()
        assert len(all_ops) == 1
        assert all_ops[0].snapshot_mercado["liq_put_x_lote"] == 500


class TestEstruturaRepository:
    def test_save_and_get_by_oportunidade(self, estrutura_repo, oportunidade_repo, instrumento_repo):
        inst = instrumento_repo.save(InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date(2026, 6, 20), tipo_opcao=TipoOpcao.AMERICANA
        ))
        op = oportunidade_repo.save(Oportunidade(
            instrumento_id=inst.id, preco_ativo=38.0, strike=38.0, dias=20,
            cdi_periodo=0.15, custo_sbth=100.0, pct_ganho_sbth=0.15,
            pct_cdi_sbth=1.0,
            custo_box=100.0, pct_ganho_box=0.20, pct_cdi_box=1.33,
            classificacao=ClassificacaoOp.BOX_1, operacao="BOX"
        ))
        est = EstruturaOperacional(
            oportunidade_id=op.id, tipo=TipoEstrutura.BOX_ITM_BASKET,
            coefic_alvo=1.0, coefic_mercado=0.95, taxa_ganho=10.0
        )
        saved = estrutura_repo.save(est)
        assert saved.id is not None

        result = estrutura_repo.get_by_oportunidade(op.id)
        assert len(result) == 1
        assert result[0].tipo == TipoEstrutura.BOX_ITM_BASKET


class TestPernaRepository:
    def test_save_and_get_by_estrutura(self, perna_repo, estrutura_repo, oportunidade_repo, instrumento_repo):
        inst = instrumento_repo.save(InstrumentoOpcional(
            ativo="PETR4", cod_put="PETRX80", cod_call="PETRZ80",
            vencimento=date(2026, 6, 20), tipo_opcao=TipoOpcao.AMERICANA
        ))
        op = oportunidade_repo.save(Oportunidade(
            instrumento_id=inst.id, preco_ativo=38.0, strike=38.0, dias=20,
            cdi_periodo=0.15, custo_sbth=100.0, pct_ganho_sbth=0.15,
            pct_cdi_sbth=1.0,
            custo_box=100.0, pct_ganho_box=0.20, pct_cdi_box=1.33,
            classificacao=ClassificacaoOp.BOX_1, operacao="BOX"
        ))
        est = estrutura_repo.save(EstruturaOperacional(
            oportunidade_id=op.id, tipo=TipoEstrutura.BOX_ITM_BASKET,
            coefic_alvo=1.0, coefic_mercado=0.95, taxa_ganho=10.0
        ))
        p1 = PernaOperacao(
            estrutura_id=est.id, codigo="PETRZ80", lado=Lado.COMPRA,
            quantidade=100, profundidade=-1, ordem=1
        )
        p2 = PernaOperacao(
            estrutura_id=est.id, codigo="PETRX80", lado=Lado.VENDA,
            quantidade=100, profundidade=0, ordem=2
        )
        perna_repo.save(p1)
        perna_repo.save(p2)

        pernas = perna_repo.get_by_estrutura(est.id)
        assert len(pernas) == 2
        assert pernas[0].lado == Lado.COMPRA
        assert pernas[1].lado == Lado.VENDA
