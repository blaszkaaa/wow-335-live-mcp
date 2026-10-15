"""Check that the normal in-game RGB panel is present again."""
from pathlib import Path
import unittest


class VisualAddonTests(unittest.TestCase):
    def test_lower_left_panel_and_no_dll_publisher(self):
        code = (Path(__file__).resolve().parents[1] / "WoWMCPData" /
                "WoWMCPData.lua").read_text(encoding="utf-8")
        self.assertIn('WoWMCPDataPanel", UIParent', code)
        self.assertIn('panel:SetPoint("BOTTOMLEFT", UIParent, "BOTTOMLEFT", 8, 8)', code)
        self.assertIn('panel:CreateTexture(nil, "OVERLAY")', code)
        self.assertIn('panel:SetScript("OnUpdate"', code)
        self.assertIn("render_page()", code)
        self.assertNotIn("WoWMCP.Publish", code)
        self.assertNotIn("native_available()", code)
        self.assertNotIn("native_refresh_age", code)


if __name__ == "__main__":
    unittest.main()
