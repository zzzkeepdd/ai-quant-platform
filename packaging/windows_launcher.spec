# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


root = Path.cwd()

a = Analysis(
    [str(root / "packaging" / "windows_launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "frontend" / "dist"), "frontend/dist"),
        (str(root / "strategies"), "strategies"),
        (str(root / "backend" / "data_cache" / "market_data"), "backend/data_cache/market_data"),
    ],
    hiddenimports=[
        "backend.app.main",
        "backend.app.ai",
        "backend.app.backtest",
        "backend.app.exchange",
        "backend.app.market_data",
        "backend.app.trading",
        "backend.app.strategy_loader",
        "ccxt",
        "openai",
        "cryptography",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numba",
        "onnxruntime",
        "openpyxl",
        "PIL",
        "pyarrow",
        "pytest",
        "scipy",
        "sklearn",
        "sympy",
        "tensorflow",
        "torch",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIQuantPlatform",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AIQuantPlatform",
)
