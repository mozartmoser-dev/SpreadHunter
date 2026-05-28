import logging

import requests

logger = logging.getLogger(__name__)

BRASIL_API_URL = "https://brasilapi.com.br/api/feriados/v1/{ano}"

HEADERS = {
    "User-Agent": "SpreadHunter/1.0",
    "Accept": "application/json",
}


class FeriadosB3Provider:
    def buscar_feriados(self, ano: int) -> list[dict]:
        feriados = []
        try:
            resp = requests.get(
                BRASIL_API_URL.format(ano=ano),
                headers=HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    feriados.append({
                        "data": item["date"],
                        "nome": item["name"],
                        "tipo": item.get("type", "nacional"),
                        "fonte": "brasilapi",
                    })
            else:
                logger.warning(f"Brasil API retornou status {resp.status_code} para ano {ano}")
        except Exception as e:
            logger.warning(f"Erro ao buscar feriados ano {ano}: {e}")

        self._adicionar_feriado_estadual_sp(feriados, ano)
        return feriados

    @staticmethod
    def _adicionar_feriado_estadual_sp(feriados: list[dict], ano: int):
        """B3 fecha em 9 de Julho (Revolução Constitucionalista - feriado SP)."""
        data_sp = f"{ano}-07-09"
        if not any(f["data"] == data_sp for f in feriados):
            feriados.append({
                "data": data_sp,
                "nome": "Revolução Constitucionalista",
                "tipo": "estadual_sp",
                "fonte": "manual",
            })
            feriados.sort(key=lambda f: f["data"])

    def buscar_varios_anos(self, anos: list[int], callback=None) -> list[dict]:
        todos = []
        for i, ano in enumerate(sorted(anos)):
            if callback:
                callback(i + 1, len(anos), str(ano))
            todos.extend(self.buscar_feriados(ano))
        return todos
