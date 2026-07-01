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
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
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
                StringStruct('FileVersion', '1.0.0'),
                StringStruct('InternalName', 'acp-cc-practice'),
                StringStruct('LegalCopyright', '© 2026 HindsightPJ'),
                StringStruct('OriginalFilename', 'acp-cc-practice.exe'),
                StringStruct('ProductName', 'ACP 云计算练习'),
                StringStruct('ProductVersion', '1.0.0'),
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
    excludes=[],
    noarchive=False,
    optimize=0,
)
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
)
