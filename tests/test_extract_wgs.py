import os
import sys

import extract_wgs


def test_parse_containers_index_nonexistent(tmp_path):
    nonexistent = tmp_path / 'no_wgs'
    assert extract_wgs.parse_containers_index(str(nonexistent)) == []

def test_parse_containers_index_valid(tmp_path):
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    index_file = wgs_dir / 'containers.index'
    index_file.write_bytes(b'header')

    hex_dir = wgs_dir / ('A' * 32)
    hex_dir.mkdir()
    (hex_dir / 'container.1').write_bytes(b'container data')

    # Also add a directory that is not 32 chars
    (wgs_dir / 'short').mkdir()

    results = extract_wgs.parse_containers_index(str(wgs_dir))
    assert len(results) == 1
    assert results[0][0] == 'A' * 32

def test_parse_containers_index_exception(tmp_path, monkeypatch, capsys):
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    (wgs_dir / 'containers.index').write_bytes(b'data')

    def mock_listdir(p):
        raise OSError('Disk error')
    monkeypatch.setattr(os, 'listdir', mock_listdir)

    results = extract_wgs.parse_containers_index(str(wgs_dir))
    assert results == []
    captured = capsys.readouterr().out
    assert 'Error reading index: Disk error' in captured

def test_extract_wgs_folder_gvas_and_dat(tmp_path, capsys):
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    c_dir = wgs_dir / 'container1'
    c_dir.mkdir()
    (c_dir / 'container.1').write_bytes(b'container info')

    # GVAS blob
    (c_dir / 'blob_gvas').write_bytes(b'GVAS_save_content')
    # DAT blob
    (c_dir / 'blob_dat').write_bytes(b'OTHER_data')
    # TMP file (should be ignored)
    (c_dir / 'blob.tmp').write_bytes(b'temp')
    # Subdir (not a file, should be skipped)
    (c_dir / 'sub_folder').mkdir()

    out_dir = tmp_path / 'out'
    count = extract_wgs.extract_wgs_folder(str(wgs_dir), str(out_dir))
    assert count == 2

    # Check extracted filenames
    extracted_files = [f.name for f in out_dir.iterdir()]
    assert any(f.endswith('.sav') for f in extracted_files)
    assert any(f.endswith('.dat') for f in extracted_files)

def test_extract_wgs_folder_exception(tmp_path, monkeypatch, capsys):
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    c_dir = wgs_dir / 'c1'
    c_dir.mkdir()
    (c_dir / 'container.1').write_bytes(b'info')
    (c_dir / 'blob_err').write_bytes(b'data')

    orig_open = open
    def mock_open(file, *args, **kwargs):
        if 'blob_err' in str(file):
            raise OSError('Failed read')
        return orig_open(file, *args, **kwargs)

    monkeypatch.setattr('builtins.open', mock_open)
    extract_wgs.extract_wgs_folder(str(wgs_dir), str(tmp_path / 'out'))
    captured = capsys.readouterr().out
    assert 'Failed processing' in captured

def test_find_all_wgs_packages(tmp_path, monkeypatch):
    local_appdata = tmp_path / 'LocalAppData'
    packages = local_appdata / 'Packages'
    packages.mkdir(parents=True)

    # Package 1 with wgs
    p1 = packages / 'Vendor.GameOne_hash'
    wgs1 = p1 / 'SystemAppData' / 'wgs'
    wgs1.mkdir(parents=True)
    (wgs1 / 'c1').mkdir()
    (wgs1 / 'c2').mkdir()

    # Package 2 without wgs
    p2 = packages / 'Vendor.OtherApp_hash'
    p2.mkdir()

    monkeypatch.setenv('LOCALAPPDATA', str(local_appdata))
    results = extract_wgs.find_all_wgs_packages()
    assert len(results) == 1
    assert results[0]['packageName'] == 'Vendor.GameOne_hash'
    assert results[0]['containerCount'] == 2

def test_find_all_wgs_packages_nonexistent(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'does_not_exist'))
    assert extract_wgs.find_all_wgs_packages() == []

def test_main_with_wgs_dir(tmp_path, monkeypatch):
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--wgs-dir', str(wgs_dir), '--output', str(out_dir)])
    extract_wgs.main()
    assert out_dir.exists()

def test_main_list_mode(tmp_path, monkeypatch, capsys):
    mock_pkgs = [{'packageName': 'Game1', 'wgsPath': '/path1', 'containerCount': 3}]
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', lambda: mock_pkgs)
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--list'])

    extract_wgs.main()
    captured = capsys.readouterr().out
    assert 'Found 1 package(s)' in captured
    assert 'Game1' in captured

def test_main_package_filter_match(tmp_path, monkeypatch):
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    mock_pkgs = [{'packageName': 'Starfield_123', 'wgsPath': str(wgs_dir), 'containerCount': 1}]
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', lambda: mock_pkgs)
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--package', 'starfield', '--output', str(out_dir)])
    extract_wgs.main()
    assert (out_dir / 'Starfield_123').exists()

def test_main_package_filter_no_match(monkeypatch, capsys):
    mock_pkgs = [{'packageName': 'GameA', 'wgsPath': '/path', 'containerCount': 1}]
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', lambda: mock_pkgs)
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--package', 'nomatch'])

    extract_wgs.main()
    captured = capsys.readouterr().out
    assert 'No local packages found matching' in captured

def test_main_no_packages_found(monkeypatch, capsys):
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', list)
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py'])

    extract_wgs.main()
    captured = capsys.readouterr().out
    assert 'No local WGS save folders found' in captured

def test_main_interactive_all(tmp_path, monkeypatch):
    wgs1 = tmp_path / 'wgs1'
    wgs1.mkdir()
    mock_pkgs = [
        {'packageName': 'GameA', 'wgsPath': str(wgs1), 'containerCount': 1}
    ]
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', lambda: mock_pkgs)
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--output', str(tmp_path / 'out')])
    monkeypatch.setattr('builtins.input', lambda prompt: 'all')

    extract_wgs.main()
    assert (tmp_path / 'out' / 'GameA').exists()

def test_main_interactive_index(tmp_path, monkeypatch):
    wgs1 = tmp_path / 'wgs1'
    wgs1.mkdir()
    mock_pkgs = [
        {'packageName': 'GameA', 'wgsPath': str(wgs1), 'containerCount': 1}
    ]
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', lambda: mock_pkgs)
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--output', str(tmp_path / 'out')])
    monkeypatch.setattr('builtins.input', lambda prompt: '1')

    extract_wgs.main()
    assert (tmp_path / 'out' / 'GameA').exists()

def test_main_interactive_invalid(monkeypatch, capsys):
    mock_pkgs = [{'packageName': 'GameA', 'wgsPath': '/path', 'containerCount': 1}]
    monkeypatch.setattr(extract_wgs, 'find_all_wgs_packages', lambda: mock_pkgs)
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py'])
    monkeypatch.setattr('builtins.input', lambda prompt: 'invalid_choice')

    extract_wgs.main()
    captured = capsys.readouterr().out
    assert 'Invalid selection.' in captured

def test_main_execution_as_module(tmp_path, monkeypatch):
    import runpy
    wgs_dir = tmp_path / 'wgs'
    wgs_dir.mkdir()
    monkeypatch.setattr(sys, 'argv', ['extract_wgs.py', '--wgs-dir', str(wgs_dir), '--output', str(tmp_path / 'out')])
    runpy.run_module('extract_wgs', run_name='__main__')
    assert (tmp_path / 'out').exists()
