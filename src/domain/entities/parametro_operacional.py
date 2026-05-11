from dataclasses import dataclass


@dataclass
class ParametroOperacional:
    chave: str
    valor: float
    estrategia: str
    descricao: str
    id: int | None = None

    PARAMETROS_DEFAULT = {
        "taxa_cdi": {"valor": 0.15, "estrategia": "GERAL", "descricao": "Taxa CDI/Selic"},
        "premio_risco_box": {"valor": 1.5, "estrategia": "BOX", "descricao": "Prêmio risco BOX"},
        "premio_risco_sbth": {"valor": 1.2, "estrategia": "SBTH", "descricao": "Prêmio risco SBTH"},
        "premio_box_sintetico_call_itm": {"valor": 3.0, "estrategia": "BOX_SINTETICO", "descricao": "Prêmio BOX sintético call ITM"},
    }

    @classmethod
    def defaults(cls) -> list["ParametroOperacional"]:
        return [
            cls(chave=k, valor=v["valor"], estrategia=v["estrategia"], descricao=v["descricao"])
            for k, v in cls.PARAMETROS_DEFAULT.items()
        ]
