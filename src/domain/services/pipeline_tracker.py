import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    nome: str
    entrada: int
    saida: int
    rejeitados: int = 0
    motivo: str = ""
    tempo_s: float = 0.0


class PipelineTracker:
    """Coleta dados do pipeline de filtros sem afetar a execução.

    Uso:
        tracker = PipelineTracker()
        use_case.varrer(..., pipeline_tracker=tracker)
        for stage in tracker.stages:
            print(stage.nome, stage.entrada, "→", stage.saida)
    """

    def __init__(self, nome_estrategia: str = ""):
        self.nome_estrategia = nome_estrategia
        self.stages: list[PipelineStage] = []
        self._last_t: float = time.perf_counter()

    def add_stage(self, nome: str, entrada: int, saida: int, motivo: str = "",
                  tempo_s: float | None = None):
        now = time.perf_counter()
        if tempo_s is None:
            tempo_s = now - self._last_t
        self._last_t = now
        self.stages.append(PipelineStage(
            nome=nome,
            entrada=entrada,
            saida=saida,
            rejeitados=entrada - saida,
            motivo=motivo,
            tempo_s=tempo_s,
        ))

    @property
    def total_entrada(self) -> int:
        return self.stages[0].entrada if self.stages else 0

    @property
    def total_saida(self) -> int:
        return self.stages[-1].saida if self.stages else 0

    def __bool__(self):
        return len(self.stages) > 0
