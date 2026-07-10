from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from src.domain.entities.workspace_snapshot import WorkspaceSnapshot
from src.infrastructure.persistence.repositories.workspace_repository import (
    WorkspaceSnapshotRepository,
    APP_VERSION,
)
from src.infrastructure.persistence.repositories.repositories import ParametroRepository

_logger = logging.getLogger(__name__)


_QSETTINGS_KEYS_CONHECIDAS = [
    "parametros/last_section",
    "colunas_ocultas",
    "colunas_ocultas_vendidas",
    "colunas_ocultas_coberta",
    "main_table_order",
    "vendidas_table_order",
    "coberta_table_order",
    "colar_table_order",
    "colar_cal_table_order",
    "box_table_order",
    "mpp_table_order",
]


def _qsettings() -> QSettings:
    return QSettings("Spreadhunter", "DesktopMonitor")


class WorkspaceService:
    QSETTINGS_ORG = "Spreadhunter"
    QSETTINGS_APP = "DesktopMonitor"

    def __init__(
        self,
        parametro_repo: ParametroRepository | None = None,
        snapshot_repo: WorkspaceSnapshotRepository | None = None,
        db_path: Path | str | None = None,
    ) -> None:
        self.db_path = db_path
        self._param_repo = parametro_repo or ParametroRepository(db_path)
        self._snapshot_repo = snapshot_repo or WorkspaceSnapshotRepository(db_path)

    def _snapshot_repo_inst(self) -> WorkspaceSnapshotRepository:
        return self._snapshot_repo

    def _param_repo_inst(self) -> ParametroRepository:
        return self._param_repo

    def ler_parametros_atuais(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for p in self._param_repo_inst().list_all():
            try:
                valor = float(p.valor)
            except (TypeError, ValueError):
                valor = p.valor
            out[p.chave] = {
                "valor": valor,
                "estrategia": p.estrategia,
                "descricao": p.descricao or "",
            }
        return out

    def ler_workspace_atual(self) -> dict[str, Any]:
        qs = self._qsettings()
        out: dict[str, Any] = {}
        for key in _QSETTINGS_KEYS_CONHECIDAS:
            try:
                valor = qs.value(key)
            except Exception as e:
                _logger.warning("Falha lendo QSettings[%s]: %s", key, e)
                continue
            if valor is None:
                continue
            out[key] = valor
        return out

    def _qsettings(self) -> QSettings:
        org = os.environ.get("SPREADHUNTER_QSETTINGS_ORG", self.QSETTINGS_ORG)
        app = os.environ.get("SPREADHUNTER_QSETTINGS_APP", self.QSETTINGS_APP)
        return QSettings(org, app)

    def criar_snapshot(self, nome: str) -> WorkspaceSnapshot:
        snapshot = WorkspaceSnapshot(
            id=None,
            nome=nome,
            created_at=_now(),
            is_system=False,
            app_version=APP_VERSION,
            parametros=self.ler_parametros_atuais(),
            workspace=self.ler_workspace_atual(),
        )
        return self._snapshot_repo_inst().criar(snapshot)

    def restaurar(self, snapshot_id: int) -> None:
        snapshot = self._snapshot_repo_inst().obter(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot id={snapshot_id} não encontrado")

        self._aplicar_parametros(snapshot.parametros)
        self._aplicar_workspace(snapshot.workspace)

    def _aplicar_parametros(self, parametros: dict[str, dict[str, Any]]) -> None:
        for chave, raw in parametros.items():
            if not isinstance(raw, dict):
                continue
            valor = raw.get("valor")
            estrategia = raw.get("estrategia", "GERAL")
            descricao = raw.get("descricao", "")
            valor_str = str(valor) if valor is not None else ""
            from src.domain.entities.parametro_operacional import ParametroOperacional
            p = ParametroOperacional(
                chave=chave,
                valor=valor_str,
                estrategia=estrategia or "GERAL",
                descricao=descricao or "",
            )
            try:
                self._param_repo_inst().save(p)
            except Exception as e:
                _logger.warning("Falha ao restaurar parametro %s: %s", chave, e)
        self._param_repo_inst().invalidate_cache()

    def _aplicar_workspace(self, workspace: dict[str, Any]) -> None:
        qs = self._qsettings()
        for key in _QSETTINGS_KEYS_CONHECIDAS:
            if key in workspace:
                valor = workspace[key]
                try:
                    qs.setValue(key, valor)
                except (TypeError, ValueError) as e:
                    _logger.warning("QSettings invalido para chave %s: %s", key, e)
            else:
                try:
                    qs.remove(key)
                except Exception:
                    pass
        try:
            qs.sync()
        except Exception:
            pass

    def garantir_system_default(self) -> WorkspaceSnapshot | None:
        if self._snapshot_repo_inst().existe_system_default():
            return None
        return self._snapshot_repo_inst().criar_system_default_se_ausente(
            parametros=self.ler_parametros_atuais(),
            workspace=self.ler_workspace_atual(),
        )

    def exportar_arquivo(self, snapshot_id: int, destino: Path) -> Path:
        snapshot = self._snapshot_repo_inst().obter(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot id={snapshot_id} não encontrado")
        destino = Path(destino)
        if destino.suffix.lower() != ".shwsp":
            destino = destino.with_suffix(".shwsp")
        destino.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot.to_json()
        with open(str(destino), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return destino

    def importar_arquivo(self, origem: Path) -> WorkspaceSnapshot:
        origem = Path(origem)
        if not origem.exists():
            raise FileNotFoundError(str(origem))
        with open(str(origem), "r", encoding="utf-8") as f:
            payload = json.load(f)
        snapshot = WorkspaceSnapshot.from_json(payload)
        if not snapshot.app_version:
            snapshot.app_version = APP_VERSION
        snapshot.is_system = False
        nome_original = snapshot.nome
        if self._snapshot_repo_inst().obter_por_nome(snapshot.nome) is not None:
            snapshot.nome = self._proximo_nome_livre(snapshot.nome)
        return self._snapshot_repo_inst().criar(snapshot)

    def _proximo_nome_livre(self, base: str) -> str:
        repo = self._snapshot_repo_inst()
        n = 2
        novo = f"{base} ({n})"
        while repo.obter_por_nome(novo) is not None:
            n += 1
            novo = f"{base} ({n})"
        return novo


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
