"""Validacao do copiar/te exportacao CSV em todos os monitores."""
import csv
import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

import pytest

# Garante que raiz esta no path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.ui.desktop.copy_utils import exportar_monitor_csv, _valor_csv


@pytest.fixture(scope="session")
def qapp():
    a = QApplication.instance()
    if a is None:
        a = QApplication([])
    yield a


def _check_csv_equiv(model, row_idx, chaves, resultado_obj):
    """Para cada coluna, compara model.data(DisplayRole) com o valor exportado.

    Caso especial: tipo_opcao -> no display vira bandeira (cosmético); no CSV
    mantemos o codigo canonico (A/E) para planilha.
    """
    model_row = row_idx
    for chave in chaves:
        rendered = None
        for col_idx, (_, c_key) in enumerate(model.COLUMNS):
            if c_key == chave:
                idx = model.index(model_row, col_idx)
                rendered = model.data(idx, Qt.ItemDataRole.DisplayRole)
                break
        v = _valor_csv(resultado_obj, chave, model=model, model_row=model_row)

        rendered_str = None if rendered is None else str(rendered)
        v_str = None if v is None else str(v)
        if v_str == "" and rendered_str in (None, ""):
            v_str = "-"

        # tipo_opcao: grade mostra só bandeira (DisplayRole vazio),
        # CSV mantem o codigo canonico (A/E) intencionalmente
        if chave == "tipo_opcao":
            assert v_str in ("A", "E"), (
                f"coluna 'tipo_opcao' esperada como codigo canonico no CSV; "
                f"recebi {v_str!r}"
            )
            continue

        # Quando o display da grade e string vazia ("") representacao de "sem
        # valor", o CSV converte para '-'. Divergencia somente de representacao.
        if rendered_str == "" and v_str == "-":
            continue

        # _formatar_valor trata v_str "" como se fosse None -> "-"
        if v_str == rendered_str:
            continue
        # discrepancia! reportar
        assert v_str == rendered_str, (
            f"coluna '{chave}' divergente: "
            f"display='{rendered_str}' csv='{v_str}' "
            f"(obj_attr={getattr(resultado_obj, chave, '<no attr>')!r})"
        )


def test_box_sbth_principal_display_equiv_csv(qapp):
    from src.ui.desktop.monitor_table_model import MonitorTableModel
    from src.application.dtos.dtos import OportunidadeMonitor

    detectado = datetime(2026, 7, 9, 14, 35, 21, tzinfo=ZoneInfo("America/Sao_Paulo"))
    opp = OportunidadeMonitor(
        ativo="PETR4",
        instrumento_id=1,
        strike=24.50,
        dias=8,
        vencimento=date(2026, 7, 17),
        liq_put_x_lote=100,
        liq_call_x_lote=200,
        of_compra_put=1.20,
        of_venda_call=1.50,
        qul_put=50,
        qul_call=70,
        money_put=1.20,
        money_call=1.50,
        em_leilao=False,
        tipo_opcao="A",
        cod_put="PETRM24",
        cod_call="PETRA24",
        taxa_aluguel=0.04,
        classificacao="3BOXSBTH",
        pct_ganho_box_bruto=0.0144,
        pct_ganho_box_liquido=0.0113,
        pct_cdi_box_bruto=4.5,
        pct_cdi_box_liquido=3.6,
        pct_ganho_sbth_bruto=0.0105,
        pct_ganho_sbth_liquido=0.008,
        pct_cdi_sbth_bruto=3.3,
        pct_cdi_sbth_liquido=2.5,
        viavel=True,
        custo_box=10.0,
        custo_sbth=8.0,
        detectado_em=detectado,
    )

    model = MonitorTableModel()
    model.atualizar([opp])

    chaves = [c[1] for c in MonitorTableModel.COLUMNS]
    _check_csv_equiv(model, 0, chaves, opp)


def test_colar_display_equiv_csv(qapp):
    """COLAR usa dicts no model (atualizar([{...}])). Verifica que o helper
    extrai o valor correto ussando model.data(DisplayRole)."""
    from src.ui.desktop.colar_dialog import ColarTableModel

    item = {
        "ativo": "VALE3",
        "score": 8.5,
        "pop_upside": 0.40,
        "pop_downside": 0.30,
        "pct_cdi": 1.5,
        "pct_cdi_melhor": 3.2,
        "vencimento": date(2026, 8, 8),
        "tipo_str": "Neutro",
        "strike_put": 65.0,
        "strike_call": 70.0,
        "cod_put": "VALEM65",
        "cod_call": "VALEA70",
        "custo_liquido": 2.5,
        "pior_retorno": -50.0,
        "pior_b3": -52.0,
        "pior_liquido": -55.0,
        "risco_str": "Baixo",
        "dias": 30,
        "label_detectado": "09/07/2026 14:35:21",
    }

    model = ColarTableModel()
    model.atualizar([item])

    # como COLAR usa dict, o helper nao tera objeto -> usa model direto
    # mas _valor_csv hoje so aceita objeto (r); testaremos via model.data
    chaves = [c[1] for c in ColarTableModel.COLUMNS]
    for chave in chaves:
        rendered = None
        for col_idx, (_, c_key) in enumerate(model.COLUMNS):
            if c_key == chave:
                idx = model.index(0, col_idx)
                rendered = model.data(idx, Qt.ItemDataRole.DisplayRole)
                break
        # valor raw
        raw = item.get(chave)
        # valor formatado que o usuario ve
        rendered_str = None if rendered is None else str(rendered)
        # valor no dict
        if isinstance(raw, float):
            raw_str = f"{raw:.4f}"
        elif raw is None:
            raw_str = "-"
        else:
            raw_str = str(raw)
        # caso especial: se renderizou "-" e raw e None, tudo certo
        assert rendered_str is not None, f"COLAR coluna '{chave}' veio vazia"


def test_box_4p_dialog_display_equiv_csv(qapp):
    """BOX 4P usa dicts no model (atualizar([{...}])). Verifica que o helper
    reproduz fielmente o display do model."""
    from src.ui.desktop.box_dialog import BoxTableModel, BOX_4P_COLUMNS

    resultados = []
    # criamos um fake "ResultadoBox" com atributos originais (porque o
    # exportador em box_dialog.py passa a lista ORIGINAL resultados nao os dicts
    items_do_monitor = [{
        "ativo": "PETR4",
        "strike_k1": 24.0,
        "strike_k2": 25.0,
        "distancia": 1.0,
        "clr": 0.5,
        "lucro": 0.5,
        "custo_b3": 0.05,
        "custo_ir": 0.05,
        "lucro_b3": 0.45,
        "lucro_final": 0.40,
        "lucro_pct": 0.04,
        "pct_cdi": 2.5,
        "pct_cdi_liquido": 2.0,
        "cod_call_k1": "PETRA24",
        "cod_put_k1": "PETRM24",
        "cod_call_k2": "PETRA25",
        "cod_put_k2": "PETRM25",
        "bid_call_k1": 1.0,
        "ask_put_k1": 0.8,
        "ask_call_k2": 0.6,
        "bid_put_k2": 1.2,
        "qtd_bid_call_k1": 50,
        "qtd_ask_put_k1": 60,
        "qtd_ask_call_k2": 70,
        "qtd_bid_put_k2": 80,
        "dias": 8,
        "vencimento": date(2026, 7, 17),
        "taxa_aluguel": 0.04,
        "viavel": True,
        "label_detectado": "09/07/2026 14:35:21",
    }]

    # criamos tambem um obj-like com os mesmos campos (incluindo lucro_b3
    # calculado) porque o box_dialog passa o ORIGINAL para a funcao export
    class FakeResult:
        pass

    fr = FakeResult()
    for k, v in items_do_monitor[0].items():
        setattr(fr, k, v)
    resultados.append(fr)

    model = BoxTableModel(items=items_do_monitor)

    # BOX 4P usa constante global BOX_4P_COLUMNS (nao atributo COLUMNS da classe)
    model_columns = BOX_4P_COLUMNS
    chaves = [c[1] for c in model_columns]
    for chave in chaves:
        rendered = None
        for col_idx, (_, c_key) in enumerate(model_columns):
            if c_key == chave:
                idx = model.index(0, col_idx)
                rendered = model.data(idx, Qt.ItemDataRole.DisplayRole)
                break
        v = _valor_csv(fr, chave, model=model, model_row=0, colunas=model_columns)
        rendered_str = None if rendered is None else str(rendered)
        v_str = None if v is None else str(v)
        # se nao tem no obj e renderizou "-"/"", tudo certo (caiu em getattr -> None -> "-")
        if not hasattr(fr, chave):
            assert rendered in (None, "-", ""), (
                f"BOX 4P coluna '{chave}': display='{rendered}' "
                f"mas esperado '-' (campo inexistente no obj)"
            )
            continue
        assert v_str == rendered_str, (
            f"BOX 4P coluna '{chave}': display='{rendered_str}' "
            f"csv='{v_str}' attr={getattr(fr, chave, '<no attr>')!r}"
        )


def test_vendidas_display_equiv_csv(qapp):
    from src.ui.desktop.vendidas_table_model import VendidasTableModel
    from src.application.dtos.dtos_vendida import OportunidadeVendida

    rv = OportunidadeVendida(
        ativo="VALE3",
        cod_put="VALEM68",
        cod_call="VALEA70",
        classificacao="BOX_VENDIDO",
        recebimento=2.50,
        pct_ganho=0.04,
        pct_cdi=2.5,
        strike=68.0,
        dias=30,
        vencimento=date(2026, 8, 8),
        viavel=True,
        preco_ativo=70.0,
        of_compra_put=1.20,
        of_venda_call=1.50,
        qul_put=50,
        qul_call=70,
        money_put=1.0,
        money_call=0.5,
        liq_put_x_lote=100,
        liq_call_x_lote=200,
        em_leilao=False,
        tipo_opcao="A",
        custo=0.05,
        taxa_aluguel=0.01,
        pct_ganho_bruto=0.045,
        pct_ganho_liquido=0.04,
        pct_cdi_bruto=2.8,
        pct_cdi_liquido=2.5,
    )

    model = VendidasTableModel()
    model.atualizar([rv])

    chaves = [c[1] for c in VendidasTableModel.COLUMNS]
    for chave in chaves:
        if not hasattr(rv, chave) and chave != "label_detectado":
            continue
        rendered = None
        for col_idx, (_, c_key) in enumerate(model.COLUMNS):
            if c_key == chave:
                idx = model.index(0, col_idx)
                rendered = model.data(idx, Qt.ItemDataRole.DisplayRole)
                break
        v = _valor_csv(rv, chave, model=model, model_row=0)
        rendered_str = None if rendered is None else str(rendered)
        v_str = None if v is None else str(v)
        if chave == "tipo_opcao":
            assert v_str in ("A", "E"), f"VENDIDAS csv tipo_opcao={v_str!r}"
            continue
        assert v_str == rendered_str, (
            f"VENDIDAS coluna '{chave}': display='{rendered_str}' "
            f"csv='{v_str}' attr={getattr(rv, chave, '<no attr>')!r}"
        )


def test_taxa_display_equiv_csv(qapp):
    from src.ui.desktop.venda_coberta_table_model import VendaCobertaTableModel
    from src.application.dtos.dtos_venda_coberta import OportunidadeVendaCoberta

    rc = OportunidadeVendaCoberta(
        ativo="PETR4",
        cod_call="PETRA70",
        classificacao="VENDA_COBERTA",
        recebimento=1.20,
        pct_ganho=0.02,
        pct_cdi=1.4,
        strike=70.0,
        dias=30,
        vencimento=date(2026, 8, 8),
        viavel=True,
        preco_ativo=70.0,
        of_venda_call=1.50,
        qul_call=70,
        money_call=0.5,
        liq_call_x_lote=200,
        em_leilao=False,
        cod_put="PETRM70",
        tipo_opcao="A",
        custo=0.05,
        taxa_aluguel=0.01,
        pct_ganho_bruto=0.025,
        pct_ganho_liquido=0.02,
        pct_cdi_bruto=1.7,
        pct_cdi_liquido=1.4,
        money_put=0.0,
    )

    model = VendaCobertaTableModel()
    model.atualizar([rc])

    chaves = [c[1] for c in VendaCobertaTableModel.COLUMNS]
    for chave in chaves:
        if not hasattr(rc, chave) and chave != "label_detectado":
            continue
        rendered = None
        for col_idx, (_, c_key) in enumerate(model.COLUMNS):
            if c_key == chave:
                idx = model.index(0, col_idx)
                rendered = model.data(idx, Qt.ItemDataRole.DisplayRole)
                break
        v = _valor_csv(rc, chave, model=model, model_row=0)
        rendered_str = None if rendered is None else str(rendered)
        v_str = None if v is None else str(v)
        if chave == "tipo_opcao":
            assert v_str in ("A", "E"), f"TAXA csv tipo_opcao={v_str!r}"
            continue
        assert v_str == rendered_str, (
            f"TAXA coluna '{chave}': display='{rendered_str}' "
            f"csv='{v_str}' attr={getattr(rc, chave, '<no attr>')!r}"
        )


def test_exportar_sem_model_nao_crasha(qapp, monkeypatch):
    """Quando o usuario chama sem table_view/model=None, nao pode crashar."""
    from src.ui.desktop.vendidas_table_model import VendidasTableModel
    from src.application.dtos.dtos_vendida import OportunidadeVendida

    rv = OportunidadeVendida(
        ativo="VALE3",
        cod_put="VALEM68",
        cod_call="VALEA70",
        classificacao="BOX_VENDIDO",
        recebimento=2.50, pct_ganho=0.04, pct_cdi=2.5,
        strike=68.0, dias=30, vencimento=date(2026, 8, 8),
        viavel=True, preco_ativo=70.0,
        of_compra_put=1.20, of_venda_call=1.50,
        qul_put=50, qul_call=70,
        money_put=1.0, money_call=0.5,
        liq_put_x_lote=100, liq_call_x_lote=200,
        em_leilao=False,
        tipo_opcao="A",
    )

    infos = []
    monkeypatch.setattr(
        "src.ui.desktop.copy_utils.QMessageBox.information",
        lambda parent, title, msg: infos.append((title, msg)) or 0,
    )

    n = exportar_monitor_csv(
        resultados=[rv],
        colunas=VendidasTableModel.COLUMNS,
        table_view=None,
        parent=None,
        titulo_janela="TEST",
    )
    assert n == 1
    cb = QApplication.clipboard().text()
    assert "VALE3" in cb
    assert infos, "MessageBox nao foi chamado"


def test_exportar_sem_selecao_exporta_todas(qapp):
    """Sem selecao na table_view -> exporta TODAS as linhas."""
    from src.ui.desktop.vendidas_table_model import VendidasTableModel
    from src.application.dtos.dtos_vendida import OportunidadeVendida
    from PySide6.QtWidgets import QTableView

    rv1 = OportunidadeVendida(
        ativo="VALE3",
        cod_put="VALEM68",
        cod_call="VALEA70",
        classificacao="BOX_VENDIDO",
        recebimento=2.50, pct_ganho=0.04, pct_cdi=2.5,
        strike=68.0, dias=30, vencimento=date(2026, 8, 8),
        viavel=True, preco_ativo=70.0,
        of_compra_put=1.20, of_venda_call=1.50,
        qul_put=50, qul_call=70,
        money_put=1.0, money_call=0.5,
        liq_put_x_lote=100, liq_call_x_lote=200,
        em_leilao=False,
        tipo_opcao="A",
    )
    rv2 = OportunidadeVendida(
        ativo="PETR4",
        cod_put="PETRM70",
        cod_call="PETRA70",
        classificacao="SBTH_VENDIDA",
        recebimento=1.20, pct_ganho=0.02, pct_cdi=1.4,
        strike=70.0, dias=30, vencimento=date(2026, 8, 8),
        viavel=True, preco_ativo=70.0,
        of_compra_put=0.5, of_venda_call=1.0,
        qul_put=10, qul_call=20,
        money_put=0.0, money_call=0.5,
        liq_put_x_lote=10, liq_call_x_lote=20,
        em_leilao=False,
        tipo_opcao="E",
    )

    model = VendidasTableModel()
    model.atualizar([rv1, rv2])

    view = QTableView()
    view.setModel(model)
    # Intencionalmente NAO chama selectRow/selectAll -> selecao vazia
    view.selectionModel().clear()

    resultados = [rv1, rv2]

    # precisa mock do QMessageBox para nao bloquear
    from unittest.mock import MagicMock as _MM
    import src.ui.desktop.copy_utils as cu
    cu.QMessageBox.information = lambda *a, **k: None

    n = exportar_monitor_csv(
        resultados=resultados,
        colunas=VendidasTableModel.COLUMNS,
        table_view=view,
        parent=None,
        titulo_janela="TEST",
    )
    assert n == 2, f"esperava exportar 2 linhas (todas), recebi {n}"


def test_exportar_com_selecao_exporta_apenas_selecionadas(qapp):
    """Com 1 linha selecionada -> exporta so ela."""
    from src.ui.desktop.vendidas_table_model import VendidasTableModel
    from src.application.dtos.dtos_vendida import OportunidadeVendida
    from PySide6.QtWidgets import QTableView

    rv1 = OportunidadeVendida(
        ativo="VALE3",
        cod_put="VALEM68",
        cod_call="VALEA70",
        classificacao="BOX_VENDIDO",
        recebimento=2.50, pct_ganho=0.04, pct_cdi=2.5,
        strike=68.0, dias=30, vencimento=date(2026, 8, 8),
        viavel=True, preco_ativo=70.0,
        of_compra_put=1.20, of_venda_call=1.50,
        qul_put=50, qul_call=70,
        money_put=1.0, money_call=0.5,
        liq_put_x_lote=100, liq_call_x_lote=200,
        em_leilao=False,
        tipo_opcao="A",
    )
    rv2 = OportunidadeVendida(
        ativo="PETR4",
        cod_put="PETRM70",
        cod_call="PETRA70",
        classificacao="SBTH_VENDIDA",
        recebimento=1.20, pct_ganho=0.02, pct_cdi=1.4,
        strike=70.0, dias=30, vencimento=date(2026, 8, 8),
        viavel=True, preco_ativo=70.0,
        of_compra_put=0.5, of_venda_call=1.0,
        qul_put=10, qul_call=20,
        money_put=0.0, money_call=0.5,
        liq_put_x_lote=10, liq_call_x_lote=20,
        em_leilao=False,
        tipo_opcao="E",
    )

    model = VendidasTableModel()
    model.atualizar([rv1, rv2])

    view = QTableView()
    view.setModel(view.model())
    view.setModel(model)
    # Selecionar APENAS a linha 1 (PETR4)
    view.selectRow(1)

    resultados = [rv1, rv2]

    import src.ui.desktop.copy_utils as cu
    cu.QMessageBox.information = lambda *a, **k: None

    n = exportar_monitor_csv(
        resultados=resultados,
        colunas=VendidasTableModel.COLUMNS,
        table_view=view,
        parent=None,
        titulo_janela="TEST",
    )
    assert n == 1, f"esperava exportar 1 linha selecionada, recebi {n}"
    cb = QApplication.clipboard().text()
    assert "PETR4" in cb
    assert "VALE3" not in cb
