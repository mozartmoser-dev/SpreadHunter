import json
from collections import OrderedDict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QPushButton, QLabel, QScrollArea, QFrame,
    QCheckBox, QComboBox, QLineEdit, QMessageBox, QHBoxLayout,
    QSlider, QFileDialog,
    QListWidget, QListWidgetItem, QStackedWidget,
)
from PySide6.QtCore import Qt, QSettings

from src.infrastructure.persistence.repositories.repositories import ParametroRepository
from src.domain.entities.parametro_operacional import ParametroOperacional
from src.ui.desktop.theme import Palette

class NoWheelSpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        # Ignora o evento de roda para evitar mudanças acidentais ao rolar a tela
        event.ignore()


ESTRATEGIA_LABELS = {
    "GERAL": "Geral",
    "SBTH": "SBTH (Synthetic Buy & Hold)",
    "BOX": "BOX Comprado 3 Pontas",
    "BOX_SINTETICO": "BOX Sintetico / Pescaria Basket",
    "PERFORMANCE": "Ajuste de Performance",
    "TELEGRAM": "Notificações Telegram",
    "SOM": "Som de Notificação (🔔)",
    "COLAR": "Colar Protetivo",
    "COLLAR_CALENDARIO": "Collar Calendário",
    "BOX_4P": "Box Spread 4 Pontas",
    "VENDA_COBERTA": "Taxa",
    "COLLAR_CALENDARIO_CAUDA": "Collar Cal. Cauda Assíncrona",
    "SBTH_VENDIDA": "SBTH Vendida",
}

ESTRATEGIA_COLORS = {
    "GERAL": Palette.TEXT_PRIMARY,
    "SBTH": Palette.CYAN,
    "BOX": Palette.ACCENT_BLUE_BRIGHT,
    "BOX_SINTETICO": Palette.PURPLE,
    "PERFORMANCE": Palette.YELLOW,
    "TELEGRAM": Palette.GREEN,
    "SOM": "#e67e22",
    "COLAR": "#1abc9c",
    "COLLAR_CALENDARIO": "#f39c12",
    "BOX_4P": "#e74c3c",
    "VENDA_COBERTA": "#2ecc71",
    "COLLAR_CALENDARIO_CAUDA": "#e67e22",
    "IMPORTACAO": "#8e44ad",
}

PARAMETROS_POR_ESTRATEGIA = {
    "GERAL": [
        ("taxa_cdi", "Taxa CDI/Selic"),
        ("tema_visual", "Aspecto do Sistema"),
        ("fonte_market_data", "Fonte de Market Data"),
        ("fonte_tamanho", "Tamanho da Fonte (8-16)"),
        ("openfast_send_delay_ms", "Delay SQT (ms)"),
        ("rtd_refresh_timeout_ms", "Timeout RTD RefreshData (ms, 0=sem timeout)"),
        ("taxa_aluguel_habilitado", "Habilitar Coleta Taxa Aluguel"),
        ("investsite_timeout_ms", "Timeout InvestSite (ms)"),
        ("investsite_delay_ms", "Delay entre Requisições InvestSite (ms)"),
    ],
    "BOX": [
        ("premio_risco_box", "Premio risco BOX (x CDI)"),
        ("box_qtd_ativo", "Qtd compra ativo"),
        ("box_prof_ativo", "Profund. book ativo"),
        ("box_qtd_put", "Qtd compra PUT"),
        ("box_prof_put", "Profund. book PUT"),
        ("box_qtd_call", "Qtd venda Call"),
        ("box_prof_call", "Profund. book Call"),
    ],
    "SBTH": [
        ("premio_risco_sbth", "Premio risco SBTH (x CDI)"),
        ("sbth_qtd_ativo", "Qtd compra ativo"),
        ("sbth_prof_ativo", "Profund. book ativo"),
        ("sbth_qtd_put", "Qtd compra PUT"),
        ("sbth_prof_put", "Profund. book PUT"),
    ],
    "BOX_SINTETICO": [
        ("premio_box_sintetico_call_itm", "Premio risco Box sintetico (x CDI)"),
        ("basket_qtd_call_itm", "Qtd compra Call ITM"),
        ("basket_prof_call_itm", "Profund. Call ITM"),
        ("basket_qtd_put", "Qtd compra PUT"),
        ("basket_prof_put", "Profund. PUT"),
        ("basket_qtd_call", "Qtd venda Call ATM"),
        ("basket_prof_call", "Profund. Call ATM"),
    ],
    "PERFORMANCE": [
        ("perf_carga_inteligente", "Habilitar Carga Inteligente (0=Off, 1=On)"),
        ("perf_range_min", "Filtro Strike Min (%)"),
        ("perf_range_max", "Filtro Strike Max (%)"),
        ("perf_limite_meses", "Limite Vencimento (Meses, 0=S.Lim)"),
        ("perf_dias_minimos", "Dias Minimos Vencimento"),
        ("onda2_dte_min", "DTE minimo Onda 2"),
        ("onda2_dte_max", "DTE maximo Onda 2"),
    ],
    "TELEGRAM": [
        ("notif_telegram_enable", "Habilitar Telegram"),
        ("telegram_bot_token", "Token do Bot Telegram"),
        ("telegram_chat_id", "ID do Chat Telegram"),
        ("telegram_cleanup_timeout", "Timeout limpeza historico (s)"),
    ],
    "SOM": [
        ("som_arquivo", "Arquivo de Som (.wav)"),
        ("som_volume", "Volume (0-100%)"),
        ("som_arquivo_vendidas", "Som VENDIDAS (.wav)"),
        ("som_volume_vendidas", "Volume VENDIDAS (0-100%)"),
        ("som_arquivo_coberta", "Som TAXA (.wav)"),
        ("som_volume_coberta", "Volume TAXA (0-100%)"),
    ],
    "VENDA_COBERTA": [
        ("venda_coberta_premio_risco", "Premio Risco (x CDI)"),
        ("venda_coberta_lote_liquidez", "Lote Liquidez CALL"),
        ("venda_coberta_dias_minimos", "Dias Minimos Vencimento"),
        ("venda_coberta_dist_max_pct", "Distancia Max Strike Abaixo Spot"),
    ],
    "SBTH_VENDIDA": [
        ("sbth_vendida_dist_ativo", "Distancia Minima Strike/Spot (x)"),
    ],
    "COLAR": [
        ("premio_risco_colar", "Premio risco Colar (x CDI)"),
        ("colar_dist_max_pct", "Distancia maxima do strike (%)"),
        ("colar_qtd_ativo", "Qtd compra ativo"),
        ("colar_prof_ativo", "Profund. book ativo"),
        ("colar_qtd_call", "Qtd venda CALL"),
        ("colar_prof_call", "Profund. book Call"),
        ("colar_qtd_put", "Qtd compra PUT"),
        ("colar_prof_put", "Profund. book Put"),
        ("ranking_peso_colar_pop", "Peso Pop no Score Ranking"),
        ("ranking_peso_colar_cdi", "Peso % CDI no Score Ranking"),
        ("ranking_peso_colar_risco", "Peso risco leilão (inverso) no Score Ranking"),
        ("white_list_colar", "Whitelist de ativos (separados por virgula)"),
    ],
    "COLLAR_CALENDARIO": [
        ("calendario_strike_diff_max", "Max strikes de diferenca call-put"),
        ("limiar_classificacao_calendario", "Limiar classificacao (% spread)"),
        ("be_search_range_mult", "Margem busca breakeven (+/-)"),
        ("calendario_call_otm_max", "Call OTM max (0.08 = 8% acima do spot)"),
        ("calendario_qtd_ativo", "Qtd compra ativo"),
        ("calendario_prof_ativo", "Profund. book ativo"),
        ("calendario_qtd_call", "Qtd venda CALL"),
        ("calendario_prof_call", "Profund. book Call"),
        ("calendario_qtd_put", "Qtd compra PUT"),
        ("calendario_prof_put", "Profund. book Put"),
        ("dte_call_min", "DTE call minima (dias)"),
        ("dte_call_max", "DTE call maxima (dias)"),
        ("dte_extra_min", "Diferenca DTE put−call minima (dias)"),
        ("dte_extra_max", "Diferenca DTE put−call maxima (dias)"),
        ("dte_total_max", "DTE total maximo (dias)"),
        ("premio_risco_colar_calendario", "Premio risco (x CDI)"),
        ("ranking_peso_theta", "Peso θ líq. no Score Ranking"),
        ("ranking_peso_cdi", "Peso % CDI no Score Ranking"),
        ("ranking_peso_sigma", "Peso sigma folga no Score Ranking"),
        ("ranking_peso_credito", "Peso crédito no Score Ranking"),
        ("ranking_peso_liquidez", "Peso liquidez no Score Ranking"),
        ("white_list_colar_calendario", "Whitelist de ativos (separados por virgula)"),
        ("telegram_cleanup_timeout", "Timeout historico Telegram (s)"),
    ],
    "COLLAR_CALENDARIO_CAUDA": [
        ("calda_habilitado", "Habilitar Cauda Assincrona (1=sim, 0=nao)"),
        ("calda_premio_risco", "Premio risco (x CDI)"),
        ("calda_desvios_cauda", "Desvios padrao para breakeven sup."),
        ("calda_ratio_max", "Ratio maximo CALL:ativo"),
    ],
    "BOX_4P": [
        ("box_premio_risco", "Premio risco (x CDI)"),
        ("box_qtd_min", "Qtd min contratos por perna"),
        ("box_soh_europeia", "So aceitar opcoes europeias"),
        ("white_list_box4p", "Whitelist de ativos (separados por virgula)"),
        ("mpp_habilitado", "Habilitar MPP (Priorizacao Pescaria)"),
        ("mpp_instantaneo_interval", "Ciclos entre calculos MPP (default 4)"),
    ],
    "IMPORTACAO": [
        ("import_max_months", "Meses a frente para importar series"),
        ("black_list_import", "Blacklist de ativos (separados por virgula)"),
    ],
}


PARAMETROS_INFO = {
    "taxa_cdi": {
        "descricao": "Taxa de juros anual usada como referencia para calcular se uma operacao vale a pena. Quanto maior a taxa CDI, maior o retorno esperado dos investimentos.",
        "usado_em": "Todas as estrategias (BOX, SBTH, Colar, Collar Calendario). E usada para converter o lucro em % do CDI, permitindo comparar operacoes de diferentes prazos.",
        "precedencia": "Banco de Dados -> 14.50% (padrao no codigo)",
    },
    "tema_visual": {
        "descricao": "Escolhe a aparencia visual do sistema. Voce pode escolher entre Azul Marinho (claro), Grafite (escuro) ou Charcoal (mais escuro ainda).",
        "usado_em": "Interface grafica como um todo.",
        "precedencia": "Banco de Dados -> Azul Marinho (padrao)",
    },
    "fonte_market_data": {
        "descricao": "Define a fonte de dados de mercado em tempo real. 'Profit RTD' usa o servidor RTD do Profit Pro via COM/DCOM. 'Open Fast Socket' usa conexao TCP direta (localhost:557) sem COM.",
        "usado_em": "MercadoDataProvider — todas as estrategias que consomem precos em tempo real.",
        "precedencia": "Banco de Dados -> 'openfast' (Open Fast Socket, padrao)",
    },
    "openfast_send_delay_ms": {
        "descricao": "Delay em milissegundos entre comandos SQT enviados ao servidor Open Fast. 2ms evita sobrecarga no FastTrade. 0 = delay minimo (1ms, max performance).",
        "usado_em": "OpenFastSocketAdapter — controle de taxa de envio de assinaturas.",
        "precedencia": "Banco de Dados -> 2 (padrao)",
    },
    "taxa_aluguel_habilitado": {
        "descricao": "Habilita a coleta diária automática/manual das taxas de aluguel (BTC) de ações diretamente do site InvestSite.",
        "usado_em": "ColetarTaxasAluguelUseCase e botão da barra de ferramentas principal.",
        "precedencia": "Banco de Dados -> Ativado (padrão)",
    },
    "investsite_timeout_ms": {
        "descricao": "Timeout em milissegundos para cada requisição HTTP ao InvestSite. Se a página demorar mais que este valor, o ativo é considerado falha.",
        "usado_em": "InvestSiteClient.fetch_taxa_aluguel — timeout do requests.get().",
        "precedencia": "Banco de Dados -> 10000 (padrão, 10 segundos)",
    },
    "fonte_tamanho": {
        "descricao": "Tamanho da fonte do sistema (8-16). Aplica-se a todas as tabelas de monitoramento. "
                     "O valor padrao e 9. Requer reinicio da varredura para aplicar nas novas conexoes.",
        "usado_em": "main_window.py — font das tabelas compradas e vendidas.",
        "precedencia": "Banco de Dados -> 9 (padrão)",
    },
    "investsite_delay_ms": {
        "descricao": "Delay em milissegundos entre requisições consecutivas ao InvestSite durante a coleta. Evita sobrecarga no servidor e bloqueio de IP. A coleta de ~194 ativos com 500ms leva ~97 segundos.",
        "usado_em": "ColetarTaxasAluguelUseCase.executar — time.sleep() entre ativos.",
        "precedencia": "Banco de Dados -> 500 (padrão, 0.5 segundos)",
    },
    "premio_risco_box": {
        "descricao": "Retorno minimo exigido para aceptar uma operacao de BOX Comprado 3 Pontas, medido em vezes o CDI. Exemplo: 1.3 significa que a operacao precisa render pelo menos 1.3x o CDI para ser viavel.",
        "usado_em": "Monitor de Oportunidades (filtro de viabilidade para BOX 3P).",
        "precedencia": "Banco de Dados -> 1.3 (padrao no codigo)",
    },
    "box_qtd_ativo": {
        "descricao": "Quantidade de acoes que voce pretende comprar em cada operacao de BOX 3P. Define o tamanho minimo da operacao no book de ofertas.",
        "usado_em": "Monitor de Oportunidades (profundidade para BOX 3P).",
        "precedencia": "Banco de Dados -> 1000 (padrao)",
    },
    "box_prof_ativo": {
        "descricao": "Posicao no book de ofertas para compra do ativo. 1 = melhor oferta de venda, 2 = segunda melhor, -1 = melhor oferta de compra.",
        "usado_em": "Monitor de Oportunidades (coleta de precos para BOX 3P).",
        "precedencia": "Banco de Dados -> 1 (padrao)",
    },
    "box_qtd_put": {
        "descricao": "Quantidade de opcoes PUT que voce pretende vender em cada operacao de BOX 3P.",
        "usado_em": "Monitor de Oportunidades (profundidade para BOX 3P).",
        "precedencia": "Banco de Dados -> 1000 (padrao)",
    },
    "box_prof_put": {
        "descricao": "Posicao no book para venda da PUT. -1 = melhor oferta de compra (mais agressivo).",
        "usado_em": "Monitor de Oportunidades (coleta de precos para BOX 3P).",
        "precedencia": "Banco de Dados -> -1 (padrao)",
    },
    "box_qtd_call": {
        "descricao": "Quantidade de opcoes CALL que voce pretende comprar em cada operacao de BOX 3P.",
        "usado_em": "Monitor de Oportunidades (profundidade para BOX 3P).",
        "precedencia": "Banco de Dados -> 1000 (padrao)",
    },
    "box_prof_call": {
        "descricao": "Posicao no book para compra da CALL. 1 = melhor oferta de venda.",
        "usado_em": "Monitor de Oportunidades (coleta de precos para BOX 3P).",
        "precedencia": "Banco de Dados -> 1 (padrao)",
    },
    "premio_risco_sbth": {
        "descricao": "Retorno minimo exigido para aceptar uma operacao de SBTH, medido em vezes o CDI. SBTH simula a compra de acoes usando opcoes, entao precisa render mais que comprar a acao a vista.",
        "usado_em": "Monitor de Oportunidades (filtro de viabilidade para SBTH).",
        "precedencia": "Banco de Dados -> 1.1 (padrao no codigo)",
    },
    "sbth_qtd_ativo": {
        "descricao": "Quantidade de acoes que voce pretende comprar na operacao de SBTH.",
        "usado_em": "Monitor de Oportunidades (profundidade para SBTH).",
        "precedencia": "Banco de Dados -> 1000 (padrao)",
    },
    "sbth_prof_ativo": {
        "descricao": "Posicao no book para compra do ativo no SBTH.",
        "usado_em": "Monitor de Oportunidades (coleta de precos para SBTH).",
        "precedencia": "Banco de Dados -> 1 (padrao)",
    },
    "sbth_qtd_put": {
        "descricao": "Quantidade de PUT que voce vende (escreve) na operacao de SBTH.",
        "usado_em": "Monitor de Oportunidades (profundidade para SBTH).",
        "precedencia": "Banco de Dados -> 1000 (padrao)",
    },
    "sbth_prof_put": {
        "descricao": "Posicao no book para venda da PUT no SBTH.",
        "usado_em": "Monitor de Oportunidades (coleta de precos para SBTH).",
        "precedencia": "Banco de Dados -> -1 (padrao)",
    },
    "premio_box_sintetico_call_itm": {
        "descricao": "Retorno minimo exigido para a operacao de BOX Sintetico / Basket (3 pernas com opcao ITM), em vezes o CDI. Precisa ser maior que o BOX comum porque e uma operacao mais complexa.",
        "usado_em": "Montagem de Basket ITM (filtro de viabilidade).",
        "precedencia": "Banco de Dados -> 3.0 (padrao no codigo)",
    },
    "basket_qtd_call_itm": {
        "descricao": "Quantidade de opcoes CALL ITM compradas no Basket.",
        "usado_em": "Montagem de Basket (profundidade).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "basket_prof_call_itm": {
        "descricao": "Posicao no book para compra da CALL ITM no Basket.",
        "usado_em": "Montagem de Basket (coleta de precos).",
        "precedencia": "Banco de Dados -> 1 (padrao)",
    },
    "basket_qtd_put": {
        "descricao": "Quantidade de PUT vendidas no Basket.",
        "usado_em": "Montagem de Basket (profundidade).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "basket_prof_put": {
        "descricao": "Posicao no book para venda da PUT no Basket.",
        "usado_em": "Montagem de Basket (coleta de precos).",
        "precedencia": "Banco de Dados -> -1 (padrao)",
    },
    "basket_qtd_call": {
        "descricao": "Quantidade de CALL ATM vendidas no Basket.",
        "usado_em": "Montagem de Basket (profundidade).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "basket_prof_call": {
        "descricao": "Posicao no book para venda da CALL ATM no Basket.",
        "usado_em": "Montagem de Basket (coleta de precos).",
        "precedencia": "Banco de Dados -> -1 (padrao)",
    },
    "perf_carga_inteligente": {
        "descricao": "Quando ativado, o sistema carrega apenas instrumentos com strike proximo ao preco do ativo, ignorando opcoes muito distantes. Melhora a performance em acoes com muitas opcoes listadas.",
        "usado_em": "Carga de instrumentos (filtro de strike na importacao).",
        "precedencia": "Banco de Dados -> 1 (ativado, padrao)",
    },
    "perf_range_min": {
        "descricao": "Limite inferior do filtro de strike (em porcentagem do preco do ativo). Exemplo: -50% em um ativo de R$ 30 significa ignorar opcoes com strike abaixo de R$ 15.",
        "usado_em": "Carga de instrumentos (filtro de importacao).",
        "precedencia": "Banco de Dados -> -50% (padrao)",
    },
    "perf_range_max": {
        "descricao": "Limite superior do filtro de strike (em porcentagem do preco do ativo). Exemplo: +50% em um ativo de R$ 30 significa ignorar opcoes com strike acima de R$ 45.",
        "usado_em": "Carga de instrumentos (filtro de importacao).",
        "precedencia": "Banco de Dados -> 50% (padrao)",
    },
    "perf_limite_meses": {
        "descricao": "Limite de vencimento em meses para considerar uma opcao. 0 = sem limite. Exemplo: 3 significa ignorar opcoes com vencimento superior a 3 meses.",
        "usado_em": "Carga de instrumentos (filtro de importacao).",
        "precedencia": "Banco de Dados -> 0 (sem limite, padrao)",
    },
    "perf_dias_minimos": {
        "descricao": "Quantidade minima de dias ate o vencimento para uma opcao ser considerada. Opcoes muito proximas do vencimento tem baixa liquidez e alto risco.",
        "usado_em": "Monitores de BOX, Colar e Collar Calendario (filtro de dias minimos).",
        "precedencia": "Banco de Dados -> 10 dias (padrao no codigo)",
    },
    "onda2_dte_min": {
        "descricao": "DTE minimo para um instrumento receber registro completo (Onda 2). Abaixo disto, so tem cabecalho de book.",
        "usado_em": "MercadoDataProvider — manutencao Onda 2.",
        "precedencia": "Spinner -> Banco de Dados -> 7 (padrao)",
    },
    "onda2_dte_max": {
        "descricao": "DTE maximo para registro completo Onda 2. Opcoes muito longas (>180D) raramente tem liquidez.",
        "usado_em": "MercadoDataProvider — manutencao Onda 2.",
        "precedencia": "Spinner -> Banco de Dados -> 180 (padrao)",
    },
    "notif_telegram_enable": {
        "descricao": "Ativa o envio de notificacoes via Telegram quando operacoes interessantes sao encontradas.",
        "usado_em": "Monitor de Oportunidades (envio de mensagens apos cada varredura).",
        "precedencia": "Banco de Dados -> Desativado (padrao)",
    },
    "telegram_bot_token": {
        "descricao": "Token do bot do Telegram para enviar mensagens. Obtenha criando um bot no @BotFather do Telegram.",
        "usado_em": "Servico de notificacao Telegram.",
        "precedencia": "Banco de Dados",
    },
    "telegram_chat_id": {
        "descricao": "ID do chat ou grupo do Telegram para onde as mensagens serao enviadas.",
        "usado_em": "Servico de notificacao Telegram.",
        "precedencia": "Banco de Dados",
    },
    "som_arquivo": {
        "descricao": "Caminho para um arquivo .wav que será tocado quando houver oportunidades viáveis (🔔). "
                     "Deixe vazio para usar o beep padrão do sistema (winsound). "
                     "Sons do Windows em C:\\Windows\\Media\\ podem ser usados (ex: 'Windows Notify.wav').",
        "usado_em": "som_service.tocar() — todos os diálogos com sino (Collar, Collar Cal., Box 4P, MPP, main window).",
        "precedencia": "Banco de Dados -> Vazio (beep padrão)",
    },
    "som_volume": {
        "descricao": "Volume do som de notificação, de 0 (mudo) a 100 (máximo). "
                     "Afeta apenas quando um arquivo .wav está configurado. O beep padrão ignora este volume.",
        "usado_em": "som_service.tocar() — QSoundEffect.setVolume().",
        "precedencia": "Banco de Dados -> 100 (padrão)",
    },
    "som_arquivo_vendidas": {
        "descricao": "Caminho para um arquivo .wav para notificacoes de VENDIDAS. "
                     "Deixe vazio para usar o beep padrão do sistema (winsound). "
                     "Sons do Windows em C:\\Windows\\Media\\ podem ser usados.",
        "usado_em": "som_service.tocar_vendidas() — main window (tabela vendidas).",
        "precedencia": "Banco de Dados -> Vazio (beep padrão)",
    },
    "som_volume_vendidas": {
        "descricao": "Volume do som de notificacao de VENDIDAS, de 0 (mudo) a 100 (máximo).",
        "usado_em": "som_service.tocar_vendidas().",
        "precedencia": "Banco de Dados -> 100 (padrão)",
    },
    "som_arquivo_coberta": {
        "descricao": "Caminho para um arquivo .wav para notificacoes de TAXA. "
                     "Deixe vazio para usar o beep padrão do sistema (winsound).",
        "usado_em": "som_service.tocar_coberta() — main window (tabela TAXA/Venda Coberta).",
        "precedencia": "Banco de Dados -> Vazio (beep padrão)",
    },
    "som_volume_coberta": {
        "descricao": "Volume do som de notificacao de TAXA, de 0 (mudo) a 100 (máximo).",
        "usado_em": "som_service.tocar_coberta().",
        "precedencia": "Banco de Dados -> 100 (padrão)",
    },
    "premio_risco_colar": {
        "descricao": "Retorno minimo exigido para aceptar um Colar Protetivo, em vezes o CDI. O Colar compra PUT e vende CALL para proteger uma posicao em acoes.",
        "usado_em": "Monitor de Colares (filtro de viabilidade).",
        "precedencia": "Banco de Dados -> 1.05 (padrao no codigo)",
    },
    "colar_dist_max_pct": {
        "descricao": "Distancia maxima (em porcentagem) entre o preco do ativo e os strikes considerados para montar um Colar. Valores maiores incluem mais combinacoes, mas podem gerar resultados ruins.",
        "usado_em": "Monitor de Colares (filtro de agrupamento de strikes).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 0.15 (15%, padrao)",
    },
    "calendario_strike_diff_max": {
        "descricao": "Numero maximo de niveis de strike de diferenca entre a CALL e a PUT no Collar Calendario. Ex: 2 = permite ate 2 strikes de distancia (cada ativo tem seu step ex: PETR4 step R$0.50, entao 2 steps = R$1.00).",
        "usado_em": "Monitor de Collar Calendario (filtro de pareamento).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 2 (padrao)",
    },
    "limiar_classificacao_calendario": {
        "descricao": "Limiar para classificar o tipo do Collar Calendario (NEUTRO/ALTA/BAIXA). Valor multiplicado pelo spread entre strikes. Ex: 0.15 = 15% do spread. Quanto menor, mais estreita a faixa NEUTRO.",
        "usado_em": "Calculadora de Collar Calendario (classificacao de tipo).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 0.15 (padrao)",
    },
    "be_search_range_mult": {
        "descricao": "Margem de seguranca para a busca de breakeven no Collar Calendario. O grafico de payoff busca raizes entre (menor strike x (1 - margem)) e (maior strike x (1 + margem)). Ex: 0.15 = busca entre 85% e 115% dos strikes.",
        "usado_em": "Calculadora de Collar Calendario (calculo de breakeven).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 0.15 (padrao)",
    },
    "premio_risco_colar_calendario": {
        "descricao": "Retorno minimo exigido para o Collar Calendario, em vezes o CDI. O Collar Calendario combina opcoes de vencimentos diferentes para capturar a diferenca de tempo.",
        "usado_em": "Monitor de Collar Calendario (filtro de viabilidade).",
        "precedencia": "Banco de Dados -> 1.2 (padrao no codigo)",
    },
    "calendario_call_otm_max": {
        "descricao": "Quanto a CALL pode estar acima do preco do ativo (fora do dinheiro / OTM) para ser considerada no Collar Calendario, em porcentagem. Exemplo: 0.04 = permite CALL ate 4% acima do spot.",
        "usado_em": "Monitor de Collar Calendario (filtro de selecao de CALLs).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 0.04 (4%, padrao)",
    },
    "taxa_emolumento_pct": {
        "descricao": "Taxa cobrada pela B3 sobre o valor financeiro da operacao (emolumentos). Atualmente 0.025% por perna. Entra no calculo do lucro liquido.",
        "usado_em": "Calculadora de Custos B3 (BOX 4P, Colar, Collar Calendario).",
        "precedencia": "Banco de Dados -> 0.00025 (0.025%, padrao fixo B3)",
    },
    "taxa_liquidacao_pct": {
        "descricao": "Taxa de liquidacao cobrada pela B3. Atualmente 0.0275% por perna. Somada aos emolumentos para calcular o custo total B3.",
        "usado_em": "Calculadora de Custos B3 (BOX 4P, Colar, Collar Calendario).",
        "precedencia": "Banco de Dados -> 0.000275 (0.0275%, padrao fixo B3)",
    },
    "colar_qtd_ativo": {
        "descricao": "Quantidade de acoes para comprar em cada operacao de Colar Protetivo. Usado pelo botao 'Basket PNT' para gerar a ordem. Voce pode alterar manualmente depois de colar no PNT.",
        "usado_em": "Dialog de detalhes do Colar Protetivo (exportacao PNT).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "colar_qtd_call": {
        "descricao": "Quantidade de opcoes CALL para vender em cada operacao de Colar Protetivo.",
        "usado_em": "Dialog de detalhes do Colar Protetivo (exportacao PNT).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "colar_qtd_put": {
        "descricao": "Quantidade de opcoes PUT para comprar em cada operacao de Colar Protetivo.",
        "usado_em": "Dialog de detalhes do Colar Protetivo (exportacao PNT).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "calendario_qtd_ativo": {
        "descricao": "Quantidade de acoes para comprar em cada operacao de Collar Calendario.",
        "usado_em": "Dialog de detalhes do Collar Calendario (exportacao PNT).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "calendario_qtd_call": {
        "descricao": "Quantidade de opcoes CALL para vender em cada operacao de Collar Calendario.",
        "usado_em": "Dialog de detalhes do Collar Calendario (exportacao PNT).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "calendario_qtd_put": {
        "descricao": "Quantidade de opcoes PUT para comprar em cada operacao de Collar Calendario.",
        "usado_em": "Dialog de detalhes do Collar Calendario (exportacao PNT).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "colar_qul_min_put": {
        "descricao": "Quantidade minima de negocios realizados (QUL) que a PUT precisa ter para ser considerada no Colar. Filtra opcoes com baixa liquidez.",
        "usado_em": "Monitor de Colares (filtro de liquidez).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "colar_qul_min_call": {
        "descricao": "Quantidade minima de negocios realizados (QUL) que a CALL precisa ter para ser considerada no Colar.",
        "usado_em": "Monitor de Colares (filtro de liquidez).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "box_premio_risco": {
        "descricao": "Retorno minimo exigido para aceptar uma operacao de Box Spread 4 Pontas, em vezes o CDI. O Box 4P usa 4 opcoes (2 CALLs + 2 PUTs) em 2 strikes diferentes.",
        "usado_em": "Monitor de Box 4P (filtro de viabilidade).",
        "precedencia": "Banco de Dados -> 1.08 (padrao no codigo)",
    },
    "box_qtd_min": {
        "descricao": "Quantidade minima de contratos que cada perna do Box 4P precisa ter no book. Garante que a operacao pode ser executada inteira.",
        "usado_em": "Monitor de Box 4P (filtro de profundidade).",
        "precedencia": "Banco de Dados -> 100 (padrao)",
    },
    "box_soh_europeia": {
        "descricao": "Quando ativado, aceita apenas opcoes europeias (sem risco de exercicio antecipado). Opcoes americanas podem ser exercidas a qualquer momento, o que quebra a estrategia.",
        "usado_em": "Monitor de Box 4P (filtro de tipo de opcao).",
        "precedencia": "Banco de Dados -> Ativado (padrao)",
    },
    "colar_risco_baixo_vov_min": {
        "descricao": "Volume minimo no book de ofertas (VOV para PUT, VOC para CALL) para considerar o risco de despernamento como baixo. Acima deste valor, o book tem profundidade para executar a operacao inteira sem desequilibrar.",
        "usado_em": "Calculadora de Colar (classificacao de risco de leilao/despernamento).",
        "precedencia": "Banco de Dados -> 1000 (padrao)",
    },
    "elegibilidade_strike_max_pct": {
        "descricao": "Strike maximo da CALL ITM em porcentagem do preco do ativo para ser elegivel na Pescaria de Basket. Exemplo: 0.70 = so aceita CALL com strike ate 70% do spot (30% dentro do dinheiro).",
        "usado_em": "Elegibilidade de Pescaria / Basket (filtro de profundidade ITM).",
        "precedencia": "Banco de Dados -> 0.70 (70%, padrao)",
    },
    "dte_call_min": {
        "descricao": "Dias minimos ate o vencimento (DTE) para a perna CALL no Collar Calendario. Opcoes com menos dias que isto sao ignoradas.",
        "usado_em": "Monitor de Collar Calendario (filtro DTE).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 29 (padrao)",
    },
    "dte_call_max": {
        "descricao": "Dias maximos ate o vencimento para a CALL ser considerada a perna curta (menor DTE) no Collar Calendario. Acima deste valor, a opcao vira candidata a perna longa (PUT).",
        "usado_em": "Monitor de Collar Calendario (classificacao call/put).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 60 (padrao)",
    },
    "dte_extra_min": {
        "descricao": "Diferenca minima de dias entre o vencimento da PUT e da CALL no Collar Calendario. Garante um espacamento minimo para o calendario funcionar.",
        "usado_em": "Monitor de Collar Calendario (filtro de pareamento).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 30 (padrao)",
    },
    "dte_extra_max": {
        "descricao": "Diferenca maxima de dias entre PUT e CALL no Collar Calendario. Impede que o calendario fique muito largo (risco alto).",
        "usado_em": "Monitor de Collar Calendario (filtro de pareamento).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 90 (padrao)",
    },
    "dte_total_max": {
        "descricao": "Dias maximos ate o vencimento para QUALQUER perna no Collar Calendario. Opcoes com DTE acima disto sao ignoradas completamente.",
        "usado_em": "Monitor de Collar Calendario (filtro DTE inicial).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 120 (padrao)",
    },
    "white_list_colar_calendario": {
        "descricao": "Lista de ativos que aparecem marcados por padrao ao abrir o Collar Calendario. Se vazia, todos os ativos disponiveis aparecem marcados. Separar por virgula (ex: PETR4,VALE3,ITUB4).",
        "usado_em": "Interface do Collar Calendario (pre-selecao de ativos).",
        "precedencia": "Banco de Dados -> Vazio (todos marcados)",
    },
    "telegram_cleanup_timeout": {
        "descricao": "Tempo em segundos apos o qual uma oportunidade enviada pelo Telegram e removida do historico. Apos este prazo, a mesma oportunidade pode ser re-enviada.",
        "usado_em": "Monitor de Oportunidades (limpeza de historico).",
        "precedencia": "Spinner -> Banco de Dados -> 300 (5 min, padrao)",
    },
    "ranking_peso_colar_pop": {
        "descricao": "Peso da Pop balanceada normalizada no Score de Ranking do Colar Protetivo. Pop_NORM = (100 − |Pop↑ − Pop↓|) ÷ max(Pop_BALANCEADA) no lote. Penaliza operações com distribuição assimétrica (ex: 92%% abaixo e 5%% acima). Quanto mais balanceada, maior o score.",
        "usado_em": "Monitor de Colar Protetivo (cálculo do Score, ordenação padrão decrescente).",
        "precedencia": "Banco de Dados -> 3.0 (padrão no seed)",
    },
    "ranking_peso_colar_cdi": {
        "descricao": "Peso do % CDI (pior cenário) normalizado no Score do Colar Protetivo.  CDI_NORM = pct_cdi ÷ max(pct_cdi) no lote.",
        "usado_em": "Monitor de Colar Protetivo (cálculo do Score).",
        "precedencia": "Banco de Dados -> 2.0 (padrão no seed)",
    },
    "ranking_peso_colar_risco": {
        "descricao": "Peso do risco de leilão (inverso) no Score do Colar Protetivo. RISCO = 1.0 (Baixo), 0.5 (Médio), 0.0 (Alto). Penaliza operações com book fino e risco de despernamento.",
        "usado_em": "Monitor de Colar Protetivo (cálculo do Score).",
        "precedencia": "Banco de Dados -> 1.0 (padrão no seed)",
    },
    "ranking_peso_theta": {
        "descricao": "Peso do theta líquido normalizado no Score de Ranking do Collar Calendário. Quanto maior, mais o ranking favorece operações com alto decaimento temporal (theta positivo). θLíq_NORM = |theta_líquido| ÷ max(|θLíq|) no lote.",
        "usado_em": "Monitor de Collar Calendário (cálculo do Score, ordenação padrão decrescente).",
        "precedencia": "Banco de Dados -> 3.0 (padrão no seed)",
    },
    "ranking_peso_cdi": {
        "descricao": "Peso do % CDI normalizado no Score de Ranking. Quanto maior, mais o ranking prioriza retorno sobre o CDI. CDI_NORM = pct_cdi ÷ max(pct_cdi) no lote.",
        "usado_em": "Monitor de Collar Calendário (cálculo do Score).",
        "precedencia": "Banco de Dados -> 2.0 (padrão no seed)",
    },
    "ranking_peso_sigma": {
        "descricao": "Peso da folga sigma (distância aos strikes em desvios padrão) no Score de Ranking. Mede a probabilidade de a CALL expirar OTM. SIGMA_FOLGA = min(|spot−K_call|,|spot−K_put|) ÷ (spot × σ_IV × √(DTE_call/252)). Valores altos = mais folga = maior chance de sucesso.",
        "usado_em": "Monitor de Collar Calendário (cálculo do Score).",
        "precedencia": "Banco de Dados -> 2.0 (padrão no seed)",
    },
    "ranking_peso_credito": {
        "descricao": "Peso do crédito líquido normalizado no Score de Ranking. Mede o carregamento positivo da estrutura. CRÉDITO_NORM = max(0, net_credito ÷ capital_empregado) ÷ max(cred_ratio) no lote.",
        "usado_em": "Monitor de Collar Calendário (cálculo do Score).",
        "precedencia": "Banco de Dados -> 1.0 (padrão no seed)",
    },
    "ranking_peso_liquidez": {
        "descricao": "Peso da liquidez no Score de Ranking. Atualmente fixo em 1.0 (neutro) para todos os resultados — reservado para futura implementação com dados de volume/OI. LIQ = 1.0.",
        "usado_em": "Monitor de Collar Calendário (cálculo do Score).",
        "precedencia": "Banco de Dados -> 0.5 (padrão no seed)",
    },
    "mpp_habilitado": {
        "descricao": "Quando ativado, o Motor de Priorizacao de Pescaria (MPP) calcula o score instantaneo dos boxes periodicamente. Quando desativado, o MPP nao consome CPU e o ranking nao e atualizado automaticamente.",
        "usado_em": "Motor de Priorizacao de Pescaria (ciclo de varredura do worker).",
        "precedencia": "Banco de Dados -> 1 (ativado, padrao no seed)",
    },
    "mpp_instantaneo_interval": {
        "descricao": "Numero de ciclos de varredura entre cada calculo do score instantaneo MPP. Cada ciclo dura ~2.5s. Default 4 = ~10s. Aumente para reduzir consumo de CPU (ex: 24 = ~60s).",
        "usado_em": "Motor de Priorizacao de Pescaria (frequencia de atualizacao).",
        "precedencia": "Banco de Dados -> 4 (padrao no seed)",
    },
}


class ParametrosWidget(QWidget):
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.repo = ParametroRepository(db_path)
        self._widgets: dict[str, QWidget] = {}
        self._pct_chaves: set[str] = set()
        self._setup_ui()
        self._carregar()

    # Ordem de exibição da sidebar (esquerda). Ordem dos parâmetros por
    # estratégia continua igual à definida em PARAMETROS_POR_ESTRATEGIA.
    _SIDEBAR_ORDER = [
        "GERAL",
        "COLAR",
        "COLLAR_CALENDARIO",
        "BOX",
        "BOX_SINTETICO",
        "BOX_4P",
        "SBTH",
        "VENDA_COBERTA",
        "SBTH_VENDIDA",
        "COLLAR_CALENDARIO_CAUDA",
        "PERFORMANCE",
        "TELEGRAM",
        "SOM",
    ]

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(8)

        body = QHBoxLayout()
        body.setContentsMargins(8, 8, 8, 0)
        body.setSpacing(8)

        self.sidebar = self._build_sidebar()
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self._pages = {}    # estrategia -> QWidget pagina
        self._build_stack_pages()
        body.addWidget(self.stack, stretch=1)

        outer_layout.addLayout(body)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: {}; max-height: 1px;".format(Palette.BORDER))
        outer_layout.addWidget(sep)

        self.btn_salvar = QPushButton("Salvar Parametros")
        self.btn_salvar.setProperty("class", "primary")
        self.btn_salvar.clicked.connect(self._salvar)
        outer_layout.addWidget(self.btn_salvar)

        btn_export = QPushButton("💾 Exportar Config")
        btn_export.setFixedHeight(24)
        btn_export.setStyleSheet("font-size: 8pt;")
        btn_export.clicked.connect(self._exportar_json)
        outer_layout.addWidget(btn_export)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_layout.addWidget(self.lbl_status)

        self.sidebar.currentItemChanged.connect(self._on_sidebar_changed)
        self._restore_selection()

    def _build_sidebar(self) -> QListWidget:
        lista = QListWidget()
        lista.setFixedWidth(250)
        lista.setUniformItemSizes(True)
        lista.setSpacing(2)
        lista.setStyleSheet("""
            QListWidget {
                background-color: #14141f;
                border: 1px solid #2d2d44;
                border-radius: 6px;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
                color: #cfcfdc;
            }
            QListWidget::item:hover {
                background-color: #1f1f33;
            }
            QListWidget::item:selected {
                background-color: #2d4a7a;
                color: #ffffff;
            }
        """)

        _ESTRATEGIA_SYMBOL = {
            "GERAL": "\u2699",                       # ⚙
            "COLAR": "\U0001F6E1",                   # 🛡
            "COLLAR_CALENDARIO": "\U0001F4C5",        # 📅
            "BOX": "\U0001F4E6",                      # 📦
            "BOX_SINTETICO": "\U0001F9FA",            # 🧺
            "BOX_4P": "\U0001F9EE",                   # 🧮
            "SBTH": "\U0001F4C8",                     # 📈
            "VENDA_COBERTA": "\u25CF",                # ● (bullit color)
            "SBTH_VENDIDA": "\u25CF",
            "COLLAR_CALENDARIO_CAUDA": "\U0001FAB6",  # 🪶
            "PERFORMANCE": "\u26A1",                  # ⚡
            "TELEGRAM": "\U0001F4F2",                 # 📲
            "SOM": "\U0001F514",                      # 🔔
        }

        for key in self._SIDEBAR_ORDER:
            label = ESTRATEGIA_LABELS.get(key, key)
            color = ESTRATEGIA_COLORS.get(key, Palette.TEXT_PRIMARY)
            symbol = _ESTRATEGIA_SYMBOL.get(key, "\u25CF")
            item = QListWidgetItem("{}  {}".format(symbol, label))
            item.setData(Qt.UserRole, key)
            item.setData(int(Qt.UserRole) + 1, color)
            item.setData(int(Qt.UserRole) + 3, label)
            lista.addItem(item)
        return lista

    def _chave_som_estrategia(self, key: str) -> str:
        """Qual parâmetro de som reflete para esta estratégia."""
        if key in ("VENDA_COBERTA", "SBTH_VENDIDA"):
            return "som_arquivo_coberta"
        return "som_arquivo"

    def _build_stack_pages(self):
        for key in self._SIDEBAR_ORDER:
            params = PARAMETROS_POR_ESTRATEGIA.get(key, [])
            label = ESTRATEGIA_LABELS.get(key, key)
            color = ESTRATEGIA_COLORS.get(key, Palette.TEXT_PRIMARY)
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(8)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            inner = QWidget()
            form_holder = QVBoxLayout(inner)
            form_holder.setContentsMargins(8, 8, 8, 8)
            form_holder.setSpacing(12)

            group = QGroupBox(label)
            group.setStyleSheet(
                "QGroupBox::title {{ color: {}; }}".format(color)
            )
            form = QFormLayout()
            form.setSpacing(10)
            form.setContentsMargins(12, 20, 12, 12)

            for chave, display in params:
                self._build_param_row(form, chave, display)

            group.setLayout(form)
            form_holder.addWidget(group)
            form_holder.addStretch()
            scroll.setWidget(inner)
            page_layout.addWidget(scroll)

            self._pages[key] = page
            self.stack.addWidget(page)

    def _build_param_row(self, form, chave, display):
                if "perf_carga_inteligente" in chave or "notif_telegram_enable" in chave or "box_soh_europeia" in chave or "mpp_habilitado" in chave or "taxa_aluguel_habilitado" in chave:
                    widget = QCheckBox("Habilitado")
                    widget.setStyleSheet("color: {};".format(Palette.TEXT_PRIMARY))
                elif "tema_visual" in chave:
                    widget = QComboBox()
                    widget.addItems(["Azul Marinho", "Grafite / Slate", "True Dark / Charcoal"])
                elif "fonte_market_data" in chave:
                    widget = QComboBox()
                    widget.addItems(["Profit RTD", "Open Fast Socket"])
                elif "telegram_bot_token" in chave or "telegram_chat_id" in chave or "_list_" in chave:
                    widget = QLineEdit()
                    widget.setStyleSheet("color: {};".format(Palette.TEXT_PRIMARY))
                elif chave in ("som_arquivo", "som_arquivo_vendidas", "som_arquivo_coberta"):
                    e_vendidas = chave == "som_arquivo_vendidas"
                    e_coberta = chave == "som_arquivo_coberta"
                    container = QWidget()
                    h = QHBoxLayout(container)
                    h.setContentsMargins(0, 0, 0, 0)
                    h.setSpacing(6)

                    widget = QComboBox()
                    widget.setStyleSheet("""
                        QComboBox {
                            color: #e0e0e0; background-color: #1a1a2e;
                            border: 1px solid #2d2d44; border-radius: 4px;
                            padding: 4px 8px; min-width: 280px;
                        }
                        QComboBox::drop-down { border: 0; width: 20px; }
                        QComboBox QAbstractItemView {
                            background-color: #1a1a2e; color: #e0e0e0;
                            selection-background-color: #2d4a7a;
                            selection-color: #e0e0e0;
                            border: 1px solid #2d2d44;
                        }
                    """)
                    widget.setToolTip("Som de notificacao — escolha um arquivo .wav ou Beep do sistema")

                    from pathlib import Path
                    media = Path(r"C:\Windows\Media")
                    if media.exists():
                        widget.addItem("-- Beep do sistema (padrao) --", "")
                        for wav in sorted(media.glob("*.wav")):
                            widget.addItem(wav.stem, str(wav))
                    else:
                        widget.addItem("-- Beep do sistema (padrao) --", "")
                    widget.addItem("-- Personalizado... --", "__custom__")
                    widget.setCurrentIndex(0)
                    if e_coberta:
                        self._som_arquivo_coberta_widget = widget
                    elif e_vendidas:
                        self._som_arquivo_vendidas_widget = widget
                    else:
                        self._som_arquivo_widget = widget
                    h.addWidget(widget, stretch=1)

                    widget.currentIndexChanged.connect(
                        lambda idx, w=widget: self._on_som_combo_changed(w)
                    )

                    btn_test = QPushButton("Testar")
                    btn_test.setFixedSize(50, 24)
                    btn_test.setToolTip("Testar som atual")
                    btn_test.setStyleSheet(
                        "QPushButton {{ background: {}; color: {}; border: 1px solid {}; border-radius: 4px; font-size: 8.5pt; font-weight: bold; padding: 0; }}"
                        "QPushButton:hover {{ background: {}; }}".format(
                            Palette.BG_HOVER, Palette.GREEN, Palette.BORDER, Palette.GREEN_DIM
                        )
                    )
                    if e_coberta:
                        btn_test._som_alvo = "coberta"
                    elif e_vendidas:
                        btn_test._som_alvo = "vendidas"
                    else:
                        btn_test._som_alvo = "compradas"
                    btn_test.clicked.connect(self._testar_som_generico)
                    h.addWidget(btn_test)

                    self._widgets[chave] = widget
                    widget = container
                elif chave in ("som_volume", "som_volume_vendidas", "som_volume_coberta"):
                    container = QWidget()
                    h = QHBoxLayout(container)
                    h.setContentsMargins(0, 0, 0, 0)
                    h.setSpacing(10)

                    widget = QSlider(Qt.Horizontal)
                    widget.setRange(0, 100)
                    widget.setStyleSheet("""
                        QSlider::groove:horizontal {
                            background: #2d2d44; height: 6px; border-radius: 3px;
                        }
                        QSlider::handle:horizontal {
                            background: #e67e22; width: 14px; height: 14px;
                            border-radius: 7px; margin: -4px 0;
                        }
                        QSlider::sub-page:horizontal {
                            background: #e67e22; border-radius: 3px;
                        }
                    """)
                    h.addWidget(widget, stretch=1)

                    lbl_vol = QLabel("100%")
                    lbl_vol.setStyleSheet("color: {}; font-size: 9pt; font-weight: bold; min-width: 36px;".format(Palette.TEXT_PRIMARY))
                    lbl_vol.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    widget.valueChanged.connect(lambda v, l=lbl_vol: l.setText(f"{v}%"))
                    h.addWidget(lbl_vol)

                    self._widgets[chave] = widget
                    widget = container
                else:
                    widget = NoWheelSpinBox()
                    if chave == "perf_range_min":
                        widget.setRange(-100.0, 0.0)
                        widget.setSuffix(" %")
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "perf_range_max":
                        widget.setRange(0.0, 100.0)
                        widget.setSuffix(" %")
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "perf_limite_meses":
                        widget.setRange(0.0, 60.0)
                        widget.setSuffix(" meses")
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "perf_dias_minimos":
                        widget.setRange(0.0, 365.0)
                        widget.setSuffix(" dias")
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "calendario_call_otm_max":
                        widget.setRange(0.0, 100.0)
                        widget.setSuffix(" %")
                        widget.setDecimals(2)
                        widget.setSingleStep(0.5)
                        self._pct_chaves.add(chave)
                    elif chave == "calendario_strike_diff_max":
                        widget.setRange(0, 50)
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "onda2_dte_min":
                        widget.setRange(0, 365)
                        widget.setSuffix(" dias")
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "onda2_dte_max":
                        widget.setRange(0, 730)
                        widget.setSuffix(" dias")
                        widget.setDecimals(0)
                        widget.setSingleStep(1)
                    elif chave == "telegram_cleanup_timeout":
                        widget.setRange(30, 86400)
                        widget.setSuffix(" s")
                        widget.setDecimals(0)
                        widget.setSingleStep(30)
                    elif chave in ("limiar_classificacao_calendario", "be_search_range_mult"):
                        widget.setRange(0.0, 100.0)
                        widget.setSuffix(" %")
                        widget.setDecimals(2)
                        widget.setSingleStep(0.5)
                        self._pct_chaves.add(chave)
                    else:
                        widget.setRange(-100.0, 100000.0)
                        if "prof" in chave or "qtd" in chave or "meses" in chave or "inteligente" in chave or "interval" in chave or "dte" in chave:
                            widget.setDecimals(0)
                            widget.setSingleStep(1 if "qtd" not in chave else 100)
                        else:
                            widget.setDecimals(4)
                            widget.setSingleStep(0.01)

                param_label = QLabel(display + ":")
                param_label.setStyleSheet("color: {}; font-size: 9pt;".format(Palette.TEXT_SECONDARY))

                btn_info = QPushButton("\u24d8")
                btn_info.setFixedSize(18, 18)
                btn_info.setStyleSheet(
                    "QPushButton {{ color: {}; background: transparent; border: none; font-size: 11pt; }}"
                    "QPushButton:hover {{ color: {}; }}".format(Palette.TEXT_MUTED, Palette.GREEN)
                )
                info = PARAMETROS_INFO.get(chave, {})
                if info:
                    desc = info.get("descricao", "")
                    btn_info.setToolTip(desc)
                    widget.setToolTip(desc)
                    btn_info.clicked.connect(
                        lambda checked, c=chave, d=display: self._mostrar_info(c, d)
                    )

                label_row = QWidget()
                label_layout = QHBoxLayout(label_row)
                label_layout.setContentsMargins(0, 0, 0, 0)
                label_layout.setSpacing(2)
                label_layout.addWidget(param_label)
                label_layout.addWidget(btn_info)
                label_layout.addStretch()

                form.addRow(label_row, widget)
                if chave not in ("som_arquivo", "som_volume", "som_arquivo_vendidas", "som_volume_vendidas", "som_arquivo_coberta", "som_volume_coberta"):
                    self._widgets[chave] = widget

    def _on_sidebar_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            return
        key = current.data(Qt.UserRole)
        page = self._pages.get(key)
        if page is not None:
            self.stack.setCurrentWidget(page)
            self._save_selection(key)

    def _save_selection(self, key: str):
        QSettings().setValue("parametros/last_section", key)

    def _restore_selection(self):
        last = QSettings().value("parametros/last_section", "GERAL")
        for i in range(self.sidebar.count()):
            it = self.sidebar.item(i)
            if it.data(Qt.UserRole) == last:
                self.sidebar.setCurrentRow(i)
                return
        if self.sidebar.count() > 0:
            self.sidebar.setCurrentRow(0)

    # ---- Tranche 3: ícones reativos (viáveis por estratégia) ----

    def bind_monitor_signals(self, worker):
        """Conecta sinais do monitor para atualizar contador 🔴 da estratégia."""
        if not worker:
            return
        self._worker = worker
        if hasattr(worker, "oportunidades_atualizadas"):
            worker.oportunidades_atualizadas.connect(
                lambda lst: self._update_counter("BOX", self._count_viaveis_box_sbth(lst, "box"))
            )
            worker.oportunidades_atualizadas.connect(
                lambda lst: self._update_counter("SBTH", self._count_viaveis_box_sbth(lst, "sbth"))
            )
            worker.oportunidades_atualizadas.connect(
                lambda lst: self._update_counter("BOX_SINTETICO",
                    self._count_viaveis_box_sbth(lst, "box_sintetico"))
            )
        if hasattr(worker, "boxes_atualizados"):
            worker.boxes_atualizados.connect(
                lambda lst: self._update_counter("BOX_4P",
                    sum(1 for it in lst if getattr(it, "viavel", False)))
            )
        if hasattr(worker, "colares_atualizados"):
            worker.colares_atualizados.connect(
                lambda lst: self._update_counter("COLAR",
                    sum(1 for it in lst if getattr(it, "viavel", False)))
            )
        if hasattr(worker, "colares_calendario_atualizados"):
            worker.colares_calendario_atualizados.connect(
                lambda lst: self._update_counter("COLLAR_CALENDARIO",
                    sum(1 for it in lst if getattr(it, "viavel", False)))
            )
        if hasattr(worker, "oportunidades_coberta_atualizadas"):
            worker.oportunidades_coberta_atualizadas.connect(
                lambda lst: self._update_counter("VENDA_COBERTA",
                    sum(1 for it in lst if getattr(it, "viavel", False)))
            )

    def _count_viaveis_box_sbth(self, lst, kind):
        n = 0
        for it in lst:
            classifica = getattr(it, "operacao", None) or getattr(it, "classificacao", None) or ""
            if kind == "box" and "BOX" in str(classifica).upper() and getattr(it, "viavel", False):
                n += 1
            elif kind == "sbth" and "SBTH" in str(classifica).upper() and getattr(it, "viavel", False):
                n += 1
            elif kind == "box_sintetico" and "BOXSBTH" in str(classifica).upper() and getattr(it, "viavel", False):
                n += 1
        return n

    def _update_counter(self, key, n):
        if n is None:
            return
        for i in range(self.sidebar.count()):
            it = self.sidebar.item(i)
            if it.data(Qt.UserRole) == key:
                self._set_item_counter(it, n)
                return

    def _set_item_counter(self, item: QListWidgetItem, n: int):
        prev = item.data(int(Qt.UserRole) + 2) or 0
        if prev == n:
            return
        item.setData(int(Qt.UserRole) + 2, n)
        text_base = item.data(int(Qt.UserRole) + 3) or item.text()
        item.setData(int(Qt.UserRole) + 3, text_base)
        if n > 0:
            item.setText("{}  🔴 {}".format(text_base.rstrip(), n))
        else:
            item.setText("{}".format(text_base.rstrip()))

    def _mostrar_info(self, chave: str, display: str):
        info = PARAMETROS_INFO.get(chave, {})
        if not info:
            return

        desc = info.get("descricao", "")
        usado = info.get("usado_em", "")
        prec = info.get("precedencia", "")

        msg = QMessageBox(self)
        msg.setWindowTitle(display)
        msg.setIcon(QMessageBox.Information)
        texto = (
            "<b style='font-size:11pt;'>O que faz:</b><br>"
            "{}<br><br>"
            "<b style='font-size:11pt;'>Onde é usado:</b><br>"
            "{}<br><br>"
            "<b style='font-size:11pt;'>Ordem de precedência:</b><br>"
            "{}"
        ).format(desc, usado, prec)
        msg.setText(texto)
        msg.exec_()

    def _carregar(self):
        for chave, widget in self._widgets.items():
            param = self.repo.get_by_chave(chave)
            val = param.valor if param else ParametroOperacional.PARAMETROS_DEFAULT.get(chave, {}).get("valor", 0.0)
            
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(val))
            elif isinstance(widget, QComboBox):
                if chave in ("som_arquivo", "som_arquivo_vendidas", "som_arquivo_coberta"):
                    val_str = str(val).strip()
                    for i in range(widget.count()):
                        if widget.itemData(i) == val_str:
                            widget.setCurrentIndex(i)
                            break
                    else:
                        widget.setCurrentIndex(0)
                elif chave == "fonte_market_data":
                    idx = 1 if str(val) == "openfast" else 0
                    widget.setCurrentIndex(idx)
                else:
                    idx = int(val)
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))
            elif isinstance(widget, QSlider):
                widget.setValue(int(float(val)))
            elif isinstance(widget, QDoubleSpinBox):
                if chave in self._pct_chaves:
                    widget.setValue(val * 100)
                else:
                    widget.setValue(val)

    def _salvar(self):
        try:
            for chave, widget in self._widgets.items():
                if isinstance(widget, QCheckBox):
                    valor = 1.0 if widget.isChecked() else 0.0
                elif isinstance(widget, QComboBox):
                    if chave in ("som_arquivo", "som_arquivo_vendidas", "som_arquivo_coberta"):
                        valor = widget.currentData() or ""
                    elif chave == "fonte_market_data":
                        valor = "openfast" if widget.currentIndex() == 1 else "profit"
                    else:
                        valor = int(widget.currentIndex())
                elif isinstance(widget, QLineEdit):
                    valor = widget.text().strip()
                elif isinstance(widget, QSlider):
                    valor = float(widget.value())
                else:
                    valor = widget.value()
                    if chave in self._pct_chaves:
                        valor = valor / 100.0
                    
                param = self.repo.get_by_chave(chave)
                if param:
                    param.valor = valor
                    self.repo.save(param)
                else:
                    defaults = ParametroOperacional.PARAMETROS_DEFAULT
                    if chave in defaults:
                        d = defaults[chave]
                        p = ParametroOperacional(
                            chave=chave,
                            valor=valor,
                            estrategia=d["estrategia"],
                            descricao=d["descricao"],
                        )
                        self.repo.save(p)
            self._exportar_json()
            self.lbl_status.setText("Parametros salvos com sucesso.")
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold; padding: 4px;".format(Palette.GREEN)
            )
        except Exception as e:
            self.lbl_status.setText("Erro: {}".format(str(e)))
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold; padding: 4px;".format(Palette.RED)
            )

    def _exportar_json(self):
        base = Path(__file__).resolve().parent.parent.parent.parent
        json_path = base / "config" / "parametros_default.json"
        backup_path = base / "backconfsh" / "configsh.json"
        try:
            all_params = self.repo.list_all()
            parametros = []
            for p in all_params:
                parametros.append({
                    "chave": p.chave,
                    "valor": str(p.valor),
                    "estrategia": p.estrategia,
                    "descricao": p.descricao or "",
                })
            data = {
                "_comment": "Blueprint de parametros do SpreadHunter. Valores usados como seed na criacao do banco. Altere aqui para customizar sua instalacao.",
                "parametros": parametros,
            }
            with open(str(json_path), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            backup_path.parent.mkdir(exist_ok=True)
            with open(str(backup_path), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _on_som_combo_changed(self, combo: QComboBox):
        data = combo.currentData()
        if data == "__custom__":
            path, _ = QFileDialog.getOpenFileName(
                self, "Selecionar arquivo de som (.wav)",
                r"C:\Windows\Media",
                "Arquivos WAV (*.wav);;Todos (*.*)"
            )
            if path:
                combo.blockSignals(True)
                combo.insertItem(combo.count() - 1, Path(path).stem, path)
                combo.blockSignals(False)
                combo.setCurrentIndex(combo.count() - 2)
            else:
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)

    def _testar_som_generico(self):
        sender = self.sender()
        alvo = getattr(sender, "_som_alvo", "compradas") if sender else "compradas"
        chave_volume = {"compradas": "som_volume", "vendidas": "som_volume_vendidas", "coberta": "som_volume_coberta"}.get(alvo, "som_volume")
        attr_combo = {"compradas": "_som_arquivo_widget", "vendidas": "_som_arquivo_vendidas_widget", "coberta": "_som_arquivo_coberta_widget"}.get(alvo, "_som_arquivo_widget")
        combo = getattr(self, attr_combo, None)
        slider = self._widgets.get(chave_volume)
        arquivo = combo.currentData() or "" if combo else ""
        volume = (slider.value() / 100.0) if slider else 1.0
        if arquivo and Path(arquivo).exists():
            from src.infrastructure.services.som_service import _tocar_wav, _gerar_wav_volume
            try:
                tmp = _gerar_wav_volume(arquivo, volume)
                _tocar_wav(tmp)
                return
            except Exception:
                pass
        import winsound
        if alvo == "coberta":
            winsound.Beep(800, 200)
            winsound.Beep(1000, 150)
        elif alvo == "vendidas":
            winsound.Beep(600, 300)
        else:
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 150)
