#!/usr/bin/env python3
"""Process one string ID at a time - rename from old ID to new ID"""
import sys
import re
import subprocess
from pathlib import Path

def find_next_available_id(existing_ids, start_from=30000):
    """Find next available ID in safe range"""
    current = start_from
    while current in existing_ids:
        current += 1
        if current > 32767:
            raise Exception("No available IDs in safe range!")
    return current

def replace_in_codebase(old_id, new_id):
    """Replace old_id with new_id across entire codebase"""
    # Pattern that matches the ID with non-digit boundaries
    pattern = f'([^0-9]){old_id}([^0-9])'
    replacement = f'\\1{new_id}\\2'
    
    # Find all Python and XML files (excluding this script and strings.po)
    cmd = [
        'find', '.', '-type', 'f',
        '(', '-name', '*.py', '-o', '-name', '*.xml', ')',
        '!', '-path', '*/strings.po',
        '!', '-path', '*/process_one_id.py',
        '!', '-path', '*/.git/*'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    files = result.stdout.strip().split('\n')
    
    updated_files = []
    for filepath in files:
        if not filepath:
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = re.sub(pattern, replacement, content)
            
            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated_files.append(filepath)
        except:
            pass
    
    return updated_files

def update_strings_po(old_id, new_id):
    """Update the ID in strings.po"""
    filepath = 'resources/language/resource.language.en_gb/strings.po'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the msgctxt line
    pattern = f'msgctxt "#{old_id}"'
    replacement = f'msgctxt "#{new_id}"'
    
    new_content = content.replace(pattern, replacement)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return pattern in content

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: process_one_id.py <old_id> <new_id>")
        sys.exit(1)
    
    old_id = int(sys.argv[1])
    new_id = int(sys.argv[2])
    
    # Update codebase
    updated_files = replace_in_codebase(old_id, new_id)
    
    # Update strings.po
    updated_po = update_strings_po(old_id, new_id)
    
    print(f"✓ Renamed {old_id} → {new_id}")
    if updated_files:
        print(f"  Updated {len(updated_files)} file(s) in codebase")
    if updated_po:
        print(f"  Updated strings.po")
