import os
import sys
import shutil
import zipfile
from pathlib import Path
import pytest
from unittest.mock import patch

import deploy_to_steam

def test_deploy_saves_nonexistent_src(tmp_path, capsys):
    nonexistent = tmp_path / 'does_not_exist'
    target = tmp_path / 'target'
    res = deploy_to_steam.deploy_saves(nonexistent, target)
    assert res is False
    captured = capsys.readouterr().out
    assert 'Error: Source directory does not exist' in captured

def test_deploy_saves_success_default_backup(tmp_path, capsys):
    src = tmp_path / 'saves_source'
    src.mkdir()
    (src / 'sub').mkdir()
    (src / 'save1.sav').write_text('save1 data')
    (src / 'sub' / 'save2.sav').write_text('save2 data')

    target = tmp_path / 'saves_target'
    res = deploy_to_steam.deploy_saves(src, target)
    assert res is True

    # Check default backup zip
    expected_zip = tmp_path / 'saves_source_Backup.zip'
    assert expected_zip.exists()
    with zipfile.ZipFile(expected_zip, 'r') as zf:
        namelist = zf.namelist()
        assert 'save1.sav' in namelist
        assert 'sub/save2.sav' in namelist or 'sub\\save2.sav' in namelist

    # Check target files copied
    assert (target / 'save1.sav').read_text() == 'save1 data'
    assert (target / 'sub' / 'save2.sav').read_text() == 'save2 data'

    captured = capsys.readouterr().out
    assert 'SUCCESS' in captured
    assert 'Deployed 2 save file(s)' in captured

def test_deploy_saves_custom_backup(tmp_path):
    src = tmp_path / 'saves_source'
    src.mkdir()
    (src / 'save.sav').write_bytes(b'binary save')
    target = tmp_path / 'saves_target'
    custom_backup = tmp_path / 'custom_folder' / 'my_backup.zip'

    res = deploy_to_steam.deploy_saves(src, target, backup_zip=custom_backup)
    assert res is True
    assert custom_backup.exists()
    assert (target / 'save.sav').read_bytes() == b'binary save'

def test_main_with_cli_args(tmp_path, monkeypatch, capsys):
    src = tmp_path / 'source'
    src.mkdir()
    (src / 'test.sav').write_text('hello')
    target = tmp_path / 'dest'
    backup = tmp_path / 'backup.zip'

    monkeypatch.setattr(sys, 'argv', ['deploy_to_steam.py', '--source', str(src), '--target', str(target), '--backup', str(backup)])
    deploy_to_steam.main()

    assert (target / 'test.sav').exists()
    assert backup.exists()

def test_main_interactive_target(tmp_path, monkeypatch, capsys):
    src = tmp_path / 'source'
    src.mkdir()
    (src / 'test.sav').write_text('hello')
    target = tmp_path / 'interactive_dest'

    monkeypatch.setattr(sys, 'argv', ['deploy_to_steam.py', '--source', str(src)])
    monkeypatch.setattr('builtins.input', lambda prompt: str(target))
    deploy_to_steam.main()

    assert (target / 'test.sav').exists()
    captured = capsys.readouterr().out
    assert 'Common save locations:' in captured

def test_main_interactive_target_empty(tmp_path, monkeypatch, capsys):
    src = tmp_path / 'source'
    src.mkdir()

    monkeypatch.setattr(sys, 'argv', ['deploy_to_steam.py', '--source', str(src)])
    monkeypatch.setattr('builtins.input', lambda prompt: '   ')
    deploy_to_steam.main()

    captured = capsys.readouterr().out
    assert 'Error: No target directory provided.' in captured

def test_main_execution_as_module(tmp_path, monkeypatch):
    import runpy
    src = tmp_path / 'source'
    src.mkdir()
    (src / 'test.sav').write_text('content')
    target = tmp_path / 'target'

    monkeypatch.setattr(sys, 'argv', ['deploy_to_steam.py', '--source', str(src), '--target', str(target)])
    runpy.run_module('deploy_to_steam', run_name='__main__')
    assert (target / 'test.sav').exists()
