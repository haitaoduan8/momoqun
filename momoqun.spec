# PyInstaller：无控制台（windowed）。Windows 产出 dist/momoqun/momoqun.exe
# 必须在 Windows 上构建 —— 不能在 Mac 上交叉编译 .exe
# 构建：pip install pyinstaller && pyinstaller momoqun.spec
# 采用 COLLECT 目录模式（非 onefile），因为运行时需要读取 webui/templates/ 和 config/

import os as _os
import adbutils as _adbutils
import uiautomator2 as _u2

_adb_src = _os.path.join(_os.path.dirname(_adbutils.__file__), 'binaries')
_u2_assets = _os.path.join(_os.path.dirname(_u2.__file__), 'assets')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('data', 'data'),
        # adb.exe 放在 exe 同级目录，确保一定能被找到
        (_os.path.join(_adb_src, 'adb.exe'), '.'),
        (_os.path.join(_adb_src, 'AdbWinApi.dll'), '.'),
        (_os.path.join(_adb_src, 'AdbWinUsbApi.dll'), '.'),
        (_os.path.join(_u2_assets, 'app-uiautomator.apk'), 'assets'),
        (_os.path.join(_u2_assets, 'u2.jar'), 'assets'),
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
        'uiautomator2',
        'adbutils',
        'cv2',
        'numpy',
        'lxml',
        'PIL',
        'retry2',
        'core',
        'core.driver',
        'core.pipeline',
        'core.chatter',
        'core.greeter',
        'core.group_invite',
        'core.message_pool',
        'data',
        'data.storage',
        'device_manager',
        'utils',
        'utils.helpers',
        'actions',
        'actions.chat_topbar',
        'actions.config_loader',
        'actions.mutual_friend',
        'actions.scroll_engine',
        'actions.ui_hierarchy',
        'flet',
        'flet_web',
        'flet_core',
        'flet_runtime',
        'requests',
        'ui',
        'ui.app',
        'ui.theme',
        'ui.adb_panel',
        'ui.config_panel',
        'ui.device_list',
        'ui.log_area',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pkg_resources',
        'setuptools',
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
