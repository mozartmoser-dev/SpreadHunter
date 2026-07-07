import pytest
from datetime import date
from unittest.mock import MagicMock, patch
import sqlite3

from src.domain.entities.taxa_aluguel import TaxaAluguel
from src.infrastructure.integrations.investsite_client import InvestSiteClient
from src.infrastructure.persistence.repositories.repositories import TaxaAluguelRepository
from src.application.use_cases.coletar_taxas_aluguel import ColetarTaxasAluguelUseCase
from src.infrastructure.persistence.database import init_db

# HTML mockado baseado no conteúdo real retornado pelo InvestSite
MOCK_HTML_SUCESSO = """
<html>
<body>
<section id="resumo"> O código de negociação BBDC4 da empresa BRADESCO está sendo alugado atualmente (02/07/2026) por uma taxa média anualizada de 0,47%. A média dessa taxa nos últimos 7 dias foi de 0,25%. E nos últimos 28 dias foi de 0,09%. Informações adicionais...</section>
</body>
</html>
"""

MOCK_HTML_VAZIO = """
<html>
<body>
<section id="resumo">Este ativo não está sendo alugado atualmente ou não possui informações.</section>
</body>
</html>
"""


class TestInvestSiteClient:
    def test_parse_html_sucesso(self):
        client = InvestSiteClient()
        dados = client.parse_html(MOCK_HTML_SUCESSO, "BBDC4")
        assert dados is not None
        assert dados["ativo"] == "BBDC4"
        assert dados["data"] == date(2026, 7, 2)
        assert dados["taxa_atual"] == 0.47
        assert dados["taxa_7d"] == 0.25
        assert dados["taxa_28d"] == 0.09

    def test_parse_html_vazio(self):
        client = InvestSiteClient()
        dados = client.parse_html(MOCK_HTML_VAZIO, "BOVA11")
        assert dados is None


class TestTaxaAluguelRepository:
    @pytest.fixture
    def test_db(self, tmp_path):
        db_file = tmp_path / "test_spreadhunter.db"
        # Inicializa o banco de testes em arquivo temporário
        init_db(str(db_file))
        return str(db_file)

    def test_save_and_get_latest(self, test_db):
        repo = TaxaAluguelRepository(test_db)
        taxa = TaxaAluguel(
            ativo="BBDC4",
            data=date(2026, 7, 2),
            taxa_atual=0.47,
            taxa_7d=0.25,
            taxa_28d=0.09
        )
        
        saved = repo.save(taxa)
        assert saved.id is not None

        # Busca o mais recente
        latest = repo.get_latest_by_ativo("BBDC4")
        assert latest is not None
        assert latest.ativo == "BBDC4"
        assert latest.data == date(2026, 7, 2)
        assert latest.taxa_atual == 0.47

    def test_save_conflict_upsert(self, test_db):
        repo = TaxaAluguelRepository(test_db)
        taxa1 = TaxaAluguel(
            ativo="BBDC4",
            data=date(2026, 7, 2),
            taxa_atual=0.47,
            taxa_7d=0.25,
            taxa_28d=0.09
        )
        repo.save(taxa1)

        taxa2 = TaxaAluguel(
            ativo="BBDC4",
            data=date(2026, 7, 2),
            taxa_atual=0.55,  # Atualização da taxa
            taxa_7d=0.30,
            taxa_28d=0.10
        )
        repo.save(taxa2)

        latest = repo.get_latest_by_ativo("BBDC4")
        assert latest is not None
        assert latest.taxa_atual == 0.55  # Valida o UPSERT
        
    def test_get_latest_all(self, test_db):
        repo = TaxaAluguelRepository(test_db)
        repo.save(TaxaAluguel("PETR4", date(2026, 7, 1), 0.1, 0.1, 0.1))
        repo.save(TaxaAluguel("PETR4", date(2026, 7, 2), 0.2, 0.2, 0.2))
        repo.save(TaxaAluguel("VALE3", date(2026, 7, 2), 0.3, 0.3, 0.3))

        latest_dict = repo.get_latest_all()
        assert len(latest_dict) == 2
        assert latest_dict["PETR4"].data == date(2026, 7, 2)
        assert latest_dict["PETR4"].taxa_atual == 0.2
        assert latest_dict["VALE3"].taxa_atual == 0.3


class TestColetarTaxasAluguelUseCase:
    @pytest.fixture
    def test_db(self, tmp_path):
        db_file = tmp_path / "test_spreadhunter.db"
        init_db(str(db_file))
        return str(db_file)

    def test_use_case_executa_coleta(self, test_db):
        from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
        from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository
        
        # Insere ativos mock no banco
        inst_repo = InstrumentoRepository(test_db)
        inst_repo.save(InstrumentoOpcional(ativo="BBDC4", cod_put="BBDCU36", cod_call="BBDCG36", vencimento=date(2026, 7, 20), tipo_opcao=TipoOpcao.EUROPEIA))
        inst_repo.save(InstrumentoOpcional(ativo="PETR4", cod_put="PETRU36", cod_call="PETRG36", vencimento=date(2026, 7, 20), tipo_opcao=TipoOpcao.EUROPEIA))

        use_case = ColetarTaxasAluguelUseCase(test_db)
        
        # Mock do client para simular retorno
        use_case.client = MagicMock()
        use_case.client.fetch_taxa_aluguel.side_effect = lambda ativo: {
            "ativo": ativo,
            "data": date(2026, 7, 2),
            "taxa_atual": 0.47 if ativo == "BBDC4" else 0.85,
            "taxa_7d": 0.25,
            "taxa_28d": 0.09
        }

        resumo = use_case.executar()
        assert resumo["status"] == "sucesso"
        assert resumo["sucessos"] == 2
        assert resumo["falhas"] == 0

        # Verifica se gravou no banco
        taxa_repo = TaxaAluguelRepository(test_db)
        assert taxa_repo.get_latest_by_ativo("BBDC4").taxa_atual == 0.47
        assert taxa_repo.get_latest_by_ativo("PETR4").taxa_atual == 0.85

    def test_use_case_desabilitado(self, test_db):
        from src.infrastructure.persistence.repositories.repositories import ParametroRepository
        param_repo = ParametroRepository(test_db)
        p = param_repo.get_by_chave("taxa_aluguel_habilitado")
        if p is None:
            from src.domain.entities.parametro_operacional import ParametroOperacional
            p = ParametroOperacional(chave="taxa_aluguel_habilitado", valor=0.0, estrategia="GERAL", descricao="")
        else:
            p.valor = 0.0
        param_repo.save(p)

        use_case = ColetarTaxasAluguelUseCase(test_db)
        resumo = use_case.executar()
        
        assert resumo["status"] == "desabilitado"
        assert resumo["sucessos"] == 0
