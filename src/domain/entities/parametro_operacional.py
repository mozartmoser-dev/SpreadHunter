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
        "premio_risco_box": {"valor": 1.3, "estrategia": "BOX", "descricao": "Premio risco BOX"},
        "premio_risco_sbth": {"valor": 1.1, "estrategia": "SBTH", "descricao": "Premio risco SBTH"},
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
        "perf_dias_minimos": {"valor": 10.0, "estrategia": "PERFORMANCE", "descricao": "Dias Minimos para Vencimento"},
        "tema_visual": {"valor": 0.0, "estrategia": "GERAL", "descricao": "Tema Visual (0=Marinho, 1=Grafite, 2=Charcoal)"},
        "notif_telegram_enable": {"valor": 0.0, "estrategia": "TELEGRAM", "descricao": "Habilitar Telegram"},
        "telegram_bot_token": {"valor": "0", "estrategia": "TELEGRAM", "descricao": "Token Telegram"},
        "telegram_chat_id": {"valor": "0", "estrategia": "TELEGRAM", "descricao": "Chat ID Telegram"},
        "premio_risco_colar": {"valor": 0.7, "estrategia": "COLAR", "descricao": "Premio risco Colar (x CDI)"},
        "colar_dist_max_pct": {"valor": 0.15, "estrategia": "COLAR", "descricao": "Distancia maxima do strike (%)"},
        "calendario_strike_diff_pct": {"valor": 0.10, "estrategia": "COLLAR_CALENDARIO", "descricao": "Max diff % entre strikes call e put"},
        "premio_risco_colar_calendario": {"valor": 0.9, "estrategia": "COLLAR_CALENDARIO", "descricao": "Premio risco Collar Calendario (x CDI)"},
        "calendario_call_otm_max": {"valor": 0.08, "estrategia": "COLLAR_CALENDARIO", "descricao": "Max OTM da call (% do spot)"},
        "taxa_emolumento_pct": {"valor": 0.00025, "estrategia": "GERAL", "descricao": "Taxa de emolumento B3 (% do financeiro)"},
        "taxa_liquidacao_pct": {"valor": 0.000275, "estrategia": "GERAL", "descricao": "Taxa de liquidacao B3 (% do financeiro)"},
        "colar_qul_min_put": {"valor": 100.0, "estrategia": "COLAR", "descricao": "Qtd minima negociada (QUL) para PUT"},
        "colar_qul_min_call": {"valor": 100.0, "estrategia": "COLAR", "descricao": "Qtd minima negociada (QUL) para CALL"},
        "box_premio_risco": {"valor": 1.08, "estrategia": "BOX_4P", "descricao": "Premio risco Box 4P (x CDI)"},
        "box_qtd_min": {"valor": 100, "estrategia": "BOX_4P", "descricao": "Qtd min contratos por perna"},
        "box_soh_europeia": {"valor": 1.0, "estrategia": "BOX_4P", "descricao": "So aceitar opcoes europeias (1=sim, 0=aceita americanas)"},
        "colar_risco_baixo_vov_min": {"valor": 1000.0, "estrategia": "COLAR", "descricao": "VOV/VOC mínimo para risco baixo de despernamento"},
        "elegibilidade_strike_max_pct": {"valor": 0.70, "estrategia": "BOX_SINTETICO", "descricao": "Strike máximo % do spot para elegibilidade de pescaria"},
        "dte_call_min": {"valor": 29.0, "estrategia": "COLLAR_CALENDARIO", "descricao": "DTE mínimo para call no collar calendário"},
        "dte_call_max": {"valor": 60.0, "estrategia": "COLLAR_CALENDARIO", "descricao": "DTE máximo para call no collar calendário"},
        "dte_extra_min": {"valor": 30.0, "estrategia": "COLLAR_CALENDARIO", "descricao": "Spread DTE mínimo entre put e call"},
        "dte_extra_max": {"valor": 90.0, "estrategia": "COLLAR_CALENDARIO", "descricao": "Spread DTE máximo entre put e call"},
        "dte_total_max": {"valor": 120.0, "estrategia": "COLLAR_CALENDARIO", "descricao": "DTE máximo total para qualquer perna"},
        "import_max_months": {"valor": 9.0, "estrategia": "IMPORTACAO", "descricao": "Meses a frente da data para importar series"},
        "white_list_box4p": {"valor": "", "estrategia": "BOX_4P", "descricao": "Whitelist de ativos para Box 4P"},
        "white_list_colar_calendario": {"valor": "", "estrategia": "COLLAR_CALENDARIO", "descricao": "Whitelist de ativos para Collar Calendario"},
        "white_list_colar": {"valor": "", "estrategia": "COLAR", "descricao": "Whitelist de ativos para Colar Protetivo"},
    }
