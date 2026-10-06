'''
Unit Tests for Glassdoor Configuration & Package Structure
Validates configuration loading, validation rules, and package exports.
Fulfills Phase B deliverable: Package skeleton and config schema integration.
'''

import unittest
from unittest.mock import patch

from modules.config_loader import (
    get_platform,
    validate_glassdoor_config,
    load_profile,
)
import platforms.glassdoor as glassdoor


class TestGlassdoorConfig(unittest.TestCase):
    def test_package_exports(self):
        self.assertTrue(hasattr(glassdoor, "GlassdoorBrowser"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorAuth"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorSearch"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorParser"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorForm"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorSubmitter"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorCaptchaHandler"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorApplier"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorRotator"))
        self.assertTrue(hasattr(glassdoor, "GlassdoorJobItem"))

    def test_get_platform_glassdoor(self):
        cfg = get_platform("glassdoor")
        self.assertIsInstance(cfg, dict)
        self.assertTrue(cfg.get("enabled"))
        self.assertIn("search_terms", cfg)
        self.assertIn("search_location", cfg)
        self.assertIn("experience_years", cfg)
        self.assertIn("apply_mode", cfg)

    def test_validate_glassdoor_config_success(self):
        self.assertTrue(validate_glassdoor_config())

    @patch("modules.config_loader.get_platform")
    def test_validate_glassdoor_config_missing(self, mock_get_plat):
        mock_get_plat.return_value = None
        with self.assertRaises(ValueError) as ctx:
            validate_glassdoor_config()
        self.assertIn("Missing 'glassdoor' section", str(ctx.exception))

    @patch("modules.config_loader.get_platform")
    def test_validate_glassdoor_config_invalid_search_terms(self, mock_get_plat):
        mock_get_plat.return_value = {
            "enabled": True,
            "search_terms": [],
            "search_location": "India",
            "experience_years": 5,
        }
        with self.assertRaises(ValueError) as ctx:
            validate_glassdoor_config()
        self.assertIn("search_terms", str(ctx.exception))

    @patch("modules.config_loader.get_platform")
    def test_validate_glassdoor_config_invalid_apply_mode(self, mock_get_plat):
        mock_get_plat.return_value = {
            "enabled": True,
            "search_terms": ["Developer"],
            "search_location": "India",
            "experience_years": 5,
            "apply_mode": "unsupported_mode",
            "pause_before_submit": False,
        }
        with self.assertRaises(ValueError) as ctx:
            validate_glassdoor_config()
        self.assertIn("apply_mode", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
