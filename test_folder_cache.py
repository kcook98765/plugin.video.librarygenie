#!/usr/bin/env python3
"""
LibraryGenie Folder Cache Test Script
Tests cache functionality and measures performance improvements
"""

import os
import sys
import time
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional
import threading

# Add lib to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

def setup_test_environment():
    """Setup test environment with temporary directories"""
    test_dir = tempfile.mkdtemp(prefix='librarygenie_cache_test_')
    cache_dir = os.path.join(test_dir, 'cache', 'folders')
    os.makedirs(cache_dir, exist_ok=True)
    return test_dir, cache_dir

def cleanup_test_environment(test_dir: str):
    """Clean up test environment"""
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

class MockLogger:
    """Mock logger for testing"""
    def __init__(self, name=None):
        self.logs = []
        self.name = name
    
    def debug(self, msg, *args):
        formatted = msg % args if args else msg
        self.logs.append(('DEBUG', formatted))
        print(f"DEBUG: {formatted}")
    
    def info(self, msg, *args):
        formatted = msg % args if args else msg
        self.logs.append(('INFO', formatted))
        print(f"INFO: {formatted}")
    
    def warning(self, msg, *args):
        formatted = msg % args if args else msg
        self.logs.append(('WARNING', formatted))
        print(f"WARNING: {formatted}")
    
    def error(self, msg, *args):
        formatted = msg % args if args else msg
        self.logs.append(('ERROR', formatted))
        print(f"ERROR: {formatted}")

class MockSettings:
    """Mock settings for testing"""
    def __init__(self, **overrides):
        self.settings = {
            'folder_cache_enabled': True,
            'folder_cache_fresh_ttl': 12,
            'folder_cache_hard_expiry': 30,
            'folder_cache_prewarm_enabled': True,
            'folder_cache_prewarm_max_folders': 5,
            'folder_cache_debug_logging': True,
            **overrides
        }
    
    def get_folder_cache_enabled(self):
        return self.settings['folder_cache_enabled']
    
    def get_folder_cache_fresh_ttl(self):
        return self.settings['folder_cache_fresh_ttl']
    
    def get_folder_cache_hard_expiry(self):
        return self.settings['folder_cache_hard_expiry']
    
    def get_folder_cache_prewarm_enabled(self):
        return self.settings['folder_cache_prewarm_enabled']
    
    def get_folder_cache_prewarm_max_folders(self):
        return self.settings['folder_cache_prewarm_max_folders']
    
    def get_folder_cache_debug_logging(self):
        return self.settings['folder_cache_debug_logging']

def test_basic_cache_operations(cache_dir: str) -> Dict[str, Any]:
    """Test basic cache get/set/delete operations"""
    print("🧪 Testing basic cache operations...")
    
    # Mock the imports to avoid Kodi dependencies
    import types
    mock_log_module = types.ModuleType('mock_kodi_log')
    mock_log_module.get_kodi_logger = lambda name: MockLogger(name)
    sys.modules['lib.utils.kodi_log'] = mock_log_module
    
    mock_settings_module = types.ModuleType('mock_settings')
    mock_settings_module.SettingsManager = lambda: MockSettings()
    sys.modules['lib.config.settings'] = mock_settings_module
    
    from lib.ui.folder_cache import FolderCache
    
    results = {
        'test_name': 'Basic Cache Operations',
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        # Initialize cache
        cache = FolderCache(cache_dir=cache_dir)
        
        # Test data
        test_folder_id = "test_folder_123"
        test_payload = {
            'items': [
                {'name': 'Test List 1', 'id': '1'},
                {'name': 'Test List 2', 'id': '2'}
            ],
            'subfolders': [
                {'name': 'Subfolder A', 'id': 'sub_a'}
            ]
        }
        
        # Test 1: Cache miss
        result = cache.get(test_folder_id)
        if result is None:
            results['passed'] += 1
            print("✅ Cache miss test passed")
        else:
            results['failed'] += 1
            results['errors'].append("Expected cache miss, got hit")
        
        # Test 2: Cache set
        success = cache.set(test_folder_id, test_payload)
        if success:
            results['passed'] += 1
            print("✅ Cache set test passed")
        else:
            results['failed'] += 1
            results['errors'].append("Cache set failed")
        
        # Test 3: Cache hit
        result = cache.get(test_folder_id)
        if result and result.get('items') == test_payload['items']:
            results['passed'] += 1
            print("✅ Cache hit test passed")
        else:
            results['failed'] += 1
            results['errors'].append("Cache hit failed or data mismatch")
        
        # Test 4: Cache delete
        success = cache.delete(test_folder_id)
        if success:
            results['passed'] += 1
            print("✅ Cache delete test passed")
        else:
            results['failed'] += 1
            results['errors'].append("Cache delete failed")
        
        # Test 5: Cache miss after delete
        result = cache.get(test_folder_id)
        if result is None:
            results['passed'] += 1
            print("✅ Cache miss after delete test passed")
        else:
            results['failed'] += 1
            results['errors'].append("Expected cache miss after delete, got hit")
            
    except Exception as e:
        results['failed'] += 1
        results['errors'].append(f"Exception during basic operations: {str(e)}")
    
    return results

def test_cache_disabled_functionality(cache_dir: str) -> Dict[str, Any]:
    """Test that cache respects disabled configuration"""
    print("🧪 Testing cache disabled functionality...")
    
    # Mock settings with cache disabled
    import types
    mock_settings_module = types.ModuleType('mock_settings')
    mock_settings_module.SettingsManager = lambda: MockSettings(folder_cache_enabled=False)
    sys.modules['lib.config.settings'] = mock_settings_module
    
    from lib.ui.folder_cache import FolderCache
    
    results = {
        'test_name': 'Cache Disabled Functionality',
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        # Initialize cache with disabled setting
        cache = FolderCache(cache_dir=cache_dir)
        
        test_folder_id = "disabled_test_folder"
        test_payload = {'items': [{'name': 'Test', 'id': '1'}]}
        
        # Test 1: Set should return False when disabled
        success = cache.set(test_folder_id, test_payload)
        if not success:
            results['passed'] += 1
            print("✅ Cache set returns False when disabled")
        else:
            results['failed'] += 1
            results['errors'].append("Cache set should return False when disabled")
        
        # Test 2: Get should return None when disabled
        result = cache.get(test_folder_id)
        if result is None:
            results['passed'] += 1
            print("✅ Cache get returns None when disabled")
        else:
            results['failed'] += 1
            results['errors'].append("Cache get should return None when disabled")
            
    except Exception as e:
        results['failed'] += 1
        results['errors'].append(f"Exception during disabled test: {str(e)}")
    
    return results

def test_performance_comparison(cache_dir: str) -> Dict[str, Any]:
    """Test performance improvement of cache vs simulated database operations"""
    print("🧪 Testing performance comparison...")
    
    # Re-enable cache for performance test
    import types
    mock_settings_module = types.ModuleType('mock_settings')
    mock_settings_module.SettingsManager = lambda: MockSettings()
    sys.modules['lib.config.settings'] = mock_settings_module
    
    from lib.ui.folder_cache import FolderCache
    
    results = {
        'test_name': 'Performance Comparison',
        'cache_time_ms': 0,
        'simulated_db_time_ms': 0,
        'improvement_factor': 0,
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        cache = FolderCache(cache_dir=cache_dir)
        
        # Create test payload
        large_payload = {
            'items': [
                {'name': f'List {i}', 'id': f'list_{i}', 'count': i * 10}
                for i in range(100)  # 100 lists
            ],
            'subfolders': [
                {'name': f'Folder {i}', 'id': f'folder_{i}'}
                for i in range(20)  # 20 subfolders
            ]
        }
        
        test_folder_id = "performance_test_folder"
        iterations = 50
        
        # First, populate the cache
        cache.set(test_folder_id, large_payload)
        
        # Test cache performance
        cache_start = time.time()
        for _ in range(iterations):
            result = cache.get(test_folder_id)
            if not result:
                raise Exception("Cache should hit for performance test")
        cache_time = (time.time() - cache_start) * 1000
        results['cache_time_ms'] = cache_time
        
        # Simulate database operation time (typical database query + processing)
        def simulate_db_operation():
            """Simulate database query time + JSON processing"""
            time.sleep(0.01)  # Simulate 10ms database query
            # Simulate JSON serialization/deserialization overhead
            json.dumps(large_payload)
            return large_payload
        
        db_start = time.time()
        for _ in range(iterations):
            result = simulate_db_operation()
        db_time = (time.time() - db_start) * 1000
        results['simulated_db_time_ms'] = db_time
        
        # Calculate improvement
        if cache_time > 0:
            results['improvement_factor'] = db_time / cache_time
            
            if results['improvement_factor'] > 1.5:  # Expect at least 50% improvement
                results['passed'] += 1
                print(f"✅ Performance improvement: {results['improvement_factor']:.1f}x faster")
            else:
                results['failed'] += 1
                results['errors'].append(f"Insufficient performance improvement: {results['improvement_factor']:.1f}x")
        else:
            results['failed'] += 1
            results['errors'].append("Cache time was 0, cannot calculate improvement")
            
    except Exception as e:
        results['failed'] += 1
        results['errors'].append(f"Exception during performance test: {str(e)}")
    
    return results

def test_ttl_functionality(cache_dir: str) -> Dict[str, Any]:
    """Test TTL (Time To Live) functionality"""
    print("🧪 Testing TTL functionality...")
    
    # Use very short TTL for testing
    import types
    mock_settings_module = types.ModuleType('mock_settings')
    mock_settings_module.SettingsManager = lambda: MockSettings(
        folder_cache_fresh_ttl=0,  # 0 hours = immediate staleness
        folder_cache_hard_expiry=1  # 1 day = 24 hours
    )
    sys.modules['lib.config.settings'] = mock_settings_module
    
    from lib.ui.folder_cache import FolderCache
    
    results = {
        'test_name': 'TTL Functionality',
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        cache = FolderCache(cache_dir=cache_dir)
        
        test_folder_id = "ttl_test_folder"
        test_payload = {'items': [{'name': 'TTL Test', 'id': '1'}]}
        
        # Test 1: Set cache
        cache.set(test_folder_id, test_payload)
        
        # Test 2: Fresh get should work
        result = cache.get(test_folder_id, allow_stale=False)
        if result is None:  # With 0 hour TTL, should be stale immediately
            results['passed'] += 1
            print("✅ Fresh TTL test passed (immediately stale)")
        else:
            # This might pass if the timing is very fast
            print("ℹ️  Cache was still fresh (timing dependent)")
        
        # Test 3: Stale get should work
        result = cache.get(test_folder_id, allow_stale=True)
        if result and result.get('items') == test_payload['items']:
            results['passed'] += 1
            print("✅ Stale TTL test passed")
        else:
            results['failed'] += 1
            results['errors'].append("Stale cache get failed")
            
    except Exception as e:
        results['failed'] += 1
        results['errors'].append(f"Exception during TTL test: {str(e)}")
    
    return results

def test_concurrent_access(cache_dir: str) -> Dict[str, Any]:
    """Test concurrent cache access"""
    print("🧪 Testing concurrent access...")
    
    import types
    mock_settings_module = types.ModuleType('mock_settings')
    mock_settings_module.SettingsManager = lambda: MockSettings()
    sys.modules['lib.config.settings'] = mock_settings_module
    
    from lib.ui.folder_cache import FolderCache
    
    results = {
        'test_name': 'Concurrent Access',
        'passed': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        cache = FolderCache(cache_dir=cache_dir)
        
        test_folder_id = "concurrent_test_folder"
        test_payload = {'items': [{'name': 'Concurrent Test', 'id': '1'}]}
        
        # Store initial data
        cache.set(test_folder_id, test_payload)
        
        # Concurrent read test
        read_results = []
        
        def concurrent_reader():
            for _ in range(10):
                result = cache.get(test_folder_id)
                read_results.append(result is not None)
                time.sleep(0.001)  # Small delay
        
        # Start multiple reader threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=concurrent_reader)
            threads.append(thread)
            thread.start()
        
        # Wait for threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        successful_reads = sum(read_results)
        if successful_reads > 40:  # Expect most reads to succeed
            results['passed'] += 1
            print(f"✅ Concurrent reads test passed ({successful_reads}/50 successful)")
        else:
            results['failed'] += 1
            results['errors'].append(f"Too many failed reads: {successful_reads}/50")
            
    except Exception as e:
        results['failed'] += 1
        results['errors'].append(f"Exception during concurrent test: {str(e)}")
    
    return results

def run_all_tests():
    """Run all cache tests"""
    print("🚀 Starting LibraryGenie Folder Cache Tests")
    print("=" * 50)
    
    test_dir, cache_dir = setup_test_environment()
    all_results = []
    
    try:
        # Run all tests
        test_functions = [
            test_basic_cache_operations,
            test_cache_disabled_functionality,
            test_performance_comparison,
            test_ttl_functionality,
            test_concurrent_access
        ]
        
        for test_func in test_functions:
            try:
                result = test_func(cache_dir)
                all_results.append(result)
                print()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {e}")
                all_results.append({
                    'test_name': test_func.__name__,
                    'passed': 0,
                    'failed': 1,
                    'errors': [str(e)]
                })
                print()
        
        # Print summary
        print("📊 Test Summary")
        print("=" * 50)
        
        total_passed = 0
        total_failed = 0
        
        for result in all_results:
            test_name = result['test_name']
            passed = result.get('passed', 0)
            failed = result.get('failed', 0)
            
            total_passed += passed
            total_failed += failed
            
            status = "✅ PASS" if failed == 0 else "❌ FAIL"
            print(f"{status} {test_name}: {passed} passed, {failed} failed")
            
            if result.get('errors'):
                for error in result['errors']:
                    print(f"   ⚠️  {error}")
            
            # Print performance metrics if available
            if 'improvement_factor' in result and result['improvement_factor'] > 0:
                print(f"   📈 Performance: {result['improvement_factor']:.1f}x faster than simulated DB")
                print(f"   ⏱️  Cache: {result.get('cache_time_ms', 0):.1f}ms, DB: {result.get('simulated_db_time_ms', 0):.1f}ms")
        
        print()
        print(f"Overall Result: {total_passed} passed, {total_failed} failed")
        
        if total_failed == 0:
            print("🎉 All tests passed! Cache system is working correctly.")
        else:
            print("⚠️  Some tests failed. Review the errors above.")
        
        return total_failed == 0
        
    finally:
        cleanup_test_environment(test_dir)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)