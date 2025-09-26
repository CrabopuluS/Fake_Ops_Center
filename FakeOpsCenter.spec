# PyInstaller spec file for building the Fake Ops Center desktop application.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

project_root = Path(__file__).parent


def collect_directory(source: Path, prefix: str) -> list[tuple[str, str]]:
    """Recursively collect files from *source* preserving relative paths."""

    data_files: list[tuple[str, str]] = []
    for file_path in source.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(source)
            target_path = Path(prefix) / relative_path
            data_files.append((str(file_path), str(target_path)))
    return data_files


hiddenimports = collect_submodules("qasync")

analysis = Analysis(
    [str(project_root / "src" / "fake_ops_center" / "app.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "config.yaml"), "."),
        *collect_directory(project_root / "themes", "themes"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="FakeOpsCenter",
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
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FakeOpsCenter",
)
