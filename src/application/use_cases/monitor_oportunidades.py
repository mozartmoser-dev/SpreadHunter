import logging
import time

import numpy as np
from datetime import date

from src.application.dtos.dtos import OportunidadeMonitor
from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calculadora_box_sbth import CalculadoraBoxSbth, DadosMercado
from src.domain.services.pipeline_tracker import PipelineTracker
from src.domain.services.calculadora_vetorizada import CalculadoraVetorizada
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    TaxaAluguelRepository,
)
from src.infrastructure.notifications.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class MonitorOportunidadesUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self.telegram_service = TelegramService(db_path)
        self._calculadora = None
        self._calc_vetorizada = None
        self._lotes_cache = {}
        self._historico_enviado = {}  # Guarda as taxas das oportunidades enviadas

    def _get_param(self, chave: str, default: float) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def _get_calculadoras(self):
        if self._calculadora is None:
            taxa_cdi = self._get_param("taxa_cdi", 0.1450)
            premio_box = self._get_param("premio_risco_box", 1.5)
            premio_sbth = self._get_param("premio_risco_sbth", 1.2)
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            ir = self._get_param("taxa_ir_pct", 0.15)
            self._calculadora = CalculadoraBoxSbth(taxa_cdi, premio_box, premio_sbth, emol, liq, ir)
            self._calc_vetorizada = CalculadoraVetorizada(taxa_cdi, premio_box, premio_sbth, emol, liq, ir)
        return self._calculadora, self._calc_vetorizada

    def recarregar_parametros(self):
        self._calculadora = None
        self._calc_vetorizada = None
        self._lotes_cache = {}
        # Invalida o cache do repositório para garantir leitura do banco
        self.param_repo.invalidate_cache()

    def _lote_liquidez_put(self, operacao: str) -> float:
        if "lote_put_box" not in self._lotes_cache:
            self._lotes_cache["lote_put_box"] = self._get_param("box_qtd_put", 1000)
            self._lotes_cache["lote_put_sbth"] = self._get_param("sbth_qtd_put", 1000)
            
        if operacao in ("BOX", "BOXSBTH"):
            return self._lotes_cache["lote_put_box"]
        return self._lotes_cache["lote_put_sbth"]

    def _lote_liquidez_call(self, operacao: str) -> float:
        if "lote_call_box" not in self._lotes_cache:
            self._lotes_cache["lote_call_box"] = self._get_param("box_qtd_call", 1000)
            
        if operacao in ("BOX", "BOXSBTH"):
            return self._lotes_cache["lote_call_box"]
        return 0.0

    def varrer(self, dados_mercado: dict[str, dict], pipeline_tracker: PipelineTracker | None = None) -> list[OportunidadeMonitor]:
        calc_oo, calc_vec = self._get_calculadoras()
        inst_map = self.inst_repo.get_all_mapped()
        taxa_repo = TaxaAluguelRepository(self.db_path)
        taxa_map = taxa_repo.get_latest_all()
        resultados = []
        hoje = date.today()

        if not dados_mercado:
            if pipeline_tracker is not None:
                pipeline_tracker.nome_estrategia = "BOX/SBTH"
                pipeline_tracker.add_stage("1. Dados de mercado", 0, 0, "Nenhum dado do RTD disponível")
                self._ultimo_pipeline = pipeline_tracker
            return []

        # 1. Preparação dos dados para vetorização
        _t_pre = time.perf_counter()
        chaves = list(dados_mercado.keys())
        chaves_parsed = [tuple(k.split("|", 1)) for k in chaves]
        n = len(chaves)
        
        # Filtra instrumentos válidos, não vencidos e com dias mínimos
        dias_minimos = self._get_param("perf_dias_minimos", 10)
        indices_validos = []
        filtro_sem_inst = 0
        filtro_dte = 0
        for i, k in enumerate(chaves):
            inst = inst_map.get(chaves_parsed[i])
            if not inst or (inst.vencimento and inst.vencimento <= hoje):
                filtro_sem_inst += 1
                continue
            if inst.dias_ate_vencimento is not None and inst.dias_ate_vencimento < dias_minimos:
                filtro_dte += 1
                continue
            indices_validos.append(i)
        
        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "BOX/SBTH"
            n0 = n
            n1 = n0 - filtro_sem_inst
            n2 = n1 - filtro_dte
            pipeline_tracker.add_stage("1. Dados de mercado", n0, n0, f"{n0} instrumentos na base",
                tempo_s=time.perf_counter() - _t_pre)
            pipeline_tracker.add_stage("2. Instrumento válido", n0, n1, "Instrumento não encontrado ou já vencido",
                tempo_s=0.0)
            pipeline_tracker.add_stage("3. DTE mínimo", n1, n2, f"DTE < {dias_minimos}d (Parâmetros > PERFORMANCE)",
                tempo_s=0.0)
            # os próximos estágios serão preenchidos após a vetorização

        if not indices_validos:
            if pipeline_tracker is not None:
                self._ultimo_pipeline = pipeline_tracker
            return []
            
        _t_calc = time.perf_counter()

        # Extrai arrays apenas para os válidos
        idx = np.array(indices_validos)
        keys_validas = [chaves[i] for i in indices_validos]
        
        def get_arr(key_field, default=0.0):
            return np.array([dados_mercado[chaves[i]].get(key_field, default) for i in indices_validos], dtype=float)

        p_ativo = get_arr("preco_ativo")
        of_v_ativo = get_arr("of_venda_ativo")
        of_v_put = get_arr("of_venda_put")
        of_c_call = get_arr("of_compra_call")
        def _get_clean_strike(key):
            d = dados_mercado[key]
            # Prioridade Única: RTD (Verdade Absoluta do Profit)
            s_rtd = d.get("strike_rtd")
            return s_rtd if (s_rtd and s_rtd > 0) else 0.0

        strikes = np.array([_get_clean_strike(k) for k in keys_validas])
        dias = np.array([inst_map[chaves_parsed[i]].dias_ate_vencimento for i in indices_validos])
        vov_p = get_arr("vov_put_boca")
        voc_c = get_arr("voc_call_boca")
        em_leilao = np.array([dados_mercado[chaves[i]].get("em_leilao", False) for i in indices_validos])

        # Lotes de liquidez (usamos o padrão do BOX para o filtro grosso da vetorização)
        lote_put = self._lote_liquidez_put("BOX")
        lote_call = self._lote_liquidez_call("BOX")

        vencimentos = np.array([inst_map[chaves_parsed[i]].vencimento for i in indices_validos], dtype="datetime64[D]")

        # 2. Cálculo Vetorizado (Super Rápido)
        res_vec = calc_vec.calcular(
            p_ativo, of_v_ativo, of_v_put, of_c_call, strikes, dias,
            vov_p, voc_c, lote_put, lote_call, em_leilao, vencimentos
        )

        # 3. Criação de DTOs apenas para o que for minimamente interessante
        # (Viáveis ou com prêmio razoável)
        n_calc = 0
        c_pca_zero = 0
        for i in range(len(keys_validas)):
            # Se não for viavel e tiver prêmio baixo, ignora para economizar objetos
            # Sempre inclui a oportunidade calculada
            key = keys_validas[i]
            ativo_k, cod_put_k = key.split("|", 1)
            inst = inst_map[(ativo_k, cod_put_k)]
            mercado = dados_mercado[key]

            pca = mercado.get("of_venda_ativo", 0.0) or 0.0
            if pca <= 0:
                pca = mercado.get("preco_ativo", 0.0) or 0.0
            if pca <= 0:
                c_pca_zero += 1
                continue

            n_calc += 1
            
            opp = self._calcular_oportunidade(inst, mercado, calc_oo, taxa_map)
            if opp:
                resultados.append(opp)

        if pipeline_tracker is not None:
            n_opps = len(resultados)
            n_viaveis = sum(1 for r in resultados if r.viavel)
            c_tp_op = sum(1 for r in resultados if r.classificacao == "TP.Op")
            c_leilao = sum(1 for r in resultados if r.em_leilao and r.classificacao != "TP.Op")
            c_sem_liq = sum(1 for r in resultados if not r.viavel and not r.em_leilao and r.classificacao != "TP.Op")
            tempo_calc = time.perf_counter() - _t_calc
            pipeline_tracker.add_stage("4. Preço compra ativo", n2, n2 - c_pca_zero,
                "Ask do ativo zerado — sem oferta de venda disponível",
                tempo_s=tempo_calc)
            pipeline_tracker.add_stage("5. Cálculo vetorizado", n2 - c_pca_zero, n_calc,
                "Strike/Preço zerados ou fora da faixa de cálculo",
                tempo_s=0.0)
            pipeline_tracker.add_stage("6. Oportunidades calculadas", n_calc, n_opps,
                "_calcular_oportunidade retornou None (dados incompletos)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("7. Classificação (prêmio-risco)", n_opps, n_opps - c_tp_op,
                f"{c_tp_op} não atingem prêmio-risco BOX nem SBTH (Parâmetros > BOX)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("8. Em leilão", n_opps - c_tp_op, n_opps - c_tp_op - c_leilao,
                f"{c_leilao} em leilão (Parâmetros > BOX > lote_liquidez_box)",
                tempo_s=0.0)
            pipeline_tracker.add_stage("9. Liquidez (lote)", n_opps - c_tp_op - c_leilao, n_viaveis,
                f"{c_sem_liq} com volume abaixo do lote mínimo",
                tempo_s=0.0)
            pipeline_tracker.add_stage("10. Resultados", n_viaveis, n_viaveis,
                f"{n_viaveis} viáveis, {n_opps - n_viaveis} não viáveis",
                tempo_s=0.0)
            logger.info("PipelineTracker BOX/SBTH: %d -> %d (viaveis=%d)", n, n_opps, n_viaveis)
            self._ultimo_pipeline = pipeline_tracker

        resultados.sort(key=lambda o: (not o.viavel, -max(o.pct_cdi_box, o.pct_cdi_sbth)))
        # Envio opcional de notificação por Telegram quando há oportunidades viáveis
        if hasattr(self, "telegram_service") and self.telegram_service.is_enabled():
            import time as _time_local
            viaveis = [o for o in resultados if o.viavel]
            novas_ou_melhores = []
            now = _time_local.time()

            for o in viaveis:
                key_hist = f"{o.ativo}_{o.strike:.2f}"
                last = self._historico_enviado.get(key_hist)
                
                melhorou = False
                if not last:
                    melhorou = True
                else:
                    # Só envia novamente se o rendimento CDI ou %ganho atual superou o último enviado
                    if o.classificacao == "1BOX":
                        if o.pct_cdi_box > last["pct_cdi_box"] or o.pct_ganho_box > last["pct_ganho_box"]:
                            melhorou = True
                    elif o.classificacao == "2SBTH":
                        if o.pct_cdi_sbth > last["pct_cdi_sbth"] or o.pct_ganho_sbth > last["pct_ganho_sbth"]:
                            melhorou = True
                    elif o.classificacao == "3BOXSBTH":
                        if (o.pct_cdi_box > last["pct_cdi_box"] or o.pct_cdi_sbth > last["pct_cdi_sbth"] or
                            o.pct_ganho_box > last["pct_ganho_box"] or o.pct_ganho_sbth > last["pct_ganho_sbth"]):
                            melhorou = True
                    else:
                        max_cdi_atual = max(o.pct_cdi_box, o.pct_cdi_sbth)
                        max_cdi_antigo = max(last["pct_cdi_box"], last["pct_cdi_sbth"])
                        max_ganho_atual = max(o.pct_ganho_box, o.pct_ganho_sbth)
                        max_ganho_antigo = max(last["pct_ganho_box"], last["pct_ganho_sbth"])
                        if max_cdi_atual > max_cdi_antigo or max_ganho_atual > max_ganho_antigo:
                            melhorou = True

                # Atualiza as taxas e o timestamp no histórico
                self._historico_enviado[key_hist] = {
                    "pct_cdi_box": o.pct_cdi_box,
                    "pct_cdi_sbth": o.pct_cdi_sbth,
                    "pct_ganho_box": o.pct_ganho_box,
                    "pct_ganho_sbth": o.pct_ganho_sbth,
                    "timestamp": now
                }

                if melhorou:
                    novas_ou_melhores.append(o)

            cleanup_timeout = int(self._get_param("telegram_cleanup_timeout", 300))
            chaves_para_remover = [
                k for k, v in self._historico_enviado.items()
                if now - v["timestamp"] > cleanup_timeout
            ]
            for k in chaves_para_remover:
                self._historico_enviado.pop(k, None)

            # Dispara o Telegram apenas para as novas/melhoradas, uma por vez
            if novas_ou_melhores:
                for o in novas_ou_melhores:
                    text = self._montar_mensagem_telegram(o)
                    self.telegram_service.send(text)
        return resultados

    def _montar_mensagem_telegram(self, o) -> str:
        from datetime import datetime
        emoji = "🚀"
        classif_label = o.classificacao if o.classificacao else "TP.Op"
        operacao_label = o.operacao if o.operacao else classif_label

        if o.vencimento:
            venc_str = o.vencimento.strftime("%d/%m/%Y")
            dias_str = f" ({o.dias} dias)" if o.dias else ""
            vencimento_display = f"{venc_str}{dias_str}"
        else:
            vencimento_display = "N/A"

        msg = f"{emoji} <b>OPORTUNIDADE DETECTADA</b>\n\n"
        msg += f"Ativo: {o.ativo}\n"
        msg += f"Operação: {operacao_label}\n"
        msg += f"Strike: R$ {o.strike:.2f}\n"
        msg += f"Vencimento: {vencimento_display}\n"
        msg += f"Classificação: {classif_label}\n\n"

        msg += "--- Pernas da Estrutura ---\n"
        msg += f"• Compra Ativo ({o.ativo}): R$ {o.preco_compra_ativo:.2f}\n"
        msg += f"• Compra Put ({o.cod_put}): R$ {o.of_venda_put:.2f}\n"
        if o.of_compra_call and o.of_compra_call > 0:
            msg += f"• Venda Call ({o.cod_call}): R$ {o.of_compra_call:.2f}\n"
        msg += "\n"

        msg += "--- Custos e Rentabilidade ---\n"
        if o.custo_sbth and o.custo_sbth > 0:
            msg += f"• Custo SBTH: R$ {o.custo_sbth:.2f}\n"
            msg += f"• Ganho % SBTH: {o.pct_ganho_sbth * 100:.2f}%\n"
            msg += f"• vs CDI SBTH: {o.pct_cdi_sbth:.2f}x CDI\n"
        else:
            msg += "• SBTH: (N/A)\n"
        msg += "\n"
        if o.custo_box and o.custo_box > 0:
            msg += f"• Custo BOX: R$ {o.custo_box:.2f}\n"
            msg += f"• Ganho % BOX: {o.pct_ganho_box * 100:.2f}%\n"
            msg += f"• vs CDI BOX: {o.pct_cdi_box:.2f}x CDI\n"
        else:
            msg += "• BOX: (N/A)\n"
        msg += "\n"

        status = "VIÁVEL ✅" if o.viavel else "NÃO VIÁVEL ❌"
        msg += f"Status: {status}"

        return msg

    def _calcular_oportunidade(self, inst, mercado, calc, taxa_map=None):
        if mercado is None:
            return None
        p_ref = mercado["preco_ativo"]

        strike = mercado.get("strike_rtd")
        if not strike or strike <= 0:
            logger.warning("Strike RTD invalido para %s — ignorando", inst.cod_put)
            return None

        dados = DadosMercado(
            preco_ativo=mercado["preco_ativo"],
            of_compra_ativo=mercado.get("of_compra_ativo", 0.0),
            of_venda_ativo=mercado.get("of_venda_ativo", 0.0),
            of_compra_put=mercado.get("of_compra_put", 0.0),
            of_venda_put=mercado.get("of_venda_put", 0.0),
            of_compra_call=mercado.get("of_compra_call", 0.0),
            of_venda_call=mercado.get("of_venda_call", 0.0),
            strike=strike,
            premio_put=mercado.get("premio_put", 0.0),
            premio_call=mercado.get("premio_call", 0.0),
            dias=inst.dias_ate_vencimento,
            em_leilao=mercado.get("em_leilao", False),
            status_put=mercado.get("status_put", ""),
            status_call=mercado.get("status_call", ""),
            status_ativo=mercado.get("status_ativo", ""),
            vov_put_boca=mercado.get("vov_put_boca", 0.0),
            voc_call_boca=mercado.get("voc_call_boca", 0.0),
            qul_put=mercado.get("qul_put", 0.0),
            qul_call=mercado.get("qul_call", 0.0),
        )
        resultado = calc.calcular(dados)

        lote_put = self._lote_liquidez_put(resultado.operacao)
        lote_call = self._lote_liquidez_call(resultado.operacao)
        liq_put_x_lote = dados.vov_put_boca - lote_put
        liq_call_x_lote = dados.voc_call_boca - lote_call

        tem_liquidez = liq_put_x_lote >= 0 and liq_call_x_lote >= 0
        viavel = (
            resultado.operacao in ("BOX", "SBTH", "BOXSBTH")
            and not dados.em_leilao
            and tem_liquidez
        )

        return OportunidadeMonitor(
            instrumento_id=inst.id or 0,
            ativo=inst.ativo,
            strike=strike,
            vencimento=inst.vencimento,
            dias=dados.dias,
            cod_put=inst.cod_put,
            cod_call=inst.cod_call,
            tipo_opcao=inst.tipo_opcao.value,
            classificacao=resultado.classificacao,
            operacao=resultado.operacao,
            custo_sbth=resultado.custo_sbth,
            pct_ganho_sbth=resultado.pct_ganho_sbth,
            pct_cdi_sbth=resultado.pct_cdi_sbth,
            pct_cdi_sbth_liquido=resultado.pct_cdi_sbth_liquido,
            custo_box=resultado.custo_box,
            pct_ganho_box=resultado.pct_ganho_box,
            pct_cdi_box=resultado.pct_cdi_box,
            pct_cdi_box_liquido=resultado.pct_cdi_box_liquido,
            cdi_periodo=resultado.cdi_periodo,
            viavel=viavel,
            preco_compra_ativo=dados.preco_compra_ativo,
            of_venda_put=dados.of_venda_put,
            of_compra_call=dados.of_compra_call,
            em_leilao=dados.em_leilao,
            liq_put_x_lote=liq_put_x_lote,
            liq_call_x_lote=liq_call_x_lote,
            of_compra_put=dados.of_compra_put,
            of_venda_call=dados.of_venda_call,
            qul_put=dados.qul_put,
            qul_call=dados.qul_call,
            money_put=max(dados.strike - dados.preco_ativo, 0.0),
            money_call=max(dados.preco_ativo - dados.strike, 0.0),
            taxa_aluguel=taxa_map.get(inst.ativo).taxa_atual if taxa_map and taxa_map.get(inst.ativo) else 0.0,
        )
