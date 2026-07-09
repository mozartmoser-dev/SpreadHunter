class CalculadoraCustosB3:
    TAXA_EMOLUMENTO_OPCAO = 0.000250
    TAXA_LIQUIDACAO_OPCAO = 0.000275
    TAXA_REGISTRO_OPCAO = 0.000100
    ISS_PADRAO = 0.0
    TAXA_IR_PADRAO = 0.15  # 99,9% das operacoes sao swing trade (15%). Se for day trade, alterar para 0.20.

    def __init__(self, taxa_emolumento: float | None = None, taxa_liquidacao: float | None = None,
                 taxa_ir: float | None = None, taxa_registro: float | None = None,
                 iss: float | None = None):
        self.taxa_emolumento = taxa_emolumento if taxa_emolumento is not None else self.TAXA_EMOLUMENTO_OPCAO
        self.taxa_liquidacao = taxa_liquidacao if taxa_liquidacao is not None else self.TAXA_LIQUIDACAO_OPCAO
        self.taxa_registro = taxa_registro if taxa_registro is not None else self.TAXA_REGISTRO_OPCAO
        self.iss = iss if iss is not None else self.ISS_PADRAO
        self.taxa_ir = taxa_ir if taxa_ir is not None else self.TAXA_IR_PADRAO

    def taxa_total(self) -> float:
        """Taxa total para opções (emol + liq + reg + iss)."""
        return self.taxa_emolumento + self.taxa_liquidacao + self.taxa_registro + self.iss

    def taxa_total_stock(self) -> float:
        """Taxa total para ações (emol + liq + iss — sem registro)."""
        return self.taxa_emolumento + self.taxa_liquidacao + self.iss

    def custos_opcao(self, premio_medio: float, n_pernas: int = 1, ida_e_volta: bool = True) -> float:
        """Custo B3 para opções: taxa_total × prêmio médio × pernas × (2 se ida_e_volta)."""
        fator = 2 if ida_e_volta else 1
        return self.taxa_total() * premio_medio * n_pernas * fator

    def custos_opcao_vetor(self, premio_medio: 'np.ndarray', n_pernas: int = 1, ida_e_volta: bool = True) -> 'np.ndarray':
        import numpy as np
        fator = 2 if ida_e_volta else 1
        return self.taxa_total() * premio_medio * n_pernas * fator

    def custos_stock(self, preco: float, n_acoes: int = 1, ida_e_volta: bool = True) -> float:
        """Custo B3 para ações: taxa_total_stock × preço × ações × (2 se ida_e_volta)."""
        fator = 2 if ida_e_volta else 1
        return self.taxa_total_stock() * preco * n_acoes * fator

    def custos_stock_vetor(self, preco: 'np.ndarray', n_acoes: int = 1, ida_e_volta: bool = True) -> 'np.ndarray':
        import numpy as np
        fator = 2 if ida_e_volta else 1
        return self.taxa_total_stock() * preco * n_acoes * fator

    def ajustar_ir(self, lucro_liquido: float) -> float:
        if lucro_liquido <= 0:
            return 0.0
        return lucro_liquido * self.taxa_ir

    def ajustar_ir_vetor(self, lucro_liquido: 'np.ndarray') -> 'np.ndarray':
        import numpy as np
        return np.where(lucro_liquido > 0, lucro_liquido * self.taxa_ir, 0.0)

    def resumo(self, premio_medio: float, n_pernas: int) -> str:
        custo = self.custos_opcao(premio_medio, n_pernas)
        return (
            f"Custos B3 ({n_pernas} pernas): "
            f"emol=({self.taxa_emolumento:.4f})+liq=({self.taxa_liquidacao:.4f})"
            f"+reg=({self.taxa_registro:.4f})+iss=({self.iss:.4f})"
            f"={self.taxa_total():.4f} x premio=R${premio_medio:.2f} x {n_pernas} = R${custo:.4f}"
        )

    def calcular_custos_vendida(
        self,
        *,
        preco_ativo: float,
        premio_medio_opcoes: float,
        n_pernas_opcoes: int,
        n_acoes: int = 1,
    ) -> float:
        """Custo B3 de uma estrutura vendida.

        Cobrado ida-e-volta: assume que a posição pode ser fechada antes do
        vencimento (rolagem é comum). Mesma tarifação B3 das estruturas
        compradas — a B3 não distingue lado, cobra dos dois lados.

        Estruturas vendidas atualmente:
        - BOX_VENDIDA: vende ação + vende PUT + compra CALL → 2 opções + 1 ação
        - SBTH_VENDIDA: vende ação + vende PUT → 1 opção + 1 ação
        """
        if preco_ativo <= 0 or n_pernas_opcoes <= 0:
            return 0.0
        return (
            self.custos_opcao(premio_medio_opcoes, n_pernas=n_pernas_opcoes, ida_e_volta=True)
            + self.custos_stock(preco_ativo, n_acoes=n_acoes, ida_e_volta=True)
        )
