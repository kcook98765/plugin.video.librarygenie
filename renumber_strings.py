#!/usr/bin/env python3
"""
Renumber all string IDs in LibraryGenie addon to safe range (30000+)
Avoids Kodi core reserved IDs
"""

import re
import os
from collections import OrderedDict

# Files to search and replace
PY_FILES = []
XML_FILES = []
PO_FILES = ['resources/language/resource.language.en_gb/strings.po']

# Find all Python and XML files
for root, dirs, files in os.walk('.'):
    # Skip hidden dirs and non-addon dirs
    if '/.git' in root or '/venv' in root or '/__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            PY_FILES.append(os.path.join(root, file))
        elif file.endswith('.xml'):
            XML_FILES.append(os.path.join(root, file))

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
    
    return entries, content

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

def replace_in_file(filepath, mapping):
    """Replace string IDs in a file using the mapping"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    replacements = 0
    
    # Sort by old_id descending to avoid partial replacements
    for old_id in sorted(mapping.keys(), reverse=True):
        new_id = mapping[old_id]
        if old_id == new_id:
            continue
        
        # Different patterns for different file types
        if filepath.endswith('.py'):
            # L(32500), getLocalizedString(32500)
            patterns = [
                (rf'\bL\({old_id}\)', f'L({new_id})'),
                (rf'getLocalizedString\({old_id}\)', f'getLocalizedString({new_id})'),
                (rf'ADDON\.getLocalizedString\({old_id}\)', f'ADDON.getLocalizedString({new_id})')
            ]
        elif filepath.endswith('.xml'):
            # $LOCALIZE[32500] or label="32500"
            patterns = [
                (rf'\$LOCALIZE\[{old_id}\]', f'$LOCALIZE[{new_id}]'),
                (rf'label="{old_id}"', f'label="{new_id}"')
            ]
        elif filepath.endswith('.po'):
            # msgctxt "#32500"
            patterns = [
                (rf'msgctxt "#{old_id}"', f'msgctxt "#{new_id}"')
            ]
        else:
            continue
        
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                replacements += re.subn(pattern, replacement, content)[1]
                content = new_content
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return replacements
    
    return 0

def main():
    print("=== LibraryGenie String ID Renumbering ===\n")
    
    # Step 1: Extract strings
    print("Step 1: Extracting strings from .po file...")
    entries, original_po = extract_strings_from_po(PO_FILES[0])
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
    
    # Step 3: Build new .po file
    print("\nStep 3: Building new strings.po...")
    new_po_content = build_new_po_content(entries, mapping)
    with open('strings_new.po', 'w', encoding='utf-8') as f:
        f.write(new_po_content)
    print(f"  Created strings_new.po")
    
    # Step 4: Replace in all files
    print("\nStep 4: Replacing IDs in codebase...")
    all_files = PY_FILES + XML_FILES + PO_FILES
    total_replacements = 0
    
    for filepath in all_files:
        try:
            reps = replace_in_file(filepath, mapping)
            if reps > 0:
                print(f"  {filepath}: {reps} replacements")
                total_replacements += reps
        except Exception as e:
            print(f"  ERROR in {filepath}: {e}")
    
    print(f"\n  Total replacements: {total_replacements}")
    
    # Step 5: Verify
    print("\nStep 5: Verification...")
    print(f"  New strings.po created: strings_new.po")
    print(f"  To apply: mv strings_new.po resources/language/resource.language.en_gb/strings.po")
    
    print("\n=== Complete ===")
    print("\nNext steps:")
    print("1. Review strings_new.po")
    print("2. If satisfied, replace original: mv strings_new.po resources/language/resource.language.en_gb/strings.po")
    print("3. Test the addon to verify all labels display correctly")

if __name__ == '__main__':
    main()
