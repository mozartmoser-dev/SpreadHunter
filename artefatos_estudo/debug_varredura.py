import logging
logging.basicConfig(level=logging.DEBUG)

from src.infrastructure.persistence.database import get_db_path
from src.infrastructure.providers.rtd_profit import RTDProfit
from src.infrastructure.providers.mercado_data_provider import MercadoDataProvider
from src.application.use_cases.monitor_oportunidades import MonitorOportunidadesUseCase
from src.ui.desktop.monitor_table_model import MonitorTableModel

db_path = str(get_db_path())
rtd = RTDProfit()
provider = MercadoDataProvider(db_path, rtd)

dados = provider.capturar_dados_mercado()
print(f"Dados capturados: {len(dados)}")

uc = MonitorOportunidadesUseCase(db_path)
resultados = uc.varrer(dados)
print(f"Resultados da varredura: {len(resultados)}")
viaveis = [r for r in resultados if r.viavel]
print(f"Viaveis: {len(viaveis)}")

# Testando a logica da tabela
model = MonitorTableModel()
model.atualizar(resultados)
print(f"Tabela linhas: {model.rowCount()}")

model.atualizar(resultados)
print(f"Tabela linhas após att 2: {model.rowCount()}")
