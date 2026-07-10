from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class WorkspaceSnapshot:
    id: int | None
    nome: str
    created_at: datetime
    is_system: bool
    app_version: str
    parametros: dict[str, dict[str, Any]] = field(default_factory=dict)
    workspace: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "app_version": self.app_version,
            "saved_at": self.created_at.isoformat(),
            "nome": self.nome,
            "is_system": self.is_system,
            "parametros": self.parametros,
            "workspace": self.workspace,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "WorkspaceSnapshot":
        return cls(
            id=None,
            nome=str(payload.get("nome", "Sem nome")),
            created_at=datetime.fromisoformat(payload["saved_at"])
            if "saved_at" in payload else datetime.now(),
            is_system=bool(payload.get("is_system", False)),
            app_version=str(payload.get("app_version", "")),
            parametros=dict(payload.get("parametros", {})),
            workspace=dict(payload.get("workspace", {})),
        )

    def serialize(self) -> tuple[str, str]:
        return (
            json.dumps(self.parametros, ensure_ascii=False, sort_keys=True),
            json.dumps(self.workspace, ensure_ascii=False, sort_keys=True),
        )

    @classmethod
    def deserialize(
        cls,
        *,
        id: int | None,
        nome: str,
        created_at: datetime,
        is_system: bool,
        app_version: str,
        parametros_json: str,
        workspace_json: str,
    ) -> "WorkspaceSnapshot":
        try:
            parametros = json.loads(parametros_json) if parametros_json else {}
        except (ValueError, TypeError):
            parametros = {}
        try:
            workspace = json.loads(workspace_json) if workspace_json else {}
        except (ValueError, TypeError):
            workspace = {}
        if not isinstance(parametros, dict):
            parametros = {}
        if not isinstance(workspace, dict):
            workspace = {}
        return cls(
            id=id,
            nome=nome,
            created_at=created_at,
            is_system=is_system,
            app_version=app_version,
            parametros=parametros,
            workspace=workspace,
        )

    SYSTEM_DEFAULT_NAME = "system_default"
