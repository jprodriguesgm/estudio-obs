"""Estúdio — organiza sozinho as gravações do OBS por professor, pela agenda do dia."""
__version__ = "1.1.1"


def ui_ok() -> bool:
    """A tela foi junto (confere o app empacotado)."""
    from pathlib import Path
    return (Path(__file__).resolve().parent / "ui" / "index.html").is_file()
