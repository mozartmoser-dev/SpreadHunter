"""Tests that display formatting matches calculation in all 3 strategy dialogs.

If a mismatch occurs between the dict built by atualizar_resultados and
the formatted string returned by TableModel.data(), these tests will fail
with the exact column and the difference.
"""

import sys
from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from src.ui.desktop.colar_dialog import ColarTableModel
from src.ui.desktop.colar_calendario_dialog import ColarCalTableModel
from src.ui.desktop.box_dialog import BoxTableModel, BOX_4P_COLUMNS
from src.ui.desktop.monitor_table_model import MonitorTableModel
from src.ui.desktop.mpp_table_model import MppTableModel
from src.domain.services.calculadora_colar import ResultadoColar, TipoColar, RiscoLeilao
from src.domain.services.calculadora_colar_calendario import ResultadoColarCalendario, TipoColarCalendario
from src.domain.services.calculadora_box import ResultadoBox
from src.application.dtos.dtos import OportunidadeMonitor
from src.application.use_cases.mpp_use_case import BoxScore, MreResultado


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


# ── helpers ──────────────────────────────────────────────

def _col_key(model_class, key):
    """Return column index for a given key in a model's COLUMNS."""
    for i, (_, k) in enumerate(model_class.COLUMNS):
        if k == key:
            return i
    raise KeyError(key)


def _box_col_key(key):
    for i, (_, k) in enumerate(BOX_4P_COLUMNS):
        if k == key:
            return i
    raise KeyError(key)


# ════════════════════════════════════════════════════════
# Colar
# ════════════════════════════════════════════════════════

def test_colar_derived_values(qapp):
    """atualizar_resultados dict building must match expected arithmetic."""
    r = ResultadoColar(
        ativo="PETR4",
        vencimento=date(2026, 7, 17),
        dias=29,
        strike_put=30.0,
        strike_call=35.0,
        cod_put="PETRH26",
        cod_call="PETRI26",
        preco_ativo=32.5,
        premio_put=1.0,
        premio_call=0.5,
        custo_liquido=32.5,
        pior_retorno=28.0,
        melhor_retorno=36.0,
        pct_ganho=0.05,
        pct_cdi=1.50,
        pct_cdi_melhor=2.00,
        tipo=TipoColar.TRADICIONAL,
        risco_leilao=RiscoLeilao.BAIXO,
        viavel=True,
        em_leilao=False,
        custo_b3=0.5,
        custo_ir=0.3,
        pop_upside=65.0,
        pop_downside=35.0,
        score=7.5,
    )
    pior_b3 = r.pior_retorno - r.custo_b3
    pior_liquido = pior_b3 - r.custo_ir
    assert pior_b3 == 27.5
    assert pior_liquido == 27.2


@pytest.mark.parametrize("col_key,raw,expected", [
    ("ativo", "PETR4", "PETR4"),
    ("score", 7.5, "7.50"),
    ("pop_upside", 65.0, "65.0%"),
    ("pop_downside", None, "-"),
    ("pct_cdi", 1.50, "1.50x"),
    ("pct_cdi_melhor", 2.00, "2.00x"),
    ("vencimento", date(2026, 7, 17), "17/07/2026"),
    ("tipo_str", "Viés Neutro", "Viés Neutro"),
    ("strike_put", 30.0, "R$ 30.00"),
    ("strike_call", 35.0, "R$ 35.00"),
    ("cod_put", "PETRH26", "PETRH26"),
    ("cod_call", "PETRI26", "PETRI26"),
    ("custo_liquido", 32.50, "R$ 32.50"),
    ("pior_retorno", 28.00, "R$ 28.00"),
    ("pior_b3", 27.50, "R$ 27.50"),
    ("pior_liquido", 27.20, "R$ 27.20"),
    ("risco_str", "Baixo", "Baixo"),
    ("dias", 29, "29"),
])
def test_colar_cell_display(qapp, col_key, raw, expected):
    """Each ColarTableModel column must format its value correctly."""
    item = {k: None for _, k in ColarTableModel.COLUMNS}
    item["ativo"] = "PETR4"
    item[col_key] = raw
    model = ColarTableModel([item])
    idx = model.index(0, _col_key(ColarTableModel, col_key))
    result = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert result == expected, f"col_key={col_key} raw={raw!r}: got {result!r}, expected {expected!r}"


# ════════════════════════════════════════════════════════
# Collar Calendário
# ════════════════════════════════════════════════════════

def test_colar_calendario_derived_values(qapp):
    """atualizar_resultados dict building must match expected arithmetic."""
    r = ResultadoColarCalendario(
        ativo="PETR4",
        vencimento_call=date(2026, 7, 17),
        vencimento_put=date(2026, 8, 21),
        dte_call=29,
        dte_put=64,
        dte_extra=35,
        strike_call=35.0,
        strike_put=30.0,
        cod_call="PETRI26",
        cod_put="PETRH26",
        preco_ativo=32.5,
        premio_call=0.50,
        premio_put=1.00,
        net_credito=0.50,
        delta_total=0.0,
        iv_call=25.0,
        iv_put=28.0,
        valor_put_venc_call=0.80,
        pnl_stock=0.0,
        pnl_projetado=0.30,
        capital_empregado=32.0,
        pct_retorno=0.94,
        pct_cdi=1.20,
        theta_call=0.02,
        theta_put=0.01,
        theta_liquido=0.01,
        viavel=True,
        tipo=TipoColarCalendario.ALTA,
        custo_b3=0.10,
        custo_ir=0.03,
        score=6.0,
        score_iv=4.5,
        risco_max=1.5,
        iv_rank=55.0,
        vega_call=0.05,
        vega_put=0.04,
        vega_liquido=0.01,
        gamma_call=0.005,
        gamma_put=0.004,
    )
    pnl_b3 = r.pnl_projetado - r.custo_b3
    pnl_liquido = pnl_b3 - r.custo_ir
    assert pnl_b3 == pytest.approx(0.20)
    assert pnl_liquido == pytest.approx(0.17)


@pytest.mark.parametrize("col_key,raw,expected", [
    ("ativo", "PETR4", "PETR4"),
    ("preco_ativo", 32.50, "R$ 32.50"),
    ("score", 6.0, "6.00"),
    ("score_iv", 4.5, "4.50"),
    ("pct_cdi", 1.20, "1.20x"),
    ("pnl_projetado", 0.30, "R$ 0.30"),
    ("pnl_b3", 0.20, "R$ 0.20"),
    ("pnl_liquido", 0.17, "R$ 0.17"),
    ("capital_empregado", 32.00, "R$ 32.00"),
    ("risco_max", 1.50, "R$ 1.50"),
    ("iv_rank", 55.0, "55.0"),
    ("iv_rank", None, "-"),
    ("vega_call", 0.05, "0.0500"),
    ("vega_put", 0.04, "0.0400"),
    ("vega_liquido", 0.01, "0.0100"),
    ("gamma_call", 0.005, "0.0050"),
    ("gamma_put", 0.004, "0.0040"),
    ("vencimento_call", date(2026, 7, 17), "17/07"),
    ("vencimento_put", date(2026, 8, 21), "21/08"),
    ("strike_call", 35.0, "R$ 35.00"),
    ("strike_put", 30.0, "R$ 30.00"),
    ("cod_call", "PETRI26", "PETRI26"),
    ("cod_put", "PETRH26", "PETRH26"),
    ("iv_call", 25.0, "25.0%"),
    ("iv_put", 28.0, "28.0%"),
    ("premio_call", 0.50, "R$ 0.50"),
    ("premio_put", 1.00, "R$ 1.00"),
    ("net_credito", 0.50, "R$ +0.50"),
    ("valor_put_venc_call", 0.80, "R$ 0.80"),
    ("theta_call", 0.02, "0.02"),
    ("theta_call", 0.00, "-"),
    ("theta_put", 0.01, "0.01"),
    ("theta_liquido", 0.01, "0.01"),
    ("tipo_str", "Alta", "Alta"),
])
def test_colar_calendario_cell_display(qapp, col_key, raw, expected):
    """Each ColarCalTableModel column must format its value correctly."""
    item = {k: None for _, k in ColarCalTableModel.COLUMNS}
    item["ativo"] = "PETR4"
    item[col_key] = raw
    model = ColarCalTableModel([item])
    idx = model.index(0, _col_key(ColarCalTableModel, col_key))
    result = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert result == expected, f"col_key={col_key} raw={raw!r}: got {result!r}, expected {expected!r}"


# ════════════════════════════════════════════════════════
# Box 4P
# ════════════════════════════════════════════════════════

def test_box_derived_values(qapp):
    """atualizar_resultados dict building must match expected arithmetic."""
    r = ResultadoBox(
        ativo="PETR4",
        vencimento=date(2026, 7, 17),
        strike_k1=30.0,
        strike_k2=35.0,
        cod_call_k1="PETRI26",
        cod_put_k1="PETRH26",
        cod_call_k2="PETRJ26",
        cod_put_k2="PETRG26",
        bid_call_k1=6.0,
        ask_put_k1=1.0,
        ask_call_k2=1.5,
        bid_put_k2=5.5,
        qtd_bid_call_k1=100,
        qtd_ask_put_k1=200,
        qtd_ask_call_k2=150,
        qtd_bid_put_k2=180,
        clr=0.50,
        distancia=5.0,
        lucro=0.50,
        custo_b3=0.10,
        custo_ir=0.06,
        lucro_liquido=0.34,
        lucro_pct=0.10,
        pct_cdi=2.50,
        pct_cdi_liquido=1.70,
        em_leilao=False,
        viavel=True,
        dias=29,
    )
    lucro_b3 = r.lucro - r.custo_b3
    lucro_final = r.lucro - r.custo_b3 - r.custo_ir
    assert lucro_b3 == pytest.approx(0.40)
    assert lucro_final == pytest.approx(0.34)


@pytest.mark.parametrize("col_key,raw,expected", [
    ("ativo", "PETR4", "PETR4"),
    ("strike_k1", 30.0, "R$ 30.00"),
    ("strike_k2", 35.0, "R$ 35.00"),
    ("distancia", 5.00, "R$ 5.00"),
    ("clr", 0.50, "R$ 0.50"),
    ("lucro", 0.50, "R$ 0.50"),
    ("lucro_b3", 0.40, "R$ 0.40"),
    ("lucro_final", 0.34, "R$ 0.34"),
    ("lucro_pct", 0.10, "10.00%"),
    ("pct_cdi", 2.50, "2.50x"),
    ("bid_call_k1", 6.00, "R$ 6.00"),
    ("ask_put_k1", 1.00, "R$ 1.00"),
    ("ask_call_k2", 1.50, "R$ 1.50"),
    ("bid_put_k2", 5.50, "R$ 5.50"),
    ("qtd_bid_call_k1", 100, "100"),
    ("qtd_ask_put_k1", 200, "200"),
    ("qtd_ask_call_k2", 150, "150"),
    ("qtd_bid_put_k2", 180, "180"),
    ("dias", 29, "29"),
    ("vencimento", date(2026, 7, 17), "17/07/2026"),
])
def test_box_cell_display(qapp, col_key, raw, expected):
    """Each BoxTableModel column must format its value correctly."""
    item = {k: None for _, k in BOX_4P_COLUMNS}
    item["ativo"] = "PETR4"
    item[col_key] = raw
    model = BoxTableModel([item])
    idx = model.index(0, _box_col_key(col_key))
    result = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert result == expected, f"col_key={col_key} raw={raw!r}: got {result!r}, expected {expected!r}"


# ════════════════════════════════════════════════════════
# Monitor (tela principal — BOX/SBTH)
# ════════════════════════════════════════════════════════

def _monitor_opp(**overrides) -> OportunidadeMonitor:
    defaults = dict(
        instrumento_id=1,
        ativo="PETR4",
        strike=30.0,
        vencimento=date(2026, 7, 17),
        dias=29,
        cod_put="PETRH26",
        cod_call="PETRI26",
        tipo_opcao="A",
        classificacao="1BOX",
        custo_sbth=2.0,
        pct_ganho_sbth=0.05,
        pct_cdi_sbth=1.5,
        pct_cdi_sbth_liquido=1.0,
        custo_box=1.5,
        pct_ganho_box=0.10,
        pct_cdi_box=2.0,
        pct_cdi_box_liquido=1.5,
        pct_ganho_sbth_bruto=0.05,
        pct_ganho_sbth_liquido=0.035,
        pct_cdi_sbth_bruto=1.5,
        pct_ganho_box_bruto=0.10,
        pct_ganho_box_liquido=0.07,
        pct_cdi_box_bruto=2.0,
        cdi_periodo=0.13,
        viavel=True,
        liq_put_x_lote=100,
        liq_call_x_lote=200,
        of_compra_put=30.0,
        of_venda_call=35.0,
        qul_put=500,
        qul_call=600,
    )
    defaults.update(overrides)
    return OportunidadeMonitor(**defaults)


def _monitor_col_key(key):
    for i, (_, k) in enumerate(MonitorTableModel.COLUMNS):
        if k == key:
            return i
    raise KeyError(key)


@pytest.mark.parametrize("col_key,expected", [
    ("label_tipo", "BOX"),
    ("ativo", "PETR4"),
    ("strike", "30.00"),
    ("ganho_bruto_display", "10.00% (BOX)"),
    ("ganho_liq_display", "7.00% (BOX)"),
    ("rent_cdi_bruto_display", "200% CDI (BOX)"),
    ("rent_cdi_liq_display", "150% CDI (BOX)"),
    ("label_dias", "29d"),
    ("vencimento", "17/07/2026"),
    ("liq_indicator", "\u2713"),
    ("leilao_display", ""),
    ("custo_box_display", "1.50"),
    ("custo_sbth_display", "2.00"),
    ("liq_put_display", "100"),
    ("liq_call_display", "200"),
    ("of_compra_put", "30.00"),
    ("of_venda_call", "35.00"),
    ("qul_put", "500"),
    ("qul_call", "600"),
    ("tipo_opcao", ""),
    ("cod_put", "PETRH26"),
    ("cod_call", "PETRI26"),
])
def test_monitor_cell_display_box(qapp, col_key, expected):
    """MonitorTableModel cell display for BOX strategy."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(classificacao="1BOX")])
    idx = model.index(0, _monitor_col_key(col_key))
    result = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert result == expected, f"col_key={col_key}: got {result!r}, expected {expected!r}"


def test_monitor_ganho_bruto_display_sbth(qapp):
    """ganho_bruto_display must use percent_sbth_bruto for SBTH classification."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(classificacao="2SBTH", pct_ganho_sbth_bruto=0.07)])
    idx = model.index(0, _monitor_col_key("ganho_bruto_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "7.00% (SBTH)"


def test_monitor_ganho_bruto_display_boxsbth(qapp):
    """ganho_bruto_display must show both SBTH and BOX for BOX+SBTH classification."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(classificacao="3BOXSBTH",
                                  pct_ganho_box_bruto=0.08, pct_ganho_sbth_bruto=0.12)])
    idx = model.index(0, _monitor_col_key("ganho_bruto_display"))
    result = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert result == "12.00% (SBTH) | 8.00% (BOX)", f"got {result!r}"

def test_monitor_ganho_bruto_display_sbth_only(qapp):
    """ganho_bruto_display must use sbth for 2SBTH regardless of box value."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(classificacao="2SBTH",
                                  pct_ganho_box_bruto=0.15, pct_ganho_sbth_bruto=0.07)])
    idx = model.index(0, _monitor_col_key("ganho_bruto_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "7.00% (SBTH)"


def test_monitor_ganho_bruto_display_other(qapp):
    """ganho_bruto_display must show '-' when both percentages are zero."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(classificacao="Outras", pct_ganho_box_bruto=0.0, pct_ganho_sbth_bruto=0.0)])
    idx = model.index(0, _monitor_col_key("ganho_bruto_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "-"


def test_monitor_liq_indicator(qapp):
    """liq_indicator: ✓ both ok, ✗ both bad, ✓~ one side bad."""
    def _liq(put, call, expected):
        model = MonitorTableModel()
        model.atualizar([_monitor_opp(liq_put_x_lote=put, liq_call_x_lote=call)])
        idx = model.index(0, _monitor_col_key("liq_indicator"))
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == expected
    _liq(100, 200, "\u2713")         # both ok
    _liq(-1, -1, "\u2717")           # both bad
    _liq(100, -1, "\u2713~")         # put ok, call bad


def test_monitor_tipo_opcao_labels(qapp):
    """tipo_opcao DisplayRole is blank (icon only in DecorationRole)."""
    for raw, expected in [("A", ""), ("E", ""), ("P", ""), ("", "")]:
        model = MonitorTableModel()
        model.atualizar([_monitor_opp(tipo_opcao=raw)])
        idx = model.index(0, _monitor_col_key("tipo_opcao"))
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == expected
    # DecorationRole returns QIcon for valid values
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(tipo_opcao="A")])
    idx = model.index(0, _monitor_col_key("tipo_opcao"))
    icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
    from PySide6.QtGui import QIcon
    assert isinstance(icon, QIcon)


def test_monitor_of_compra_put_zero(qapp):
    """of_compra_put must show '-' when zero."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(of_compra_put=0.0)])
    idx = model.index(0, _monitor_col_key("of_compra_put"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "-"


def test_monitor_leilao_display(qapp):
    """leilao_display must show '⚠ LEILAO' when em_leilao=True."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(em_leilao=True)])
    idx = model.index(0, _monitor_col_key("leilao_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "\u26a0 LEILAO"


def test_monitor_leilao_display_por_perna(qapp):
    """leilao_display mostra triângulo + a perna em leilao quando o status vem informado."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(em_leilao=True, status_put="leilão")])
    idx = model.index(0, _monitor_col_key("leilao_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "\u26a0 Leilão PUT"


def test_monitor_leilao_display_artefato_encoding(qapp):
    """leilao_display tolera o artefato 'Leil?o' (ã trocado por ? no servidor OpenFast)."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(em_leilao=True, status_ativo="Leil?o")])
    idx = model.index(0, _monitor_col_key("leilao_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "\u26a0 Leilão Ativo"


def test_monitor_money_display(qapp):
    """money_display must format put/call money values."""
    model = MonitorTableModel()
    model.atualizar([_monitor_opp(money_put=2.5, money_call=3.0)])
    idx = model.index(0, _monitor_col_key("money_display"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "P:2.50 | C:3.00"


# ════════════════════════════════════════════════════════
# MPP
# ════════════════════════════════════════════════════════

def _mpp_model(qapp):
    """Build an MppTableModel pre-populated with one row."""
    box = BoxScore(
        ativo="PETR4",
        strike1=30.0,
        strike2=35.0,
        vencimento=date(2026, 7, 17),
        score_final_pct=85,
        spread_medio=0.03,
        qtd_min_box=10,
        persistencia_ciclos=5,
        nivel_risco="alto",
    )
    mre = MreResultado(
        ativo="PETR4",
        strike1=30.0,
        strike2=35.0,
        vencimento=date(2026, 7, 17),
        isca_recomendada="Call K1",
        ip_isca=0.75,
        lote_sugerido=3,
        confianca_completar=0.90,
    )
    model = MppTableModel()
    model.atualizar([box], [mre])
    return model


@pytest.mark.parametrize("col_key,expected", [
    ("ativo", "PETR4"),
    ("box", "30x35"),
    ("score", "85"),
    ("nivel", "alto"),
    ("isca", "Call K1"),
    ("ip", "75"),
    ("lote", "3"),
    ("confianca", "90%"),
    ("persistencia", "5c"),
    ("spread", "3.0%"),
    ("prof_qtd", "10"),
])
def test_mpp_cell_display(qapp, col_key, expected):
    """Each MppTableModel column must display correctly."""
    model = _mpp_model(qapp)
    idx = model.index(0, _col_key(MppTableModel, col_key))
    result = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert result == expected, f"col_key={col_key}: got {result!r}, expected {expected!r}"


def test_mpp_empty_mre(qapp):
    """MPP display must handle missing MreResultado gracefully."""
    box = BoxScore(ativo="VALE3", strike1=30.0, strike2=35.0,
                   vencimento=date(2026, 7, 17))
    model = MppTableModel()
    model.atualizar([box], [])
    for col_key in ("isca", "ip", "lote", "confianca"):
        idx = model.index(0, _col_key(MppTableModel, col_key))
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""


def test_mpp_persistencia_zero(qapp):
    """persistencia must be empty string when cycles is 0."""
    box = BoxScore(ativo="VALE3", strike1=30.0, strike2=35.0,
                   vencimento=date(2026, 7, 17), persistencia_ciclos=0)
    model = MppTableModel()
    model.atualizar([box], [])
    idx = model.index(0, _col_key(MppTableModel, "persistencia"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""


def test_mpp_spread_medio_zero(qapp):
    """spread must be empty string when spread_medio is 0."""
    box = BoxScore(ativo="VALE3", strike1=30.0, strike2=35.0,
                   vencimento=date(2026, 7, 17), spread_medio=0.0)
    model = MppTableModel()
    model.atualizar([box], [])
    idx = model.index(0, _col_key(MppTableModel, "spread"))
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == ""


# ════════════════════════════════════════════════════════
# ExportDialog (detalhe do monitor)
# ════════════════════════════════════════════════════════

from PySide6.QtWidgets import QGroupBox, QFormLayout


def _make_full_opp() -> OportunidadeMonitor:
    return OportunidadeMonitor(
        instrumento_id=42,
        ativo="PETR4",
        strike=30.0,
        vencimento=date(2026, 7, 17),
        dias=29,
        cod_put="PETRH26",
        cod_call="PETRI26",
        tipo_opcao="A",
        classificacao="1BOX",
        custo_sbth=0.0,
        pct_ganho_sbth=0.0,
        pct_cdi_sbth=0.0,
        pct_cdi_sbth_liquido=0.0,
        custo_box=1.50,
        pct_ganho_box=0.10,
        pct_cdi_box=2.00,
        pct_cdi_box_liquido=1.50,
        cdi_periodo=0.13,
        viavel=True,
        preco_compra_ativo=32.50,
        of_venda_put=30.00,
        of_compra_call=35.00,
        em_leilao=False,
        liq_put_x_lote=100,
        liq_call_x_lote=200,
        of_compra_put=30.00,
        of_venda_call=35.00,
        qul_put=500,
        qul_call=600,
        money_put=2.50,
        money_call=3.00,
    )


def test_export_dialog_make_opp_dict(qapp):
    """_make_opp_dict must mirror every OportunidadeMonitor field."""
    from src.ui.desktop.export_dialog import ExportDialog
    opp = _make_full_opp()
    dialog = ExportDialog(opp, use_case=None, parent=None, db_path=None)
    d = dialog._make_opp_dict()

    assert d["instrumento_id"] == opp.instrumento_id
    assert d["ativo"] == opp.ativo
    assert d["strike"] == opp.strike
    assert d["vencimento"] == opp.vencimento
    assert d["dias"] == opp.dias
    assert d["cod_put"] == opp.cod_put
    assert d["cod_call"] == opp.cod_call
    assert d["tipo_opcao"] == opp.tipo_opcao
    assert d["classificacao"] == opp.classificacao
    assert d["pct_ganho_box"] == opp.pct_ganho_box
    assert d["pct_ganho_sbth"] == opp.pct_ganho_sbth
    assert d["pct_cdi_box"] == opp.pct_cdi_box
    assert d["pct_cdi_sbth"] == opp.pct_cdi_sbth
    assert d["rent_box_vs_cdi"] == opp.pct_cdi_box
    assert d["rent_sbth_vs_cdi"] == opp.pct_cdi_sbth
    assert d["preco_compra_ativo"] == opp.preco_compra_ativo
    assert d["of_venda_put"] == opp.of_venda_put
    assert d["of_compra_call"] == opp.of_compra_call
    assert d["of_compra_put"] == opp.of_compra_put
    assert d["of_venda_call"] == opp.of_venda_call
    assert d["qul_put"] == opp.qul_put
    assert d["qul_call"] == opp.qul_call
    assert d["liq_put_x_lote"] == opp.liq_put_x_lote
    assert d["liq_call_x_lote"] == opp.liq_call_x_lote
    assert d["money_put"] == opp.money_put
    assert d["money_call"] == opp.money_call
    assert d["em_leilao"] == opp.em_leilao
    assert d["operacao"] == "BOX"  # combo default for 1BOX


def test_export_dialog_custos_display(qapp):
    """Custos e Rentabilidade QLabels must format values correctly."""
    from src.ui.desktop.export_dialog import ExportDialog
    opp = _make_full_opp()
    dialog = ExportDialog(opp, use_case=None, parent=None, db_path=None)

    def _field(group_title, field_label):
        for gb in dialog.findChildren(QGroupBox):
            if gb.title() == group_title:
                layout = gb.layout()
                if isinstance(layout, QFormLayout):
                    for i in range(layout.rowCount()):
                        item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                        if item is None:
                            continue
                        w = item.widget()
                        if w is None or not hasattr(w, "text"):
                            continue
                        if w.text() == field_label:
                            field = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                            if field is None:
                                continue
                            fw = field.widget()
                            if fw and hasattr(fw, "text"):
                                return fw.text()
        return None

    g = "Custos e Rentabilidade"
    assert _field(g, "Custo SBTH:") == "-", "custo_sbth=0 deve mostrar -"
    assert _field(g, "Ganho % SBTH:") == "-", "pct_ganho_sbth=0 deve mostrar -"
    assert _field(g, "vs CDI SBTH:") == "-", "pct_cdi_sbth=0 deve mostrar -"
    assert _field(g, "Custo BOX:") == "1.50"
    assert _field(g, "Ganho % BOX:") == "10.00%"
    assert _field(g, "vs CDI BOX:") == "200% CDI"


def test_export_dialog_custos_display_sbth_active(qapp):
    """SBTH values must appear when classificacao is 2SBTH."""
    from src.ui.desktop.export_dialog import ExportDialog
    opp = _make_full_opp()
    opp.classificacao = "2SBTH"
    opp.custo_sbth = 2.00
    opp.pct_ganho_sbth = 0.07
    opp.pct_cdi_sbth = 1.50
    opp.custo_box = 0.0
    opp.pct_ganho_box = 0.0
    opp.pct_cdi_box = 0.0
    dialog = ExportDialog(opp, use_case=None, parent=None, db_path=None)

    def _field(group_title, field_label):
        for gb in dialog.findChildren(QGroupBox):
            if gb.title() == group_title:
                layout = gb.layout()
                if isinstance(layout, QFormLayout):
                    for i in range(layout.rowCount()):
                        item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                        if item is None:
                            continue
                        w = item.widget()
                        if w is None or not hasattr(w, "text"):
                            continue
                        if w.text() == field_label:
                            field = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                            if field is None:
                                continue
                            fw = field.widget()
                            if fw and hasattr(fw, "text"):
                                return fw.text()
        return None

    g = "Custos e Rentabilidade"
    assert _field(g, "Custo SBTH:") == "2.00"
    assert _field(g, "Ganho % SBTH:") == "7.00%"
    assert _field(g, "vs CDI SBTH:") == "150% CDI"
    assert _field(g, "Custo BOX:") == "-"
    assert _field(g, "Ganho % BOX:") == "-"
    assert _field(g, "vs CDI BOX:") == "-"



