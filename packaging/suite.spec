# -*- mode: python ; coding: utf-8 -*-
# Civic Media Studio — PyInstaller onedir spec (specs/09 §5).
#
# Build via packaging/build_suite.sh, from the repo's OWN .venv (a foreign
# venv is "ALWAYS the wrong thing to do" per PyInstaller and a hard error in
# 7.0). onedir, not onefile: onefile would unpack ~364 MB to a temp dir on
# every launch and break the signing story — the seal must cover the tree
# that runs, not an archive that extracts (specs/09 §1).

import pathlib
import re

from PyInstaller.utils.hooks import collect_data_files

REPO = pathlib.Path(SPECPATH).resolve().parent
VENDOR = REPO / "packaging" / "vendor" / "ffmpeg"

# Version from pyproject.toml, sanitized to the numeric triple CFBundle wants.
_pyproject = (REPO / "pyproject.toml").read_text()
_raw = re.search(r'^version\s*=\s*"([^"]+)"', _pyproject, re.M).group(1)
VERSION = re.match(r"(\d+\.\d+\.\d+)", _raw).group(1)

datas = [
    # Destinations are load-bearing: suite/server.py resolves
    # Path(__file__).parent/"static" and depth resolves parents[2]/templates
    # — both verified to need NO _MEIPASS branch as long as these land at
    # exactly these relative paths (specs/09 §5, "non-issues").
    (str(REPO / "suite" / "static"), "suite/static"),
    (str(REPO / "depth" / "templates"), "depth/templates"),
    # Interpreter's seed glossaries (interpreter/glossaries/<town>.json).
    # pyproject's package-data declares these for a WHEEL build; PyInstaller
    # doesn't read package-data, so a frozen Interpreter would find no seed
    # (glossary.SEEDS.is_dir() False -> towns() empty, load() an empty
    # scaffold). Ship them by name.
    (str(REPO / "interpreter" / "glossaries"), "interpreter/glossaries"),
    # The web edition's reader shell. web/emit.py reads these at press time;
    # today the frozen press path refuses earlier (no site/ to press into),
    # so this is insurance, not a live dependency — but the day the desk
    # presses an edition from the frozen app, absence here becomes a crash.
    (str(REPO / "web" / "static"), "web/static"),
]
# faster-whisper ships silero_vad_v6.onnx as package data and hooks-contrib
# 2026.6 has NO hook for it; without this Scribe dies on the FIRST transcribe
# (vad_filter=True -> get_assets_path()) — measured, specs/09 §5.
datas += collect_data_files("faster_whisper")

binaries = [
    # The LGPL ffmpeg/ffprobe from packaging/build_ffmpeg.sh. czcore/tools.py
    # resolves sys._MEIPASS/czbin/<name> when frozen — the two paths must
    # move together.
    (str(VENDOR / "bin" / "ffmpeg"), "czbin"),
    (str(VENDOR / "bin" / "ffprobe"), "czbin"),
]

a = Analysis(
    [str(REPO / "packaging" / "launch_suite.py")],
    pathex=[str(REPO)],
    binaries=binaries,
    datas=datas,
    # The Cocoa backend is reached by a static function-level import and is
    # already in the TOC; naming it is belt-and-braces (specs/09 §5). The
    # Make-wave packages and Pillow arrive through suite.server's own
    # imports; named here for the same reason. The community wing
    # (publisher/memory/interpreter/narrator) arrives the same way — through
    # suite/tools/*.py's `from <pkg> import ...` and server.py's register
    # hooks — and czcore.mt / czcore.tts are imported lazily inside
    # functions (a shape PyInstaller's static walk can miss), so both are
    # named explicitly.
    hiddenimports=["webview.platforms.cocoa",
                   "highlighter", "grabber", "indexer", "slate",
                   "publisher", "memory", "interpreter", "narrator",
                   # czcore.mt / czcore.tts / czcore.vision / czcore.mt_local and
                   # pypdf are all imported lazily inside functions (a shape the
                   # static walk misses); Memory's documents.py imports pypdf,
                   # the local-model engines import their runtimes on demand.
                   "czcore.mt", "czcore.tts", "czcore.vision", "czcore.mt_local",
                   "pypdf",
                   "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
                   "PIL.ImageFilter"],
    excludes=[
        # Stencil's torch/SAM2 runtime is the v1.1 on-demand component:
        # torch alone triples the bundle (364 MB -> 1.1 GB, measured). The
        # Stencil page says so honestly when frozen (suite/tools/stencil.py).
        "torch", "torchvision", "torchgen", "functorch", "sam2", "training",
        "triton", "networkx", "sympy", "mpmath",
        "hydra", "omegaconf", "iopath", "portalocker",
        # builder/dev-only, never runtime
        "PyInstaller", "pip", "setuptools", "wheel",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Civic Media Studio",
    console=False,
    target_arch="arm64",   # the stack has no universal2 wheels (specs/09 §1)
)

coll = COLLECT(exe, a.binaries, a.datas, name="Civic Media Studio")

app = BUNDLE(
    coll,
    name="Civic Media Studio.app",
    bundle_identifier="org.civicmedia.studio",
    icon=str(REPO / "packaging" / "icon.icns"),   # make_icon.py, committed
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "Civic Media Studio",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.video",
        # LSMinimumSystemVersion is MEASURED and patched in by
        # build_suite.sh after the tree exists (max minos over every Mach-O)
        # — declaring a floor lower than the binaries' own is exactly the
        # kind of quiet lie the covenant bans.
    },
)
