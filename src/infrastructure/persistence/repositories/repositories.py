import json
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.entities.oportunidade import Oportunidade, ClassificacaoOp
from src.domain.entities.estrutura_operacional import EstruturaOperacional, TipoEstrutura
from src.domain.entities.perna_operacao import PernaOperacao, Lado
from src.domain.entities.parametro_operacional import ParametroOperacional
from src.domain.entities.taxa_aluguel import TaxaAluguel
from src.infrastructure.persistence.database import get_connection


def _parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def _parse_datetime(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _row_strike(row: sqlite3.Row) -> float | None:
    """Safely extract strike column (may not exist in legacy DB)."""
    try:
        return row["strike"]
    except (IndexError, KeyError):
        return None


class InstrumentoRepository:
    _cache_all = None
    _cache_mapped = None
    _lock = threading.Lock()

    def __init__(self, db_path=None):
        self.db_path = db_path

    @classmethod
    def invalidate_cache(cls):
        with cls._lock:
            cls._cache_all = None
            cls._cache_mapped = None

    def save(self, instrumento: InstrumentoOpcional) -> InstrumentoOpcional:
        self.invalidate_cache()
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao)
                VALUES (?, ?, ?, ?, ?)""",
                (instrumento.ativo, instrumento.cod_put, instrumento.cod_call,
                instrumento.vencimento.isoformat(),
                instrumento.tipo_opcao.value)
            )
            conn.commit()
            instrumento.id = cursor.lastrowid
            return instrumento
        finally:
            conn.close()

    def save_batch(self, instrumentos: list[InstrumentoOpcional]) -> int:
        self.invalidate_cache()
        conn = get_connection(self.db_path)
        try:
            rows = [
                (i.ativo, i.cod_put, i.cod_call, i.vencimento.isoformat(), i.tipo_opcao.value)
                for i in instrumentos
            ]
            conn.executemany(
                "INSERT INTO instrumentos_base (ativo, cod_put, cod_call, vencimento, tipo_opcao) VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def get_all(self) -> list[InstrumentoOpcional]:
        with self.__class__._lock:
            if self.__class__._cache_all is not None:
                return list(self.__class__._cache_all)
        
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM instrumentos_base").fetchall()
            inst_list = [
                InstrumentoOpcional(
                    id=row["id"],
                    ativo=row["ativo"],
                    cod_put=row["cod_put"],
                    cod_call=row["cod_call"],
                    vencimento=_parse_date(row["vencimento"]),
                    tipo_opcao=TipoOpcao(row["tipo_opcao"]),
                    strike=_row_strike(row),
                    created_at=_parse_datetime(row["created_at"]) if "created_at" in row.keys() else None,
                )
                for row in rows
            ]
            with self.__class__._lock:
                self.__class__._cache_all = inst_list
            return list(inst_list)
        finally:
            conn.close()

    def get_all_mapped(self) -> dict[tuple[str, str], InstrumentoOpcional]:
        """Retorna dicionário {(ativo, cod_put): InstrumentoOpcional}.
        Chave composta evita confusao entre ativos com mesmo codigo de opcao.
        """
        with self.__class__._lock:
            if self.__class__._cache_mapped is not None:
                return dict(self.__class__._cache_mapped)
        
        all_inst = self.get_all()
        mapped = {(i.ativo, i.cod_put): i for i in all_inst}
        with self.__class__._lock:
            self.__class__._cache_mapped = mapped
        return dict(mapped)

    def get_by_ativo(self, ativo: str) -> list[InstrumentoOpcional]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM instrumentos_base WHERE ativo = ?", (ativo,)
            ).fetchall()
            return [
                InstrumentoOpcional(
                    id=row["id"],
                    ativo=row["ativo"],
                    cod_put=row["cod_put"],
                    cod_call=row["cod_call"],
                    vencimento=_parse_date(row["vencimento"]),
                    tipo_opcao=TipoOpcao(row["tipo_opcao"]),
                    strike=_row_strike(row),
                    created_at=_parse_datetime(row["created_at"]) if "created_at" in row.keys() else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_proximos_vencimentos(self, limite: int = 30) -> list[date]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT vencimento FROM instrumentos_base "
                "WHERE vencimento >= date('now') ORDER BY vencimento LIMIT ?",
                (limite,),
            ).fetchall()
            return sorted(set(_parse_date(row["vencimento"]) for row in rows if row["vencimento"]))
        finally:
            conn.close()

    def delete_all(self) -> int:
        self.invalidate_cache()
        conn = get_connection(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            cursor = conn.execute("DELETE FROM instrumentos_base")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class ParametroRepository:
    _caches: dict[str, dict] = {}
    _locks: dict[str, threading.Lock] = {}
    _dict_lock = threading.Lock()

    def __init__(self, db_path=None):
        self.db_path = db_path

    def _cache_key(self) -> str:
        return str(Path(self.db_path).resolve()) if self.db_path else "default"

    def invalidate_cache(self):
        key = self._cache_key()
        with self._dict_lock:
            self._caches.pop(key, None)
            self._locks.pop(key, None)

    def save(self, param: ParametroOperacional) -> ParametroOperacional:
        self.invalidate_cache()
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO parametros_operacionais (chave, valor, estrategia, descricao)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, estrategia=excluded.estrategia, descricao=excluded.descricao""",
                (param.chave, param.valor, param.estrategia, param.descricao)
            )
            conn.commit()
            param.id = cursor.lastrowid
            return param
        finally:
            conn.close()

    def get_by_chave(self, chave: str) -> ParametroOperacional | None:
        key = self._cache_key()
        with self._dict_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            lock = self._locks[key]
        with lock:
            cache = self._caches.get(key)
            if cache is None:
                cache = self._fill_cache()
                with self._dict_lock:
                    self._caches[key] = cache
            return cache.get(chave)

    def _fill_cache(self) -> dict:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM parametros_operacionais").fetchall()
            cache = {}
            for row in rows:
                val_raw = row["valor"]
                try:
                    valor = float(val_raw)
                except (ValueError, TypeError):
                    valor = val_raw
                cache[row["chave"]] = ParametroOperacional(
                    id=row["id"], chave=row["chave"], valor=valor,
                    estrategia=row["estrategia"], descricao=row["descricao"]
                )
            return cache
        finally:
            conn.close()

    def list_all(self) -> list[ParametroOperacional]:
        key = self._cache_key()
        with self._dict_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            lock = self._locks[key]
        with lock:
            cache = self._caches.get(key)
            if cache is None:
                cache = self._fill_cache()
                with self._dict_lock:
                    self._caches[key] = cache
            return list(cache.values())

    def get_by_estrategia(self, estrategia: str) -> list[ParametroOperacional]:
        key = self._cache_key()
        with self._dict_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            lock = self._locks[key]
        with lock:
            cache = self._caches.get(key)
            if cache is None:
                cache = self._fill_cache()
                with self._dict_lock:
                    self._caches[key] = cache
            return [p for p in cache.values() if p.estrategia == estrategia]

    def seed_defaults(self) -> None:
        self.invalidate_cache()
        """Insere os parâmetros padrão APENAS se ainda não existirem no banco.
        Nunca sobrescreve valores que o usuário já tenha alterado.
        """
        conn = get_connection(self.db_path)
        try:
            for param in ParametroOperacional.defaults():
                conn.execute(
                    """INSERT OR IGNORE INTO parametros_operacionais
                       (chave, valor, estrategia, descricao)
                       VALUES (?, ?, ?, ?)""",
                    (param.chave, param.valor, param.estrategia, param.descricao),
                )
            conn.commit()
        finally:
            conn.close()


class OportunidadeRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, oportunidade: Oportunidade) -> Oportunidade:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO oportunidades
                (instrumento_id, preco_ativo, strike, dias, cdi_periodo,
                custo_sbth, pct_ganho_sbth, pct_cdi_sbth,
                custo_box, pct_ganho_box, pct_cdi_box,
                classificacao, operacao, snapshot_mercado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (oportunidade.instrumento_id, oportunidade.preco_ativo,
                oportunidade.strike, oportunidade.dias, oportunidade.cdi_periodo,
                oportunidade.custo_sbth, oportunidade.pct_ganho_sbth, oportunidade.pct_cdi_sbth,
                oportunidade.custo_box, oportunidade.pct_ganho_box, oportunidade.pct_cdi_box,
                oportunidade.classificacao.value, oportunidade.operacao,
                json.dumps(oportunidade.snapshot_mercado))
            )
            conn.commit()
            oportunidade.id = cursor.lastrowid
            return oportunidade
        finally:
            conn.close()

    def get_all(self) -> list[Oportunidade]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM oportunidades").fetchall()
            return [self._row_to_entity(row) for row in rows]
        finally:
            conn.close()

    def _row_to_entity(self, row) -> Oportunidade:
        return Oportunidade(
            id=row["id"],
            instrumento_id=row["instrumento_id"],
            preco_ativo=row["preco_ativo"],
            strike=row["strike"],
            dias=row["dias"],
            cdi_periodo=row["cdi_periodo"],
            custo_sbth=row["custo_sbth"],
            pct_ganho_sbth=row["pct_ganho_sbth"],
            pct_cdi_sbth=row["pct_cdi_sbth"],
            custo_box=row["custo_box"],
            pct_ganho_box=row["pct_ganho_box"],
            pct_cdi_box=row["pct_cdi_box"],
            classificacao=ClassificacaoOp(row["classificacao"]),
            operacao=row["operacao"],
            snapshot_mercado=json.loads(row["snapshot_mercado"] or "{}"),
        )

    def get_historico_completo(self, limite: int = 5000) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """SELECT o.id, o.created_at, i.ativo, o.strike, o.operacao, o.dias, o.preco_ativo,
                          o.custo_box, o.pct_ganho_box, o.pct_cdi_box,
                          o.custo_sbth, o.pct_ganho_sbth, o.pct_cdi_sbth,
                          o.snapshot_mercado
                   FROM oportunidades o
                   JOIN instrumentos_base i ON o.instrumento_id = i.id
                   ORDER BY o.created_at DESC
                   LIMIT ?""", (limite,)
            )
            rows = cursor.fetchall()
            res = []
            for r in rows:
                res.append({
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "ativo": r["ativo"],
                    "strike": r["strike"],
                    "operacao": r["operacao"],
                    "dias": r["dias"],
                    "preco_ativo": r["preco_ativo"],
                    "custo_box": r["custo_box"],
                    "pct_ganho_box": r["pct_ganho_box"],
                    "pct_cdi_box": r["pct_cdi_box"],
                    "custo_sbth": r["custo_sbth"],
                    "pct_ganho_sbth": r["pct_ganho_sbth"],
                    "pct_cdi_sbth": r["pct_cdi_sbth"],
                    "snapshot_mercado": r["snapshot_mercado"],
                })
            return res
        finally:
            conn.close()

    def get_historico_com_estrutura(self, limite: int = 5000) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """SELECT o.id, o.created_at, i.ativo, o.strike, o.operacao, o.dias,
                          o.preco_ativo, o.cdi_periodo,
                          o.custo_box, o.pct_ganho_box, o.pct_cdi_box,
                          o.custo_sbth, o.pct_ganho_sbth, o.pct_cdi_sbth,
                          o.classificacao, o.snapshot_mercado,
                          e.id AS estrutura_id, e.tipo AS estrutura_tipo,
                          e.coefic_alvo, e.coefic_mercado, e.taxa_ganho,
                          p.id AS perna_id, p.codigo AS perna_codigo,
                          p.lado AS perna_lado, p.quantidade AS perna_qtd,
                          p.profundidade AS perna_profundidade, p.ordem AS perna_ordem
                   FROM oportunidades o
                   JOIN instrumentos_base i ON o.instrumento_id = i.id
                   LEFT JOIN estruturas_operacionais e ON e.oportunidade_id = o.id
                   LEFT JOIN pernas_operacao p ON p.estrutura_id = e.id
                   ORDER BY o.created_at DESC, e.id, p.ordem
                   LIMIT ?""", (limite,)
            )
            rows = cursor.fetchall()
            oportunidades: dict[int, dict] = {}
            for r in rows:
                oid = r["id"]
                if oid not in oportunidades:
                    oportunidades[oid] = {
                        "id": oid,
                        "created_at": r["created_at"],
                        "ativo": r["ativo"],
                        "strike": r["strike"],
                        "operacao": r["operacao"],
                        "dias": r["dias"],
                        "preco_ativo": r["preco_ativo"],
                        "cdi_periodo": r["cdi_periodo"],
                        "custo_box": r["custo_box"],
                        "pct_ganho_box": r["pct_ganho_box"],
                        "pct_cdi_box": r["pct_cdi_box"],
                        "custo_sbth": r["custo_sbth"],
                        "pct_ganho_sbth": r["pct_ganho_sbth"],
                        "pct_cdi_sbth": r["pct_cdi_sbth"],
                        "classificacao": r["classificacao"],
                        "snapshot_mercado": r["snapshot_mercado"],
                        "estruturas": [],
                    }
                eid = r["estrutura_id"]
                if eid is not None:
                    opp = oportunidades[oid]
                    estrutura_existente = next((e for e in opp["estruturas"] if e["id"] == eid), None)
                    if estrutura_existente is None:
                        estrutura_existente = {
                            "id": eid,
                            "tipo": r["estrutura_tipo"],
                            "coefic_alvo": r["coefic_alvo"],
                            "coefic_mercado": r["coefic_mercado"],
                            "taxa_ganho": r["taxa_ganho"],
                            "pernas": [],
                        }
                        opp["estruturas"].append(estrutura_existente)
                    pid = r["perna_id"]
                    if pid is not None:
                        estrutura_existente["pernas"].append({
                            "id": pid,
                            "codigo": r["perna_codigo"],
                            "lado": r["perna_lado"],
                            "quantidade": r["perna_qtd"],
                            "profundidade": r["perna_profundidade"],
                            "ordem": r["perna_ordem"],
                        })
            return list(oportunidades.values())
        finally:
            conn.close()

    def delete_by_id(self, o_id: int) -> bool:
        conn = get_connection(self.db_path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                """DELETE FROM pernas_operacao 
                   WHERE estrutura_id IN (
                       SELECT id FROM estruturas_operacionais WHERE oportunidade_id = ?
                   )""", (o_id,)
            )
            conn.execute("DELETE FROM estruturas_operacionais WHERE oportunidade_id = ?", (o_id,))
            cursor = conn.execute("DELETE FROM oportunidades WHERE id = ?", (o_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class EstruturaRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, estrutura: EstruturaOperacional) -> EstruturaOperacional:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO estruturas_operacionais
                   (oportunidade_id, tipo, coefic_alvo, coefic_mercado, taxa_ganho)
                   VALUES (?, ?, ?, ?, ?)""",
                (estrutura.oportunidade_id, estrutura.tipo.value,
                 estrutura.coefic_alvo, estrutura.coefic_mercado, estrutura.taxa_ganho)
            )
            conn.commit()
            estrutura.id = cursor.lastrowid
            return estrutura
        finally:
            conn.close()

    def get_by_id(self, estrutura_id: int) -> EstruturaOperacional | None:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM estruturas_operacionais WHERE id = ?", (estrutura_id,)
            ).fetchone()
            if not row:
                return None
            return EstruturaOperacional(
                id=row["id"],
                oportunidade_id=row["oportunidade_id"],
                tipo=TipoEstrutura(row["tipo"]),
                coefic_alvo=row["coefic_alvo"],
                coefic_mercado=row["coefic_mercado"],
                taxa_ganho=row["taxa_ganho"],
            )
        finally:
            conn.close()

    def get_all(self) -> list[EstruturaOperacional]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM estruturas_operacionais").fetchall()
            return [
                EstruturaOperacional(
                    id=row["id"],
                    oportunidade_id=row["oportunidade_id"],
                    tipo=TipoEstrutura(row["tipo"]),
                    coefic_alvo=row["coefic_alvo"],
                    coefic_mercado=row["coefic_mercado"],
                    taxa_ganho=row["taxa_ganho"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_by_oportunidade(self, oportunidade_id: int) -> list[EstruturaOperacional]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM estruturas_operacionais WHERE oportunidade_id = ?",
                (oportunidade_id,)
            ).fetchall()
            return [
                EstruturaOperacional(
                    id=row["id"],
                    oportunidade_id=row["oportunidade_id"],
                    tipo=TipoEstrutura(row["tipo"]),
                    coefic_alvo=row["coefic_alvo"],
                    coefic_mercado=row["coefic_mercado"],
                    taxa_ganho=row["taxa_ganho"],
                )
                for row in rows
            ]
        finally:
            conn.close()


class PernaRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, perna: PernaOperacao) -> PernaOperacao:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO pernas_operacao
                   (estrutura_id, codigo, lado, quantidade, profundidade, ordem)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (perna.estrutura_id, perna.codigo, perna.lado.value,
                 perna.quantidade, perna.profundidade, perna.ordem)
            )
            conn.commit()
            perna.id = cursor.lastrowid
            return perna
        finally:
            conn.close()

    def get_by_estrutura(self, estrutura_id: int) -> list[PernaOperacao]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM pernas_operacao WHERE estrutura_id = ? ORDER BY ordem",
                (estrutura_id,)
            ).fetchall()
            return [
                PernaOperacao(
                    id=row["id"],
                    estrutura_id=row["estrutura_id"],
                    codigo=row["codigo"],
                    lado=Lado(row["lado"]),
                    quantidade=row["quantidade"],
                    profundidade=row["profundidade"],
                    ordem=row["ordem"],
                )
                for row in rows
            ]
        finally:
            conn.close()


COLUNAS_DIVIDENDOS = "ativo, tipo, data_com, data_ex, data_pagamento, data_aprovacao, valor, tipo_acao, preco_fechamento, fonte"

class DividendoRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, div: dict) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                f"""INSERT INTO dividendos ({COLUNAS_DIVIDENDOS})
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ativo, data_com, tipo, data_pagamento) DO UPDATE SET
                       data_ex=excluded.data_ex,
                       data_aprovacao=excluded.data_aprovacao,
                       valor=excluded.valor,
                       tipo_acao=excluded.tipo_acao,
                       preco_fechamento=excluded.preco_fechamento,
                       fonte=excluded.fonte,
                       atualizado_em=CURRENT_TIMESTAMP""",
                (div["ativo"], div.get("tipo"), div.get("data_com"),
                 div.get("data_ex"), div.get("data_pagamento"),
                 div.get("data_aprovacao"), div.get("valor"),
                 div.get("tipo_acao"), div.get("preco_fechamento"),
                 div.get("fonte", "statusinvest"))
            )
            conn.commit()
        finally:
            conn.close()

    def save_batch(self, dividendos: list[dict]) -> int:
        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                f"""INSERT INTO dividendos ({COLUNAS_DIVIDENDOS})
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ativo, data_com, tipo, data_pagamento) DO UPDATE SET
                       data_ex=excluded.data_ex,
                       data_aprovacao=excluded.data_aprovacao,
                       valor=excluded.valor,
                       tipo_acao=excluded.tipo_acao,
                       preco_fechamento=excluded.preco_fechamento,
                       fonte=excluded.fonte,
                       atualizado_em=CURRENT_TIMESTAMP""",
                [(d["ativo"], d.get("tipo"), d.get("data_com"),
                  d.get("data_ex"), d.get("data_pagamento"),
                  d.get("data_aprovacao"), d.get("valor"),
                  d.get("tipo_acao"), d.get("preco_fechamento"),
                  d.get("fonte", "statusinvest"))
                 for d in dividendos]
            )
            conn.commit()
            return len(dividendos)
        finally:
            conn.close()

    def get_all(self) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM dividendos ORDER BY data_com DESC, ativo"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_ex_hoje(self) -> list[dict]:
        from datetime import date
        hoje = date.today().isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM dividendos WHERE data_ex = ? ORDER BY ativo",
                (hoje,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_proximos(self, dias: int = 30) -> list[dict]:
        from datetime import date, timedelta
        hoje = date.today().isoformat()
        fim = (date.today() + timedelta(days=dias)).isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM dividendos WHERE data_com >= ? AND data_com <= ? ORDER BY data_com, ativo",
                (hoje, fim)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_by_ativo(self, ativo: str) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM dividendos WHERE ativo = ? ORDER BY data_com DESC",
                (ativo,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_ex_range(self, data_inicio: str, data_fim: str) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM dividendos WHERE data_ex BETWEEN ? AND ? ORDER BY data_ex, ativo",
                (data_inicio, data_fim)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_all(self) -> int:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM dividendos")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class FeriadoB3Repository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save_batch(self, feriados: list[dict]) -> int:
        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO feriados_b3 (data, nome, tipo, fonte)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(data) DO UPDATE SET
                       nome=excluded.nome,
                       tipo=excluded.tipo,
                       fonte=excluded.fonte,
                       atualizado_em=CURRENT_TIMESTAMP""",
                [(f["data"], f["nome"], f.get("tipo", "nacional"), f.get("fonte", "brasilapi"))
                 for f in feriados]
            )
            conn.commit()
            return len(feriados)
        finally:
            conn.close()

    def get_all(self) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM feriados_b3 ORDER BY data"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_by_ano(self, ano: int) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM feriados_b3 WHERE data >= ? AND data <= ? ORDER BY data",
                (f"{ano}-01-01", f"{ano}-12-31")
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_anos_disponiveis(self) -> list[int]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT CAST(substr(data, 1, 4) AS INTEGER) AS ano FROM feriados_b3 ORDER BY ano"
            ).fetchall()
            return [r["ano"] for r in rows]
        finally:
            conn.close()

    def delete_by_ano(self, ano: int) -> int:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM feriados_b3 WHERE data >= ? AND data <= ?",
                (f"{ano}-01-01", f"{ano}-12-31")
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_all(self) -> int:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM feriados_b3")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class TaxaAluguelRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, taxa: TaxaAluguel) -> TaxaAluguel:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO taxas_aluguel (ativo, data, taxa_atual, taxa_7d, taxa_28d)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(ativo, data) DO UPDATE SET
                       taxa_atual=excluded.taxa_atual,
                       taxa_7d=excluded.taxa_7d,
                       taxa_28d=excluded.taxa_28d,
                       created_at=CURRENT_TIMESTAMP""",
                (taxa.ativo, taxa.data.isoformat(), taxa.taxa_atual, taxa.taxa_7d, taxa.taxa_28d)
            )
            conn.commit()
            taxa.id = cursor.lastrowid
            return taxa
        finally:
            conn.close()

    def get_latest_by_ativo(self, ativo: str) -> TaxaAluguel | None:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM taxas_aluguel WHERE ativo = ? ORDER BY data DESC LIMIT 1",
                (ativo,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_entity(row)
        finally:
            conn.close()

    def get_latest_all(self) -> dict[str, TaxaAluguel]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                """SELECT t1.* FROM taxas_aluguel t1
                   INNER JOIN (
                       SELECT ativo, MAX(data) as max_data FROM taxas_aluguel GROUP BY ativo
                   ) t2 ON t1.ativo = t2.ativo AND t1.data = t2.max_data"""
            ).fetchall()
            return {row["ativo"]: self._row_to_entity(row) for row in rows}
        finally:
            conn.close()

    def _row_to_entity(self, row) -> TaxaAluguel:
        return TaxaAluguel(
            id=row["id"],
            ativo=row["ativo"],
            data=_parse_date(row["data"]),
            taxa_atual=row["taxa_atual"],
            taxa_7d=row["taxa_7d"],
            taxa_28d=row["taxa_28d"],
            created_at=row["created_at"]
        )


COLUNAS_CALENDARIO_RESULTADOS = "ativo, cnpj, nome_empresa, data_publicacao, trimestre_referencia, tipo_documento, tipo_evento, fonte"

class CalendarioResultadosRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save_batch(self, items: list[dict]) -> int:
        if not items:
            return 0
        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                f"""INSERT INTO calendario_resultados ({COLUNAS_CALENDARIO_RESULTADOS})
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ativo, data_publicacao, trimestre_referencia, tipo_evento) DO UPDATE SET
                       cnpj=excluded.cnpj,
                       nome_empresa=excluded.nome_empresa,
                       tipo_documento=excluded.tipo_documento,
                       fonte=excluded.fonte,
                       atualizado_em=CURRENT_TIMESTAMP""",
                [(d["ativo"], d.get("cnpj"), d.get("nome_empresa"),
                  d["data_publicacao"], d.get("trimestre_referencia"),
                  d.get("tipo_documento", "ITR"), d.get("tipo_evento", "previsto"),
                  d.get("fonte", "webwallet"))
                 for d in items]
            )
            conn.commit()
            return len(items)
        finally:
            conn.close()

    def get_all(self) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM calendario_resultados ORDER BY data_publicacao, ativo"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_proximos(self, dias: int = 60) -> list[dict]:
        from datetime import date, timedelta
        hoje = date.today().isoformat()
        fim = (date.today() + timedelta(days=dias)).isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM calendario_resultados WHERE data_publicacao >= ? AND data_publicacao <= ? ORDER BY data_publicacao, ativo",
                (hoje, fim)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_by_ativo(self, ativo: str) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM calendario_resultados WHERE ativo = ? ORDER BY data_publicacao DESC",
                (ativo,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_publicados(self, ativo: str = "") -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            if ativo:
                rows = conn.execute(
                    "SELECT * FROM calendario_resultados WHERE tipo_evento = 'publicado' AND ativo = ? ORDER BY data_publicacao DESC",
                    (ativo,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM calendario_resultados WHERE tipo_evento = 'publicado' ORDER BY data_publicacao DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_previstos(self, dias: int = 60) -> list[dict]:
        from datetime import date, timedelta
        hoje = date.today().isoformat()
        fim = (date.today() + timedelta(days=dias)).isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM calendario_resultados WHERE tipo_evento = 'previsto' AND data_publicacao >= ? AND data_publicacao <= ? ORDER BY data_publicacao, ativo",
                (hoje, fim)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_all(self) -> int:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM calendario_resultados")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_by_fonte(self, fonte: str) -> int:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM calendario_resultados WHERE fonte = ?", (fonte,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_cnpj_ticker_map(self) -> dict[str, str]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT cnpj, ativo FROM calendario_resultados WHERE cnpj IS NOT NULL AND cnpj != ''"
            ).fetchall()
            return {r["cnpj"]: r["ativo"] for r in rows}
        finally:
            conn.close()


class HistoricoSimulacoesRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def salvar_lote(self, registros: list[dict]) -> int:
        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO historico_simulacoes
                   (id_chassi, estagio, ativo, preco_ativo, strike_call, strike_put,
                    dte_original, iv_call, ratio_call, ratio_put,
                    pnl_cauda_esq, pnl_cauda_dir, be_esq, be_dir, pct_cdi,
                    qtd_acao, premio_call, premio_put, preco_compra,
                    cod_call, cod_put, vencimento_call, vencimento_put,
                    dte_put, dte_extra, iv_put,
                    iv_rank_call, iv_rank_put,
                    net_credito, capital_empregado, pnl_projetado,
                    pct_retorno, pct_cdi_liquido, custo_b3, custo_ir,
                    theta_liquido, delta_total, vega_liquido,
                    valor_put_venc_call, pop_upside, pop_downside,
                    score, score_iv,
                    tipo_estrategia)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?,
                           ?, ?, ?, ?,
                           ?, ?, ?,
                           ?, ?, ?,
                           ?, ?,
                           ?)""",
                [
                    (r["id_chassi"], r["estagio"], r["ativo"],
                     r["preco_ativo"], r["strike_call"], r["strike_put"],
                     r["dte_original"], r["iv_call"],
                     r["ratio_call"], r["ratio_put"],
                     r["pnl_cauda_esq"], r["pnl_cauda_dir"],
                     r.get("be_esq"), r.get("be_dir"), r["pct_cdi"],
                     r.get("qtd_acao", 100),
                     r.get("premio_call", 0), r.get("premio_put", 0),
                     r.get("preco_compra", 0),
                     r.get("cod_call"), r.get("cod_put"),
                     r.get("vencimento_call"), r.get("vencimento_put"),
                     r.get("dte_put"), r.get("dte_extra"), r.get("iv_put"),
                     r.get("iv_rank_call"), r.get("iv_rank_put"),
                     r.get("net_credito"), r.get("capital_empregado"), r.get("pnl_projetado"),
                     r.get("pct_retorno"), r.get("pct_cdi_liquido"), r.get("custo_b3"), r.get("custo_ir"),
                     r.get("theta_liquido"), r.get("delta_total"), r.get("vega_liquido"),
                     r.get("valor_put_venc_call"), r.get("pop_upside"), r.get("pop_downside"),
                     r.get("score"), r.get("score_iv"),
                     r.get("tipo_estrategia", "Calendario"))
                    for r in registros
                ]
            )
            conn.commit()
            return len(registros)
        finally:
            conn.close()

    def listar(self, limite: int = 500) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM historico_simulacoes ORDER BY detectado_em DESC LIMIT ?",
                (limite,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def listar_por_chassi(self, id_chassi: str) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM historico_simulacoes WHERE id_chassi = ? ORDER BY estagio",
                (id_chassi,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def contar(self) -> int:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) AS total FROM historico_simulacoes").fetchone()
            return row["total"] if row else 0
        finally:
            conn.close()

    def limpar(self) -> int:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM historico_simulacoes")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def exportar_tudo(self) -> list[dict]:
        rows = self.listar(limite=999999)
        return rows
