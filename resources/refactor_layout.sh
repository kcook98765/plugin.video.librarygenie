#!/usr/bin/env bash
set -euo pipefail

# Run from repo root. Requires git.

# 1) Create new package folders
mkdir -p resources/lib/core
mkdir -p resources/lib/kodi
mkdir -p resources/lib/data
mkdir -p resources/lib/integrations/jsonrpc
mkdir -p resources/lib/integrations/remote_api
mkdir -p resources/lib/media
mkdir -p resources/lib/config
mkdir -p resources/lib/utils

# 2) Ensure they are Python packages
touch resources/lib/core/__init__.py
touch resources/lib/kodi/__init__.py
touch resources/lib/data/__init__.py
touch resources/lib/integrations/__init__.py
touch resources/lib/integrations/jsonrpc/__init__.py
touch resources/lib/integrations/remote_api/__init__.py
touch resources/lib/media/__init__.py
touch resources/lib/config/__init__.py
touch resources/lib/utils/__init__.py

# 3) Move files (no splitting; just grouping)
# Move context.py first (so we keep the original implementation)
if [ -f resources/lib/context.py ]; then
  git mv resources/lib/context.py resources/lib/core/context.py
fi

git mv resources/lib/runner.py                        resources/lib/core/runner.py
git mv resources/lib/route_handlers.py               resources/lib/core/route_handlers.py
git mv resources/lib/navigation_manager.py           resources/lib/core/navigation_manager.py
git mv resources/lib/directory_builder.py            resources/lib/core/directory_builder.py
git mv resources/lib/options_manager.py              resources/lib/core/options_manager.py

git mv resources/lib/kodi_helper.py                  resources/lib/kodi/kodi_helper.py
git mv resources/lib/listitem_builder.py             resources/lib/kodi/listitem_builder.py
git mv resources/lib/listitem_infotagvideo.py        resources/lib/kodi/listitem_infotagvideo.py
git mv resources/lib/context_menu_builder.py         resources/lib/kodi/context_menu_builder.py
git mv resources/lib/window_search.py                resources/lib/kodi/window_search.py
git mv resources/lib/url_builder.py                  resources/lib/kodi/url_builder.py

git mv resources/lib/database_manager.py             resources/lib/data/database_manager.py
git mv resources/lib/query_manager.py                resources/lib/data/query_manager.py
git mv resources/lib/results_manager.py              resources/lib/data/results_manager.py
git mv resources/lib/folder_list_manager.py          resources/lib/data/folder_list_manager.py

git mv resources/lib/jsonrpc_manager.py              resources/lib/integrations/jsonrpc/jsonrpc_manager.py

git mv resources/lib/remote_api_client.py            resources/lib/integrations/remote_api/remote_api_client.py
git mv resources/lib/remote_api_setup.py             resources/lib/integrations/remote_api/remote_api_setup.py
git mv resources/lib/authenticate_code.py            resources/lib/integrations/remote_api/authenticate_code.py
git mv resources/lib/imdb_upload_manager.py          resources/lib/integrations/remote_api/imdb_upload_manager.py
git mv resources/lib/shortlist_importer.py           resources/lib/integrations/remote_api/shortlist_importer.py

git mv resources/lib/media_manager.py                resources/lib/media/media_manager.py

git mv resources/lib/config_manager.py               resources/lib/config/config_manager.py
git mv resources/lib/settings_manager.py             resources/lib/config/settings_manager.py
git mv resources/lib/addon_ref.py                    resources/lib/config/addon_ref.py
git mv resources/lib/addon_helper.py                 resources/lib/config/addon_helper.py

git mv resources/lib/singleton_base.py               resources/lib/utils/singleton_base.py
git mv resources/lib/utils.py                        resources/lib/utils/utils.py

# 4) Create a thin shim for addon.xml’s context entrypoint
cat > resources/lib/context.py <<'PY'
# Shim entrypoint kept for addon.xml compatibility.
# Delegates to the real implementation in core/context.py
from .core.context import run as _run  # rename to your callable if needed

def run(*args, **kwargs):
    return _run(*args, **kwargs)

if __name__ == "__main__":
    run()
PY

git add resources/lib/context.py

# 5) Rewrite imports to new package paths
python3 - <<'PY'
import os, re, io, sys

# Map old module names -> new dotted paths
MAPPING = {
    'runner':                          'core.runner',
    'route_handlers':                  'core.route_handlers',
    'navigation_manager':              'core.navigation_manager',
    'directory_builder':               'core.directory_builder',
    'options_manager':                 'core.options_manager',

    'kodi_helper':                     'kodi.kodi_helper',
    'listitem_builder':                'kodi.listitem_builder',
    'listitem_infotagvideo':           'kodi.listitem_infotagvideo',
    'context_menu_builder':            'kodi.context_menu_builder',
    'window_search':                   'kodi.window_search',
    'url_builder':                     'kodi.url_builder',

    'database_manager':                'data.database_manager',
    'query_manager':                   'data.query_manager',
    'results_manager':                 'data.results_manager',
    'folder_list_manager':             'data.folder_list_manager',

    'jsonrpc_manager':                 'integrations.jsonrpc.jsonrpc_manager',

    'remote_api_client':               'integrations.remote_api.remote_api_client',
    'remote_api_setup':                'integrations.remote_api.remote_api_setup',
    'authenticate_code':               'integrations.remote_api.authenticate_code',
    'imdb_upload_manager':             'integrations.remote_api.imdb_upload_manager',
    'shortlist_importer':              'integrations.remote_api.shortlist_importer',

    'media_manager':                   'media.media_manager',

    'config_manager':                  'config.config_manager',
    'settings_manager':                'config.settings_manager',
    'addon_ref':                       'config.addon_ref',
    'addon_helper':                    'config.addon_helper',

    'singleton_base':                  'utils.singleton_base',
    'utils':                           'utils.utils',
}

PY_FILE_EXTS = {'.py'}
ROOTS = ['.', 'resources/lib', 'resources']

# Patterns to catch both "from .X import" and "import resources.lib.X as ..."
pat_from_rel = re.compile(r'^(from\s+\.)([a-zA-Z_][a-zA-Z0-9_]*)\s+(import\s+.+)$')
pat_import_abs = re.compile(r'^(from\s+resources\.lib\.)([a-zA-Z_][a-zA-Z0-9_\.]*)\s+(import\s+.+)$')
pat_plain_import = re.compile(r'^(import\s+resources\.lib\.)([a-zA-Z_][a-zA-Z0-9_\.]*)(\s+as\s+\w+|\s*)$')

def rewrite_line(line: str) -> str:
    # from .module import ...
    m = pat_from_rel.match(line)
    if m:
        prefix, mod, rest = m.groups()
        if mod in MAPPING:
            return f"{prefix}{MAPPING[mod]} {rest}\n"
        return line

    # from resources.lib.module import ...
    m = pat_import_abs.match(line)
    if m:
        prefix, mod, rest = m.groups()
        parts = mod.split('.')
        if parts and parts[0] in MAPPING:
            parts[0] = MAPPING[parts[0]]
            return f"{prefix}{'.'.join(parts)} {rest}\n"
        return line

    # import resources.lib.module [as alias]
    m = pat_plain_import.match(line)
    if m:
        prefix, mod, tail = m.groups()
        parts = mod.split('.')
        if parts and parts[0] in MAPPING:
            parts[0] = MAPPING[parts[0]]
            return f"{prefix}{'.'.join(parts)}{tail}\n"
        return line

    return line

def process_file(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    changed = False
    new_lines = []
    for ln in lines:
        nl = rewrite_line(ln)
        if nl != ln:
            changed = True
        new_lines.append(nl)
    if changed:
        with io.open(path, 'w', encoding='utf-8', newline='') as f:
            f.writelines(new_lines)
        print(f"rewrote imports: {path}")

def walk_and_rewrite():
    for root, dirs, files in os.walk('.'):
        # skip .git and non-code dirs
        if '.git' in root.split(os.sep):
            continue
        for fn in files:
            if os.path.splitext(fn)[1] in PY_FILE_EXTS:
                process_file(os.path.join(root, fn))

if __name__ == '__main__':
    walk_and_rewrite()
PY

git add -A

echo "====== STAGED CHANGES SUMMARY ======"
git status --short
echo
git diff --staged --name-status
