#!/usr/bin/env python3
"""
Renumber all string IDs in LibraryGenie addon to safe range (30000+)
Avoids Kodi core reserved IDs
"""

import re
import os
from collections import OrderedDict

def extract_strings_from_po(filepath):
    """Extract all string entries from .po file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match msgctxt entries
    pattern = r'msgctxt "#(\d+)"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"'
    matches = re.findall(pattern, content)
    
    entries = OrderedDict()
    for string_id, msgid, msgstr in matches:
        entries[int(string_id)] = {
            'msgid': msgid,
            'msgstr': msgstr,
            'original_id': int(string_id)
        }
    
    return entries

def create_id_mapping(entries, start_id=30000):
    """Create mapping from old IDs to new sequential IDs"""
    mapping = {}
    used_ids = set(entries.keys())
    new_id = start_id
    
    for old_id in sorted(entries.keys()):
        # Find next available ID
        while new_id in used_ids and new_id != old_id:
            new_id += 1
        
        mapping[old_id] = new_id
        new_id += 1
    
    return mapping

def build_new_po_content(entries, mapping):
    """Build new strings.po with renumbered IDs"""
    lines = []
    lines.append('# LibraryGenie Language File')
    lines.append('# Addon for Kodi')
    lines.append('')
    
    for old_id in sorted(entries.keys()):
        new_id = mapping[old_id]
        entry = entries[old_id]
        lines.append(f'msgctxt "#{new_id}"')
        lines.append(f'msgid "{entry["msgid"]}"')
        lines.append(f'msgstr "{entry["msgstr"]}"')
        lines.append('')
    
    return '\n'.join(lines)

def replace_in_codebase(mapping, exclude_files):
    """Replace all 5-digit string IDs globally across codebase"""
    total_replacements = 0
    files_changed = []
    
    # Find all files to process
    for root, dirs, files in os.walk('.'):
        # Skip hidden and irrelevant dirs
        if '/.git' in root or '/venv' in root or '/__pycache__' in root:
            continue
        
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Skip excluded files
            if any(excl in filepath for excl in exclude_files):
                continue
            
            # Only process text files
            if not (filename.endswith('.py') or filename.endswith('.xml') or filename.endswith('.po')):
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Sort by old_id descending to avoid partial replacements (e.g., 3000 before 30000)
                for old_id in sorted(mapping.keys(), reverse=True):
                    new_id = mapping[old_id]
                    if old_id == new_id:
                        continue
                    
                    # Regex: exactly 5 digits with non-digit before and after
                    # Using word boundary \D to ensure we don't match partial numbers
                    pattern = rf'(\D){old_id}(\D)'
                    replacement = rf'\g<1>{new_id}\g<2>'
                    content = re.sub(pattern, replacement, content)
                
                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Count actual replacements
                    reps = sum(1 for old, new in mapping.items() if old != new and str(old) in original_content)
                    total_replacements += reps
                    files_changed.append((filepath, reps))
            
            except Exception as e:
                print(f"  ERROR processing {filepath}: {e}")
    
    return total_replacements, files_changed

def main():
    print("=== LibraryGenie String ID Renumbering ===\n")
    
    po_file = 'resources/language/resource.language.en_gb/strings.po'
    new_po_file = 'strings_new.po'
    
    # Step 1: Extract strings
    print("Step 1: Extracting strings from .po file...")
    entries = extract_strings_from_po(po_file)
    print(f"  Found {len(entries)} string entries")
    
    # Step 2: Create mapping
    print("\nStep 2: Creating ID mapping (starting at 30000)...")
    mapping = create_id_mapping(entries, start_id=30000)
    changes = sum(1 for old, new in mapping.items() if old != new)
    print(f"  {changes} IDs need to be changed")
    
    # Show sample mappings
    print("\n  Sample mappings:")
    count = 0
    for old_id, new_id in mapping.items():
        if old_id != new_id and count < 10:
            print(f"    {old_id} -> {new_id}")
            count += 1
    
    # Step 3: Replace in codebase (excluding .po files)
    print("\nStep 3: Replacing IDs globally in codebase...")
    print("  Using regex: (\\D){5-digit-number}(\\D)")
    exclude_files = [po_file, new_po_file, 'renumber_strings.py']
    total_replacements, files_changed = replace_in_codebase(mapping, exclude_files)
    
    for filepath, reps in files_changed[:20]:  # Show first 20 files
        print(f"  {filepath}: ~{reps} IDs changed")
    
    if len(files_changed) > 20:
        print(f"  ... and {len(files_changed) - 20} more files")
    
    print(f"\n  Files modified: {len(files_changed)}")
    
    # Step 4: Build new .po file
    print("\nStep 4: Building new strings.po...")
    new_po_content = build_new_po_content(entries, mapping)
    with open(new_po_file, 'w', encoding='utf-8') as f:
        f.write(new_po_content)
    print(f"  Created {new_po_file}")
    
    # Step 5: Summary
    print("\n=== Complete ===")
    print(f"\nSummary:")
    print(f"  - {changes} string IDs renumbered")
    print(f"  - {len(files_changed)} files modified")
    print(f"  - New strings file: {new_po_file}")
    
    print("\nNext steps:")
    print(f"1. Review {new_po_file}")
    print(f"2. If satisfied, replace original: mv {new_po_file} {po_file}")
    print("3. Test the addon to verify all labels display correctly")

if __name__ == '__main__':
    main()
