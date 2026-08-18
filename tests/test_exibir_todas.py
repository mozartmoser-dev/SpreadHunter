from types import SimpleNamespace

from src.ui.desktop.filtros_exibicao import _filtra_exibir_todas_viavel


def _box(viavel=True):
    return SimpleNamespace(classificacao="1BOX", viavel=viavel)


class TestFiltraExibirTodas:
    def test_viavel_oculta_nao_viaveis_quando_desmarcado(self):
        rs = [_box(True), _box(False)]
        out = _filtra_exibir_todas_viavel(rs, mostrar_todas=False)
        assert all(r.viavel for r in out)
        assert len(out) == 1

    def test_viavel_mostra_tudo_quando_marcado(self):
        rs = [_box(True), _box(False)]
        out = _filtra_exibir_todas_viavel(rs, mostrar_todas=True)
        assert len(out) == 2
