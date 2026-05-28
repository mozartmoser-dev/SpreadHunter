import pytest
from datetime import date, timedelta
from src.application.dtos.dtos import OportunidadeMonitor
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase


@pytest.fixture
def monitor_uc(tmp_path):
    from src.infrastructure.persistence.database import init_db
    from src.infrastructure.persistence.repositories.repositories import ParametroRepository
    db_path = tmp_path / "test_telegram.db"
    init_db(db_path)
    param_repo = ParametroRepository(db_path)
    param_repo.seed_defaults()
    return MonitorOportunidadesUseCase(db_path)


def test_mensagem_telegram_pct_ganho_formatado_corretamente(monitor_uc):
    opp = OportunidadeMonitor(
        instrumento_id=1,
        ativo="PETR4",
        strike=54.96,
        vencimento=date.today() + timedelta(days=8),
        dias=8,
        cod_put="PETRQ555W5",
        cod_call="PETRQ555W5",
        tipo_opcao="A",
        classificacao="2SBTH",
        operacao="SBTH",
        custo_sbth=54.73,
        pct_ganho_sbth=0.0042,  # 0.42%
        pct_cdi_sbth=1.41,
        custo_box=0.0,
        pct_ganho_box=0.0,
        pct_cdi_box=0.0,
        viavel=True,
        preco_compra_ativo=45.50,
        of_venda_put=9.23,
        of_compra_call=0.0,
    )

    msg = monitor_uc._montar_mensagem_telegram(opp)

    assert "Ganho % SBTH: 0.42%" in msg
    assert "vs CDI SBTH: 1.41x CDI" in msg


def test_mensagem_telegram_pct_ganho_box_formatado_corretamente(monitor_uc):
    opp = OportunidadeMonitor(
        instrumento_id=1,
        ativo="PETR4",
        strike=54.96,
        vencimento=date.today() + timedelta(days=8),
        dias=8,
        cod_put="PETRQ555W5",
        cod_call="PETRQ555W5",
        tipo_opcao="A",
        classificacao="1BOX",
        operacao="BOX",
        custo_sbth=0.0,
        pct_ganho_sbth=0.0,
        pct_cdi_sbth=0.0,
        custo_box=54.73,
        pct_ganho_box=0.0042,  # 0.42%
        pct_cdi_box=1.50,
        viavel=True,
        preco_compra_ativo=45.50,
        of_venda_put=9.23,
        of_compra_call=1.00,
    )

    msg = monitor_uc._montar_mensagem_telegram(opp)

    assert "Ganho % BOX: 0.42%" in msg
    assert "vs CDI BOX: 1.50x CDI" in msg
