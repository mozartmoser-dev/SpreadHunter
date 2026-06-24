import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    nome: str
    entrada: int
    saida: int
    rejeitados: int = 0
    motivo: str = ""


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

    def add_stage(self, nome: str, entrada: int, saida: int, motivo: str = ""):
        self.stages.append(PipelineStage(
            nome=nome,
            entrada=entrada,
            saida=saida,
            rejeitados=entrada - saida,
            motivo=motivo,
        ))

    @property
    def total_entrada(self) -> int:
        return self.stages[0].entrada if self.stages else 0

    @property
    def total_saida(self) -> int:
        return self.stages[-1].saida if self.stages else 0

    def __bool__(self):
        return len(self.stages) > 0
