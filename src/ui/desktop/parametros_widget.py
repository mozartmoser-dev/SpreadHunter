from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QDoubleSpinBox, QPushButton, QLabel, QScrollArea, QFrame,
    QCheckBox, QComboBox, QLineEdit, QMessageBox, QHBoxLayout,
)
from PyQt5.QtCore import Qt

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
    "COLAR": "Colar Protetivo",
    "COLLAR_CALENDARIO": "Collar Calendário",
    "BOX_4P": "Box Spread 4 Pontas",
}

ESTRATEGIA_COLORS = {
    "GERAL": Palette.TEXT_PRIMARY,
    "SBTH": Palette.CYAN,
    "BOX": Palette.ACCENT_BLUE_BRIGHT,
    "BOX_SINTETICO": Palette.PURPLE,
    "PERFORMANCE": Palette.YELLOW,
    "TELEGRAM": Palette.GREEN,
    "COLAR": "#1abc9c",
    "COLLAR_CALENDARIO": "#f39c12",
    "BOX_4P": "#e74c3c",
    "IMPORTACAO": "#8e44ad",
}

PARAMETROS_POR_ESTRATEGIA = {
    "GERAL": [
        ("taxa_cdi", "Taxa CDI/Selic"),
        ("tema_visual", "Aspecto do Sistema"),
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
    ],
    "TELEGRAM": [
        ("notif_telegram_enable", "Habilitar Telegram"),
        ("telegram_bot_token", "Token do Bot Telegram"),
        ("telegram_chat_id", "ID do Chat Telegram"),
    ],
    "COLAR": [
        ("premio_risco_colar", "Premio risco Colar (x CDI)"),
        ("colar_dist_max_pct", "Distancia maxima do strike (%)"),
    ],
    "COLLAR_CALENDARIO": [
        ("calendario_strike_diff_pct", "Max diff % entre strikes"),
    ],
    "BOX_4P": [
        ("box_premio_risco", "Premio risco (x CDI)"),
        ("box_qtd_min", "Qtd min contratos por perna"),
        ("box_soh_europeia", "So aceitar opcoes europeias"),
        ("white_list_box4p", "Whitelist de ativos (separados por virgula)"),
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
    "calendario_strike_diff_pct": {
        "descricao": "Diferenca maxima permitida entre o strike da CALL e o strike da PUT no Collar Calendario, em porcentagem do preco do ativo. Quanto menor, mais parecidos os strikes.",
        "usado_em": "Monitor de Collar Calendario (filtro de pareamento).",
        "precedencia": "Spinner da Tela -> Banco de Dados -> 0.03 (3%, padrao)",
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
}


class ParametrosWidget(QWidget):
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.repo = ParametroRepository(db_path)
        self._widgets: dict[str, QWidget] = {}
        self._setup_ui()
        self._carregar()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        for estrategia, params in PARAMETROS_POR_ESTRATEGIA.items():
            label = ESTRATEGIA_LABELS.get(estrategia, estrategia)
            color = ESTRATEGIA_COLORS.get(estrategia, Palette.TEXT_PRIMARY)
            group = QGroupBox(label)
            group.setStyleSheet(
                "QGroupBox::title {{ color: {}; }}".format(color)
            )
            form = QFormLayout()
            form.setSpacing(10)
            form.setContentsMargins(12, 20, 12, 12)

            for chave, display in params:
                if "perf_carga_inteligente" in chave or "notif_telegram_enable" in chave or "box_soh_europeia" in chave:
                    widget = QCheckBox("Habilitado")
                    widget.setStyleSheet("color: {};".format(Palette.TEXT_PRIMARY))
                elif "tema_visual" in chave:
                    widget = QComboBox()
                    widget.addItems(["Azul Marinho", "Grafite / Slate", "True Dark / Charcoal"])
                elif "telegram_bot_token" in chave or "telegram_chat_id" in chave or "_list_" in chave:
                    widget = QLineEdit()
                    widget.setStyleSheet("color: {};".format(Palette.TEXT_PRIMARY))
                else:
                    widget = NoWheelSpinBox()
                    widget.setRange(-100.0, 100000.0)
                    if "prof" in chave or "qtd" in chave or "meses" in chave or "inteligente" in chave:
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
                    btn_info.setToolTip(info.get("descricao", ""))
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
                self._widgets[chave] = widget

            group.setLayout(form)
            layout.addWidget(group)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: {}; max-height: 1px;".format(Palette.BORDER))
        outer_layout.addWidget(sep)

        self.btn_salvar = QPushButton("Salvar Parametros")
        self.btn_salvar.setProperty("class", "primary")
        self.btn_salvar.clicked.connect(self._salvar)
        outer_layout.addWidget(self.btn_salvar)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        outer_layout.addWidget(self.lbl_status)

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
                widget.setCurrentIndex(int(val))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(val)

    def _salvar(self):
        try:
            for chave, widget in self._widgets.items():
                if isinstance(widget, QCheckBox):
                    valor = 1.0 if widget.isChecked() else 0.0
                elif isinstance(widget, QComboBox):
                    valor = float(widget.currentIndex())
                elif isinstance(widget, QLineEdit):
                    valor = widget.text().strip()
                else:
                    valor = widget.value()
                    
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
            self.lbl_status.setText("Parametros salvos com sucesso.")
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold; padding: 4px;".format(Palette.GREEN)
            )
        except Exception as e:
            self.lbl_status.setText("Erro: {}".format(str(e)))
            self.lbl_status.setStyleSheet(
                "color: {}; font-weight: bold; padding: 4px;".format(Palette.RED)
            )
