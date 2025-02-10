
# Setting Up Kodi Addon Development in Replit

This guide explains how to configure a Replit workspace for Kodi addon development.

## Initial Setup

1. Create a new Repl and select "Python" as the template
2. Install the Kodistubs package in your Repl using the Dependencies tool or command:

```bash
pip install Kodistubs
```

## Required Files

Your Repl should have these essential files:

- `addon.xml` - Addon manifest file
- `main.py` - Entry point
- Resources folder structure:
  ```
  resources/
  ├── lib/
  │   └── your_python_files.py
  ├── language/
  │   └── resource.language.en_gb/
  │       └── strings.po
  └── settings.xml
  ```

## Development Tips

1. **IDE Features**: Replit will provide code completion and documentation for Kodi's Python API through Kodistubs.

2. **Testing**: Since Kodi addons require the Kodi runtime environment, you cannot directly run the code in Replit. However, you can:
   - Use Replit for code development and version control
   - Write and test non-Kodi specific functions
   - Use mock objects for testing Kodi-specific functionality

3. **Common Issues**:
   - Import errors for xbmc modules are normal - Kodistubs provides type hints only
   - Kodi GUI elements won't render in Replit

## Best Practices

1. Organize your code into modules under `resources/lib/`
2. Use clear naming conventions
3. Keep Kodi-specific code isolated from business logic
4. Comment your code thoroughly

## Version Control

Replit's Git integration allows you to:
1. Commit changes
2. Create branches
3. Push to remote repositories

## Next Steps

1. Create your addon's basic structure
2. Implement your addon's core functionality
3. Use Replit's collaboration features for team development
4. Package your addon for distribution

Remember: While you can't run the addon directly in Replit, it provides an excellent development environment with proper code completion and documentation support through Kodistubs.
