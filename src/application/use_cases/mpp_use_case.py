import logging
import math
from collections import defaultdict, deque
from datetime import date, datetime
from dataclasses import dataclass, field

from src.domain.entities.instrumento_opcional import TipoOpcao
from src.domain.services.calendario_b3 import dc_to_du
from src.domain.services.market_data_source import FieldName
from src.infrastructure.persistence.database import get_connection
from src.infrastructure.persistence.repositories.repositories import ParametroRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PernaImediata:
    codigo: str
    bid: float
    ask: float
    bid_qtd: int
    ask_qtd: int
    strike: float
    tipo: str


@dataclass(slots=True)
class BoxScore:
    ativo: str
    strike1: float
    strike2: float
    vencimento: date
    cod_call_k1: str = ""
    cod_put_k1: str = ""
    cod_call_k2: str = ""
    cod_put_k2: str = ""
    score_estrutural_box: float = 0.0
    score_instantaneo_box: float = 0.0
    score_final: float = 0.0
    score_final_pct: float = 0.0
    erro_paridade_box: float = 0.0
    spread_medio: float = 0.0
    profundidade_min: float = 0.0
    qtd_min_box: int = 0
    persistencia_ciclos: int = 0
    nivel_risco: str = "baixo"
    justificativa: str = ""


@dataclass(slots=True)
class MreResultado:
    ativo: str
    strike1: float
    strike2: float
    vencimento: date
    score_box: float = 0.0
    isca_recomendada: str = ""
    ip_isca: float = 0.0
    lote_sugerido: int = 0
    confianca_completar: float = 0.0
    nivel_recomendacao: str = "baixa"
    justificativa: str = ""


class MPPUseCase:
    MPP_INTERVAL = 24
    SNAPSHOT_THRESHOLD = 70
    SNAPSHOT_INTERVAL = 10
    SNAPSHOT_RETENTION_DAYS = 30

    def __init__(self, db_path=None):
        self.db_path = db_path
        self._param_repo = ParametroRepository(db_path)

        self.spread_history: dict[str, deque] = {}
        self.persistencia: dict[str, int] = {}
        self.taxa_sucesso_cache: dict[str, float] = {}
        self.score_estrutural_cache: dict[str, dict] = {}
        self._snapshot_counter: dict[str, int] = {}
        self._snapshot_buffer: list[tuple] = []
        self._estrutural_carregado = False
        self._ultimo_rtd_counter: int = 0
        self._cached_box_scores: list[BoxScore] = []
        self._cached_mre: list[MreResultado] = []
        self._params_cache: dict[str, float] = {}
        self._carregar_spread_history()

    def _get_param(self, chave: str, default: float = 0.0) -> float:
        cached = self._params_cache.get(chave)
        if cached is not None:
            return cached
        param = self._param_repo.get_by_chave(chave)
        if param:
            self._params_cache[chave] = param.valor
            return param.valor
        self._params_cache[chave] = default
        return default

    def _get_whitelist(self) -> list[str]:
        param = self._param_repo.get_by_chave("white_list_box4p")
        if param and param.valor:
            raw = str(param.valor)
            return [a.strip().upper() for a in raw.split(",") if a.strip()]
        return []

    def obter_taxa_cdi(self) -> float:
        return float(self._param_repo.get_by_chave("taxa_cdi").valor)

    def precisa_atualizar_cache(self) -> bool:
        from src.domain.services.calendario_b3 import eh_feriado
        hoje = date.today()
        if hoje.weekday() >= 5:
            return False
        if eh_feriado(hoje):
            return False
        conn = get_connection(self.db_path)
        try:
            row = conn.execute("SELECT MAX(data_ref) FROM mpp_cache_opcoesnet").fetchone()
            ultima = row[0] if row else None
        finally:
            conn.close()
        if not ultima:
            return True
        return ultima < hoje.isoformat()

    def carregar_estrutural(self, provider=None) -> bool:
        self.persistencia.clear()
        self._snapshot_counter.clear()
        self.limpar_snapshots_antigos()

        if provider is None:
            from src.infrastructure.providers.mercado_estrutural_provider import MercadoEstruturalProvider
            provider = MercadoEstruturalProvider()

        ativos = self._get_whitelist()
        if not ativos:
            logger.warning("MPP: whitelist vazia, pulando carregamento estrutural")
            return False

        dados_novos = 0
        resultados = provider.fetch_all_whitelist(ativos)

        for ativo, dados in resultados.items():
            if dados is None:
                continue
            self._salvar_cache(ativo, dados)
            dados_novos += 1

        if dados_novos == 0:
            logger.warning("MPP: nenhum dado novo obtido — usando cache do dia anterior")
            return self._carregar_cache_existente()

        self._calcular_scores_estruturais()
        self._carregar_taxas_sucesso()
        self._estrutural_carregado = True
        logger.info(f"MPP estrutural carregado: {dados_novos} ativos")
        return True

    def _salvar_cache(self, ativo: str, dados: list[dict]):
        hoje = date.today().isoformat()
        conn = get_connection(self.db_path)
        try:
            for d in dados:
                oi = (d.get("titulares") or 0) + (d.get("lancadores") or 0)
                conn.execute("""
                    INSERT OR REPLACE INTO mpp_cache_opcoesnet
                    (ativo, opcao, strike, tipo, vencimento, oi, volume_financeiro,
                     num_negocios, iv, delta, gamma, ultimo_preco, mod, data_ref)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ativo, d.get("opcao", ""), d.get("strike", 0.0),
                    d.get("tipo", ""), d.get("vencimento", ""),
                    oi, d.get("volume_financeiro", 0.0),
                    d.get("num_negocios", 0), d.get("iv", 0.0),
                    d.get("delta", 0.0), d.get("gamma", 0.0),
                    d.get("ultimo_preco", 0.0), d.get("mod", ""), hoje
                ))
            conn.commit()
        finally:
            conn.close()

    def _carregar_cache_existente(self) -> bool:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM mpp_cache_opcoesnet").fetchone()
            if row[0] == 0:
                return False
            return True
        finally:
            conn.close()

    def _calcular_scores_estruturais(self):
        hoje = date.today().isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("""
                SELECT * FROM mpp_cache_opcoesnet WHERE data_ref = ?
            """, (hoje,)).fetchall()
        finally:
            conn.close()

        if not rows:
            return

        agrupados: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            agrupados[r["ativo"]].append(dict(r))

        self.score_estrutural_cache.clear()
        conn = get_connection(self.db_path)
        try:
            for ativo, opts in agrupados.items():
                strikes_oi = {o["strike"]: o["oi"] for o in opts if o["strike"] > 0}
                strikes_iv = {o["strike"]: {
                    "iv": o["iv"], "delta": o["delta"],
                    "num_negocios": o["num_negocios"], "oi": o["oi"]
                } for o in opts if o["strike"] > 0}

                for o in opts:
                    strike = o["strike"]
                    if strike <= 0:
                        continue

                    score_oi = self._calcular_score_oi(strike, strikes_oi)
                    score_volume = self._calcular_score_volume(o["num_negocios"])
                    score_curvatura = self._calcular_curvatura_iv(
                        o["iv"], o["delta"], o["num_negocios"], o["oi"], strike, strikes_iv
                    )
                    score_estrutural = 0.15 * score_oi + 0.10 * score_volume + 0.10 * score_curvatura

                    self.score_estrutural_cache[o["opcao"]] = {
                        "score_oi": score_oi,
                        "score_volume": score_volume,
                        "score_curvatura_iv": score_curvatura,
                        "score_estrutural": score_estrutural,
                        "ativo": ativo,
                        "strike": strike,
                        "vencimento": o["vencimento"],
                    }

                    conn.execute("""
                        INSERT OR REPLACE INTO mpp_score_estrutural
                        (ativo, opcao, strike, vencimento, score_oi, score_volume,
                         score_curvatura_iv, score_estrutural, data_ref)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ativo, o["opcao"], strike, o["vencimento"],
                        round(score_oi, 4), round(score_volume, 4),
                        round(score_curvatura, 4), round(score_estrutural, 4),
                        hoje
                    ))
            conn.commit()
        finally:
            conn.close()

    def _calcular_score_oi(self, strike: float, strikes_oi: dict[float, int]) -> float:
        oi_atual = strikes_oi.get(strike, 0)
        strikes_sorted = sorted(strikes_oi.keys())
        try:
            idx = strikes_sorted.index(strike)
        except ValueError:
            return 0.0
        vizinhos_idx = [idx + d for d in (-2, -1, 1, 2) if 0 <= idx + d < len(strikes_sorted)]
        oi_viz = [strikes_oi[strikes_sorted[i]] for i in vizinhos_idx]
        if not oi_viz:
            return 0.0
        media = sum(oi_viz) / len(oi_viz)
        ratio = oi_atual / max(media, 1)
        score_concentracao = min(ratio / 5.0, 1.0)

        peso_absoluto = self._get_param("mpp_oi_peso_absoluto", 0.40)
        peso_concentracao = self._get_param("mpp_oi_peso_concentracao", 0.60)
        cap_absoluto = self._get_param("mpp_oi_cap_absoluto", 10000)
        score_tamanho = min(oi_atual / cap_absoluto, 1.0)

        return peso_concentracao * score_concentracao + peso_absoluto * score_tamanho

    def _calcular_score_volume(self, num_negocios: int) -> float:
        return 1.0 / (1.0 + num_negocios / 100.0)

    def _calcular_curvatura_iv(self, iv: float, delta: float, num_neg: int, oi: int,
                                strike: float, strikes_iv: dict) -> float:
        if abs(delta) < 0.15 or abs(delta) > 0.85:
            return 0.0
        if num_neg < 10 and oi < 500:
            return 0.0
        strikes_sorted = sorted(strikes_iv.keys())
        try:
            idx = strikes_sorted.index(strike)
        except ValueError:
            return 0.0
        iv_vizinhos = []
        for d in (-1, 1):
            ni = idx + d
            if 0 <= ni < len(strikes_sorted):
                iv_vizinhos.append(strikes_iv[strikes_sorted[ni]]["iv"])
        if not iv_vizinhos:
            return 0.0
        media_iv = sum(iv_vizinhos) / len(iv_vizinhos)
        if media_iv <= 0:
            return 0.0
        curvatura = abs(iv - media_iv)
        normalizador = self._get_param("mpp_curvatura_normalizador", 0.10)
        if normalizador <= 0:
            normalizador = 0.10
        return min(curvatura / normalizador, 1.0)

    def _carregar_taxas_sucesso(self):
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("""
                SELECT ativo,
                       CAST(SUM(box_encontrado) AS REAL) / NULLIF(COUNT(*), 0) as taxa,
                       COUNT(*) as total
                FROM mpp_historico_distorcoes
                WHERE created_at >= date('now', '-90 days')
                GROUP BY ativo
            """).fetchall()
            self.taxa_sucesso_cache.clear()
            for r in rows:
                if r["total"] >= 5:
                    self.taxa_sucesso_cache[r["ativo"]] = r["taxa"] or 0.0
                else:
                    self.taxa_sucesso_cache[r["ativo"]] = 0.0
        finally:
            conn.close()

    def calcular_instantaneo(self, rtd) -> tuple[list[BoxScore], list[MreResultado]]:
        cdi = self.obter_taxa_cdi()
        ativos = self._get_whitelist()
        if not ativos:
            return [], []

        if hasattr(rtd, 'update_counter'):
            counter = rtd.update_counter
            if counter == self._ultimo_rtd_counter and self._cached_box_scores:
                return self._cached_box_scores, self._cached_mre
            self._ultimo_rtd_counter = counter

        soh_europeia = bool(self._get_param("box_soh_europeia", 1))
        spread_max_pct = self._get_param("box_spread_max_pct", 0.40)
        inst_map = self._obter_instrumentos_mapa(ativos)
        hoje = date.today()
        grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)

        for codigo, inst in inst_map.items():
            if not inst["vencimento"] or inst["vencimento"] <= hoje:
                continue
            if inst["ativo"].upper() not in ativos:
                continue

            c_call = rtd.ler_campos(inst["cod_call"], FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.VOL_ASK, FieldName.STRIKE)
            c_put = rtd.ler_campos(inst["cod_put"], FieldName.BID, FieldName.ASK, FieldName.VOL_BID, FieldName.VOL_ASK, FieldName.STRIKE)

            bid_call = c_call.get(FieldName.BID) or 0.0
            ask_call = c_call.get(FieldName.ASK) or 0.0
            bid_put = c_put.get(FieldName.BID) or 0.0
            ask_put = c_put.get(FieldName.ASK) or 0.0
            qtd_bid_call = int(c_call.get(FieldName.VOL_BID) or 0)
            qtd_ask_call = int(c_call.get(FieldName.VOL_ASK) or 0)
            qtd_bid_put = int(c_put.get(FieldName.VOL_BID) or 0)
            qtd_ask_put = int(c_put.get(FieldName.VOL_ASK) or 0)

            if bid_call <= 0 or ask_call <= 0 or bid_put <= 0 or ask_put <= 0:
                continue

            strike = c_put.get(FieldName.STRIKE) or 0.0
            if not strike or strike <= 0:
                strike = c_call.get(FieldName.STRIKE) or 0.0
            if not strike or strike <= 0:
                continue

            grupo_key = (inst["ativo"], inst["vencimento"])
            grupos[grupo_key].append({
                "codigo": codigo,
                "strike": strike,
                "cod_call": inst["cod_call"],
                "cod_put": inst["cod_put"],
                "bid_call": bid_call,
                "ask_call": ask_call,
                "bid_put": bid_put,
                "ask_put": ask_put,
                "qtd_bid_call": qtd_bid_call,
                "qtd_ask_call": qtd_ask_call,
                "qtd_bid_put": qtd_bid_put,
                "qtd_ask_put": qtd_ask_put,
                "tipo_opcao": inst["tipo_opcao"],
            })

        if not grupos:
            return [], []

        resultados_box: list[BoxScore] = []
        resultados_mre: list[MreResultado] = []

        for (ativo, vencimento), members in grupos.items():
            spot = rtd.ler_campo_cache(ativo, FieldName.ASK) or 0.0
            if spot <= 0:
                continue

            days = (vencimento - hoje).days
            dias_uteis = dc_to_du(hoje, vencimento, days)
            if dias_uteis <= 0:
                continue

            members.sort(key=lambda m: m["strike"])
            spread_limite = spot * spread_max_pct if spot > 0 and spread_max_pct > 0 else float("inf")

            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    k1 = members[i]
                    k2 = members[j]

                    if (k2["strike"] - k1["strike"]) > spread_limite:
                        break

                    if soh_europeia and k1.get("tipo_opcao") != "E":
                        continue

                    score = self._calcular_score_box(
                        k1, k2, ativo, vencimento, spot, cdi, dias_uteis
                    )
                    if score is not None:
                        resultados_box.append(score)
                        self.salvar_snapshot(score)
                        mre = self._calcular_mre(k1, k2, score, cdi, dias_uteis, spot)
                        resultados_mre.append(mre)

        resultados_box.sort(key=lambda b: -b.score_final_pct)
        self._flush_spread_history()
        self._flush_snapshot_buffer()
        self._cached_box_scores = resultados_box
        self._cached_mre = resultados_mre
        return resultados_box, resultados_mre

    def _obter_instrumentos_mapa(self, ativos: list[str] | None = None) -> dict:
        conn = get_connection(self.db_path)
        try:
            if ativos:
                placeholders = ",".join("?" * len(ativos))
                rows = conn.execute(
                    f"SELECT * FROM instrumentos_base WHERE UPPER(ativo) IN ({placeholders})",
                    [a.upper() for a in ativos]
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM instrumentos_base").fetchall()
            mapa = {}
            for r in rows:
                cod_put = r["cod_put"]
                venc = r["vencimento"]
                if isinstance(venc, str):
                    venc = date.fromisoformat(venc)
                mapa[cod_put] = {
                    "cod_put": cod_put,
                    "cod_call": r["cod_call"],
                    "ativo": r["ativo"],
                    "vencimento": venc,
                    "tipo_opcao": r["tipo_opcao"],
                }
            return mapa
        finally:
            conn.close()

    def _calcular_score_box(self, k1: dict, k2: dict, ativo: str, vencimento: date,
                             spot: float, cdi: float, dias_uteis: int) -> BoxScore | None:
        if k1["strike"] >= k2["strike"]:
            return None
        t = dias_uteis / 252.0
        r = cdi
        r_cont = math.log(1 + r) if r > 0 else 0.0

        call_k1_mid = (k1["bid_call"] + k1["ask_call"]) / 2
        put_k1_mid  = (k1["bid_put"]  + k1["ask_put"])  / 2
        call_k2_mid = (k2["bid_call"] + k2["ask_call"]) / 2
        put_k2_mid  = (k2["bid_put"]  + k2["ask_put"])  / 2

        call_k1, put_k1 = k1["bid_call"], k1["ask_put"]
        call_k2, put_k2 = k2["ask_call"], k2["bid_put"]

        paridade_k1 = spot - k1["strike"] * math.exp(-r_cont * t)
        erro_k1 = abs((call_k1_mid - put_k1_mid) - paridade_k1)
        spread_k1 = (k1["ask_call"] - k1["bid_call"]) + (k1["ask_put"] - k1["bid_put"])
        erro_k1_pct = erro_k1 / max(spread_k1, 0.01)

        paridade_k2 = spot - k2["strike"] * math.exp(-r_cont * t)
        erro_k2 = abs((call_k2_mid - put_k2_mid) - paridade_k2)
        spread_k2 = (k2["ask_call"] - k2["bid_call"]) + (k2["ask_put"] - k2["bid_put"])
        erro_k2_pct = erro_k2 / max(spread_k2, 0.01)

        erro_box = max(erro_k1_pct, erro_k2_pct)
        fator_premio = self._calcular_fator_premio_cdi(
            k1["bid_call"], k1["ask_put"], k2["ask_call"], k2["bid_put"],
            spot, k1["strike"], k2["strike"], r, r_cont, t
        )
        normalizador_paridade = self._get_param("mpp_paridade_normalizador", 0.10)
        if normalizador_paridade <= 0:
            normalizador_paridade = 0.10
        score_paridade_box = min(erro_box / normalizador_paridade, 1.0) * fator_premio

        spreads = []
        profundidades = []
        imbalances = []
        pernas_data = [
            (k1["cod_call"], k1["bid_call"], k1["ask_call"], k1["qtd_bid_call"], k1["qtd_ask_call"]),
            (k1["cod_put"], k1["bid_put"], k1["ask_put"], k1["qtd_bid_put"], k1["qtd_ask_put"]),
            (k2["cod_call"], k2["bid_call"], k2["ask_call"], k2["qtd_bid_call"], k2["qtd_ask_call"]),
            (k2["cod_put"], k2["bid_put"], k2["ask_put"], k2["qtd_bid_put"], k2["qtd_ask_put"]),
        ]

        anomalias = []
        for codigo, bid, ask, bid_qtd, ask_qtd in pernas_data:
            mid = (ask + bid) / 2
            if mid > 0:
                spread_pct = (ask - bid) / mid
            else:
                spread_pct = 0.0
            spreads.append(spread_pct)

            depth = bid_qtd + ask_qtd
            score_prof = 1.0 / (1.0 + depth / 50.0)
            profundidades.append(score_prof)

            if bid_qtd + ask_qtd > 0:
                imb = abs(bid_qtd - ask_qtd) / (bid_qtd + ask_qtd)
            else:
                imb = 0.0
            imbalances.append(imb)

            self._atualizar_spread_history(codigo, spread_pct)
            anomalias.append(self._calcular_anomalia(codigo, spread_pct))

        spread_medio = sum(spreads) / len(spreads)
        score_spread_medio = min(spread_medio / 0.10, 1.0)

        profundidade_min = min(profundidades)

        qtd_min_box = min(
            k1["qtd_bid_call"] + k1["qtd_ask_call"],
            k1["qtd_bid_put"]  + k1["qtd_ask_put"],
            k2["qtd_bid_call"] + k2["qtd_ask_call"],
            k2["qtd_bid_put"]  + k2["qtd_ask_put"],
        )

        imbalance_medio = sum(imbalances) / len(imbalances)
        score_anomalia_medio = sum(anomalias) / len(anomalias) if anomalias else 0.0

        peso_paridade = self._get_param("mpp_peso_paridade", 0.25)
        peso_spread = self._get_param("mpp_peso_spread", 0.20)
        peso_profundidade = self._get_param("mpp_peso_profundidade", 0.10)
        peso_imbalance = self._get_param("mpp_peso_imbalance", 0.0)
        peso_anomalia = self._get_param("mpp_peso_spread_anomalia", 0.05)
        soma_pesos = peso_paridade + peso_spread + peso_profundidade + peso_imbalance + peso_anomalia
        if soma_pesos <= 0:
            soma_pesos = 0.65

        score_instantaneo = (
            (peso_paridade / soma_pesos) * score_paridade_box +
            (peso_spread / soma_pesos) * score_spread_medio +
            (peso_profundidade / soma_pesos) * profundidade_min +
            (peso_imbalance / soma_pesos) * imbalance_medio +
            (peso_anomalia / soma_pesos) * score_anomalia_medio
        )

        peso_estrutural = self._get_param("mpp_peso_estrutural", 0.35)
        peso_instantaneo = self._get_param("mpp_peso_instantaneo", 0.65)
        peso_estrutural = max(0.0, min(1.0, peso_estrutural))
        peso_instantaneo = max(0.0, min(1.0, peso_instantaneo))
        soma_pesos_final = peso_estrutural + peso_instantaneo
        if soma_pesos_final <= 0:
            peso_estrutural, peso_instantaneo = 0.35, 0.65

        score_estrutural_box = self._calcular_score_estrutural_box(k1, k2)

        score_final = peso_estrutural * score_estrutural_box + peso_instantaneo * score_instantaneo

        score_final *= self._calcular_fator_dte(dias_uteis)

        chave_pers = f"{ativo}_{k1['strike']}_{k2['strike']}"
        pers_ciclos = self._atualizar_persistencia(chave_pers, erro_box)
        pers_divisor = self._get_param("mpp_persistencia_divisor", 20.0)
        pers_max_mult = self._get_param("mpp_persistencia_max_mult", 0.50)
        mult_pers = 1.0 + min(pers_ciclos / pers_divisor, pers_max_mult)
        score_final *= mult_pers

        bonus = self._calcular_bonus_historico(ativo)
        score_final *= (1.0 + bonus)

        score_final_pct = score_final * 100.0

        nivel = self._classificar_nivel(score_final_pct)

        just = self._gerar_justificativa(ativo, score_paridade_box, fator_premio, pers_ciclos, bonus)

        return BoxScore(
            ativo=ativo,
            strike1=k1["strike"],
            strike2=k2["strike"],
            vencimento=vencimento,
            cod_call_k1=k1.get("cod_call", ""),
            cod_put_k1=k1.get("cod_put", ""),
            cod_call_k2=k2.get("cod_call", ""),
            cod_put_k2=k2.get("cod_put", ""),
            score_estrutural_box=score_estrutural_box,
            score_instantaneo_box=score_instantaneo,
            score_final=score_final,
            score_final_pct=round(score_final_pct, 1),
            erro_paridade_box=round(erro_box, 4),
            spread_medio=round(spread_medio, 4),
            profundidade_min=round(profundidade_min, 4),
            qtd_min_box=qtd_min_box,
            persistencia_ciclos=pers_ciclos,
            nivel_risco=nivel,
            justificativa=just,
        )

    def _calcular_fator_dte(self, dias_uteis: int) -> float:
        if dias_uteis <= 0:
            return 0.0
        dte_min = int(self._get_param("mpp_dte_ideal_min", 10))
        dte_max = int(self._get_param("mpp_dte_ideal_max", 25))
        fator_min = self._get_param("mpp_dte_fator_min", 0.60)
        if dte_min <= 0 or dte_max <= dte_min:
            return 1.0
        if dias_uteis < dte_min:
            return max(fator_min, dias_uteis / dte_min)
        if dias_uteis > dte_max:
            excesso_rel = (dias_uteis - dte_max) / dte_max
            return max(fator_min, 1.0 - excesso_rel)
        return 1.0

    def _calcular_fator_premio_cdi(self, call_k1, put_k1, call_k2, put_k2,
                                    spot, k1, k2, r, r_cont, t) -> float:
        premio_risco = self._get_param("box_premio_risco", 1.08)
        box_valor = (call_k1 - put_k1) - (call_k2 - put_k2)
        box_teorico = (k2 - k1) * math.exp(-r_cont * t)
        premio_abs = box_teorico - box_valor
        if premio_abs <= 0:
            return 0.0
        premio_pct = premio_abs / max(k2 - k1, 0.01)
        cdi_periodo = (1 + r) ** t - 1
        vezes_cdi = premio_pct / cdi_periodo if cdi_periodo > 0 else 0.0
        if vezes_cdi < premio_risco:
            return 0.0
        if vezes_cdi >= premio_risco * 2:
            return 1.0
        return (vezes_cdi - premio_risco) / premio_risco

    def _calcular_score_estrutural_box(self, k1: dict, k2: dict) -> float:
        scores = []
        for chave in (k1["cod_call"], k1["cod_put"], k2["cod_call"], k2["cod_put"]):
            escore = self.score_estrutural_cache.get(chave, {}).get("score_estrutural", 0.0)
            scores.append(escore)
        return sum(scores) / len(scores) if scores else 0.0

    def _carregar_spread_history(self):
        if not self.db_path:
            return
        try:
            conn = get_connection(self.db_path)
            try:
                rows = conn.execute("""
                    SELECT codigo, spread_pct FROM mpp_spread_history
                    ORDER BY codigo, created_at
                """).fetchall()
                hist_len = int(self._get_param("mpp_spread_history_len", 200))
                for r in rows:
                    cod = r["codigo"]
                    if cod not in self.spread_history:
                        self.spread_history[cod] = deque(maxlen=hist_len)
                    self.spread_history[cod].append(r["spread_pct"])
            finally:
                conn.close()
        except Exception:
            self.spread_history = {}

    def _atualizar_spread_history(self, codigo: str, spread_pct: float):
        if codigo not in self.spread_history:
            hist_len = int(self._get_param("mpp_spread_history_len", 200))
            self.spread_history[codigo] = deque(maxlen=hist_len)
        self.spread_history[codigo].append(spread_pct)

    def _flush_spread_history(self):
        """Persiste spread history em batch — chamado no final do ciclo MPP."""
        if not self.db_path or not self.spread_history:
            return
        hist_len = int(self._get_param("mpp_spread_history_len", 200))
        inserts = []
        codigos_atuais = set()
        for codigo, hist in self.spread_history.items():
            if hist:
                inserts.append((codigo, hist[-1]))
                codigos_atuais.add(codigo)
        if not inserts:
            return
        try:
            conn = get_connection(self.db_path)
            try:
                conn.executemany(
                    "INSERT INTO mpp_spread_history (codigo, spread_pct) VALUES (?, ?)",
                    inserts
                )
                for codigo in codigos_atuais:
                    conn.execute(
                        "DELETE FROM mpp_spread_history WHERE codigo = ? AND id NOT IN ("
                        "SELECT id FROM mpp_spread_history WHERE codigo = ? ORDER BY created_at DESC LIMIT ?)",
                        (codigo, codigo, hist_len)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    def _calcular_anomalia(self, codigo: str, spread_pct: float) -> float:
        min_anomalia = self._get_param("mpp_spread_min_anomalia", 0.02)
        if spread_pct < min_anomalia:
            return 0.0
        hist = self.spread_history.get(codigo)
        if not hist or len(hist) < 10:
            return 0.0
        media = sum(hist) / len(hist)
        if media <= 0:
            return 0.0
        anomalia = spread_pct / media
        return min(anomalia / 5.0, 1.0)

    def _atualizar_persistencia(self, chave_box: str, erro_paridade_pct: float) -> int:
        limite = self._get_param("mpp_erro_paridade_limiar", 0.02)
        if erro_paridade_pct > limite:
            self.persistencia[chave_box] = self.persistencia.get(chave_box, 0) + 1
        else:
            self.persistencia[chave_box] = 0
        return self.persistencia[chave_box]

    def _calcular_bonus_historico(self, ativo: str) -> float:
        taxa = self.taxa_sucesso_cache.get(ativo, 0.0)
        bonus_max = self._get_param("mpp_bonus_max", 0.15)
        bonus_taxa = self._get_param("mpp_bonus_taxa", 0.25)
        bonus = min(taxa * bonus_taxa, bonus_max)
        return bonus

    def _classificar_nivel(self, score_pct: float) -> str:
        if score_pct >= 85:
            return "crítico"
        if score_pct >= 70:
            return "alto"
        if score_pct >= 50:
            return "médio"
        return "baixo"

    def _gerar_justificativa(self, ativo: str, score_paridade: float,
                              fator_premio: float, pers_ciclos: int, bonus: float) -> str:
        partes = []
        if score_paridade > 0.5:
            partes.append(f"paridade={score_paridade:.2f}")
        if fator_premio <= 0:
            partes.append("prêmio abaixo do CDI")
        if pers_ciclos > 10:
            partes.append(f"persistência={pers_ciclos} ciclos")
        if bonus > 0.05:
            partes.append(f"bônus histórico={bonus:.2%}")
        return "; ".join(partes) if partes else "sem destaques"

    def _calcular_mre(self, k1: dict, k2: dict, box: BoxScore,
                       cdi: float, dias_uteis: int, spot: float) -> MreResultado:
        pernas = [
            ("CALL", k1["cod_call"], k1["bid_call"], k1["ask_call"], k1["qtd_bid_call"], k1["qtd_ask_call"], k1["strike"]),
            ("PUT", k1["cod_put"], k1["bid_put"], k1["ask_put"], k1["qtd_bid_put"], k1["qtd_ask_put"], k1["strike"]),
            ("CALL", k2["cod_call"], k2["bid_call"], k2["ask_call"], k2["qtd_bid_call"], k2["qtd_ask_call"], k2["strike"]),
            ("PUT", k2["cod_put"], k2["bid_put"], k2["ask_put"], k2["qtd_bid_put"], k2["qtd_ask_put"], k2["strike"]),
        ]

        melhor_ip = -1.0
        melhor_perna = ""
        for tipo, codigo, bid, ask, bid_qtd, ask_qtd, strike in pernas:
            depth = bid_qtd + ask_qtd
            if depth <= 0:
                continue
            mid = (ask + bid) / 2
            spread_pct = (ask - bid) / mid if mid > 0 else 0.0
            imb = abs(bid_qtd - ask_qtd) / depth if depth > 0 else 0.0
            chave_pers = f"{box.ativo}_{k1['strike']}_{k2['strike']}"
            pers = self.persistencia.get(chave_pers, 0)
            ip = self._calcular_ip(spread_pct, depth, pers, imb)
            if ip > melhor_ip:
                melhor_ip = ip
                melhor_perna = f"{tipo} {codigo}"

        lote_base = int(self._get_param("mre_lote_base", 100))
        max_pct = self._get_param("mre_profundidade_max_pct", 0.20)
        profundidades_box = [
            k1["qtd_bid_call"] + k1["qtd_ask_call"],
            k1["qtd_bid_put"] + k1["qtd_ask_put"],
            k2["qtd_bid_call"] + k2["qtd_ask_call"],
            k2["qtd_bid_put"] + k2["qtd_ask_put"],
        ]
        prof_min_box = min(profundidades_box)
        lote_sug = min(lote_base, int(prof_min_box * max_pct))
        lote_sug = max(lote_sug, 1)

        conf = self._confianca_completar(prof_min_box, lote_sug, box.spread_medio)

        if conf < 0.3:
            nivel_rec = "baixa"
            just = f"Confiança baixa ({conf:.0%}) — pouca profundidade"
        elif conf > 0.7:
            nivel_rec = "alta"
            just = f"Boa confiança ({conf:.0%})"
        else:
            nivel_rec = "média"
            just = f"Confiança média ({conf:.0%})"

        return MreResultado(
            ativo=box.ativo,
            strike1=box.strike1,
            strike2=box.strike2,
            vencimento=box.vencimento,
            score_box=box.score_final_pct,
            isca_recomendada=melhor_perna,
            ip_isca=round(melhor_ip, 2),
            lote_sugerido=lote_sug,
            confianca_completar=round(conf, 4),
            nivel_recomendacao=nivel_rec,
            justificativa=just,
        )

    def _calcular_ip(self, spread_pct: float, profundidade: int,
                      persistencia_ciclos: int, imbalance: float) -> float:
        if profundidade <= 0:
            return 0.0
        spread_score = min(spread_pct / 0.10, 1.0)
        prof_score = min(profundidade / 500.0, 1.0)
        pers_score = min(persistencia_ciclos / 40.0, 1.0)
        imb_score = imbalance
        return 0.40 * spread_score + 0.30 * prof_score + 0.20 * pers_score + 0.10 * imb_score

    def _confianca_completar(self, profundidade_min_box: int, lote: int,
                              spread_medio_box: float) -> float:
        if profundidade_min_box <= 0 or lote <= 0:
            return 0.0
        prof_suf = min(profundidade_min_box / (lote * 3), 1.0)
        spread_fav = max(1.0 - spread_medio_box * 5.0, 0.0)
        return prof_suf * spread_fav

    def salvar_snapshot(self, box: BoxScore):
        if box.score_final_pct < self.SNAPSHOT_THRESHOLD:
            return
        chave = f"{box.ativo}_{box.strike1}_{box.strike2}"
        count = self._snapshot_counter.get(chave, 0) + 1
        if count < self.SNAPSHOT_INTERVAL:
            self._snapshot_counter[chave] = count
            return
        self._snapshot_counter[chave] = 0
        self._snapshot_buffer.append((
            box.ativo, box.strike1, box.strike2, box.vencimento.isoformat(),
            box.score_final_pct, box.score_estrutural_box, box.score_instantaneo_box
        ))

    def _flush_snapshot_buffer(self):
        if not self._snapshot_buffer:
            return
        conn = get_connection(self.db_path)
        try:
            conn.executemany("""
                INSERT INTO mpp_snapshot
                (ativo, strike1, strike2, vencimento, score_final, score_estrutural, score_instantaneo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, self._snapshot_buffer)
            conn.commit()
        finally:
            conn.close()
        self._snapshot_buffer.clear()


    def limpar_snapshots_antigos(self):
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                DELETE FROM mpp_snapshot
                WHERE timestamp < datetime('now', '-24 hours')
            """)
            conn.execute("""
                DELETE FROM mpp_historico_distorcoes
                WHERE created_at < datetime('now', '-7 days')
            """)
            conn.execute("""
                DELETE FROM mpp_spread_history
                WHERE created_at < datetime('now', '-3 days')
            """)
            conn.commit()
        finally:
            conn.close()

    def registrar_box_encontrado(self, ativo: str, strike1: float, strike2: float,
                                  score_box: float, encontrado: bool = True):
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                INSERT INTO mpp_historico_distorcoes
                (ativo, strike1, strike2, data, score_box, box_encontrado)
                VALUES (?, ?, ?, date('now'), ?, ?)
            """, (ativo, strike1, strike2, score_box, 1 if encontrado else 0))
            conn.commit()
        finally:
            conn.close()
