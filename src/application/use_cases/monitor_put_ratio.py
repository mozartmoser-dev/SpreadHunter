import logging
import math
import time
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.domain.entities.instrumento_opcional import InstrumentoOpcional
from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.calculadora_put_ratio import (
    CalculadoraPutRatio, ResultadoPutRatio, RATIOS_DEFAULT,
)
from src.domain.services.market_data_source import FieldName
from src.domain.services.pipeline_tracker import PipelineTracker
from src.infrastructure.integrations.opcoesnet_client import OpcoesNetClient
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository, ParametroRepository,
)
from src.infrastructure.providers import stale_trace

logger = logging.getLogger(__name__)

FILTROS_PUT_RATIO = [
    "1. Vencimento",
    "2. Ativo (whitelist)",
    "3. Dados RTD (strike/book)",
    "4. DTE + IV Rank/Percentile",
    "5. K1 OTM (% do spot)",
    "6. Spread K1-K2 minimo",
    "7. Credito minimo (R$/acao)",
    "8. Profundidade minima (book)",
    "9. Pareamento (K1>K2, credit>0)",
]


def _is_weekly(cod: str | None) -> bool:
    return bool(cod) and len(cod) >= 2 and cod[-2].upper() == "W"

class MonitorPutRatioUseCase:
    _cache_iv_historico: dict[str, tuple[float, float, float, list[float]]] = {}

    def _ler_campo_cache(self, rtd, codigo: str, campo: FieldName):
        if getattr(rtd, 'suporta_push', False) and getattr(rtd, 'disponivel', True):
            return rtd.ler_campo_cache(codigo, campo, allow_stale=True)
        return rtd.ler_campo_cache(codigo, campo)

    def _forcar_leitura(self, rtd, codigo: str, campo: FieldName):
        push = getattr(rtd, 'suporta_push', False) and getattr(rtd, 'disponivel', True)
        try:
            return rtd.forcar_leitura(codigo, campo, allow_stale=push, timeout_ms=200)
        except TypeError:
            try:
                return rtd.forcar_leitura(codigo, campo, allow_stale=push)
            except TypeError:
                return rtd.forcar_leitura(codigo, campo)

    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self._calculadora = None

    def _carregar_iv_historico(self, ativo: str) -> tuple[float, float, float, list[float]] | None:
        if ativo in self._cache_iv_historico:
            self._t_stats["n_hit"] += 1
            return self._cache_iv_historico[ativo]
        t0 = time.perf_counter()
        self._t_stats["n_miss"] += 1
        self._t_stats["n_http"] += 1
        try:
            client = OpcoesNetClient()
            hist = client.get_stock_history_formatted(ativo, 252)
            if not hist:
                return None
            valores = [c["vol_impl"] for c in hist if c.get("vol_impl") and c["vol_impl"] > 0]
            if len(valores) < 60:
                return None
            stats = (min(valores), max(valores), valores[-1], valores)
            self._cache_iv_historico[ativo] = stats
            return stats
        except Exception:
            return None
        finally:
            self._t_stats["http"] += time.perf_counter() - t0

    def _get_calculadora(self) -> CalculadoraPutRatio:
        if self._calculadora is None:
            param_cdi = self.param_repo.get_by_chave("taxa_cdi")
            taxa_cdi = param_cdi.valor
            param_risco = self.param_repo.get_by_chave("put_ratio_premio_risco")
            premio = param_risco.valor if param_risco else 1.0
            emol = self._get_param("taxa_emolumento_pct", 0.00025)
            liq = self._get_param("taxa_liquidacao_pct", 0.000275)
            reg = self._get_param("taxa_registro_pct", 0.0001)
            iss = self._get_param("taxa_iss_pct", 0.0)
            alpha = self._get_param("put_ratio_peso_alpha", 0.5)
            beta = self._get_param("put_ratio_peso_beta", 0.3)
            gamma = self._get_param("put_ratio_peso_gamma", 0.2)
            self._calculadora = CalculadoraPutRatio(taxa_cdi, premio, emol, liq,
                                                     taxa_registro=reg, iss=iss,
                                                     peso_alpha=alpha, peso_beta=beta, peso_gamma=gamma)
        return self._calculadora

    def recarregar_parametros(self):
        self._calculadora = None
        self.param_repo.invalidate_cache()
        self._cache_iv_historico.clear()

    def limpar_cache_iv(self):
        """Invalida o cache de IV histórico para re-buscar do opcoes.net.br.

        Chamado ao iniciar o scanner do Put Ratio: o histórico de vol_impl só
        muda de um dia para o outro, então re-busca 1x por dia (na abertura da
        varredura) os ativos que passam pelo pipeline, em vez de cache eterno.
        """
        self._cache_iv_historico.clear()

    def _get_param(self, chave: str, default: float = 0.0) -> float:
        param = self.param_repo.get_by_chave(chave)
        return param.valor if param else default

    def _get_qtd_min_perna(self) -> int:
        param = self.param_repo.get_by_chave("put_ratio_qtd_min")
        return int(param.valor) if param else 100

    def _get_iv_rank_min(self) -> float:
        param = self.param_repo.get_by_chave("put_ratio_iv_rank_min")
        return param.valor if param else 50.0

    def _get_whitelist(self) -> set[str] | None:
        param = self.param_repo.get_by_chave("white_list_put_ratio")
        if param and param.valor:
            raw = str(param.valor)
            ativos = [a.strip().upper() for a in raw.split(",") if a.strip()]
            return set(ativos) if ativos else None
        return None

    def _get_ratios(self) -> list[tuple[int, int]]:
        param = self.param_repo.get_by_chave("put_ratio_ratios")
        if param and param.valor:
            raw = str(param.valor)
            ratios = []
            for part in raw.split(","):
                part = part.strip()
                if "x" in part:
                    try:
                        n1, n2 = part.split("x")
                        ratios.append((int(n1), int(n2)))
                    except ValueError:
                        pass
            return ratios if ratios else RATIOS_DEFAULT
        return RATIOS_DEFAULT

    def _extrair(self, inst: InstrumentoOpcional, rtd, r_cont: float = 0.0) -> dict | None:
        # Fontes push (OpenFAST): strike canônico é do banco (opcoes.net.br).
        # "PEX" do servidor pode não ser o strike real para opções.
        strike = inst.strike if getattr(rtd, 'suporta_push', False) else None
        if not strike or strike <= 0:
            strike = self._ler_campo_cache(rtd, inst.cod_put, FieldName.STRIKE)
        if not strike or strike <= 0:
            return None

        bid_put = self._ler_campo_cache(rtd, inst.cod_put, FieldName.BID) or 0.0
        ask_put = self._ler_campo_cache(rtd, inst.cod_put, FieldName.ASK) or 0.0

        if bid_put <= 0 and ask_put <= 0:
            return None

        preco_ativo = self._ler_campo_cache(rtd, inst.ativo, FieldName.ASK) or 0.0

        status_put = rtd.ler_status_cache(inst.cod_put)
        status_ativo = rtd.ler_status_cache(inst.ativo)

        stale_trace.log_consumo("PUT_RATIO", {inst.cod_put.upper(), inst.ativo.upper()}, rtd)

        # TODO IV Rank/Percentile: bootstrap com get_stock_history_formatted()
        # (opcoesnet_client) → 252d de vol_impl → rank rolante diario
        iv_put = 0.0
        if preco_ativo > 0 and strike > 0 and inst.dias_ate_vencimento > 0:
            mid = ask_put if ask_put > 0 else bid_put
            if mid > 0 and r_cont > 0:
                T = inst.dias_ate_vencimento / 365.0
                _t_iv = time.perf_counter()
                iv_put = CalculadoraPutRatio.estimar_iv(mid, preco_ativo, strike, T, r_cont) * 100.0
                self._t_stats["iv"] += time.perf_counter() - _t_iv
                self._t_stats["n_iv"] += 1

        return {
            "strike": strike,
            "cod_put": inst.cod_put,
            "bid_put": bid_put,
            "ask_put": ask_put,
            "qtd_bid_put": int(self._ler_campo_cache(rtd, inst.cod_put, FieldName.VOL_BID) or 0),
            "qtd_ask_put": int(self._ler_campo_cache(rtd, inst.cod_put, FieldName.VOL_ASK) or 0),
            "em_leilao": not (status_put.lower() == "aberto" and status_ativo.lower() == "aberto"),
            "ativo": inst.ativo,
            "vencimento": inst.vencimento,
            "dias": inst.dias_ate_vencimento,
            "preco_ativo": preco_ativo,
            "iv_put": iv_put,
            "ts_ativo_ask": self._ts_campo(rtd, inst.ativo),
            "ts_ativo_bid": self._ts_campo_bid(rtd, inst.ativo),
            "ts_origem_ativo": self._ts_origem(rtd, inst.ativo),
            "ts_time_ativo": self._ts_time(rtd, inst.ativo),
            "ts_timeng_ativo": self._ts_timeng(rtd, inst.ativo),
        }

    def _ts_campo(self, rtd, codigo):
        getter = getattr(rtd, "get_ts_campo", None)
        if not getter:
            return None
        try:
            return getter(codigo, FieldName.ASK)
        except Exception:
            return None

    def _ts_campo_bid(self, rtd, codigo):
        getter = getattr(rtd, "get_ts_campo", None)
        if not getter:
            return None
        try:
            return getter(codigo, FieldName.BID)
        except Exception:
            return None

    def _ts_origem(self, rtd, codigo):
        getter = getattr(rtd, "get_ts_origem", None)
        if not getter:
            return None
        try:
            return getter(codigo)
        except Exception:
            return None

    def _ts_time(self, rtd, codigo):
        getter = getattr(rtd, "get_ts_time", None)
        if not getter:
            return None
        try:
            return getter(codigo)
        except Exception:
            return None

    def _ts_timeng(self, rtd, codigo):
        getter = getattr(rtd, "get_ts_timeng", None)
        if not getter:
            return None
        try:
            return getter(codigo)
        except Exception:
            return None

    def _passa_filtros(self, dados: dict) -> bool:
        if dados["dias"] <= 0:
            return False
        dte_min = self._get_param("put_ratio_dte_min", 20)
        dte_max = self._get_param("put_ratio_dte_max", 60)
        if dados["dias"] < dte_min or dados["dias"] > dte_max:
            return False
        iv_rank_min = self._get_iv_rank_min()
        if iv_rank_min > 0:
            iv_rank = dados.get("iv_rank", 0.0)
            if iv_rank < iv_rank_min:
                return False
        iv_pct_min = self._get_param("put_ratio_iv_percentile_min", 0.0)
        if iv_pct_min > 0:
            iv_pct = dados.get("iv_percentile", 0.0)
            if iv_pct < iv_pct_min:
                return False
        preco_ativo = dados.get("preco_ativo", 0.0)
        strike = dados.get("strike", 0.0)
        if preco_ativo > 0 and strike > 0:
            otm_max_pct = self._get_param("put_ratio_k1_otm_max_pct", 0.15)
            otm_min_pct = self._get_param("put_ratio_k1_otm_min_pct", 0.03)
            otm_pct = (preco_ativo - strike) / preco_ativo
            if otm_pct > otm_max_pct or otm_pct < otm_min_pct:
                return False
        return True

    def varrer(self, rtd, pipeline_tracker: PipelineTracker | None = None) -> list[ResultadoPutRatio]:
        self._t_stats = {"extrair": 0.0, "iv": 0.0, "http": 0.0,
                         "n_extrair": 0, "n_iv": 0, "n_http": 0, "n_hit": 0, "n_miss": 0}
        _t_varrer = time.perf_counter()
        calc = self._get_calculadora()
        r_cont = math.log(1 + calc.taxa_cdi)
        inst_map = self.inst_repo.get_all_mapped()
        qtd_min = self._get_qtd_min_perna()
        iv_min = self._get_iv_rank_min()
        ratios = self._get_ratios()
        whitelist = self._get_whitelist()
        spread_min_pct = self._get_param("put_ratio_spread_min_pct", 0.02)
        min_credit = self._get_param("put_ratio_min_credit", 0.10)

        hoje = date.today()
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)

        filtro_semanal = bool(self._get_param("perf_filtro_semanal", 0))

        filtro = {"total": 0, "venc": 0, "white": 0, "semanal": 0, "rtd": 0, "filtros": 0}
        n_passou = 0
        _t0 = time.perf_counter()

        for _key, inst in inst_map.items():
            filtro["total"] += 1
            if not inst.vencimento or inst.vencimento <= hoje:
                filtro["venc"] += 1
                continue
            if whitelist is not None and inst.ativo.upper() not in whitelist:
                filtro["white"] += 1
                continue

            if filtro_semanal and _is_weekly(inst.cod_put):
                filtro["semanal"] += 1
                continue

            _t_ex = time.perf_counter()
            dados = self._extrair(inst, rtd, r_cont)
            self._t_stats["extrair"] += time.perf_counter() - _t_ex
            self._t_stats["n_extrair"] += 1
            if not dados:
                filtro["rtd"] += 1
                continue

            iv_put_pct = dados.get("iv_put", 0.0)
            if iv_put_pct > 0:
                iv_hist = self._carregar_iv_historico(inst.ativo)
                if iv_hist:
                    iv_put_dec = iv_put_pct / 100.0
                    iv_min_h, iv_max_h, _, valores_h = iv_hist
                    if iv_max_h > iv_min_h:
                        dados["iv_rank"] = round(min((iv_put_dec - iv_min_h) / (iv_max_h - iv_min_h) * 100, 100.0), 1)
                        cnt_below = sum(1 for v in valores_h if v < iv_put_dec)
                        dados["iv_percentile"] = round(min(cnt_below / len(valores_h) * 100, 100.0), 1)

            if not self._passa_filtros(dados):
                filtro["filtros"] += 1
                continue

            grupo_key = (inst.ativo, inst.vencimento)
            grupos[grupo_key].append(dados)
            n_passou += 1

        n4 = 0
        if pipeline_tracker is not None:
            pipeline_tracker.nome_estrategia = "PUT_RATIO"
            n0 = filtro["total"]
            n1 = n0 - filtro["venc"]
            n2 = n1 - filtro["white"]
            n3 = n2 - filtro["rtd"] - filtro["semanal"]
            n4 = n3 - filtro["filtros"]
            pipeline_tracker.add_stage("1. Vencimento", n0, n1, "Fora do prazo")
            pipeline_tracker.add_stage("2. Ativo (whitelist)", n1, n2, "Fora da whitelist")
            pipeline_tracker.add_stage("3. Dados RTD", n2, n3, "Sem strike/book" + (" | exclui semanais (W em cod[-2])" if filtro_semanal else ""))
            dte_min_v = self._get_param('put_ratio_dte_min', 20)
            dte_max_v = self._get_param('put_ratio_dte_max', 60)
            iv_rank_v = self._get_iv_rank_min()
            otm_max_v = self._get_param('put_ratio_k1_otm_max_pct', 0.15)
            otm_min_v = self._get_param('put_ratio_k1_otm_min_pct', 0.03)
            pipeline_tracker.add_stage("4. Filtros DTE/IV/K1", n3, n4,
                                       f"DTE [{dte_min_v}, {dte_max_v}] | IV Rank >= {iv_rank_v}% | IV Pct >= {self._get_param('put_ratio_iv_percentile_min', 0.0):.0f}% | K1 OTM [{otm_min_v*100:.0f}%, {otm_max_v*100:.0f}%]")
            logger.info("PipelineTracker PUT_RATIO: %d -> %d", n0, n_passou)
            self._ultimo_pipeline = pipeline_tracker

        resultados = []

        for (ativo, vencimento), members in grupos.items():
            if len(members) < 2:
                continue

            members.sort(key=lambda m: m["strike"], reverse=True)
            ativo_results = []

            du = dc_to_du(hoje, vencimento) if vencimento else None

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    k1_data = members[i]
                    k2_data = members[j]

                    preco_ref = k1_data.get("preco_ativo", 0.0)
                    if preco_ref > 0:
                        spread = k1_data["strike"] - k2_data["strike"]
                        if spread / preco_ref < spread_min_pct:
                            continue

                    for n1, n2 in ratios:
                        iv_k1_dec = (k1_data.get("iv_put", 0.0) / 100.0) or None
                        iv_k2_dec = (k2_data.get("iv_put", 0.0) / 100.0) or None
                        resultado = calc.calcular(
                            strike_k1=k1_data["strike"],
                            strike_k2=k2_data["strike"],
                            n1=n1,
                            n2=n2,
                            ask_put_k1=k1_data["ask_put"],
                            bid_put_k2=k2_data["bid_put"],
                            qtd_ask_put_k1=k1_data["qtd_ask_put"],
                            qtd_bid_put_k2=k2_data["qtd_bid_put"],
                            cod_put_k1=k1_data["cod_put"],
                            cod_put_k2=k2_data["cod_put"],
                            ativo=ativo,
                            vencimento=vencimento,
                            dias=k1_data["dias"],
                            em_leilao=k1_data["em_leilao"] or k2_data["em_leilao"],
                            preco_ativo=k1_data.get("preco_ativo", 0.0),
                            qtd_min_perna=qtd_min,
                            du=du,
                            iv_k1=iv_k1_dec,
                            iv_k2=iv_k2_dec,
                        )
                        if resultado:
                            if resultado.credito_bruto < min_credit:
                                continue
                            resultado.iv_rank = k1_data.get("iv_rank", 0.0)
                            resultado.iv_percentile = k1_data.get("iv_percentile", 0.0)
                            resultado.detectado_em = agora
                            resultado.ts_ativo_ask = k1_data.get("ts_ativo_ask")
                            resultado.ts_ativo_bid = k1_data.get("ts_ativo_bid")
                            resultado.ts_origem_ativo = k1_data.get("ts_origem_ativo")
                            resultado.ts_time_ativo = k1_data.get("ts_time_ativo")
                            resultado.ts_timeng_ativo = k1_data.get("ts_timeng_ativo")
                            ativo_results.append(resultado)

            ativo_results.sort(key=lambda r: -r.score)
            resultados.extend(ativo_results)

        if pipeline_tracker is not None:
            pipeline_tracker.add_stage("5. Pareamento", n4, len(resultados),
                                       f"Spread >= {spread_min_pct*100:.0f}% | Cred >= R$ {min_credit:.2f} | Ratios: {','.join(f'{a}x{b}' for a,b in ratios)}")

        resultados.sort(key=lambda r: -r.score)
        ts = self._t_stats
        logger.info("PUT_RATIO_TIMING: total=%.3fs extrair=%.3fs iv=%.3fs http=%.3fs | n_extrair=%d n_iv=%d n_http=%d n_hit=%d n_miss=%d | n_passou=%d n_resultados=%d",
                     time.perf_counter() - _t_varrer, ts["extrair"], ts["iv"], ts["http"],
                     ts["n_extrair"], ts["n_iv"], ts["n_http"], ts["n_hit"], ts["n_miss"],
                     n_passou, len(resultados))
        return resultados

    def confirmar_resultados(self, rtd, resultados):
        if not hasattr(rtd, 'forcar_leitura'):
            return resultados
        calc = self._get_calculadora()
        qtd_min = self._get_qtd_min_perna()
        hoje = date.today()
        min_credit = self._get_param("put_ratio_min_credit", 0.10)
        confirmados = []
        for r in resultados:
            if not r.viavel:
                confirmados.append(r)
                continue
            ask_p1 = self._forcar_leitura(rtd, r.cod_put_k1, FieldName.ASK)
            bid_p2 = self._forcar_leitura(rtd, r.cod_put_k2, FieldName.BID)
            if any(v is None or v <= 0 for v in (ask_p1, bid_p2)):
                continue
            du = dc_to_du(hoje, r.vencimento) if r.vencimento else None
            novo = calc.calcular(
                strike_k1=r.strike_k1, strike_k2=r.strike_k2,
                n1=r.n1, n2=r.n2,
                ask_put_k1=ask_p1, bid_put_k2=bid_p2,
                qtd_ask_put_k1=r.qtd_ask_put_k1, qtd_bid_put_k2=r.qtd_bid_put_k2,
                cod_put_k1=r.cod_put_k1, cod_put_k2=r.cod_put_k2,
                ativo=r.ativo, vencimento=r.vencimento, dias=r.dias,
                em_leilao=r.em_leilao, preco_ativo=r.spot,
                qtd_min_perna=qtd_min, du=du,
                iv_k1=(r.iv_put_pct / 100.0) if r.iv_put_pct > 0 else None,
                iv_k2=None,
            )
            if novo and novo.credito_bruto >= min_credit and novo.viavel:
                novo.iv_rank = r.iv_rank
                novo.iv_percentile = r.iv_percentile
                novo.detectado_em = r.detectado_em
                confirmados.append(novo)
        return confirmados
