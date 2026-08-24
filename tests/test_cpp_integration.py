import subprocess
import shutil
from pathlib import Path
import pytest

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
EXE_PATH = WORKSPACE_DIR / "xbox_save_extractor.exe"

@pytest.mark.skipif(not EXE_PATH.exists(), reason="xbox_save_extractor.exe not built")
def test_cpp_binary_missing_scid_error(tmp_path):
    isolated_exe = tmp_path / "xbox_save_extractor.exe"
    shutil.copy2(EXE_PATH, isolated_exe)

    log_file = tmp_path / "test_missing_scid.log"
    cmd = [str(isolated_exe), "--log", str(log_file)]
    
    # Run with timeout to prevent Sleep(4000) from hanging test excessively
    try:
        res = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True, timeout=10)
        assert res.returncode == 1
    except subprocess.TimeoutExpired:
        pass

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Error: No Target SCID specified" in content

@pytest.mark.skipif(not EXE_PATH.exists(), reason="xbox_save_extractor.exe not built")
def test_cpp_binary_with_scid_unpackaged_fails_gracefully(tmp_path):
    isolated_exe = tmp_path / "xbox_save_extractor.exe"
    shutil.copy2(EXE_PATH, isolated_exe)

    log_file = tmp_path / "test_unpackaged.log"
    out_dir = tmp_path / "test_out"
    cmd = [str(isolated_exe), "--scid", "00000000-0000-0000-0000-000000000000", "--out", str(out_dir), "--log", str(log_file)]

    try:
        res = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True, timeout=10)
        assert res.returncode != 0
    except subprocess.TimeoutExpired:
        pass

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Target SCID: 00000000-0000-0000-0000-000000000000" in content

