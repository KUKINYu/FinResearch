# -*- mode: python ; coding: utf-8 -*-
# FinEngine 打包配置：python -m PyInstaller engine.spec
# 产物：dist/finengine.exe（--onefile，控制台程序，Electron 通过 stdout ready 行握手）

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    # uvicorn 使用动态导入，PyInstaller 检测不到，必须显式声明
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='finengine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 控制台程序：ready 行握手需要 stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
