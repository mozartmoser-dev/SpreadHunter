from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
from src.infrastructure.persistence.database import get_connection

_logger = logging.getLogger(__name__)

APP_VERSION = "Spreadhunter"


class WorkspaceSnapshotRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def listar(self) -> list[WorkspaceSnapshot]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM workspace_snapshots ORDER BY is_system DESC, created_at DESC"
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    def obter(self, snapshot_id: int) -> WorkspaceSnapshot | None:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM workspace_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            return self._row_to_snapshot(row) if row else None
        finally:
            conn.close()

    def obter_por_nome(self, nome: str) -> WorkspaceSnapshot | None:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM workspace_snapshots WHERE nome = ?", (nome,)
            ).fetchone()
            return self._row_to_snapshot(row) if row else None
        finally:
            conn.close()

    def criar(self, snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot:
        conn = get_connection(self.db_path)
        try:
            parametros_json, workspace_json = snapshot.serialize()
            cursor = conn.execute(
                """INSERT INTO workspace_snapshots
                       (nome, created_at, is_system, app_version, parametros_json, workspace_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.nome,
                    snapshot.created_at.isoformat()
                    if isinstance(snapshot.created_at, datetime)
                    else datetime.now(timezone.utc).isoformat(),
                    1 if snapshot.is_system else 0,
                    snapshot.app_version,
                    parametros_json,
                    workspace_json,
                ),
            )
            conn.commit()
            snapshot.id = cursor.lastrowid
            return snapshot
        finally:
            conn.close()

    def renomear(self, snapshot_id: int, novo_nome: str) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "UPDATE workspace_snapshots SET nome = ? WHERE id = ?",
                (novo_nome, snapshot_id),
            )
            conn.commit()
        finally:
            conn.close()

    def apagar(self, snapshot_id: int) -> bool:
        snapshot = self.obter(snapshot_id)
        if snapshot is None:
            return False
        if snapshot.is_system:
            _logger.warning(
                "Tentativa de apagar snapshot de sistema id=%s bloqueada.", snapshot_id
            )
            return False
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM workspace_snapshots WHERE id = ?", (snapshot_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def existe_system_default(self) -> bool:
        return self.obter_por_nome(WorkspaceSnapshot.SYSTEM_DEFAULT_NAME) is not None

    def criar_system_default_se_ausente(
        self,
        parametros: dict,
        workspace: dict,
    ) -> WorkspaceSnapshot | None:
        if self.existe_system_default():
            return None
        snapshot = WorkspaceSnapshot(
            id=None,
            nome=WorkspaceSnapshot.SYSTEM_DEFAULT_NAME,
            created_at=datetime.now(timezone.utc),
            is_system=True,
            app_version=APP_VERSION,
            parametros=parametros,
            workspace=workspace,
        )
        return self.criar(snapshot)

    @staticmethod
    def _row_to_snapshot(row) -> WorkspaceSnapshot:
        created_at_raw = row["created_at"]
        if isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = datetime.now(timezone.utc)
        elif isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        else:
            created_at = datetime.now(timezone.utc)

        return WorkspaceSnapshot.deserialize(
            id=row["id"],
            nome=row["nome"],
            created_at=created_at,
            is_system=bool(row["is_system"]),
            app_version=row["app_version"] or APP_VERSION,
            parametros_json=row["parametros_json"] or "{}",
            workspace_json=row["workspace_json"] or "{}",
        )
