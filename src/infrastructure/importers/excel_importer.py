import re
from datetime import date, datetime
from pathlib import Path

import openpyxl

from src.domain.entities.instrumento_opcional import InstrumentoOpcional, TipoOpcao


TIPO_MAP = {"A": TipoOpcao.AMERICANA, "E": TipoOpcao.EUROPEIA}


def extrair_strike(codigo: str) -> float | None:
    if not codigo:
        return None
    # Busca a parte numérica no final do código (ex: PETRA300 -> 300)
    nums = re.search(r'(\d+)[a-zA-Z]?$', codigo)
    if not nums:
        return None
    raw = nums.group(1)
    n_len = len(raw)
    
    try:
        val = float(raw)
        if n_len <= 2:
            return val
        if n_len == 3: # Ex: 300 -> 30.0
            return val / 10.0
        if n_len == 4: # Ex: 3004 -> 30.04
            return val / 100.0
        if n_len >= 5: # Ex: 30040 -> 30.04
            return val / 1000.0
        return val
    except:
        return None


def parse_vencimento(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
    return None


class ExcelImporter:
    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)

    def importar(self) -> list[InstrumentoOpcional]:
        if not self.filepath.exists():
            raise FileNotFoundError(str(self.filepath))
        wb = openpyxl.load_workbook(str(self.filepath), data_only=True)
        ws = wb.active
        instrumentos = []
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
            if not row or len(row) < 5:
                continue
            ativo = row[0]
            vencimento_raw = row[1]
            cod_put = row[2]
            cod_call = row[3]
            tipo_raw = row[4]
            if not ativo or not cod_put or not cod_call:
                continue
            vencimento = parse_vencimento(vencimento_raw)
            if vencimento is None:
                continue
            tipo_str = str(tipo_raw).strip().upper() if tipo_raw else "A"
            tipo_opcao = TIPO_MAP.get(tipo_str, TipoOpcao.AMERICANA)
            instrumentos.append(InstrumentoOpcional(
                ativo=str(ativo).strip(),
                cod_put=str(cod_put).strip(),
                cod_call=str(cod_call).strip(),
                vencimento=vencimento,
                tipo_opcao=tipo_opcao,
            ))
        wb.close()
        return instrumentos
