from PySide6.QtWidgets import QApplication


def copiar_basket_pnt(linhas: list[str]) -> None:
    clipboard = QApplication.clipboard()
    clipboard.setText("\r\n".join(linhas))


def fmt_br(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
