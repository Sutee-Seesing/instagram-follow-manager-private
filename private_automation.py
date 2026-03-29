"""Compatibility entrypoint for private automation.

Core module moved to app/private_automation.py.
"""

import runpy


if __name__ == "__main__":
    runpy.run_module("app.private_automation", run_name="__main__")
