import tempfile
from datetime import date, timedelta
from pathlib import Path

from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.application.use_cases.importar_base import ImportarBaseUseCase
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.application.use_cases.exportar_operacao import ExportarOperacaoUseCase
from src.application.dtos.dtos import OportunidadeMonitor

import pytest


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_fase3.db"
    conn = init_db(path)
    conn.close()
    ParametroRepository(path).seed_defaults()
    return path


@pytest.fixture
def importar_uc(db_path):
    return ImportarBaseUseCase(db_path)


@pytest.fixture
def monitor_uc(db_path):
    return MonitorOportunidadesUseCase(db_path)


@pytest.fixture
def exportar_uc(db_path):
    return ExportarOperacaoUseCase(db_path)


@pytest.fixture
def populated_db(db_path):
    repo = InstrumentoRepository(db_path)
    venc = date.today() + timedelta(days=20)
    for i, strike in enumerate([12.4, 15.0, 18.0]):
        repo.save(InstrumentoOpcional(
            ativo="BOVA11", cod_put="BOVAT{}".format(int(strike * 10)),
            cod_call="BOVAH{}".format(int(strike * 10)),
            strike=strike, vencimento=venc, tipo_opcao=TipoOpcao.AMERICANA,
        ))
    return db_path


class TestImportarBaseUseCase:
    def test_importar_arquivo_real(self, importar_uc):
        xlsx = Path("opcoes_consolidado.xlsx")
        if not xlsx.exists():
            pytest.skip("Arquivo xlsx nao encontrado")
        result = importar_uc.executar(xlsx)
        assert result.total_importados > 0
        assert result.total_removidos == 0
        assert len(result.ativos) > 1

    def test_reimportar_limpa_base(self, importar_uc):
        xlsx = Path("opcoes_consolidado.xlsx")
        if not xlsx.exists():
            pytest.skip("Arquivo xlsx nao encontrado")
        importar_uc.executar(xlsx)
        result = importar_uc.executar(xlsx)
        assert result.total_importados > 0
        assert result.total_removidos > 0


class TestMonitorOportunidadesUseCase:
    def test_varrer_com_dados_mercado(self, populated_db):
        venc = (date.today() + timedelta(days=20)).isoformat()
        monitor_uc = MonitorOportunidadesUseCase(populated_db)

        dados_mercado = {
            "BOVA11_15.0_{}".format(venc): {
                "preco_ativo": 18.0,
                "of_compra_ativo": 17.9, "of_venda_ativo": 18.1,
                "of_compra_put": 2.0, "of_venda_put": 2.1,
                "of_compra_call": 2.5, "of_venda_call": 2.6,
                "premio_put": 2.0, "premio_call": 2.5,
            }
        }

        resultados = monitor_uc.varrer(dados_mercado)
        assert len(resultados) > 0
        opp = resultados[0]
        assert isinstance(opp, OportunidadeMonitor)
        assert opp.ativo == "BOVA11"
        assert opp.dias >= 0
        assert opp.classificacao in ("1BOX", "2SBTH", "TP.Op")

    def test_varrer_sem_dados(self, populated_db):
        monitor_uc = MonitorOportunidadesUseCase(populated_db)
        resultados = monitor_uc.varrer({})
        assert len(resultados) == 0

    def test_oportunidade_monitor_labels(self):
        opp = OportunidadeMonitor(
            instrumento_id=1, ativo="BOVA11", strike=18.0,
            vencimento="2026-08-21", dias=20,
            cod_put="BOVAT180", cod_call="BOVAH180",
            tipo_opcao="A", classificacao="1BOX", operacao="BOX",
            custo_box=100.0, pct_ganho_box=0.80, pct_cdi_box=1.5,
            cdi_periodo=0.01,
        )
        assert opp.label_tipo == "BOX"
        assert "1.50x CDI (BOX)" == opp.label_rentabilidade
        assert opp.label_dias == "20d"
        assert "BOVA11" in opp.resumo_linha
        assert "BOX" in opp.resumo_linha

    def test_oportunidade_monitor_labels_sbth(self):
        opp = OportunidadeMonitor(
            instrumento_id=1, ativo="BOVA11", strike=18.0,
            vencimento="2026-08-21", dias=45,
            cod_put="BOVAT180", cod_call="BOVAH180",
            tipo_opcao="A", classificacao="2SBTH", operacao="SBTH",
            custo_sbth=100.0, pct_ganho_sbth=0.50, pct_cdi_sbth=1.2,
            cdi_periodo=0.02,
        )
        assert opp.label_tipo == "SBTH"
        assert "1.20x CDI (SBTH)" == opp.label_rentabilidade
        assert opp.label_dias == "45d"

    def test_viaveis_ordenados_primeiro(self, populated_db):
        venc = (date.today() + timedelta(days=20)).isoformat()
        monitor_uc = MonitorOportunidadesUseCase(populated_db)

        dados_mercado = {
            "BOVA11_12.4_{}".format(venc): {
                "preco_ativo": 18.0, "premio_put": 5.0, "premio_call": 0.5,
            },
            "BOVA11_18.0_{}".format(venc): {
                "preco_ativo": 18.0, "premio_put": 2.0, "premio_call": 2.5,
            },
        }

        resultados = monitor_uc.varrer(dados_mercado)
        if len(resultados) > 1:
            assert resultados[0].viavel or not any(r.viavel for r in resultados)


class TestExportarOperacaoUseCase:
    def test_exportar_log(self, populated_db, tmp_path):
        uc = ExportarOperacaoUseCase(populated_db)
        opp_dict = {
            "ativo": "BOVA11",
            "strike": 18.0,
            "vencimento": "2026-08-21",
            "classificacao": "1BOX",
            "operacao": "BOX",
            "pct_ganho_box": 0.05,
            "pct_cdi_box": 1.5,
            "dias": 20,
            "cod_put": "BOVAT180",
            "cod_call": "BOVAH180",
        }
        result = uc.executar_log(opp_dict, output_dir=tmp_path / "logs")
        assert result.tipo_exportacao == "LOG_OPERACAO"
        assert result.ativo == "BOVA11"
        assert result.filepath != ""
        assert Path(result.filepath).exists()

    def test_exportar_basket(self, populated_db, tmp_path):
        uc = ExportarOperacaoUseCase(populated_db)
        opp_dict = {
            "instrumento_id": 1,
            "ativo": "BOVA11",
            "strike": 18.0,
            "vencimento": (date.today() + timedelta(days=20)).isoformat(),
            "classificacao": "1BOX",
            "operacao": "BOX",
            "pct_ganho_box": 0.05,
            "pct_cdi_box": 1.5,
            "dias": 20,
            "cod_call_itm": "BOVAH124",
            "strike_itm": 12.4,
        }
        result = uc.executar_basket(opp_dict, taxa_ganho=10.0, output_dir=tmp_path / "logs")
        assert result.tipo_exportacao == "BASKET_ITM"
        assert result.ativo == "BOVA11"
        assert len(result.pernas) == 3
        assert Path(result.filepath).exists()

    def test_log_contem_rentabilidade_e_dias(self, populated_db, tmp_path):
        uc = ExportarOperacaoUseCase(populated_db)
        opp_dict = {
            "ativo": "BOVA11", "strike": 18.0,
            "vencimento": "2026-08-21",
            "classificacao": "1BOX", "operacao": "BOX",
            "pct_ganho_box": 0.05, "pct_cdi_box": 1.5,
            "dias": 20,
            "cod_put": "BOVAT180", "cod_call": "BOVAH180",
        }
        result = uc.executar_log(opp_dict, output_dir=tmp_path / "logs")
        assert result.pct_cdi == 1.5
        assert result.dias == 20
