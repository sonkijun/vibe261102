# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['sp500_gui.py'],
    pathex=[],
    binaries=[],
    # 기본 데이터 CSV를 함께 넣어 실행하자마자 분석 결과가 보이도록 함
    datas=[('S&P 500 과거 데이터.csv', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # venv에 함께 설치된 다른 Qt 바인딩/미사용 패키지는 제외
    excludes=['PySide6', 'shiboken6', 'PyQt5', 'IPython', 'ipykernel', 'scipy', 'seaborn', 'pygame'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SP500Analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SP500Analyzer',
)
app = BUNDLE(
    coll,
    name='SP500Analyzer.app',
    icon=None,
    bundle_identifier=None,
)
