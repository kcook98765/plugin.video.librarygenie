#!/usr/bin/env python3
"""Main script to renumber all string IDs one at a time"""
import subprocess
import sys

def load_ids(filename):
    """Load IDs from file"""
    with open(filename, 'r') as f:
        return set(int(line.strip()) for line in f if line.strip())

def main():
    # Load existing IDs to avoid conflicts
    existing_safe_ids = load_ids('/tmp/existing_safe_ids.txt')
    ids_to_renumber = sorted(load_ids('/tmp/ids_to_renumber.txt'))
    
    print(f"Processing {len(ids_to_renumber)} string IDs...")
    print(f"Avoiding {len(existing_safe_ids)} existing IDs in safe range")
    print()
    
    next_available = 30000
    processed = 0
    
    for old_id in ids_to_renumber:
        # Find next available ID
        while next_available in existing_safe_ids:
            next_available += 1
            if next_available > 32767:
                print("ERROR: No more available IDs in safe range!")
                sys.exit(1)
        
        new_id = next_available
        
        # Process this one ID
        result = subprocess.run(
            ['python3', 'process_one_id.py', str(old_id), str(new_id)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"ERROR processing {old_id}: {result.stderr}")
            sys.exit(1)
        
        print(result.stdout.strip())
        
        # Mark this new ID as used
        existing_safe_ids.add(new_id)
        next_available += 1
        
        processed += 1
        if processed % 10 == 0:
            print(f"Progress: {processed}/{len(ids_to_renumber)} IDs processed")
            print()
    
    print()
    print(f"✓ Complete! Processed {processed} string IDs")
    print(f"✓ All IDs now in safe range (30000-32767)")

if __name__ == '__main__':
    main()
