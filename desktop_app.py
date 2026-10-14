"""WoW MCP Control Center launcher.

Launch: py -3 desktop_app.py
UI implementation: desktop_app_modern.py
"""
from desktop_app_modern import ControlCenter, main
from ui_models import source_label, time_label

__all__ = ["ControlCenter", "main", "source_label", "time_label"]

if __name__ == "__main__":
    main()
