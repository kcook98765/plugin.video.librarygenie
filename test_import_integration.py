#!/usr/bin/env python3
"""
Integration test for Import File Media feature
Tests that all modules integrate properly without runtime errors
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def test_imports():
    """Test that all import modules can be imported"""
    print("Testing module imports...")
    
    try:
        from lib.import_export.nfo_parser import NFOParser
        print("✓ NFOParser imported")
        
        from lib.import_export.file_scanner import FileScanner
        print("✓ FileScanner imported")
        
        from lib.import_export.media_classifier import MediaClassifier
        print("✓ MediaClassifier imported")
        
        from lib.import_export.art_extractor import ArtExtractor
        print("✓ ArtExtractor imported")
        
        from lib.import_export.import_handler import ImportHandler
        print("✓ ImportHandler imported")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_instantiation():
    """Test that modules can be instantiated"""
    print("\nTesting module instantiation...")
    
    try:
        from lib.import_export.nfo_parser import NFOParser
        nfo_parser = NFOParser()
        print("✓ NFOParser instantiated")
        
        from lib.import_export.file_scanner import FileScanner
        scanner = FileScanner()
        print("✓ FileScanner instantiated")
        
        from lib.import_export.media_classifier import MediaClassifier
        classifier = MediaClassifier()
        print("✓ MediaClassifier instantiated")
        
        from lib.import_export.art_extractor import ArtExtractor
        art_extractor = ArtExtractor()
        print("✓ ArtExtractor instantiated")
        
        return True
    except Exception as e:
        print(f"✗ Instantiation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_menu_integration():
    """Test that context menu integration is present"""
    print("\nTesting context menu integration...")
    
    try:
        with open('context.py', 'r') as f:
            content = f.read()
            
        if 'import_file_media' in content:
            print("✓ Import file media action found in context.py")
        else:
            print("✗ Import file media action NOT found in context.py")
            return False
            
        if 'LG Import File Media' in content or 'Import File Media' in content:
            print("✓ Import menu item found in context.py")
        else:
            print("✗ Import menu item NOT found in context.py")
            return False
            
        return True
    except Exception as e:
        print(f"✗ Context menu check failed: {e}")
        return False


def test_router_integration():
    """Test that router integration is present"""
    print("\nTesting router integration...")
    
    try:
        with open('lib/ui/router.py', 'r') as f:
            content = f.read()
            
        if "action == 'import_file_media'" in content:
            print("✓ Import file media action handler found in router")
        else:
            print("✗ Import file media action handler NOT found in router")
            return False
            
        if 'ImportHandler' in content and 'get_storage' in content:
            print("✓ ImportHandler and storage integration found in router")
        else:
            print("✗ ImportHandler or storage integration NOT found in router")
            return False
            
        return True
    except Exception as e:
        print(f"✗ Router check failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Import File Media Integration Test")
    print("=" * 60)
    
    results = []
    
    results.append(("Module Imports", test_imports()))
    results.append(("Module Instantiation", test_instantiation()))
    results.append(("Context Menu Integration", test_context_menu_integration()))
    results.append(("Router Integration", test_router_integration()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
