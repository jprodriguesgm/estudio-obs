# PyInstaller: monta o "Estudio" (Mac: .app; Windows: pasta com o .exe).
#   pyinstaller --noconfirm packaging/estudio.spec
# Antes (o roteiro do GitHub faz):
#   modelos/whisper-large-v3-turbo/        (Mac: modelo do mlx-whisper)
#   modelos/ggml-large-v3-turbo-q8_0.bin   (Windows: modelo do whisper.cpp)
#   whisper/whisper-cli.exe + DLLs         (Windows: whisper.cpp)
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT))
from estudio import __version__  # noqa: E402

IS_MAC = sys.platform == "darwin"
IS_WIN = os.name == "nt"
NAME = "Estudio"
ICON = ROOT / "packaging" / "icon" / ("icon.icns" if IS_MAC else "icon.ico")

datas = [(str(ROOT / "estudio" / "ui"), "estudio/ui")]
binaries = []
hidden = collect_submodules("estudio")

# ffmpeg (tira o áudio do vídeo para o Whisper): vai como programa (no Mac, assinado junto com o app)
import imageio_ffmpeg  # noqa: E402
binaries.append((imageio_ffmpeg.get_ffmpeg_exe(), "imageio_ffmpeg/binaries"))
hidden += ["imageio_ffmpeg"]

modelos = ROOT / "modelos"
if IS_MAC:
    for pacote in ("mlx", "mlx_whisper", "tiktoken", "tiktoken_ext"):
        d, b, h = collect_all(pacote)
        datas += d
        binaries += b
        hidden += h
    hidden += ["tiktoken_ext.openai_public", "scipy.signal", "numba", "llvmlite", "tqdm", "more_itertools"]
    if (modelos / "whisper-large-v3-turbo" / "config.json").is_file():
        datas.append((str(modelos / "whisper-large-v3-turbo"), "modelos/whisper-large-v3-turbo"))
    else:
        print("AVISO: sem o modelo do mlx-whisper (modelos/whisper-large-v3-turbo)")
if IS_WIN:
    if (modelos / "ggml-large-v3-turbo-q8_0.bin").is_file():
        datas.append((str(modelos / "ggml-large-v3-turbo-q8_0.bin"), "modelos"))
    else:
        print("AVISO: sem o modelo do whisper.cpp (modelos/ggml-large-v3-turbo-q8_0.bin)")
    if (ROOT / "whisper").is_dir():
        datas.append((str(ROOT / "whisper"), "whisper"))
    else:
        print("AVISO: sem o whisper.cpp (pasta whisper/)")

a = Analysis(
    [str(ROOT / "packaging" / "app_main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    # o torch só serve para converter modelos; o mlx-whisper não usa na transcrição
    excludes=["torch", "matplotlib", "pytest", "IPython", "pandas", "PIL"] + ([] if IS_WIN else ["tkinter"]),
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, icon=str(ICON), upx=False)
extra = []
if IS_WIN:
    # a mesma coisa com saída de texto: usada para transcrever (sem abrir janela) e para o diagnóstico
    extra.append(EXE(pyz, a.scripts, [], exclude_binaries=True, name="estudio-terminal", console=True,
                     icon=str(ICON), upx=False))

coll = COLLECT(exe, *extra, a.binaries, a.datas, name=NAME, upx=False)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=NAME + ".app",
        icon=str(ICON),
        bundle_identifier="br.pucminas.npd.estudio",
        version=__version__,
        info_plist={
            "CFBundleDisplayName": "Estúdio",
            "CFBundleName": "Estúdio",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSMinimumSystemVersion": "13.5",     # o mlx (Whisper do Mac) pede macOS 13.5 ou mais novo
            "LSUIElement": True,                  # sem ícone no Dock: o app é a página no navegador
            "NSHighResolutionCapable": True,
            "NSDesktopFolderUsageDescription": "O Estúdio organiza as gravações do OBS na pasta que você escolher.",
            "NSDocumentsFolderUsageDescription": "O Estúdio organiza as gravações do OBS na pasta que você escolher.",
            "NSDownloadsFolderUsageDescription": "O Estúdio organiza as gravações do OBS na pasta que você escolher.",
            "NSRemovableVolumesUsageDescription": "O Estúdio lê as gravações do OBS no disco externo (SSD).",
            "NSNetworkVolumesUsageDescription": "O Estúdio lê as gravações da pasta de rede que você escolher.",
            "NSAppleEventsUsageDescription": "O Estúdio abre a janela para escolher pastas e mostra os vídeos no Finder.",
        },
    )
