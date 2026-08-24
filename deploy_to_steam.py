import os
import shutil
import zipfile
from pathlib import Path

def main():
    src_dir = Path(r"C:\StalkerRecovery\ExtractedSaves")
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    steam_save_dir = Path(local_appdata) / "Stalker2" / "Saved" / "SaveGames"
    backup_zip = Path(r"C:\StalkerRecovery\Stalker2_CloudSaves_Backup.zip")

    print("=====================================================")
    print(" S.T.A.L.K.E.R. 2 - Save Deployment to Steam")
    print("=====================================================\n")

    # 1. Create a complete Zip Backup
    print(f"[*] Creating ZIP backup at: {backup_zip}...")
    with zipfile.ZipFile(backup_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                abs_p = Path(root) / file
                rel_p = abs_p.relative_to(src_dir)
                zf.write(abs_p, rel_p)
    print(f"[+] Backup ZIP created successfully ({backup_zip.stat().st_size} bytes).\n")

    # 2. Deploy to Steam save directory
    print(f"[*] Target Steam Save Directory: {steam_save_dir}")
    steam_save_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    copied_count = 0
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            src_file = Path(root) / file
            rel_path = src_file.relative_to(src_dir)
            
            # Destination inside SaveGames
            dest_file = steam_save_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            print(f"  [+] Installed: {dest_file.name} -> {dest_file.parent}")
            copied_count += 1

    print(f"\n[*** SUCCESS ***] Deployed {copied_count} save file(s) directly to Steam!")

if __name__ == "__main__":
    main()
