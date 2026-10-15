# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo,
    StringFileInfo, StringTable, StringStruct,
    VarFileInfo, VarStruct,
)

# TD-21: Windows EXE 版本信息（右键属性可见）
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 1, 0, 0),
        prodvers=(1, 1, 0, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable('040904B0', [
                StringStruct('CompanyName', 'HindsightPJ'),
                StringStruct('FileDescription', 'ACP 云计算练习软件'),
                StringStruct('FileVersion', '1.1.0'),
                StringStruct('InternalName', 'acp-cc-practice'),
                StringStruct('LegalCopyright', '© 2026 HindsightPJ'),
                StringStruct('OriginalFilename', 'acp-cc-practice.exe'),
                StringStruct('ProductName', 'ACP 云计算练习'),
                StringStruct('ProductVersion', '1.1.0'),
            ])
        ]),
        VarFileInfo([VarStruct('Translation', [0x409, 1200])])
    ]
)

# P1-5: 使用 SPECPATH（PyInstaller 注入的全局变量，指向 spec 文件所在目录）
# 构造 data 文件的绝对路径，避免从非项目根目录调用 pyinstaller 时找不到 data 文件。
_DATA_DIR = os.path.join(SPECPATH, 'data')


a = Analysis(
    [os.path.join(SPECPATH, 'main.py')],
    pathex=[SPECPATH],
    binaries=[],
    # P1-1: 显式列出打包文件，避免开发机的明文 questions.json 被打包进 exe
    # 仅包含：加密题库 questions.enc / 试用题库 questions_trial.json / 元数据 questions_meta.json
    # 不打包 questions.json（明文全库）和 progress.json（用户数据）
    datas=[
        (os.path.join(_DATA_DIR, 'questions.enc'), 'data'),
        (os.path.join(_DATA_DIR, 'questions_trial.json'), 'data'),
        (os.path.join(_DATA_DIR, 'questions_meta.json'), 'data'),
        # TD-22: 把图标文件打包进 EXE，打包后运行时通过 sys._MEIPASS 访问
        (os.path.join(SPECPATH, 'icons', 'icon.ico'), 'icons'),
    ],
    hiddenimports=[
        'cryptography.fernet',
        'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.asymmetric.ed25519',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.backends.openssl.backend',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # P7: 裁剪 PySide6 无关组件（Essentials 之外的 Qt 模块与 tkinter 栈）
    excludes=[
        'tkinter', '_tkinter',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel',
        'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtSql', 'PySide6.QtTest',
        'PySide6.QtNetworkAuth',
        'PySide6.QtNetwork', 'PySide6.QtSvg',
    ],
    noarchive=False,
    optimize=0,
)
# P9-1: 裁剪无用的 Qt 二进制（TD-21 体积优化）
# - opengl32sw.dll（20.6MB）：软件 OpenGL 渲染回退，纯 Widgets 应用不需要
# - qdirect2d/qtiff/qjpeg/qwebp：备用平台插件与未使用的图片格式插件（项目仅 ico/png）
# - tls/networkinformation：QtNetwork 的 TLS 后端与网络可达性探测插件，随 QtNetwork 一起裁剪
# - qsvgicon/qsvg：SVG 图标插件，项目无 SVG 资源
_CUT_PATTERNS = (
    'opengl32sw', 'qdirect2d', 'qtiff', 'qjpeg', 'qwebp',
    'networkinformation', 'tls\\', 'qsvgicon', 'qsvg',
)
a.binaries = [b for b in a.binaries if not any(p in b[0] for p in _CUT_PATTERNS)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='acp-cc-practice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,
    # TD-22: 使用 icons/original/icon-1024.png 生成的多尺寸 ICO 作为 EXE 图标
    icon=os.path.join(SPECPATH, 'icons', 'icon.ico'),
)
