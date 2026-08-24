import os
import sys
import struct
import glob
from pathlib import Path

def parse_containers_index(wgs_dir):
    """
    Parses Windows Game Save (wgs) containers.index file to map 
    container GUID directories and blob files back to original save game filenames.
    """
    index_file = os.path.join(wgs_dir, "containers.index")
    if not os.path.exists(index_file):
        return []

    results = []
    with open(index_file, "rb") as f:
        data = f.read()

    # containers.index structure:
    # Header: int32 version, int32 container_count
    # Each container entry contains container display name, name, GUID directory, etc.
    try:
        # Read utf-16le strings from index file
        idx = 0
        file_len = len(data)
        
        # Search for UTF-16 string pattern or GUID folders
        containers = []
        for entry in os.listdir(wgs_dir):
            entry_path = os.path.join(wgs_dir, entry)
            if os.path.isdir(entry_path) and len(entry) == 32: # 32-char hex directory name
                container_files = [f for f in os.listdir(entry_path) if f.startswith("container.")]
                if container_files:
                    containers.append((entry, entry_path, os.path.join(entry_path, container_files[0])))

        return containers
    except Exception as e:
        print(f"Error reading index: {e}")
        return []

def extract_wgs_folder(wgs_dir, output_dir):
    print(f"[*] Scanning WGS directory: {wgs_dir}")
    os.makedirs(output_dir, exist_ok=True)
    
    extracted_count = 0
    total_bytes = 0

    # Look for container directories inside wgs_dir
    for root, dirs, files in os.walk(wgs_dir):
        for file in files:
            if file.startswith("container."):
                container_file = os.path.join(root, file)
                container_dir = root
                
                # Parse container header to get file names
                try:
                    with open(container_file, "rb") as f:
                        content = f.read()
                    
                    # Look for blob names in container file
                    # Format: UTF-16-LE strings for blob names and GUIDs
                    blob_files = [f for f in os.listdir(container_dir) if f != file and not f.endswith(".tmp")]
                    
                    for blob_file in blob_files:
                        src_path = os.path.join(container_dir, blob_file)
                        if not os.path.isfile(src_path):
                            continue
                            
                        file_size = os.path.getsize(src_path)
                        
                        # Read first few bytes to detect UE5 save format (GVAS)
                        with open(src_path, "rb") as bf:
                            header = bf.read(4)
                        
                        ext = ".sav" if header == b"GVAS" else ".dat"
                        
                        rel_dir = os.path.basename(container_dir)
                        out_name = f"{rel_dir}_{blob_file}{ext}"
                        out_path = os.path.join(output_dir, out_name)
                        
                        with open(src_path, "rb") as sf, open(out_path, "wb") as df:
                            df.write(sf.read())
                            
                        print(f"  [+] Extracted: {out_name} ({file_size} bytes)")
                        extracted_count += 1
                        total_bytes += file_size

                except Exception as e:
                    print(f"  [-] Failed processing {container_file}: {e}")

    print(f"\n[+] Extracted {extracted_count} save file(s) ({total_bytes} bytes) to: {output_dir}")
    return extracted_count

def find_all_wgs_packages():
    """Finds all installed/stored packages containing local WGS save data."""
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    packages_dir = os.path.join(local_appdata, "Packages")
    matches = []
    
    if os.path.exists(packages_dir):
        for pkg in os.listdir(packages_dir):
            wgs_path = os.path.join(packages_dir, pkg, "SystemAppData", "wgs")
            if os.path.exists(wgs_path):
                # Count containers inside
                subdirs = [d for d in os.listdir(wgs_path) if os.path.isdir(os.path.join(wgs_path, d))]
                matches.append({
                    "packageName": pkg,
                    "wgsPath": wgs_path,
                    "containerCount": len(subdirs)
                })
                    
    return matches

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Universal Windows Game Save (WGS) Local Extractor")
    parser.add_argument("--package", "-p", help="Filter by package name keyword")
    parser.add_argument("--wgs-dir", "-w", help="Direct path to SystemAppData/wgs directory")
    parser.add_argument("--output", "-o", default="ExtractedSaves_WGS", help="Output directory")
    parser.add_argument("--list", "-l", action="store_true", help="List all local packages with WGS save data")
    args = parser.parse_args()

    print("=====================================================")
    print(" Universal Windows Game Save (WGS) Local Extractor")
    print("=====================================================\n")

    if args.wgs_dir:
        extract_wgs_folder(args.wgs_dir, args.output)
        return

    all_pkgs = find_all_wgs_packages()

    if args.list:
        print(f"Found {len(all_pkgs)} package(s) with local WGS save data:\n")
        print(f"{'#':<4} {'Package Name':<65} {'Containers':<10}")
        print("-" * 80)
        for i, pkg in enumerate(all_pkgs):
            print(f"{i+1:<4} {pkg['packageName']:<65} {pkg['containerCount']:<10}")
        return

    if args.package:
        filtered = [p for p in all_pkgs if args.package.lower() in p["packageName"].lower()]
        if not filtered:
            print(f"[-] No local packages found matching '{args.package}'.")
            return
        for pkg in filtered:
            out = os.path.join(args.output, pkg["packageName"])
            extract_wgs_folder(pkg["wgsPath"], out)
        return

    if not all_pkgs:
        print("[!] No local WGS save folders found in %LOCALAPPDATA%\\Packages.")
        print("    If you want to extract directly from the cloud, use: python xbox_save_tool.py wizard")
        return

    print(f"Found {len(all_pkgs)} package(s) with local WGS save data:\n")
    print(f"{'#':<4} {'Package Name':<65} {'Containers':<10}")
    print("-" * 80)
    for i, pkg in enumerate(all_pkgs):
        print(f"{i+1:<4} {pkg['packageName']:<65} {pkg['containerCount']:<10}")

    choice = input("\nEnter package # to extract (or 'all'): ").strip()
    if choice.lower() == "all":
        for pkg in all_pkgs:
            out = os.path.join(args.output, pkg["packageName"])
            extract_wgs_folder(pkg["wgsPath"], out)
    elif choice.isdigit() and 1 <= int(choice) <= len(all_pkgs):
        selected = all_pkgs[int(choice) - 1]
        out = os.path.join(args.output, selected["packageName"])
        extract_wgs_folder(selected["wgsPath"], out)
    else:
        print("[-] Invalid selection.")

if __name__ == "__main__":
    main()
