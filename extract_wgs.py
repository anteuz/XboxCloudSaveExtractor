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
                container_index_path = os.path.join(entry_path, "container.")
                if os.path.exists(container_index_path):
                    containers.append((entry, entry_path, container_index_path))

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

def find_stalker_wgs_folders():
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    packages_dir = os.path.join(local_appdata, "Packages")
    matches = []
    
    if os.path.exists(packages_dir):
        for pkg in os.listdir(packages_dir):
            if "S.T.A.L.K.E.R" in pkg or "Chernobyl" in pkg or "GSCGameWorld" in pkg:
                wgs_path = os.path.join(packages_dir, pkg, "SystemAppData", "wgs")
                if os.path.exists(wgs_path):
                    matches.append(wgs_path)
                    
    return matches

if __name__ == "__main__":
    print("=====================================================")
    print(" S.T.A.L.K.E.R. 2 - Local WGS Save File Extractor")
    print("=====================================================\n")
    
    found = find_stalker_wgs_folders()
    out_dir = os.path.join(os.getcwd(), "ExtractedSaves_WGS")
    
    if found:
        for wgs in found:
            extract_wgs_folder(wgs, out_dir)
    else:
        print("[!] No local WGS save folders found in %LOCALAPPDATA%\\Packages.")
        print("    If you downloaded saves using main.exe, check the ./ExtractedSaves folder!")
