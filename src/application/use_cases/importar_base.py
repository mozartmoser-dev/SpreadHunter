from pathlib import Path

from src.application.dtos.dtos import ImportarResultado
from src.infrastructure.importers.excel_importer import ExcelImporter
from src.infrastructure.persistence.repositories.repositories import InstrumentoRepository


class ImportarBaseUseCase:
    def __init__(self, db_path=None):
        self.repo = InstrumentoRepository(db_path)

    def executar(self, filepath: str | Path) -> ImportarResultado:
        importer = ExcelImporter(filepath)
        instrumentos = importer.importar()

        removidos = self.repo.delete_all()
        total = self.repo.save_batch(instrumentos)

        ativos = sorted(set(i.ativo for i in instrumentos))

        return ImportarResultado(
            total_importados=total,
            total_removidos=removidos,
            ativos=ativos,
        )
