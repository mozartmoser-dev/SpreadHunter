from dataclasses import dataclass


@dataclass
class ParametroOperacional:
    chave: str
    valor: float
    estrategia: str
    descricao: str
    id: int | None = None

    @classmethod
    def defaults(cls) -> list["ParametroOperacional"]:
        return [
            cls(chave=k, valor=v["valor"], estrategia=v["estrategia"], descricao=v["descricao"])
            for k, v in cls.PARAMETROS_DEFAULT.items()
        ]

    PARAMETROS_DEFAULT = {
        "taxa_cdi": {"valor": 0.1450, "estrategia": "GERAL", "descricao": "Taxa CDI/Selic"},
        "premio_risco_box": {"valor": 1.5, "estrategia": "BOX", "descricao": "Premio risco BOX"},
        "premio_risco_sbth": {"valor": 1.2, "estrategia": "SBTH", "descricao": "Premio risco SBTH"},
        "premio_box_sintetico_call_itm": {"valor": 3.0, "estrategia": "BOX_SINTETICO", "descricao": "Premio BOX sintetico call ITM"},
        "sbth_qtd_ativo": {"valor": 1000, "estrategia": "SBTH", "descricao": "Qtd compra ativo"},
        "sbth_prof_ativo": {"valor": 1, "estrategia": "SBTH", "descricao": "Profundidade book ativo"},
        "sbth_qtd_put": {"valor": 1000, "estrategia": "SBTH", "descricao": "Qtd compra PUT"},
        "sbth_prof_put": {"valor": -1, "estrategia": "SBTH", "descricao": "Profundidade book PUT"},
        "box_qtd_ativo": {"valor": 1000, "estrategia": "BOX", "descricao": "Qtd compra ativo"},
        "box_prof_ativo": {"valor": 1, "estrategia": "BOX", "descricao": "Profundidade book ativo"},
        "box_qtd_put": {"valor": 1000, "estrategia": "BOX", "descricao": "Qtd compra PUT"},
        "box_prof_put": {"valor": -1, "estrategia": "BOX", "descricao": "Profundidade book PUT"},
        "box_qtd_call": {"valor": 1000, "estrategia": "BOX", "descricao": "Qtd venda Call"},
        "box_prof_call": {"valor": 1, "estrategia": "BOX", "descricao": "Profundidade book Call"},
        "basket_qtd_call_itm": {"valor": 100, "estrategia": "BOX_SINTETICO", "descricao": "Qtd compra Call ITM"},
        "basket_prof_call_itm": {"valor": 1, "estrategia": "BOX_SINTETICO", "descricao": "Profundidade Call ITM"},
        "basket_qtd_put": {"valor": 100, "estrategia": "BOX_SINTETICO", "descricao": "Qtd compra PUT"},
        "basket_prof_put": {"valor": -1, "estrategia": "BOX_SINTETICO", "descricao": "Profundidade PUT"},
        "basket_qtd_call": {"valor": 100, "estrategia": "BOX_SINTETICO", "descricao": "Qtd venda Call ATM"},
        "basket_prof_call": {"valor": -1, "estrategia": "BOX_SINTETICO", "descricao": "Profundidade Call ATM"},
        "perf_carga_inteligente": {"valor": 1.0, "estrategia": "PERFORMANCE", "descricao": "Carga Inteligente (Filtro Strike)"},
        "perf_range_min": {"valor": -50.0, "estrategia": "PERFORMANCE", "descricao": "Filtro Strike Min (%)"},
        "perf_range_max": {"valor": 50.0, "estrategia": "PERFORMANCE", "descricao": "Filtro Strike Max (%)"},
        "perf_limite_meses": {"valor": 0.0, "estrategia": "PERFORMANCE", "descricao": "Limite de Vencimento (Meses, 0=Sem Limite)"},
        "perf_dias_minimos": {"valor": 0.0, "estrategia": "PERFORMANCE", "descricao": "Dias Minimos para Vencimento"},
        "tema_visual": {"valor": 0.0, "estrategia": "GERAL", "descricao": "Tema Visual (0=Marinho, 1=Grafite, 2=Charcoal)"},
        "notif_telegram_enable": {"valor": 0.0, "estrategia": "TELEGRAM", "descricao": "Habilitar Telegram"},
        "telegram_bot_token": {"valor": "0", "estrategia": "TELEGRAM", "descricao": "Token Telegram"},
        "telegram_chat_id": {"valor": "0", "estrategia": "TELEGRAM", "descricao": "Chat ID Telegram"},
        "premio_risco_colar": {"valor": 1.0, "estrategia": "COLAR", "descricao": "Premio risco Colar (x CDI)"},
        "colar_dist_max_pct": {"valor": 0.3, "estrategia": "COLAR", "descricao": "Distancia maxima do strike (%)"},
    }
