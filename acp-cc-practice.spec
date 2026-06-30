# -*- mode: python ; coding: utf-8 -*-


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


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data')],
    hiddenimports=[],
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
