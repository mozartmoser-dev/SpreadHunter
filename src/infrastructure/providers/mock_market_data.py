from src.domain.services.market_data_source import FieldName, PROFIT_FIELD_STR


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


class MockDataSource:
    """Implementa MarketDataSource para testes sem RTD/OpenFAST."""
    disponivel: bool = True
    suporta_push: bool = False
    suporta_cab_skip: bool = False
    is_mock: bool = True

    def __init__(self, db_path=None):
        self.db_path = db_path
        self._mock_provider = MockMarketDataProvider(preco_base=18.0)
        self._cache: dict[str, float] = {}

    def registrar_topico(self, codigo: str, campo: FieldName) -> int:
        return 0

    def registrar_lista(self, registros: list[tuple[str, FieldName]]) -> int:
        return len(registros)

    def registrar_status(self, codigo: str) -> int:
        return 0

    def ler_campo_cache(self, codigo: str, campo: FieldName) -> float | None:
        return self._cache.get(f"{codigo}|{PROFIT_FIELD_STR.get(campo, '')}")

    def ler_campos(self, codigo: str, *campos: FieldName, allow_stale: bool = False) -> dict[FieldName, float | None]:
        return {c: self.ler_campo_cache(codigo, c) for c in campos}

    def ler_status_cache(self, codigo: str) -> str:
        return "Aberto"

    def forcar_leitura(self, codigo: str, campo: FieldName) -> float | None:
        return self.ler_campo_cache(codigo, campo)

    def refresh(self, timeout_ms: int = 0) -> dict[str, object]:
        return {}

    def desconectar(self):
        pass

    def reconectar(self) -> bool:
        return True

    def invalidar_cache(self, codigo: str, campo: FieldName):
        pass

    def popular_cache(self, dados_mercado: dict[str, dict]):
        """Preenche o cache com dados no formato dados_mercado."""
        for key, entry in dados_mercado.items():
            if "|" not in key:
                continue
            cod_put = key.split("|", 1)[1]
            # Mapeia field names do Profit
            field_map = {
                "strike_rtd": FieldName.STRIKE,
                "preco_ativo": FieldName.ASK,
                "of_venda_ativo": FieldName.ASK,
                "of_compra_ativo": FieldName.BID,
                "of_venda_put": FieldName.ASK,
                "of_compra_put": FieldName.BID,
                "of_venda_call": FieldName.ASK,
                "of_compra_call": FieldName.BID,
                "premio_put": FieldName.ASK,
                "premio_call": FieldName.BID,
                "vov_put_boca": FieldName.VOL_ASK,
                "voc_call_boca": FieldName.VOL_BID,
                "qul_put": FieldName.QTD_LAST,
                "qul_call": FieldName.QTD_LAST,
            }
            for field_key, field_name in field_map.items():
                val = entry.get(field_key)
                if val is not None:
                    # Armazena para o cod_put (opcao) e ativo
                    fstr = PROFIT_FIELD_STR.get(field_name, "")
                    self._cache[f"{cod_put}|{fstr}"] = val
            # preco_ativo também para o ativo
            ativo = key.split("|", 1)[0]
            pa = entry.get("preco_ativo", 0.0)
            if pa:
                self._cache[f"{ativo}|{PROFIT_FIELD_STR.get(FieldName.ASK)}"] = pa
                self._cache[f"{ativo}|{PROFIT_FIELD_STR.get(FieldName.BID)}"] = pa * 0.99
