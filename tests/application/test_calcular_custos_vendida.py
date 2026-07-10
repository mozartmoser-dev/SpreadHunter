"""Testes para o método calcular_custos_vendida() de CalculadoraCustosB3.

Garante que o custo B3 das estruturas vendidas (BOX_VENDIDA/SBTH_VENDIDA)
segue a fórmula coerente com o resto do módulo (emol + liq + reg + iss).
"""
import pytest

from src.domain.services.calculadora_custos_b3 import CalculadoraCustosB3


@pytest.fixture
def custos():
    return CalculadoraCustosB3()


def test_calcular_custos_vendida_zero_quando_preco_invalido(custos):
    assert custos.calcular_custos_vendida(
        preco_ativo=0.0,
        premio_medio_opcoes=1.0,
        n_pernas_opcoes=2,
    ) == 0.0
    assert custos.calcular_custos_vendida(
        preco_ativo=10.0,
        premio_medio_opcoes=1.0,
        n_pernas_opcoes=0,
    ) == 0.0


def test_calcular_custos_vendida_box_vendido_3_pernas(custos):
    """BOX Vendida: vende PUT + compra CALL + vende ação = 2 opções + 1 ação."""
    preco_ativo = 30.0
    premio_medio = 0.5  # média entre PUT e CALL, igual ao usado em box_sbth.py
    n_pernas_opcoes = 2
    n_acoes = 1

    custo = custos.calcular_custos_vendida(
        preco_ativo=preco_ativo,
        premio_medio_opcoes=premio_medio,
        n_pernas_opcoes=n_pernas_opcoes,
        n_acoes=n_acoes,
    )

    # Estruturas vendidas assumem ida-e-volta (rolagem é comum)
    esperado_opcao = custos.custos_opcao(premio_medio, n_pernas=n_pernas_opcoes, ida_e_volta=True)
    esperado_acao = custos.custos_stock(preco_ativo, n_acoes=n_acoes, ida_e_volta=True)
    assert custo == pytest.approx(esperado_opcao + esperado_acao)


def test_calcular_custos_vendida_sbth_vendido_2_pernas(custos):
    """SBTH Vendida: vende PUT + vende ação = 1 opção + 1 ação."""
    preco_ativo = 30.0
    premio_medio = 0.5
    n_pernas_opcoes = 1
    n_acoes = 1

    custo = custos.calcular_custos_vendida(
        preco_ativo=preco_ativo,
        premio_medio_opcoes=premio_medio,
        n_pernas_opcoes=n_pernas_opcoes,
        n_acoes=n_acoes,
    )

    # Estruturas vendidas assumem ida-e-volta
    esperado_opcao = custos.custos_opcao(premio_medio, n_pernas=n_pernas_opcoes, ida_e_volta=True)
    esperado_acao = custos.custos_stock(preco_ativo, n_acoes=n_acoes, ida_e_volta=True)
    assert custo == pytest.approx(esperado_opcao + esperado_acao)


def test_assinatura_aceita_argumentos_kwargs_apenas(custos):
    """Falha claramente se alguém chamar posicional (defesa contra regresso)."""
    with pytest.raises(TypeError):
        custos.calcular_custos_vendida(30.0, 0.5, 2)  # posicional deliberadamente errado
