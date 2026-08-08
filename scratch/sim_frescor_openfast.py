"""
PILOTO DESCARTAVEL — Frescor de dados em dois modelos de fonte:
  1. "socket" (OpenFast): entrega por push individual por campo; ts carimbado
     no instante exato de cada update.
  2. "rtd" (Fast Trade RTD / Excel headless): entrega em BATCH/snapshot —
     o servidor srv.rtd envia ao Excel em lotes ditados pelo
     RTDThrottleInterval; ts de TODAS as celulas carimba no tick do batch.
     A leitura (Range.Value) e instantanea da memoria RAM e sempre tem valor;
     a idade = tempo desde o ultimo tick que entregou a celula.

Espelha (sem importar de src/):
  - mercado_data_provider.py: Onda 1 de registro + scan sobre _chaves_com_book;
  - openfast_socket_adapter.py (modelo a; cache_ts por celula);
  - fast_trade_rtd_adapter.py / srv.rtd (modelo b; get_ts_campo=None ainda).

Mede, por scan, a idade do dado lido (preco_ativo ASK e celulas do book) e
agrega media/p50/p95/max + % stale (idade > limiar de 5s).

Isolado e descartavel: NAO toca em src/, NAO escreve no banco — so le
instrumentos_base read-only para a grade ter tamanho real.

Uso:
  python scratch/sim_frescor_openfast.py --modo rtd --throttle 0.25   # padrao
  python scratch/sim_frescor_openfast.py --modo socket                 # push por campo
  python scratch/sim_frescor_openfast.py --scans 60 --scan-interval 2.0
  python scratch/sim_frescor_openfast.py --no-reregistra
  python scratch/sim_frescor_openfast.py --frac-book 0.10
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sqlite3
import time
from pathlib import Path

# ---- Constantes espelhando o codigo real -------------------------------- #
STALE_LIMIAR = 5.0          # openfast_socket_adapter / re-registro (0b068d5)
CEL_ATIVO = ["ASK", "BID"]                       # precos base do ativo
CEL_PUT = ["ASK", "BID", "VOL_ASK", "QTD_LAST"]  # mercado_data_provider:546
CEL_CALL = ["BID", "ASK", "VOL_BID", "QTD_LAST"] # mercado_data_provider:547
LATENCIA_DESPERTA = 0.25     # push apos re-registro de stale (modelo)
THROTTLE_DEFAULT = 0.25      # RTDThrottleInterval do Excel no piloto (ms/1000)

TAXA_ATIVO = {"liquido": 20.0, "medio": 2.0, "iliquido": 0.15}
TAXA_OPCAO = {"liquido": 4.0, "medio": 0.4, "iliquido": 0.02}
FRAC_LIQUIDOS_DEFAULT = 0.25   # fração dos ativos tratada como com book


# ------------------------------------------------------------------------- #
def carregar_instrumentos(db_path: Path) -> list[tuple[str, str, str]]:
    """Le ativo/cod_put/cod_call do instrumentos_base (read-only)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(
            "SELECT ativo, cod_put, cod_call FROM instrumentos_base"
        )
        return [(ativo, cod_put, cod_call) for ativo, cod_put, cod_call in cur]
    finally:
        conn.close()


def classe_atividade(ativo: str, ativos_liquidos: set[str]) -> str:
    if ativo in ativos_liquidos:
        return "liquido"
    r = random.Random(ativo)
    return "medio" if r.random() < 0.5 else "iliquido"


def fator_codigo(cod: str, rng: random.Random) -> float:
    """Variacao estavel por codigo na taxa de push (0.3x-1.8x)."""
    return 0.3 + rng.random() * 1.5


# ------------------------------------------------------------------------- #
class SimuladorFrescor:
    def __init__(self, instrumentos, frac_liquidos: float,
                 scan_interval: float, n_scans: int,
                 reregistra: bool, seed: int,
                 modo: str = "rtd", throttle: float = THROTTLE_DEFAULT):
        self.rng = random.Random(seed)
        self.instrumentos = instrumentos
        self.scan_interval = scan_interval
        self.n_scans = n_scans
        self.reregistra = reregistra
        self.modo = modo
        self.throttle = throttle

        # ativos liquidos = topo por quantidade de opcoes
        qtd: dict[str, int] = {}
        for ativo, _, _ in instrumentos:
            qtd[ativo] = qtd.get(ativo, 0) + 1
        ordenados = sorted(qtd, key=qtd.get, reverse=True)
        n_liq = max(1, int(len(ordenados) * frac_liquidos))
        self.ativos_liquidos = set(ordenados[:n_liq])
        self.classe = {a: classe_atividade(a, self.ativos_liquidos)
                       for a in qtd}

        # celulas: chave -> (rate, next_push, ts)
        self.celulas: dict[tuple, list] = {}
        self.keys_book: list[str] = []   # chave ativo|cod_put com book
        self.inst_map: dict[tuple, tuple] = {}

        t0 = 0.0
        for ativo, cod_put, cod_call in instrumentos:
            self.inst_map[(ativo, cod_put)] = (ativo, cod_put, cod_call)
            cl = self.classe[ativo]
            rate_ativo = TAXA_ATIVO[cl] * fator_codigo(ativo, self.rng)
            for campo in CEL_ATIVO:
                self.celulas[(ativo, campo)] = [
                    rate_ativo, t0 + self.rng.expovariate(rate_ativo), t0,
                ]
            if cl != "liquido":
                continue
            rate_put = TAXA_OPCAO[cl] * fator_codigo(cod_put, self.rng)
            rate_call = TAXA_OPCAO[cl] * fator_codigo(cod_call, self.rng)
            for campo in CEL_PUT:
                self.celulas[(cod_put, campo)] = [
                    rate_put, t0 + self.rng.expovariate(rate_put), t0,
                ]
            for campo in CEL_CALL:
                self.celulas[(cod_call, campo)] = [
                    rate_call, t0 + self.rng.expovariate(rate_call), t0,
                ]
            self.keys_book.append(f"{ativo}|{cod_put}")

    # ---------------------------------------------------------------- #
    def _avancar_pushs(self, t: float):
        """Modo socket: push individual por campo; ts = instante do push."""
        for chave in self.celulas:
            rate, prox, _ = self.celulas[chave]
            while prox <= t:
                self.celulas[chave][2] = prox   # ts = instante do push
                prox += self.rng.expovariate(rate)
            self.celulas[chave][1] = prox

    def _avancar_batch(self, t: float):
        """Modo rtd (Excel headless): entrega em BATCH/snapshot.

        O servidor srv.rtd acumula mudancas e entrega ao Excel em lotes
        ditados pelo RTDThrottleInterval (self.throttle). O ts de TODAS as
        celulas carimba no tick do batch que as entregou — nunca entre ticks.
        Mudancas de mercado continuam ocorrendo em tempo exponencial, mas a
        visibilidade delas no scan so existe no tick seguinte ao throttle.
        """
        thr = self.throttle
        for chave in self.celulas:
            rate, prox, _ = self.celulas[chave]
            while prox <= t:
                # proximo tick do Excel que entrega o batch
                tick = math.ceil(prox / thr) * thr
                if tick > t:
                    break
                self.celulas[chave][2] = tick   # ts = tick do batch
                prox += self.rng.expovariate(rate)
            self.celulas[chave][1] = prox

    def _idade(self, chave: tuple, t: float) -> float:
        return t - self.celulas[chave][2]

    def _reregistrar_stale(self, t: float):
        """Espelha re-registro de celulas com idade >5s (acorda servidor).

        Vale para o modo socket. No modo rtd o valor da celula permanece na
        matriz do Excel mesmo sem novo batch — a leitura (Range.Value) da
        memoria RAM sempre retorna o ultimo valor capturado.
        """
        if self.modo != "socket":
            return 0
        n = 0
        for chave in self.celulas:
            if t - self.celulas[chave][2] > STALE_LIMIAR:
                self.celulas[chave][2] = t - LATENCIA_DESPERTA
                n += 1
        return n

    # ---------------------------------------------------------------- #
    def _scan(self, t: float) -> dict:
        """Um ciclo de varredura: refresh + leitura do book por chave."""
        if self.reregistra:
            self._reregistrar_stale(t)
        if self.modo == "rtd":
            self._avancar_batch(t)
        else:
            self._avancar_pushs(t)

        idades_preco: list[float] = []
        idades_celula: list[float] = []
        n_keys = 0
        for key in self.keys_book:
            ativo, cod_put = key.split("|", 1)
            inst = self.inst_map.get((ativo, cod_put))
            if inst is None:
                continue
            cod_call = inst[2]
            n_keys += 1
            # preco_ativo ASK: celula usada em todo calculo
            idades_preco.append(self._idade((ativo, "ASK"), t))
            # celulas do book lidas no scan
            for campo in CEL_PUT:
                idades_celula.append(self._idade((cod_put, campo), t))
            for campo in CEL_CALL:
                idades_celula.append(self._idade((cod_call, campo), t))

        return {"t": t, "n_keys": n_keys,
                "preco": idades_preco, "celula": idades_celula}

    # ---------------------------------------------------------------- #
    def executar(self) -> list[dict]:
        t = 0.0
        resultados = []
        for _ in range(self.n_scans):
            resultados.append(self._scan(t))
            t += self.scan_interval
        return resultados


# ------------------------------------------------------------------------- #
# ------------------------------------------------------------------------- #
def _stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "media": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0,
                "stale_pct": 0.0}
    v = sorted(vals)
    n = len(v)
    return {
        "n": n,
        "media": sum(v) / n,
        "p50": v[n // 2],
        "p95": v[int(n * 0.95) - 1],
        "max": v[-1],
        "stale_pct": 100.0 * sum(1 for x in v if x > STALE_LIMIAR) / n,
    }


def _relatorio(scan: dict) -> str:
    p = _stats(scan["preco"])
    c = _stats(scan["celula"])
    return (f"t={scan['t']:5.1f}s keys={scan['n_keys']:6d} | "
            f"PRECO med={p['media']:5.2f} p50={p['p50']:5.2f} "
            f"p95={p['p95']:6.2f} max={p['max']:6.2f} stale={p['stale_pct']:5.1f}% | "
            f"CELULA med={c['media']:5.2f} p95={c['p95']:6.2f} "
            f"max={c['max']:6.2f} stale={c['stale_pct']:5.1f}%")


def _veredito(agg: dict) -> str:
    if agg["p95"] <= 1.0:
        return "EXCELENTE (quase tempo real)"
    if agg["p95"] <= STALE_LIMIAR:
        return "BOM (dentro do limiar de 5s)"
    return "RUIM (dados envelhecendo alem do limiar)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scans", type=int, default=30)
    ap.add_argument("--scan-interval", type=float, default=2.0)
    ap.add_argument("--frac-book", type=float, default=FRAC_LIQUIDOS_DEFAULT)
    ap.add_argument("--no-reregistra", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--modo", choices=("rtd", "socket"), default="rtd",
                    help="modelo de entrega: rtd=batch Excel (padrao), "
                         "socket=push por campo")
    ap.add_argument("--throttle", type=float, default=THROTTLE_DEFAULT,
                    help="RTDThrottleInterval em segundos (default 0.25)")
    args = ap.parse_args()

    db = Path(os.environ["APPDATA"]) / "Spreadhunter" / "spreadhunter.db"
    print(f"[db] {db}  (existe={db.exists()})")
    if not db.exists():
        print("ERRO: banco nao encontrado")
        return 1

    t0 = time.perf_counter()
    insts = carregar_instrumentos(db)
    print(f"[db] {len(insts)} instrumentos lidos (read-only) em "
          f"{time.perf_counter() - t0:.2f}s")

    sim = SimuladorFrescor(
        instrumentos=insts,
        frac_liquidos=args.frac_book,
        scan_interval=args.scan_interval,
        n_scans=args.scans,
        reregistra=not args.no_reregistra,
        seed=args.seed,
        modo=args.modo,
        throttle=args.throttle,
    )
    print(f"[sim] modo={args.modo} throttle={args.throttle:.3f}s "
          f"ativos liquidos={len(sim.ativos_liquidos)} "
          f"keys com book={len(sim.keys_book)} celulas={len(sim.celulas)} "
          f"re-registro={'ON' if sim.reregistra else 'OFF'} "
          f"(scan {args.scan_interval}s x {args.scans})")

    t0 = time.perf_counter()
    res = sim.executar()
    print(f"[sim] executado em {time.perf_counter() - t0:.2f}s\n")

    print("--- scans (amostra do inicio/fim) ---")
    amostra = [res[0], res[len(res) // 2], res[-1]]
    for r in amostra:
        print(_relatorio(r))
    if args.scans > 6:
        print("  ...")

    print("\n=== AGREGADO CICLO COMPLETO ===")
    preco_vals: list[float] = []
    celula_vals: list[float] = []
    for r in res:
        preco_vals.extend(r["preco"])
        celula_vals.extend(r["celula"])
    up = _stats(preco_vals)
    uc = _stats(celula_vals)
    print(f"PRECO_ATIVO : n={up['n']:7d} media={up['media']:5.2f}s "
          f"p50={up['p50']:5.2f}s p95={up['p95']:6.2f}s "
          f"max={up['max']:6.2f}s stale>5s={up['stale_pct']:5.1f}%")
    print(f"CELULAS BOOK: n={uc['n']:7d} media={uc['media']:5.2f}s "
          f"p50={uc['p50']:5.2f}s p95={uc['p95']:6.2f}s "
          f"max={uc['max']:6.2f}s stale>5s={uc['stale_pct']:5.1f}%")
    print(f"\nVEREDITO (preco): {_veredito(up)}")
    print(f"VEREDITO (celula): {_veredito(uc)}")
    print(f"Limiar stale: {STALE_LIMIAR}s (re-registro no provider)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
