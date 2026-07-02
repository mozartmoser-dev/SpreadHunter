from src.application.dtos.dtos import OportunidadeMonitor


class MockMarketDataProvider:
    def __init__(self, preco_base: float = 18.0):
        self.preco_base = preco_base
        self._overrides: dict[str, dict] = {}

    def set_override(self, key: str, dados: dict):
        self._overrides[key] = dados

    def gerar_dados_para_instrumentos(self, instrumentos: list) -> dict[str, dict]:
        dados_mercado = {}
        for inst in instrumentos:
            key = f"{inst.ativo}|{inst.cod_put}"
            if key in self._overrides:
                dados_mercado[key] = self._overrides[key]
                continue
            strike = getattr(inst, 'strike', None) or self.preco_base
            preco = self.preco_base
            if strike > preco:
                premio_put = 0.5 + (strike - preco) * 0.3
                premio_call = 0.2
            else:
                premio_put = 0.2
                premio_call = 0.5 + (preco - strike) * 0.3
            dados_mercado[key] = {
                "preco_ativo": preco,
                "strike_rtd": strike,
                "of_compra_ativo": preco - 0.05,
                "of_venda_ativo": preco + 0.05,
                "of_compra_put": premio_put - 0.02,
                "of_venda_put": premio_put + 0.02,
                "of_compra_call": premio_call - 0.02,
                "of_venda_call": premio_call + 0.02,
                "premio_put": premio_put,
                "premio_call": premio_call,
                "vov_put_boca": 2000.0,
                "voc_call_boca": 2000.0,
                "qul_put": 100.0,
                "qul_call": 100.0,
            }
        return dados_mercado
