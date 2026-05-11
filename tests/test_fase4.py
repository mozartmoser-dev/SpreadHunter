import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from PyQt5.QtCore import Qt

from src.infrastructure.persistence.database import init_db
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
)
from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.application.dtos.dtos import OportunidadeMonitor
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.infrastructure.providers.mock_market_data import MockMarketDataProvider
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_fase4.db"
    conn = init_db(path)
    conn.close()
    ParametroRepository(path).seed_defaults()
    return path


@pytest.fixture
def populated_db(db_path):
    repo = InstrumentoRepository(db_path)
    venc = date.today() + timedelta(days=30)
    for strike in [12.4, 15.0, 18.0, 20.0]:
        repo.save(InstrumentoOpcional(
            ativo="BOVA11", cod_put="BOVAT{}".format(int(strike * 10)),
            cod_call="BOVAH{}".format(int(strike * 10)),
            strike=strike, vencimento=venc, tipo_opcao=TipoOpcao.AMERICANA,
        ))
    return db_path


def _make_opp(ativo="PETR4", classificacao="1BOX", operacao="BOX", viavel=True,
              strike=18.0, custo_box=100.0, custo_sbth=50.0):
    return OportunidadeMonitor(
        instrumento_id=1, ativo=ativo, strike=strike,
        vencimento="2026-08-21", dias=30,
        cod_put="PETRT180", cod_call="PETRH180",
        tipo_opcao="A", classificacao=classificacao, operacao=operacao,
        custo_box=custo_box, pct_ganho_box=0.80, pct_cdi_box=1.5,
        custo_sbth=custo_sbth, pct_ganho_sbth=0.30, pct_cdi_sbth=1.2,
        cdi_periodo=0.01,
        viavel=viavel,
        preco_compra_ativo=18.01, of_venda_put=2.5, of_compra_call=0.8,
    )


class TestMonitorTableModel:
    def test_empty_model(self):
        model = MonitorTableModel()
        assert model.rowCount() == 0
        assert model.columnCount() == len(MonitorTableModel.COLUMNS)

    def test_update_model(self):
        model = MonitorTableModel()
        opps = [_make_opp("BOVA11"), _make_opp("PETR4")]
        model.atualizar(opps)
        assert model.rowCount() == 2

    def test_data_display_role(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp()])
        index = model.index(0, 0)
        result = model.data(index, Qt.DisplayRole)
        assert str(result) == "PETR4"

    def test_label_tipo_column(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="1BOX")])
        tipo_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "label_tipo"][0]
        index = model.index(0, tipo_col)
        assert model.data(index, Qt.DisplayRole) == "BOX"

    def test_label_tipo_sbth(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="2SBTH", operacao="SBTH")])
        tipo_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "label_tipo"][0]
        index = model.index(0, tipo_col)
        assert model.data(index, Qt.DisplayRole) == "SBTH"

    def test_viavel_display(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(viavel=True)])
        viavel_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "viavel_display"][0]
        index = model.index(0, viavel_col)
        result = model.data(index, Qt.DisplayRole)
        assert str(result) == "SIM"

    def test_nao_viavel_display(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(viavel=False)])
        viavel_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "viavel_display"][0]
        index = model.index(0, viavel_col)
        result = model.data(index, Qt.DisplayRole)
        assert str(result) == "-"

    def test_get_oportunidade_valid(self):
        model = MonitorTableModel()
        opp = _make_opp()
        model.atualizar([opp])
        assert model.get_oportunidade(0) is opp

    def test_get_oportunidade_invalid(self):
        model = MonitorTableModel()
        assert model.get_oportunidade(0) is None

    def test_reset_model(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp()])
        assert model.rowCount() == 1
        model.atualizar([])
        assert model.rowCount() == 0

    def test_ganho_display_box(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="1BOX")])
        ganho_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "ganho_display"][0]
        index = model.index(0, ganho_col)
        assert "80.00%" == model.data(index, Qt.DisplayRole)

    def test_ganho_display_sbth(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="2SBTH", operacao="SBTH")])
        ganho_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "ganho_display"][0]
        index = model.index(0, ganho_col)
        assert "30.00%" == model.data(index, Qt.DisplayRole)

    def test_strike_display(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(strike=18.50)])
        strike_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "strike"][0]
        index = model.index(0, strike_col)
        assert model.data(index, Qt.DisplayRole) == "18.50"

    def test_custo_sbth_display(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(custo_sbth=50.25)])
        col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_sbth_display"][0]
        index = model.index(0, col)
        assert model.data(index, Qt.DisplayRole) == "50.25"

    def test_custo_box_display(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(custo_box=100.75)])
        col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_box_display"][0]
        index = model.index(0, col)
        assert model.data(index, Qt.DisplayRole) == "100.75"

    def test_custo_zero_display(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(custo_sbth=0.0, custo_box=0.0)])
        sbth_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_sbth_display"][0]
        box_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_box_display"][0]
        assert model.data(model.index(0, sbth_col), Qt.DisplayRole) == "-"
        assert model.data(model.index(0, box_col), Qt.DisplayRole) == "-"

    def test_none_value_returns_empty_string(self):
        model = MonitorTableModel()
        opp = _make_opp()
        opp.vencimento = None
        model.atualizar([opp])
        venc_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "vencimento"][0]
        result = model.data(model.index(0, venc_col), Qt.DisplayRole)
        assert result == ""

    def test_custo_sbth_struck_when_box_only(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="1BOX", custo_sbth=50.0)])
        col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_sbth_display"][0]
        index = model.index(0, col)
        font = model.data(index, Qt.FontRole)
        assert font is not None and font.strikeOut() is True
        fg = model.data(index, Qt.ForegroundRole)
        assert fg is not None

    def test_custo_box_struck_when_sbth_only(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="2SBTH", custo_box=100.0)])
        col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_box_display"][0]
        index = model.index(0, col)
        font = model.data(index, Qt.FontRole)
        assert font is not None and font.strikeOut() is True

    def test_custo_not_struck_when_both(self):
        model = MonitorTableModel()
        model.atualizar([_make_opp(classificacao="3BOXSBTH", custo_sbth=50.0, custo_box=100.0)])
        sbth_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_sbth_display"][0]
        box_col = [i for i, c in enumerate(MonitorTableModel.COLUMNS) if c[1] == "custo_box_display"][0]
        assert model.data(model.index(0, sbth_col), Qt.FontRole) is None
        assert model.data(model.index(0, box_col), Qt.FontRole) is None


class TestMockMarketDataProvider:
    def test_gerar_dados(self, populated_db):
        repo = InstrumentoRepository(populated_db)
        instrumentos = repo.get_all()
        provider = MockMarketDataProvider(preco_base=18.0)
        dados = provider.gerar_dados_para_instrumentos(instrumentos)
        assert len(dados) == 4
        for key, d in dados.items():
            assert "preco_ativo" in d
            assert "premio_put" in d
            assert "premio_call" in d
            assert d["preco_ativo"] > 0

    def test_override(self, populated_db):
        repo = InstrumentoRepository(populated_db)
        instrumentos = repo.get_all()
        provider = MockMarketDataProvider(preco_base=18.0)
        inst = instrumentos[0]
        key = "{}_{}_{}".format(inst.ativo, inst.strike, inst.vencimento.isoformat())
        provider.set_override(key, {"preco_ativo": 25.0, "premio_put": 3.0, "premio_call": 1.0})
        dados = provider.gerar_dados_para_instrumentos(instrumentos)
        assert dados[key]["preco_ativo"] == 25.0

    def test_monitor_varrer_com_mock(self, populated_db):
        repo = InstrumentoRepository(populated_db)
        instrumentos = repo.get_all()
        provider = MockMarketDataProvider(preco_base=18.0)
        dados_mercado = provider.gerar_dados_para_instrumentos(instrumentos)

        monitor_uc = MonitorOportunidadesUseCase(populated_db)
        resultados = monitor_uc.varrer(dados_mercado)
        assert len(resultados) == 4
        for r in resultados:
            assert isinstance(r, OportunidadeMonitor)
            assert r.classificacao in ("1BOX", "2SBTH", "3BOXSBTH", "TP.Op")


class TestOportunidadeMonitorDTO:
    def test_resumo_linha_box(self):
        opp = _make_opp(classificacao="1BOX", operacao="BOX")
        resumo = opp.resumo_linha
        assert "PETR4" in resumo
        assert "BOX" in resumo
        assert "30d" in resumo

    def test_resumo_linha_sbth(self):
        opp = _make_opp(classificacao="2SBTH", operacao="SBTH")
        resumo = opp.resumo_linha
        assert "SBTH" in resumo

    def test_label_dias(self):
        opp = _make_opp()
        assert opp.label_dias == "30d"

    def test_label_rentabilidade_tp(self):
        opp = _make_opp(classificacao="TP.Op", operacao="NEUTRA", viavel=False)
        assert opp.label_rentabilidade == "-"

    def test_is_box(self):
        assert _make_opp(classificacao="1BOX").is_box is True
        assert _make_opp(classificacao="3BOXSBTH").is_box is True
        assert _make_opp(classificacao="2SBTH").is_box is False
        assert _make_opp(classificacao="TP.Op").is_box is False

    def test_is_sbth(self):
        assert _make_opp(classificacao="2SBTH").is_sbth is True
        assert _make_opp(classificacao="3BOXSBTH").is_sbth is True
        assert _make_opp(classificacao="1BOX").is_sbth is False
        assert _make_opp(classificacao="TP.Op").is_sbth is False


class TestRTDConfig:
    def test_rtd_topico(self):
        from src.infrastructure.providers.rtd_config import rtd_topico
        assert rtd_topico("PETR4") == "PETR4_B_0"
        assert rtd_topico("PETRP710") == "PETRP710_B_0"

    def test_campos_constantes(self):
        from src.infrastructure.providers import rtd_config as cfg
        assert cfg.RTD_SERVIDOR == "rtdtrading.rtdserver"
        assert cfg.RTD_CAMPO_ULTIMO_PRECO == "ULT"
        assert cfg.RTD_CAMPO_OFERTA_VENDA == "OVD"
        assert cfg.RTD_CAMPO_OFERTA_COMPRA == "OCP"
        assert cfg.RTD_CAMPO_STATUS == "EST"
        assert cfg.RTD_CAMPO_STRIKE == "PEX"
        assert cfg.RTD_CAMPO_VENCIMENTO == "VAL"


class TestDadosRTDInstrumento:
    def test_premio_put_oferta_venda(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=2.5, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=0.8,
            status_put="Aberto", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        assert d.premio_put == 2.5

    def test_premio_put_fallback_compra(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=None, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=0.8,
            status_put="Aberto", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        assert d.premio_put == 2.3

    def test_premio_call_oferta_compra(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=2.5, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=0.8,
            status_put="Aberto", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        assert d.premio_call == 0.8

    def test_premio_call_fallback_venda(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=2.5, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=None,
            status_put="Aberto", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        assert d.premio_call == 1.0

    def test_em_leilao(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=2.5, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=0.8,
            status_put="Leilao", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        assert d.em_leilao is True

    def test_nao_em_leilao(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=2.5, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=0.8,
            status_put="Aberto", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        assert d.em_leilao is False

    def test_to_dados_mercado(self):
        from src.infrastructure.providers.rtd_config import DadosRTDInstrumento
        d = DadosRTDInstrumento(
            ativo="PETR4", cod_put="PETRP710", cod_call="PETRD710",
            preco_ativo=38.0, strike=None, vencimento_rtd=None,
            of_venda_put=2.5, of_compra_put=2.3,
            of_venda_call=1.0, of_compra_call=0.8,
            status_put="Aberto", status_call="Aberto", status_ativo="Aberto",
            cab_put=None, qul_put=None, vov_put=None,
            cab_call=None, qul_call=None, voc_call=None,
        )
        dm = d.to_dados_mercado()
        assert dm["preco_ativo"] == 38.0
        assert dm["of_venda_put"] == 2.5
        assert dm["of_compra_put"] == 2.3
        assert dm["of_venda_call"] == 1.0
        assert dm["of_compra_call"] == 0.8
        assert dm["premio_put"] == 2.5
        assert dm["premio_call"] == 0.8
        assert dm["em_leilao"] is False


class TestRTDProfitWithoutCOM:
    def test_rtd_nao_disponivel_sem_pywin32(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "win32com.client", None)
        from src.infrastructure.providers.rtd_profit import RTDProfit
        rtd = RTDProfit()
        assert rtd.disponivel is False
        assert rtd.ler_campo("PETR4", "ULT") is None
        assert rtd.ler_status("PETR4") == ""
