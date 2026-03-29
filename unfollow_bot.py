"""Compatibility wrapper for old script name.

Use private_automation.py for new development.
"""

import runpy


if __name__ == "__main__":
    runpy.run_module("app.private_automation", run_name="__main__")
