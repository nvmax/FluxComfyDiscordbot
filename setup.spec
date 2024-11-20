# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import download_upx

block_cipher = None

# Download and set up UPX
upx_dir = download_upx.download_upx()

a = Analysis(
    ['setup.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'logging',
        'pathlib',
        'requests',
        'tqdm',
        'urllib3',
        'huggingface_hub',
        'json',
        're',
        'threading'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',
        'numpy',
        'pandas',
        'scipy',
        'matplotlib',
        'cv2',
        'torch',
        'tensorflow',
        'keras'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Add version information
version_file = 'file_version_info.txt'
if os.path.exists(version_file):
    a.version = version_file

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    upx_dir=upx_dir,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_file,
    icon='Comfyuidiscordbotflux.ico'
)
