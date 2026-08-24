import json
import os
import sys
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import xbox_save_tool

# ----------------- log() tests -----------------

def test_log_colored_and_uncolored(capsys):
    xbox_save_tool.log("Test cyan message", color="cyan")
    captured = capsys.readouterr().out
    assert "Test cyan message" in captured

    xbox_save_tool.log("Test plain message")
    captured2 = capsys.readouterr().out
    assert "Test plain message" in captured2

def test_log_windows_platform(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "system", lambda cmd: None)
    xbox_save_tool.log("Windows color test", color="green")
    captured = capsys.readouterr().out
    assert "Windows color test" in captured

# ----------------- oauth_device_login() tests -----------------

class MockResponse:
    def __init__(self, data_dict):
        self.data_bytes = json.dumps(data_dict).encode("utf-8")
    def read(self):
        return self.data_bytes
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

def test_oauth_device_login_success(monkeypatch):
    device_code_resp = {
        "verification_uri": "https://microsoft.com/link",
        "user_code": "ABCDEFGH",
        "device_code": "dev_code_123"
    }
    token_resp = {"access_token": "test_access_token"}
    user_auth_resp = {"Token": "test_user_token"}
    xsts_resp = {
        "Token": "test_xsts_token",
        "DisplayClaims": {
            "xui": [{"uhs": "test_uhs", "xid": "123456789", "gtg": "GamerTag123"}]
        }
    }

    call_count = 0
    def mock_urlopen(req):
        nonlocal call_count
        call_count += 1
        url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
        if "oauth20_connect.srf" in url:
            return MockResponse(device_code_resp)
        elif "oauth20_token.srf" in url:
            return MockResponse(token_resp)
        elif "user.auth.xboxlive.com" in url:
            return MockResponse(user_auth_resp)
        elif "xsts.auth.xboxlive.com" in url:
            return MockResponse(xsts_resp)
        raise ValueError(f"Unexpected URL: {url}")

    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", mock_urlopen)
    res = xbox_save_tool.oauth_device_login()

    assert res is not None
    assert res["gamertag"] == "GamerTag123"
    assert res["xid"] == "123456789"
    assert res["uhs"] == "test_uhs"
    assert res["token"] == "test_xsts_token"

def test_oauth_device_login_retry_then_success(monkeypatch):
    device_code_resp = {"verification_uri": "https://link", "user_code": "CODE", "device_code": "dev"}
    token_resp = {"access_token": "tok"}
    user_auth_resp = {"Token": "utok"}
    xsts_resp = {
        "Token": "xtok",
        "DisplayClaims": {"xui": [{"uhs": "uhs", "xid": "xid"}]} # default gtg
    }

    attempts = 0
    def mock_urlopen(req):
        nonlocal attempts
        url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
        if "oauth20_connect.srf" in url:
            return MockResponse(device_code_resp)
        elif "oauth20_token.srf" in url:
            attempts += 1
            if attempts == 1:
                raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)
            return MockResponse(token_resp)
        elif "user.auth.xboxlive.com" in url:
            return MockResponse(user_auth_resp)
        elif "xsts.auth.xboxlive.com" in url:
            return MockResponse(xsts_resp)

    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    res = xbox_save_tool.oauth_device_login()
    assert res["gamertag"] == "XboxUser"

def test_oauth_device_login_timeout(monkeypatch, capsys):
    device_code_resp = {"verification_uri": "https://link", "user_code": "CODE", "device_code": "dev"}
    def mock_urlopen(req):
        url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
        if "oauth20_connect.srf" in url:
            return MockResponse(device_code_resp)
        raise urllib.error.HTTPError(url, 400, "Pending", {}, None)

    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    res = xbox_save_tool.oauth_device_login()
    assert res is None
    captured = capsys.readouterr().out
    assert "Authentication timed out." in captured

# ----------------- discover_games() tests -----------------

def test_discover_games_pagination(monkeypatch):
    page1 = {
        "titles": [{"name": "Game 1", "titleId": 101, "serviceConfigId": "scid-1"}],
        "pagingInfo": {"continuationToken": "token_page_2"}
    }
    page2 = {
        "titles": [{"name": "Game 2", "titleId": 102, "serviceConfigId": "scid-2"}],
        "pagingInfo": {"continuationToken": None}
    }

    call_num = 0
    def mock_urlopen(req):
        nonlocal call_num
        call_num += 1
        return MockResponse(page1 if call_num == 1 else page2)

    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", mock_urlopen)
    auth = {"uhs": "uhs", "token": "token", "xid": "123"}
    titles = xbox_save_tool.discover_games(auth)

    assert len(titles) == 2
    assert titles[0]["name"] == "Game 1"
    assert titles[1]["name"] == "Game 2"

def test_discover_games_exception(monkeypatch, capsys):
    def mock_urlopen(req):
        raise urllib.error.URLError("Network error")

    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", mock_urlopen)
    auth = {"uhs": "uhs", "token": "token", "xid": "123"}
    titles = xbox_save_tool.discover_games(auth)
    assert titles == []
    captured = capsys.readouterr().out
    assert "Error querying page: <urlopen error Network error>" in captured

# ----------------- lookup_store_product() tests -----------------

def test_lookup_store_product_url_and_top_level_props(monkeypatch):
    store_resp = {
        "Products": [{
            "LocalizedProperties": [{"ProductTitle": "Starfield"}],
            "Properties": {
                "PackageFamilyName": "Bethesda.Starfield_hash",
                "PackageIdentityName": "Bethesda.Starfield",
                "ApplicationId": "StarfieldApp",
                "PrimaryServiceConfigId": "00000000-0000-0000-0000-00007bf72399",
                "XboxTitleId": "2079794073"
            }
        }]
    }
    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", lambda req: MockResponse(store_resp))
    info = xbox_save_tool.lookup_store_product("https://www.xbox.com/games/store/starfield/9NCJSXWZMSBX")

    assert info is not None
    assert info["productId"] == "9NCJSXWZMSBX"
    assert info["titleName"] == "Starfield"
    assert info["packageFamilyName"] == "Bethesda.Starfield_hash"
    assert info["applicationId"] == "StarfieldApp"
    assert info["scid"] == "00000000-0000-0000-0000-00007bf72399"

def test_lookup_store_product_sku_fallback(monkeypatch):
    store_resp = {
        "Products": [{
            "LocalizedProperties": [{"ProductTitle": "Indie Game"}],
            "Properties": {
                "XboxTitleId": "12345"
            },
            "DisplaySkuAvailabilities": [{
                "Sku": {
                    "Properties": {
                        "Packages": [{
                            "PackageFamilyName": "IndieDev.Game_8wekyb3d8bbwe",
                            "PackageIdentityName": "IndieDev.Game"
                        }]
                    }
                }
            }]
        }]
    }
    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", lambda req: MockResponse(store_resp))
    info = xbox_save_tool.lookup_store_product("9N1234567890")

    assert info is not None
    assert info["packageFamilyName"] == "IndieDev.Game_8wekyb3d8bbwe"
    assert info["applicationId"] == "App"
    assert "00003039" in info["scid"] # Hex conversion of 12345

def test_lookup_store_product_empty_products(monkeypatch, capsys):
    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", lambda req: MockResponse({"Products": []}))
    res = xbox_save_tool.lookup_store_product("9N0000000000")
    assert res is None
    assert "No product found in Store Catalog." in capsys.readouterr().out

def test_lookup_store_product_network_error(monkeypatch, capsys):
    def mock_urlopen(req):
        raise OSError("HTTP 404")
    monkeypatch.setattr(xbox_save_tool.urllib.request, "urlopen", mock_urlopen)
    res = xbox_save_tool.lookup_store_product("INVALID")
    assert res is None
    assert "Store Catalog lookup failed: HTTP 404" in capsys.readouterr().out

# ----------------- generate_manifest_and_register() tests -----------------

def test_generate_manifest_and_register(tmp_path, monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    monkeypatch.setattr(xbox_save_tool.subprocess, "run", mock_run)

    res = xbox_save_tool.generate_manifest_and_register(
        identity_name="TestApp.Identity",
        pfn="TestApp.Identity_12345",
        app_id="App",
        publisher="CN=CustomPub",
        target_dir=tmp_path
    )
    assert res is True
    manifest_file = tmp_path / "AppxManifest.xml"
    assert manifest_file.exists()
    content = manifest_file.read_text(encoding="utf-8")
    assert "Identity Name=\"TestApp.Identity\"" in content
    assert "Publisher=\"CN=CustomPub\"" in content
    assert (tmp_path / "Assets" / "Logo.png").exists()

def test_generate_manifest_default_target_dir(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Warning message"
    mock_run.return_value.stdout = ""
    monkeypatch.setattr(xbox_save_tool.subprocess, "run", mock_run)

    res = xbox_save_tool.generate_manifest_and_register(
        identity_name="DefaultTest",
        pfn="DefaultTest_hash",
        app_id="Main"
    )
    assert res is True

def test_generate_manifest_dev_mode_error(monkeypatch, capsys):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Deployment failed with HRESULT: 0x80073CFF Developer Mode is required."
    mock_run.return_value.stdout = ""
    monkeypatch.setattr(xbox_save_tool.subprocess, "run", mock_run)

    res = xbox_save_tool.generate_manifest_and_register(
        identity_name="DevModeTest",
        pfn="DevModeTest_hash",
        app_id="App"
    )
    assert res is True
    captured = capsys.readouterr().out
    assert "Windows Developer Mode is required" in captured

# ----------------- extract_cloud_saves() tests -----------------

def test_extract_cloud_saves_packaged(tmp_path, monkeypatch):
    out_dir = tmp_path / "Extracted"
    log_file = xbox_save_tool.WORKSPACE_DIR / "recovery_log.txt"
    
    def mock_run(cmd, *args, **kwargs):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("Connecting...\nContainer 1/1\nEXTRACTION COMPLETE\n")
        res = MagicMock()
        res.returncode = 0
        return res

    monkeypatch.setattr(xbox_save_tool.subprocess, "run", mock_run)
    out_dir.mkdir(parents=True)
    (out_dir / "save1.sfs").write_bytes(b"save bytes")

    res = xbox_save_tool.extract_cloud_saves(
        scid="00000000-0000-0000-0000-00007bf72399",
        output_dir=str(out_dir),
        pfn="Game.PFN_123",
        app_id="App"
    )
    assert res is True
    assert (xbox_save_tool.WORKSPACE_DIR / "XboxSaves_00007bf72399_Backup.zip").exists()

def test_extract_cloud_saves_unpackaged_failed_status(tmp_path, monkeypatch):
    out_dir = tmp_path / "Extracted2"
    log_file = xbox_save_tool.WORKSPACE_DIR / "recovery_log.txt"

    def mock_popen(cmd, shell=True):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("Failed connecting to GameSaveProvider (Status: -2147467259)\n")
        return MagicMock()

    monkeypatch.setattr(xbox_save_tool.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    out_dir.mkdir(parents=True)

    res = xbox_save_tool.extract_cloud_saves(
        scid="00000000-0000-0000-0000-000000000001",
        output_dir=str(out_dir)
    )
    assert res is True

def test_extract_cloud_saves_unlink_exception_and_sleep_loop(tmp_path, monkeypatch):
    out_dir = tmp_path / "Extracted3"
    log_file = xbox_save_tool.WORKSPACE_DIR / "recovery_log.txt"
    log_file.write_text("Starting...\n", encoding="utf-8")

    def mock_unlink():
        raise PermissionError("File in use")
    monkeypatch.setattr(Path, "unlink", lambda self: mock_unlink())

    sleep_calls = 0
    def mock_sleep(s):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("EXTRACTION COMPLETE\n")

    monkeypatch.setattr(xbox_save_tool.subprocess, "Popen", lambda cmd, shell=True: MagicMock())
    monkeypatch.setattr(time, "sleep", mock_sleep)
    out_dir.mkdir(parents=True)

    res = xbox_save_tool.extract_cloud_saves(
        scid="00000000-0000-0000-0000-000000000002",
        output_dir=str(out_dir)
    )
    assert res is True
    assert sleep_calls >= 1

# ----------------- run_interactive_wizard() tests -----------------

def test_wizard_login_fails(monkeypatch):
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: None)
    xbox_save_tool.run_interactive_wizard()

def test_wizard_no_titles(monkeypatch, capsys):
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: {"xid": "1", "uhs": "u", "token": "t"})
    monkeypatch.setattr(xbox_save_tool, "discover_games", lambda auth: [])
    xbox_save_tool.run_interactive_wizard()
    assert "No titles found." in capsys.readouterr().out

def test_wizard_selection_index_and_store_lookup(tmp_path, monkeypatch):
    titles = [
        {"name": f"Game {i}", "titleId": 1000 + i, "serviceConfigId": f"scid-{i}"} for i in range(55)
    ]
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: {"xid": "1", "uhs": "u", "token": "t"})
    monkeypatch.setattr(xbox_save_tool, "discover_games", lambda auth: titles)
    
    inputs = iter(["1", "9NSTOREID123"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    mock_store_info = {
        "identityName": "Game0.Identity",
        "packageFamilyName": "Game0.Identity_hash",
        "applicationId": "App",
        "scid": "scid-0"
    }
    monkeypatch.setattr(xbox_save_tool, "lookup_store_product", lambda q: mock_store_info)
    mock_gen = MagicMock()
    mock_extract = MagicMock()
    monkeypatch.setattr(xbox_save_tool, "generate_manifest_and_register", mock_gen)
    monkeypatch.setattr(xbox_save_tool, "extract_cloud_saves", mock_extract)

    xbox_save_tool.run_interactive_wizard()
    assert mock_gen.called
    assert mock_extract.called

def test_wizard_selection_search_query_and_derived_store(monkeypatch):
    titles = [
        {"name": "Halo Infinite", "titleId": 2000, "serviceConfigId": "scid-halo"}
    ]
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: {"xid": "1", "uhs": "u", "token": "t"})
    monkeypatch.setattr(xbox_save_tool, "discover_games", lambda auth: titles)
    
    inputs = iter(["halo", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    mock_gen = MagicMock()
    mock_extract = MagicMock()
    monkeypatch.setattr(xbox_save_tool, "generate_manifest_and_register", mock_gen)
    monkeypatch.setattr(xbox_save_tool, "extract_cloud_saves", mock_extract)

    xbox_save_tool.run_interactive_wizard()
    assert mock_gen.called
    assert mock_extract.called

def test_wizard_selection_no_match(monkeypatch, capsys):
    titles = [{"name": "Forza Horizon", "titleId": 3000, "serviceConfigId": "scid-forza"}]
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: {"xid": "1", "uhs": "u", "token": "t"})
    monkeypatch.setattr(xbox_save_tool, "discover_games", lambda auth: titles)
    
    monkeypatch.setattr("builtins.input", lambda prompt: "unmatched_game")
    xbox_save_tool.run_interactive_wizard()
    assert "No matching game found." in capsys.readouterr().out

# ----------------- main() CLI commands tests -----------------

def test_main_cli_discover(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: {"xid": "1", "uhs": "u", "token": "t"})
    monkeypatch.setattr(xbox_save_tool, "discover_games", lambda auth: [{"name": "T1", "titleId": 1, "serviceConfigId": "s1"}])
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "discover"])

    xbox_save_tool.main()
    assert (tmp_path / "history.json").exists()

def test_main_cli_discover_fail(monkeypatch):
    monkeypatch.setattr(xbox_save_tool, "oauth_device_login", lambda: None)
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "discover"])
    xbox_save_tool.main()

def test_main_cli_lookup(monkeypatch):
    mock_lookup = MagicMock()
    monkeypatch.setattr(xbox_save_tool, "lookup_store_product", mock_lookup)
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "lookup", "9N1234567890"])
    xbox_save_tool.main()
    mock_lookup.assert_called_with("9N1234567890")

def test_main_cli_setup(monkeypatch):
    mock_setup = MagicMock()
    monkeypatch.setattr(xbox_save_tool, "generate_manifest_and_register", mock_setup)
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "setup", "--identity", "Id1", "--pfn", "PFN1", "--appid", "App1", "--publisher", "CN=Pub"])
    xbox_save_tool.main()
    mock_setup.assert_called_with("Id1", "PFN1", "App1", publisher="CN=Pub")

def test_main_cli_extract(monkeypatch):
    mock_extract = MagicMock()
    monkeypatch.setattr(xbox_save_tool, "extract_cloud_saves", mock_extract)
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "extract", "--scid", "scid-123", "--output", "OutFolder", "--pfn", "PFN1", "--appid", "App1"])
    xbox_save_tool.main()
    mock_extract.assert_called_with("scid-123", "OutFolder", pfn="PFN1", app_id="App1")

def test_main_cli_wizard(monkeypatch):
    mock_wizard = MagicMock()
    monkeypatch.setattr(xbox_save_tool, "run_interactive_wizard", mock_wizard)
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "wizard"])
    xbox_save_tool.main()
    assert mock_wizard.called

def test_main_execution_as_module(monkeypatch):
    import runpy
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: MockResponse({"Products": []}))
    monkeypatch.setattr(sys, "argv", ["xbox_save_tool.py", "lookup", "9N0000000000"])
    runpy.run_module("xbox_save_tool", run_name="__main__")

