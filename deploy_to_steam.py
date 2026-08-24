#!/usr/bin/env python3
"""
Universal Save Game Deployment Tool
Copies extracted save files into target game save directories (e.g. Steam, GOG, Epic) with automatic zip backup.
"""

import os
import sys
import shutil
import zipfile
import argparse
from pathlib import Path

def deploy_saves(src_dir, target_dir, backup_zip=None):
    src_path = Path(src_dir).resolve()
    target_path = Path(target_dir).resolve()

    if not src_path.exists():
        print(f"[-] Error: Source directory does not exist: {src_path}")
        return False

    print("=====================================================")
    print(" Universal Save Deployment Tool")
    print("=====================================================\n")

    # 1. Create a complete Zip Backup
    if backup_zip is None:
        backup_zip = src_path.parent / f"{src_path.name}_Backup.zip"
    else:
        backup_zip = Path(backup_zip)

    print(f"[*] Creating ZIP backup at: {backup_zip}...")
    with zipfile.ZipFile(backup_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_path):
            for file in files:
                abs_p = Path(root) / file
                rel_p = abs_p.relative_to(src_path)
                zf.write(abs_p, rel_p)
    print(f"[+] Backup ZIP created successfully ({backup_zip.stat().st_size} bytes).\n")

    # 2. Deploy to target save directory
    print(f"[*] Target Save Directory: {target_path}")
    target_path.mkdir(parents=True, exist_ok=True)

    # Copy files
    copied_count = 0
    for root, dirs, files in os.walk(src_path):
        for file in files:
            src_file = Path(root) / file
            rel_path = src_file.relative_to(src_path)
            
            dest_file = target_path / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            print(f"  [+] Installed: {dest_file.name} -> {dest_file.parent}")
            copied_count += 1

    print(f"\n[*** SUCCESS ***] Deployed {copied_count} save file(s) directly to {target_path}!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Deploy extracted saves to Steam/GOG/Epic directory")
    parser.add_argument("--source", "-s", default="ExtractedSaves", help="Directory containing extracted save files")
    parser.add_argument("--target", "-t", help="Target save directory (e.g. %LOCALAPPDATA%\\<Game>\\Saved\\SaveGames or Steam userdata path)")
    parser.add_argument("--backup", "-b", help="Optional path for backup zip file")
    args = parser.parse_args()

    target = args.target
    if not target:
        print("Common save locations:")
        print("  - Unreal Engine: %LOCALAPPDATA%\\<GameName>\\Saved\\SaveGames\\")
        print("  - Unity:         %USERPROFILE%\\AppData\\LocalLow\\<Developer>\\<GameName>\\")
        print("  - Saved Games:   %USERPROFILE%\\Saved Games\\<GameName>\\")
        print("  - Steam Remote:  <SteamFolder>\\userdata\\<SteamID>\\<AppID>\\remote\\\n")
        target = input("Enter target save directory path: ").strip()

    if not target:
        print("[-] Error: No target directory provided.")
        return

    # Expand environment variables like %LOCALAPPDATA%
    expanded_target = os.path.expandvars(target)
    deploy_saves(args.source, expanded_target, args.backup)

if __name__ == "__main__":
    main()
