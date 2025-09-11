#!/usr/bin/env python3
"""
Debug script to check Kodi Favorites database state and configuration
This script helps diagnose why Kodi Favorites might not be displaying
"""

import os
import sqlite3
import sys
import tempfile

def check_database_state():
    """Check if database exists and inspect Kodi Favorites list"""
    
    # Since we're outside Kodi environment, we'll look for the database file in common locations
    # This is just for debugging purposes
    
    # Look for database file patterns
    possible_db_paths = [
        'librarygenie.db',
        'lib/librarygenie.db', 
        os.path.join(os.getcwd(), 'librarygenie.db')
    ]
    
    db_path = None
    for path in possible_db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ Database file not found in expected locations")
        print("Expected locations checked:")
        for path in possible_db_paths:
            print(f"  - {path}")
        print("\nThis is expected if the plugin hasn't been run in Kodi yet.")
        return False
    
    print(f"✅ Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("❌ Database exists but no tables found - database needs initialization")
            return False
            
        print(f"✅ Found {len(tables)} tables: {', '.join(tables)}")
        
        # Check if lists table exists
        if 'lists' not in tables:
            print("❌ 'lists' table does not exist")
            return False
        
        # Check for Kodi Favorites list
        cursor.execute("SELECT * FROM lists WHERE name = 'Kodi Favorites'")
        kodi_favorites = cursor.fetchone()
        
        if kodi_favorites:
            print(f"✅ Found 'Kodi Favorites' list with ID {kodi_favorites['id']}")
            
            # Check how many items are in it
            cursor.execute("SELECT COUNT(*) as count FROM list_items WHERE list_id = ?", [kodi_favorites['id']])
            item_count = cursor.fetchone()['count']
            print(f"   Contains {item_count} items")
        else:
            print("❌ 'Kodi Favorites' list does not exist in database")
        
        # Check all lists
        cursor.execute("SELECT id, name, created_at FROM lists")
        all_lists = cursor.fetchall()
        print(f"\n📊 All lists in database ({len(all_lists)} total):")
        for lst in all_lists:
            cursor.execute("SELECT COUNT(*) as count FROM list_items WHERE list_id = ?", [lst['id']])
            item_count = cursor.fetchone()['count']
            print(f"   - ID {lst['id']}: '{lst['name']}' ({item_count} items) - Created: {lst['created_at']}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        return False

def check_settings_configuration():
    """Check the settings configuration"""
    
    print("\n📋 Checking settings configuration...")
    
    # Check if settings.xml exists
    settings_path = "resources/settings.xml"
    if os.path.exists(settings_path):
        print(f"✅ Found settings.xml at: {settings_path}")
        
        # Read and look for favorites_integration_enabled
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'favorites_integration_enabled' in content:
                print("✅ Found 'favorites_integration_enabled' setting in settings.xml")
                
                # Extract the setting configuration
                import re
                pattern = r'<setting[^>]*id="favorites_integration_enabled"[^>]*>'
                matches = re.findall(pattern, content)
                if matches:
                    print(f"   Configuration: {matches[0]}")
            else:
                print("❌ 'favorites_integration_enabled' setting not found in settings.xml")
                
        except Exception as e:
            print(f"❌ Error reading settings.xml: {e}")
    else:
        print(f"❌ settings.xml not found at: {settings_path}")

def simulate_startup_check():
    """Simulate what should happen when plugin starts with favorites enabled"""
    
    print("\n🚀 Simulating plugin startup with favorites integration enabled...")
    
    print("Expected behavior:")
    print("1. Plugin checks if 'favorites_integration_enabled' setting is True")
    print("2. Plugin checks if database is initialized")
    print("3. Plugin checks if 'Kodi Favorites' list exists in lists table")
    print("4. If not exists, plugin creates empty 'Kodi Favorites' list")
    print("5. Plugin includes 'Kodi Favorites' in root menu lists")
    
    print("\nFrom the logs provided:")
    print("- 'Found 0 total lists' indicates no lists exist in database")
    print("- This suggests either database is not initialized or no lists have been created")
    print("- The automatic creation of 'Kodi Favorites' list is not happening")

def main():
    print("🔍 LibraryGenie Kodi Favorites Diagnostic Tool")
    print("=" * 60)
    
    database_ok = check_database_state()
    check_settings_configuration()
    simulate_startup_check()
    
    print("\n" + "=" * 60)
    print("💡 DIAGNOSIS:")
    
    if not database_ok:
        print("❌ ISSUE: Database is missing, empty, or not properly initialized")
        print("   SOLUTION: The plugin needs to run in Kodi to initialize the database")
    else:
        print("✅ Database appears to be properly set up")
    
    print("\n📋 NEXT STEPS:")
    print("1. Verify the plugin is properly installed in Kodi")
    print("2. Check that 'favorites_integration_enabled' setting is enabled")
    print("3. Run the plugin in Kodi to trigger database initialization")
    print("4. Check if the issue persists after proper database setup")

if __name__ == "__main__":
    main()