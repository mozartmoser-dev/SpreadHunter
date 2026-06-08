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
        return self.taxa_emolumento + self.taxa_liquidacao + self.taxa_registro + self.iss

    def calcular_custos(self, strike_medio: float, n_pernas: int) -> float:
        return self.taxa_total() * strike_medio * n_pernas

    def calcular_custos_vetor(self, strike_medio: 'np.ndarray', n_pernas: int) -> 'np.ndarray':
        import numpy as np
        return self.taxa_total() * strike_medio * n_pernas

    def ajustar_ir(self, lucro_liquido: float) -> float:
        if lucro_liquido <= 0:
            return 0.0
        return lucro_liquido * self.taxa_ir

    def ajustar_ir_vetor(self, lucro_liquido: 'np.ndarray') -> 'np.ndarray':
        import numpy as np
        return np.where(lucro_liquido > 0, lucro_liquido * self.taxa_ir, 0.0)

    def resumo(self, strike_medio: float, n_pernas: int) -> str:
        custo = self.calcular_custos(strike_medio, n_pernas)
        return (
            f"Custos B3 ({n_pernas} pernas): "
            f"emol=({self.taxa_emolumento:.4f})+liq=({self.taxa_liquidacao:.4f})"
            f"+reg=({self.taxa_registro:.4f})+iss=({self.iss:.4f})"
            f"={self.taxa_total():.4f} x strike=R${strike_medio:.2f} x {n_pernas} = R${custo:.4f}"
        )
