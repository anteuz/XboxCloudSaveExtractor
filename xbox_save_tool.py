#!/usr/bin/env python3
"""
Universal Xbox Cloud Save Recovery Tool
Extracts cloud saves for ANY Xbox / Game Pass title using native Windows WinRT bridges and OAuth device authentication.
"""

import sys
import os
import re
import json
import time
import shutil
import zipfile
import subprocess
import argparse
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

CLIENT_ID = "000000004C12AE6F"
WORKSPACE_DIR = Path(__file__).resolve().parent

def log(msg, color=None):
    colors = {
        "cyan": "\033[96m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "bold": "\033[1m",
        "end": "\033[0m"
    }
    if sys.platform == "win32":
        # Enable ANSI colors in Windows terminal
        os.system("")
    if color and color in colors:
        print(f"{colors[color]}{msg}{colors['end']}")
    else:
        print(msg)

def oauth_device_login():
    """Performs Microsoft OAuth Device Code Flow to acquire Xbox Live XSTS token."""
    log("[*] Requesting Microsoft Device Code...", "yellow")
    url = "https://login.live.com/oauth20_connect.srf"
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "device_code",
        "scope": "service::user.auth.xboxlive.com::MBI_SSL"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        code_data = json.loads(resp.read().decode("utf-8"))

    log("\n=======================================================", "cyan")
    log(f" 1. Open:  {code_data.get('verification_uri')}", "bold")
    log(f" 2. Enter: {code_data.get('user_code')}", "green")
    log("=======================================================\n", "cyan")
    log("[*] Waiting for browser authorization...", "yellow")

    token_url = "https://login.live.com/oauth20_token.srf"
    token_data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": code_data["device_code"]
    }).encode("utf-8")

    access_token = None
    for _ in range(60):
        try:
            req = urllib.request.Request(token_url, data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if "access_token" in res:
                    access_token = res["access_token"]
                    break
        except urllib.error.HTTPError:
            time.sleep(5)

    if not access_token:
        log("[-] Authentication timed out.", "red")
        return None

    # User Auth
    user_url = "https://user.auth.xboxlive.com/user/authenticate"
    body = {
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"t={access_token}"
        }
    }
    req = urllib.request.Request(user_url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        user_res = json.loads(resp.read().decode("utf-8"))

    user_token = user_res["Token"]

    # XSTS Auth for xboxlive.com
    xsts_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
    body = {
        "RelyingParty": "http://xboxlive.com",
        "TokenType": "JWT",
        "Properties": {
            "UserTokens": [user_token],
            "SandboxId": "RETAIL"
        }
    }
    req = urllib.request.Request(xsts_url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        xsts_res = json.loads(resp.read().decode("utf-8"))

    xsts_token = xsts_res["Token"]
    uhs = xsts_res["DisplayClaims"]["xui"][0]["uhs"]
    xid = xsts_res["DisplayClaims"]["xui"][0]["xid"]
    gamertag = xsts_res["DisplayClaims"]["xui"][0].get("gtg", "XboxUser")

    log(f"[+] Signed in as: {gamertag} (XUID: {xid})", "green")
    return {
        "gamertag": gamertag,
        "xid": xid,
        "uhs": uhs,
        "token": xsts_token
    }

def discover_games(auth_info):
    """Fetches all played games and SCIDs for the authenticated account."""
    headers = {
        "Authorization": f"XBL3.0 x={auth_info['uhs']};{auth_info['token']}",
        "x-xbl-contract-version": "2",
        "Accept": "application/json"
    }

    log("\n[*] Scanning Xbox title history (fetching all pages)...", "yellow")
    all_titles = []
    continuation_token = None

    while True:
        params = {"maxItems": "100"}
        if continuation_token:
            params["continuationToken"] = continuation_token

        url = f"https://achievements.xboxlive.com/users/xuid({auth_info['xid']})/history/titles?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                titles = data.get("titles", [])
                all_titles.extend(titles)
                continuation_token = data.get("pagingInfo", {}).get("continuationToken")
                if not continuation_token or not titles:
                    break
        except Exception as e:
            log(f"[-] Error querying page: {e}", "red")
            break

    log(f"[+] Found {len(all_titles)} total played game(s) in account library.\n", "green")
    return all_titles

def lookup_store_product(product_id_or_url):
    """Queries Microsoft Display Catalog API for package family name, app ID, and SCID."""
    # Extract 12-char product ID if full URL passed
    m = re.search(r'([A-Za-z0-9]{12})', product_id_or_url)
    product_id = m.group(1).upper() if m else product_id_or_url.strip().upper()

    log(f"[*] Looking up Microsoft Store Catalog for Product ID: {product_id}...", "yellow")
    url = f"https://displaycatalog.mp.microsoft.com/v7.0/products/{product_id}?market=US&languages=en-US"
    req = urllib.request.Request(url, headers={"User-Agent": "XboxSaveRecovery/2.0"})

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(f"[-] Store Catalog lookup failed: {e}", "red")
        return None

    products = data.get("Products", [])
    if not products:
        log("[-] No product found in Store Catalog.", "red")
        return None

    prod = products[0]
    title_name = prod.get("LocalizedProperties", [{}])[0].get("ProductTitle", "Unknown Title")
    props = prod.get("Properties", {})

    pfn = props.get("PackageFamilyName", "")
    identity_name = props.get("PackageIdentityName", "")
    app_id = props.get("ApplicationId", "App")
    scid = props.get("PrimaryServiceConfigId", "")
    legacy_id = props.get("XboxTitleId", "")

    # Fallback search through SKU properties if not in top-level
    if not pfn:
        for sku in prod.get("DisplaySkuAvailabilities", []):
            for pack in sku.get("Sku", {}).get("Properties", {}).get("Packages", []):
                if "PackageFamilyName" in pack:
                    pfn = pack["PackageFamilyName"]
                    identity_name = pack.get("PackageIdentityName", "")
                    break

    info = {
        "productId": product_id,
        "titleName": title_name,
        "packageFamilyName": pfn,
        "identityName": identity_name if identity_name else (pfn.split("_")[0] if "_" in pfn else pfn),
        "applicationId": app_id if app_id else "App",
        "scid": scid if scid else (f"00000000-0000-0000-0000-0000{hex(int(legacy_id))[2:].zfill(8)}" if legacy_id else ""),
        "xboxTitleId": legacy_id
    }

    log(f"[+] Found Store Details for: {title_name}", "green")
    log(f"  * PFN:            {info['packageFamilyName']}")
    log(f"  * Identity Name:  {info['identityName']}")
    log(f"  * Application ID: {info['applicationId']}")
    log(f"  * Primary SCID:   {info['scid']}")
    return info

def generate_manifest_and_register(identity_name, pfn, app_id, target_dir=None):
    """Generates a minimal AppxManifest.xml matching the game's identity and registers it."""
    if not target_dir:
        target_dir = WORKSPACE_DIR

    target_dir = Path(target_dir)
    manifest_path = target_dir / "AppxManifest.xml"

    # Derive publisher from PFN (e.g. IdentityName_PublisherId)
    pub_id = pfn.split("_")[-1] if "_" in pfn else "8wekyb3d8bbwe"
    
    xml_content = f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
  <Identity Name="{identity_name}"
            ProcessorArchitecture="x64"
            Publisher="CN=GSC, O=Developer, C=US"
            Version="1.0.0.0" />
  <Properties>
    <DisplayName>{identity_name} Cloud Save Recovery</DisplayName>
    <PublisherDisplayName>Recovery Tool</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Resources>
    <Resource Language="en-US" />
  </Resources>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
  <Applications>
    <Application Id="{app_id}"
                 Executable="main.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{identity_name} Cloud Recovery"
                          Description="{identity_name} Cloud Save Recovery"
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Logo.png"
                          Square44x44Logo="Assets\\SmallLogo.png" />
    </Application>
  </Applications>
</Package>'''

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    # Ensure Assets directory exists
    assets_dir = target_dir / "Assets"
    assets_dir.mkdir(exist_ok=True)
    # Create empty placeholder PNG files if missing
    for name in ["Logo.png", "SmallLogo.png", "StoreLogo.png", "SplashScreen.png"]:
        p = assets_dir / name
        if not p.exists():
            with open(p, "wb") as f:
                # 1x1 transparent PNG bytes
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

    log(f"[+] Generated AppxManifest.xml for: {identity_name}", "green")

    # Register via PowerShell
    log("[*] Registering developer package in Windows...", "yellow")
    cmd = f'powershell -Command "Add-AppxPackage -Register \'{manifest_path}\'"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        log("[*** SUCCESS ***] Developer package registered successfully in Windows!", "green")
        return True
    else:
        log(f"[-] Registration warning: {res.stderr.strip()}", "yellow")
        return False

def extract_cloud_saves(scid, output_dir="ExtractedSaves"):
    """Runs the compiled WinRT bridge to download cloud saves for the given SCID."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Save config.json for the binary
    config_data = {
        "scid": scid,
        "output": str(out_path.resolve())
    }
    with open("config.json", "w") as f:
        json.dump(config_data, f, indent=2)

    # Compile binary if not present
    exe_path = WORKSPACE_DIR / "xbox_save_extractor.exe"
    if not exe_path.exists():
        log("[*] Compiling native WinRT Xbox save extractor...", "yellow")
        compile_cmd = 'cmd.exe /c "call \\"C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\Common7\\Tools\\VsDevCmd.bat\\" -arch=amd64 && cl /std:c++20 /EHsc /W4 generic_extractor.cpp /link windowsapp.lib /out:xbox_save_extractor.exe"'
        subprocess.run(compile_cmd, shell=True)

    # Copy binary to main.exe for package execution
    main_exe = WORKSPACE_DIR / "main.exe"
    if exe_path.exists():
        shutil.copy2(exe_path, main_exe)

    log(f"\n[*] Connecting to Xbox Live Cloud for SCID: {scid}...", "cyan")
    
    # Run extractor
    run_cmd = f'"{exe_path}" --scid "{scid}" --out "{out_path.resolve()}"'
    proc = subprocess.run(run_cmd, shell=True, text=True, capture_output=True)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)

    # Read recovery_log.txt if generated
    log_file = Path("recovery_log.txt")
    if log_file.exists():
        with open(log_file, "r") as f:
            log_content = f.read()
            if "RECOVERY COMPLETE" in log_content:
                log("\n[*** CLOUD EXTRACTION SUCCESSFUL ***]", "green")

    # Generate ZIP backup
    zip_path = WORKSPACE_DIR / f"XboxSaves_{scid[-12:]}_Backup.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(out_path):
            for file in files:
                p = Path(root) / file
                zf.write(p, p.relative_to(out_path))
    
    log(f"\n[+] Created Save Backup Archive: {zip_path}", "green")
    log(f"[+] Files extracted to: {out_path.resolve()}", "green")
    return True

def run_interactive_wizard():
    """Guided wizard for end-to-end cloud save extraction."""
    log("=====================================================", "cyan")
    log(" Universal Xbox Cloud Save Recovery Wizard", "bold")
    log("=====================================================\n", "cyan")

    # 1. Login
    auth = oauth_device_login()
    if not auth:
        return

    # 2. Discover
    titles = discover_games(auth)
    if not titles:
        log("[-] No titles found.", "red")
        return

    print(f"{'#':<4} {'Title Name':<45} {'Title ID':<12} {'SCID':<40}")
    print("-" * 105)
    for i, t in enumerate(titles[:50]):
        name = t.get("name", "Unknown")[:43]
        tid = str(t.get("titleId", ""))
        scid = t.get("serviceConfigId", "")
        print(f"{i+1:<4} {name:<45} {tid:<12} {scid:<40}")

    if len(titles) > 50:
        print(f"... and {len(titles) - 50} more games.")

    choice = input("\nEnter game # or search query (e.g. '1', or part of title name): ").strip()
    selected_title = None

    if choice.isdigit() and 1 <= int(choice) <= len(titles):
        selected_title = titles[int(choice) - 1]
    else:
        matches = [t for t in titles if choice.lower() in t.get("name", "").lower()]
        if matches:
            selected_title = matches[0]
            log(f"[+] Selected: {selected_title.get('name')}", "green")
        else:
            log("[-] No matching game found.", "red")
            return

    scid = selected_title.get("serviceConfigId", "")
    title_name = selected_title.get("name", "")
    tid = selected_title.get("titleId", "")

    # Store lookup if needed for PFN
    store_info = None
    store_query = input(f"\nEnter Microsoft Store Product ID or URL for '{title_name}' (e.g. from xbox.com/games/store, or press Enter to auto-derive): ").strip()
    if store_query:
        store_info = lookup_store_product(store_query)

    if not store_info:
        # Default identity derived from Title Name / Title ID
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', title_name)
        identity = clean_name if clean_name else f"Title{tid}"
        store_info = {
            "identityName": identity,
            "packageFamilyName": f"{identity}_8wekyb3d8bbwe",
            "applicationId": "App",
            "scid": scid
        }

    # Setup package manifest
    generate_manifest_and_register(
        identity_name=store_info["identityName"],
        pfn=store_info["packageFamilyName"],
        app_id=store_info["applicationId"]
    )

    # Extract
    out_dir = WORKSPACE_DIR / f"ExtractedSaves_{re.sub(r'[^a-zA-Z0-9_]', '_', title_name)}"
    extract_cloud_saves(scid=scid, output_dir=str(out_dir))

def main():
    parser = argparse.ArgumentParser(description="Universal Xbox Cloud Save Recovery CLI")
    subparsers = parser.add_subparsers(dest="command")

    # discover
    subparsers.add_parser("discover", help="Authenticate and list all played games and SCIDs from your account history")
    
    # lookup
    lookup_p = subparsers.add_parser("lookup", help="Look up Microsoft Store catalog details (PFN, SCID, AppId) from a Product ID or Store URL")
    lookup_p.add_argument("product", help="Microsoft Store 12-character Product ID (found in xbox.com store URL) or full URL")

    # setup
    setup_p = subparsers.add_parser("setup", help="Generate AppxManifest and register developer package")
    setup_p.add_argument("--identity", required=True, help="Package Identity Name")
    setup_p.add_argument("--pfn", required=True, help="Package Family Name")
    setup_p.add_argument("--appid", default="App", help="Application ID")

    # extract
    extract_p = subparsers.add_parser("extract", help="Download all cloud save containers for a SCID")
    extract_p.add_argument("--scid", required=True, help="Service Configuration ID (SCID)")
    extract_p.add_argument("--output", default="ExtractedSaves", help="Output directory")

    # wizard
    subparsers.add_parser("wizard", help="Interactive step-by-step extraction wizard")

    args = parser.parse_args()

    if args.command == "discover":
        auth = oauth_device_login()
        if auth:
            titles = discover_games(auth)
            with open("history.json", "w") as f:
                json.dump(titles, f, indent=2)
            print(f"{'Title Name':<45} {'Title ID':<12} {'SCID':<40}")
            print("-" * 100)
            for t in titles:
                name = t.get("name", "Unknown")[:43]
                tid = str(t.get("titleId", ""))
                scid = t.get("serviceConfigId", "")
                print(f"{name:<45} {tid:<12} {scid:<40}")
            log(f"\n[+] Saved full history to history.json", "green")

    elif args.command == "lookup":
        lookup_store_product(args.product)

    elif args.command == "setup":
        generate_manifest_and_register(args.identity, args.pfn, args.appid)

    elif args.command == "extract":
        extract_cloud_saves(args.scid, args.output)

    else:
        run_interactive_wizard()

if __name__ == "__main__":
    main()
