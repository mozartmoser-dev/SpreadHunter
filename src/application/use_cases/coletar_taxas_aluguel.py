from datetime import date
import time
import logging
from src.infrastructure.persistence.repositories.repositories import (
    InstrumentoRepository,
    ParametroRepository,
    TaxaAluguelRepository,
)
from src.domain.entities.taxa_aluguel import TaxaAluguel
from src.infrastructure.integrations.investsite_client import InvestSiteClient

logger = logging.getLogger(__name__)


class ColetarTaxasAluguelUseCase:
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.inst_repo = InstrumentoRepository(db_path)
        self.param_repo = ParametroRepository(db_path)
        self.taxa_repo = TaxaAluguelRepository(db_path)

        timeout_p = self.param_repo.get_by_chave("investsite_timeout_ms")
        timeout_s = float(timeout_p.valor) / 1000.0 if timeout_p else 10.0
        self.client = InvestSiteClient(timeout_seconds=timeout_s)

        delay_p = self.param_repo.get_by_chave("investsite_delay_ms")
        self.delay_s = float(delay_p.valor) / 1000.0 if delay_p else 0.5

    def executar(self, callback_progresso=None) -> dict:
        habilitado = self.param_repo.get_by_chave("taxa_aluguel_habilitado")
        if not habilitado or float(habilitado.valor) == 0.0:
            logger.info("Coleta de taxas de aluguel desabilitada nos parâmetros.")
            return {"status": "desabilitado", "sucessos": 0, "falhas": 0}

        instrumentos = self.inst_repo.get_all()
        ativos_unicos = sorted(list(set(inst.ativo for inst in instrumentos)))

        resumo = {"status": "sucesso", "sucessos": 0, "falhas": 0, "erros": []}
        total = len(ativos_unicos)

        for idx, ativo in enumerate(ativos_unicos):
            if callback_progresso:
                callback_progresso(idx + 1, total, ativo)

            dados = self.client.fetch_taxa_aluguel(ativo)
            if dados:
                taxa = TaxaAluguel(
                    ativo=dados["ativo"],
                    data=dados["data"],
                    taxa_atual=dados["taxa_atual"],
                    taxa_7d=dados["taxa_7d"],
                    taxa_28d=dados["taxa_28d"]
                )
                self.taxa_repo.save(taxa)
                resumo["sucessos"] += 1
            else:
                resumo["falhas"] += 1
                resumo["erros"].append(ativo)

            if idx < total - 1 and self.delay_s > 0:
                time.sleep(self.delay_s)

        return resumo
