# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata, collect_submodules
import streamlit as st

block_cipher = None

# Obtener la ruta de Streamlit de forma dinámica desde el entorno
streamlit_dir = Path(st.__path__[0])

# Recopilar metadatos de Streamlit
datas = copy_metadata('streamlit')

# Añadir recursos estáticos, la app principal y el directorio src
datas += [
    ('app.py', '.'),
    ('src', 'src'),
    (str(streamlit_dir / 'static'), 'streamlit/static'),
    (str(streamlit_dir / 'runtime'), 'streamlit/runtime'),
]

# Recopilar todos los submódulos de streamlit y dependencias críticas
hiddenimports = (
    collect_submodules('streamlit') +
    collect_submodules('shapely') +
    collect_submodules('sklearn') +
    collect_submodules('matplotlib') +
    collect_submodules('pyvista') +
    collect_submodules('comtypes') +
    collect_submodules('numpy')
)

# Añadir importaciones ocultas para las otras dependencias críticas (como VTK para pyvista)
hiddenimports += [
    "vtkmodules",
    "vtkmodules.all",
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "vtkmodules.util",
    "vtkmodules.util.numpy_support",
    "vtkmodules.numpy_interface.dataset_adapter",
]

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Revit2Etabs_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # console=False equivale a --windowed / --noconsole
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/icon/logo_R2E.ico',
)
