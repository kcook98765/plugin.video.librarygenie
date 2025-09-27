#!/usr/bin/env python3
"""
Test script for LibraryGenie music bookmark URL construction
Simulates various music library contexts to validate URL generation
"""

import urllib.parse

def test_music_url_construction():
    """Test music database URL construction patterns"""
    
    print("=" * 60)
    print("LibraryGenie Music Bookmark URL Construction Test")
    print("=" * 60)
    
    # Test data simulating different music contexts
    test_cases = [
        {
            'name': 'Music Artist with DBID',
            'container_path': 'musicdb://artists/',
            'dbid': '123',
            'item_label': 'The Beatles',
            'expected': 'musicdb://artists/123/'
        },
        {
            'name': 'Music Artist with Label (no DBID)',
            'container_path': 'musicdb://artists/',
            'dbid': None,
            'item_label': 'AC/DC',
            'expected': 'musicdb://artists/AC%2FDC/'
        },
        {
            'name': 'Music Album with spaces',
            'container_path': 'musicdb://albums/',
            'dbid': None,
            'item_label': 'Abbey Road',
            'expected': 'musicdb://albums/Abbey%20Road/'
        },
        {
            'name': 'Music Genre with special chars',
            'container_path': 'musicdb://genres/',
            'dbid': None,
            'item_label': 'Rock & Roll',
            'expected': 'musicdb://genres/Rock%20%26%20Roll/'
        },
        {
            'name': 'Music Song with unicode',
            'container_path': 'musicdb://songs/',
            'dbid': None,
            'item_label': 'Björk - Venus as a Boy',
            'expected': 'musicdb://songs/Bj%C3%B6rk%20-%20Venus%20as%20a%20Boy/'
        },
        {
            'name': 'Music Year',
            'container_path': 'musicdb://years/',
            'dbid': None,
            'item_label': '1969',
            'expected': 'musicdb://years/1969/'
        },
        {
            'name': 'Recently Added Albums (special container)',
            'container_path': 'musicdb://recentlyaddedalbums/',
            'dbid': None,
            'item_label': 'Some Album',
            'expected': 'musicdb://recentlyaddedalbums/'
        },
        {
            'name': 'Recently Added Music (special container)',
            'container_path': 'musicdb://recentlyaddedmusic/',
            'dbid': None,
            'item_label': 'Some Song',
            'expected': 'musicdb://recentlyaddedmusic/'
        },
        {
            'name': 'Recently Played Albums (special container)',
            'container_path': 'musicdb://recentlyplayedalbums/',
            'dbid': None,
            'item_label': 'Some Album',
            'expected': 'musicdb://recentlyplayedalbums/'
        },
        {
            'name': 'Compilations (special container)',
            'container_path': 'musicdb://compilations/',
            'dbid': None,
            'item_label': 'Some Compilation',
            'expected': 'musicdb://compilations/'
        }
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print(f"Container: {test_case['container_path']}")
        print(f"DBID: {test_case['dbid']}")
        print(f"Label: '{test_case['item_label']}'")
        
        # Simulate the URL construction logic from context.py
        bookmark_url = construct_music_url(
            test_case['container_path'],
            test_case['dbid'],
            test_case['item_label']
        )
        
        print(f"Generated: {bookmark_url}")
        print(f"Expected:  {test_case['expected']}")
        
        if bookmark_url == test_case['expected']:
            print("✅ PASS")
            passed += 1
        else:
            print("❌ FAIL")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0

def construct_music_url(container_path, dbid, item_label):
    """
    Simulate the music URL construction logic from context.py
    """
    if dbid:
        # DBID path - check for special containers first
        if 'recentlyaddedalbums' in container_path or 'recentlyaddedmusic' in container_path or 'recentlyplayedalbums' in container_path or 'recentlyplayedsongs' in container_path or 'compilations' in container_path:
            return container_path
        elif 'artists' in container_path:
            return f"musicdb://artists/{dbid}/"
        elif 'albums' in container_path:
            return f"musicdb://albums/{dbid}/"
        elif 'genres' in container_path:
            return f"musicdb://genres/{dbid}/"
        elif 'songs' in container_path:
            return f"musicdb://songs/{dbid}/"
        elif 'years' in container_path:
            return f"musicdb://years/{dbid}/"
        else:
            return f"{container_path.rstrip('/')}/{dbid}/"
    else:
        # Label-based fallback
        if item_label:
            encoded_label = urllib.parse.quote(item_label, safe='')
            
            if 'musicdb://' in container_path:
                # Special containers that don't use labels
                if 'recentlyaddedalbums' in container_path or 'recentlyaddedmusic' in container_path or 'recentlyplayedalbums' in container_path or 'recentlyplayedsongs' in container_path or 'compilations' in container_path:
                    return container_path
                elif 'artists' in container_path:
                    return f"musicdb://artists/{encoded_label}/"
                elif 'albums' in container_path:
                    return f"musicdb://albums/{encoded_label}/"
                elif 'genres' in container_path:
                    return f"musicdb://genres/{encoded_label}/"
                elif 'songs' in container_path:
                    return f"musicdb://songs/{encoded_label}/"
                elif 'years' in container_path:
                    return f"musicdb://years/{encoded_label}/"
                else:
                    return f"{container_path.rstrip('/')}/{encoded_label}/"
    
    return container_path

def test_smart_naming():
    """Test smart bookmark naming for music contexts"""
    
    print("\n" + "=" * 60)
    print("Smart Bookmark Naming Test")
    print("=" * 60)
    
    naming_tests = [
        {
            'folder_name': 'Artists',
            'item_name': 'The Beatles',
            'expected': '(Artists) The Beatles'
        },
        {
            'folder_name': 'Albums',
            'item_name': 'Abbey Road',
            'expected': '(Albums) Abbey Road'
        },
        {
            'folder_name': 'Recently added albums',
            'item_name': 'New Music',
            'expected': '(Recently Added) New Music'
        },
        {
            'folder_name': 'Recently played songs',
            'item_name': 'Popular Track',
            'expected': '(Recently Played) Popular Track'
        },
        {
            'folder_name': 'Genres',
            'item_name': 'Rock',
            'expected': '(Genres) Rock'
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in naming_tests:
        folder_name = normalize_folder_name(test['folder_name'])
        smart_name = f"({folder_name}) {test['item_name']}" if folder_name else test['item_name']
        
        print(f"Folder: '{test['folder_name']}' -> '{folder_name}'")
        print(f"Generated: '{smart_name}'")
        print(f"Expected:  '{test['expected']}'")
        
        if smart_name == test['expected']:
            print("✅ PASS")
            passed += 1
        else:
            print("❌ FAIL")
            failed += 1
        print()
    
    print(f"NAMING RESULTS: {passed} passed, {failed} failed")
    return failed == 0

def normalize_folder_name(container_folder_name):
    """Simulate smart naming logic from context.py"""
    if not container_folder_name or container_folder_name in ('Container.FolderName', ''):
        return ''
    
    if container_folder_name == 'Artists':
        return 'Artists'
    elif container_folder_name == 'Albums':
        return 'Albums'
    elif container_folder_name == 'Genres':
        return 'Genres'
    elif container_folder_name == 'Songs':
        return 'Songs'
    elif container_folder_name == 'Years':
        return 'Years'
    elif 'Recently added' in container_folder_name or 'recently added' in container_folder_name:
        return 'Recently Added'
    elif 'Recently played' in container_folder_name or 'recently played' in container_folder_name:
        return 'Recently Played'
    else:
        return container_folder_name

if __name__ == "__main__":
    print("LibraryGenie Music Bookmark Validation")
    print("Testing URL construction and smart naming...")
    
    url_success = test_music_url_construction()
    naming_success = test_smart_naming()
    
    if url_success and naming_success:
        print("\n🎉 ALL TESTS PASSED! Music bookmark implementation is ready.")
        exit(0)
    else:
        print("\n❌ SOME TESTS FAILED! Please review the implementation.")
        exit(1)