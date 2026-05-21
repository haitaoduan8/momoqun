# PyInstaller：无控制台（windowed）。Windows 产出 dist/momoqun/momoqun.exe
# 必须在 Windows 上构建 —— 不能在 Mac 上交叉编译 .exe
# 构建：pip install pyinstaller && pyinstaller momoqun.spec
# 采用 COLLECT 目录模式（非 onefile），因为运行时需要读取 webui/templates/ 和 config/

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('webui/templates', 'webui/templates'),
        ('config', 'config'),
    ],
    hiddenimports=[
        'fastapi',
        'uvicorn',
        'yaml',
        'starlette',
        'anyio',
        'httptools',
        'uvloop',
        'websockets',
        'watchfiles',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'uiautomator2',
        'pkg_resources',
        'setuptools',
        'device_manager',
        'core',
        'data',
        'actions',
        'utils',
        'main',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='momoqun',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    exclude_binaries=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='momoqun',
)
