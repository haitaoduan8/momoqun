# PyInstaller：无控制台（windowed）。Windows 产出 dist/momoqun/momoqun.exe
# 必须在 Windows 上构建 —— 不能在 Mac 上交叉编译 .exe
# 构建：pip install pyinstaller && pyinstaller momoqun.spec
# 采用 COLLECT 目录模式（非 onefile），因为运行时需要读取 config/ 和 webui/out/

import os as _os
import adbutils as _adbutils
import uiautomator2 as _u2

_adb_src = _os.path.join(_os.path.dirname(_adbutils.__file__), 'binaries')
_u2_assets = _os.path.join(_os.path.dirname(_u2.__file__), 'assets')

# 路线 C：把 agent APK / 协议文档 / 压测工具一并打到 dist/agent-bundle/
_apk_candidates = [
    _os.path.join('agent-android', 'app', 'build', 'outputs', 'apk', 'release', 'app-release.apk'),
    _os.path.join('agent-android', 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk'),
]
_agent_datas = []
for _p in _apk_candidates:
    if _os.path.isfile(_p):
        _agent_datas.append((_p, 'agent-bundle'))
        break
else:
    print('[spec] WARN: agent APK not found (agent-android not built); '
          'agent-bundle/app-*.apk will be missing from dist.')

for _src, _dst in (
    (_os.path.join('docs', 'agent-protocol.md'), 'agent-bundle'),
    (_os.path.join('agent-android', 'README.md'),  'agent-bundle'),
    (_os.path.join('tools', 'stress_agent_router.py'), 'agent-bundle/tools'),
):
    if _os.path.isfile(_src):
        _agent_datas.append((_src, _dst))

# Next.js 静态前端
_webui_datas = []
if _os.path.isdir('webui/out'):
    _webui_datas.append(('webui/out', 'webui/out'))
else:
    print('[spec] WARN: webui/out not found; run "cd webui && npm run build" first.')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('data', 'data'),
        (_os.path.join(_adb_src, 'adb.exe'), '.'),
        (_os.path.join(_adb_src, 'AdbWinApi.dll'), '.'),
        (_os.path.join(_adb_src, 'AdbWinUsbApi.dll'), '.'),
        (_os.path.join(_u2_assets, 'app-uiautomator.apk'), 'assets'),
        (_os.path.join(_u2_assets, 'u2.jar'), 'assets'),
        *_agent_datas,
        *_webui_datas,
    ],
    hiddenimports=[
        # Web/IO 栈
        'fastapi',
        'uvicorn',
        'yaml',
        'starlette',
        'anyio',
        'httptools',
        'uvloop',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.server',
        'watchfiles',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'fastapi.staticfiles',
        'fastapi.responses',
        # 设备 / 图像
        'uiautomator2',
        'adbutils',
        'cv2',
        'numpy',
        'lxml',
        'PIL',
        'retry2',
        # 业务核心
        'core',
        'core.driver',
        'core.drivers',
        'core.drivers.base',
        'core.drivers.u2_driver',
        'core.drivers.agent_driver',
        'core.pipeline',
        'core.chatter',
        'core.greeter',
        'core.group_invite',
        'core.message_pool',
        'core.traversal',
        'core.chat_flow',
        'core.account_check',
        # 路线 C 反向 RPC
        'agent_router',
        # 数据层
        'data',
        'data.storage',
        # 设备管理
        'device_manager',
        # 通用
        'utils',
        'utils.helpers',
        'actions',
        'actions.chat_topbar',
        'actions.config_loader',
        'actions.mutual_friend',
        'actions.scroll_engine',
        'actions.ui_hierarchy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pkg_resources',
        'setuptools',
        'main',
        'flet',
        'flet_web',
        'flet_core',
        'flet_runtime',
        'ui',
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
