#!python
import math
import os
import hashlib
import argparse

def print_overwrite(message):
    # Use \r to return to the start of the line and overwrite it
    print(f"\r{message}", end='', flush=True)

def compute_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def count_files(directory):
    total_files = 0
    for _, _, files in os.walk(directory):
        total_files += len(files)
    return total_files

def remove_duplicates(directory, all_files):
    seen_checksums = set()
    cnt = 0
    pct = 0
    file_cnt = 0
    print_overwrite(f"{file_cnt}/{all_files} ({pct}%) - {cnt} files deleted ...")
    for root, _, files in os.walk(directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                file_cnt += 1
                new_pct = math.floor(file_cnt * 100/ all_files)
                if new_pct > pct:
                    pct = new_pct
                    print_overwrite(f"{file_cnt}/{all_files} ({pct}%) - {cnt} files deleted ...")
                checksum = compute_sha256(file_path)
                if checksum in seen_checksums:
                    #print("Skipping duplicate file: {}".format(file_path))
                    os.remove(file_path)
                    cnt += 1
                else:
                    seen_checksums.add(checksum)
            except Exception as e:
                print()
                print("Failed to compute checksum for file {}: {}".format(file_path, e))
    return cnt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove duplicate files based on SHA-256 checksum.")
    parser.add_argument("directory", type=str, help="The directory to scan for duplicates")
    args = parser.parse_args()

    cnt = remove_duplicates(args.directory, count_files(args.directory))
    print()
    print(f'{cnt} duplicate files were removed.')