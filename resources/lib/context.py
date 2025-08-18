# Shim entrypoint kept for addon.xml compatibility.
# Delegates to the real implementation in core/context.py
from .core.context import run as _run  # rename to your callable if needed

def run(*args, **kwargs):
    return _run(*args, **kwargs)

if __name__ == "__main__":
    run()
