import json
from datetime import date, datetime

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao
from src.domain.entities.oportunidade import Oportunidade, ClassificacaoOp
from src.domain.entities.estrutura_operacional import EstruturaOperacional, TipoEstrutura
from src.domain.entities.perna_operacao import PernaOperacao, Lado
from src.domain.entities.parametro_operacional import ParametroOperacional
from src.infrastructure.persistence.database import get_connection


def _parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


class InstrumentoRepository:
    _cache_all = None
    _cache_mapped = None

    def __init__(self, db_path=None):
        self.db_path = db_path

    @classmethod
    def invalidate_cache(cls):
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
        if self.__class__._cache_all is not None:
            return self.__class__._cache_all
        
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM instrumentos_base").fetchall()
            self.__class__._cache_all = [
                InstrumentoOpcional(
                    id=row["id"],
                    ativo=row["ativo"],
                    cod_put=row["cod_put"],
                    cod_call=row["cod_call"],
                    vencimento=_parse_date(row["vencimento"]),
                    tipo_opcao=TipoOpcao(row["tipo_opcao"]),
                )
                for row in rows
            ]
            return self.__class__._cache_all
        finally:
            conn.close()

    def get_all_mapped(self) -> dict[str, InstrumentoOpcional]:
        """Retorna dicionário {cod_put: InstrumentoOpcional}."""
        if self.__class__._cache_mapped is not None:
            return self.__class__._cache_mapped
        
        all_inst = self.get_all()
        self.__class__._cache_mapped = {i.cod_put: i for i in all_inst}
        return self.__class__._cache_mapped

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
                    strike=row["strike"],
                )
                for row in rows
            ]
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
    _cache = None

    def __init__(self, db_path=None):
        self.db_path = db_path

    @classmethod
    def invalidate_cache(cls):
        cls._cache = None

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
        if self.__class__._cache is None:
            self._fill_cache()
        return self.__class__._cache.get(chave)

    def _fill_cache(self):
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM parametros_operacionais").fetchall()
            self.__class__._cache = {}
            for row in rows:
                val_raw = row["valor"]
                try:
                    valor = float(val_raw)
                except (ValueError, TypeError):
                    valor = val_raw
                self.__class__._cache[row["chave"]] = ParametroOperacional(
                    id=row["id"], chave=row["chave"], valor=valor,
                    estrategia=row["estrategia"], descricao=row["descricao"]
                )
        finally:
            conn.close()

    def get_by_estrategia(self, estrategia: str) -> list[ParametroOperacional]:
        if self.__class__._cache is None:
            self._fill_cache()
        return [p for p in self.__class__._cache.values() if p.estrategia == estrategia]

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

    def get_historico_completo(self) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                """SELECT o.id, o.created_at, i.ativo, o.strike, o.operacao, o.dias, o.preco_ativo,
                          o.custo_box, o.pct_ganho_box, o.pct_cdi_box,
                          o.custo_sbth, o.pct_ganho_sbth, o.pct_cdi_sbth,
                          o.snapshot_mercado
                   FROM oportunidades o
                   JOIN instrumentos_base i ON o.instrumento_id = i.id
                   ORDER BY o.created_at DESC"""
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
