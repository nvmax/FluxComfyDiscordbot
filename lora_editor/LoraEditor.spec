# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

# Get the absolute path of the script
script_path = os.path.abspath('lora_editor.py')
base_path = os.path.dirname(script_path)

# Initialize data files list
datas = []

a = Analysis(
    [script_path],
    pathex=[base_path],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'sqlite3',
        'dotenv',
        'requests',
        'huggingface_hub',
        'json',
        'logging',
        'pathlib',
        'threading'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'notebook', 'PIL.ImageQt', 'PyQt5', 'PySide2', 
        'IPython', 'pandas', 'numpy', 'scipy', 'torch', 'tensorflow', 
        'onnxruntime', 'numba', 'llvmlite', 'win32com', 'pythoncom', 
        'pywintypes', 'psutil', 'sympy', 'jinja2', 'h5py', 'wx', 
        'PyQt6', 'PySide6', 'IPython', 'nbconvert', 'nbformat'
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LoraEditor',
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
    icon=None  # You can add an icon file here if you have one
)
