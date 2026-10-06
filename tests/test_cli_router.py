'''
Unit Tests for PlatformRouter & CLI Integration (Phase 16)
Validates CLI argument parsing, PlatformRouter routing across linkedin, naukri, and all,
graceful error handling, and lazy Chrome initialization gating.
'''

import sys
import unittest
from unittest.mock import MagicMock, patch

from runAiBot import parse_cli_args
from platforms.router import PlatformRouter, LinkedInPlatform, NaukriPlatform, FounditPlatform, GlassdoorPlatform
from modules.open_chrome import _should_skip_linkedin_chrome_init


class TestPlatformRouterAndCLI(unittest.TestCase):
    def test_parse_cli_args_default(self):
        with patch.object(sys, "argv", ["runAiBot.py"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "linkedin")

    def test_parse_cli_args_explicit_platforms(self):
        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "naukri"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "naukri")

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "all"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "all")

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "linkedin"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "linkedin")

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "indeed"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "indeed")

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "foundit"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "foundit")

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "glassdoor"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "glassdoor")

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "naukri", "--check-config"]):
            args = parse_cli_args()
            self.assertEqual(args.platform, "naukri")
            self.assertTrue(args.check_config)

    def test_should_skip_linkedin_chrome_init(self):
        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "naukri"]):
            self.assertTrue(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "indeed"]):
            self.assertTrue(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "foundit"]):
            self.assertTrue(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "glassdoor"]):
            self.assertTrue(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "linkedin"]):
            self.assertFalse(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py"]):
            self.assertFalse(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py", "--platform", "all"]):
            self.assertFalse(_should_skip_linkedin_chrome_init())

        with patch.object(sys, "argv", ["runAiBot.py", "--check-config"]):
            self.assertTrue(_should_skip_linkedin_chrome_init())

    def test_router_dispatch_linkedin(self):
        mock_li = MagicMock()
        mock_li.login.return_value = True
        mock_li.search_and_apply.return_value = {"platform": "linkedin", "status": "ok"}

        mock_nk = MagicMock()
        mock_in = MagicMock()

        router = PlatformRouter(linkedin_platform=mock_li, naukri_platform=mock_nk, indeed_platform=mock_in)
        res = router.route("linkedin")

        mock_li.initialize.assert_called_once()
        mock_li.login.assert_called_once()
        mock_li.search_and_apply.assert_called_once()
        mock_li.close.assert_called_once()
        mock_nk.search_and_apply.assert_not_called()
        mock_in.search_and_apply.assert_not_called()
        self.assertEqual(res["platform"], "linkedin")

    def test_router_dispatch_naukri(self):
        mock_li = MagicMock()
        mock_nk = MagicMock()
        mock_in = MagicMock()
        mock_nk.login.return_value = True
        mock_nk.search_and_apply.return_value = {"platform": "naukri", "jobs_applied": 3}

        router = PlatformRouter(linkedin_platform=mock_li, naukri_platform=mock_nk, indeed_platform=mock_in)
        res = router.route("naukri")

        mock_nk.initialize.assert_called_once()
        mock_nk.login.assert_called_once()
        mock_nk.search_and_apply.assert_called_once()
        mock_nk.close.assert_called_once()
        mock_li.search_and_apply.assert_not_called()
        mock_in.search_and_apply.assert_not_called()
        self.assertEqual(res["platform"], "naukri")
        self.assertEqual(res["jobs_applied"], 3)

    def test_router_dispatch_indeed(self):
        mock_li = MagicMock()
        mock_nk = MagicMock()
        mock_in = MagicMock()
        mock_in.login.return_value = True
        mock_in.search_and_apply.return_value = {"platform": "indeed", "jobs_applied": 4}

        router = PlatformRouter(linkedin_platform=mock_li, naukri_platform=mock_nk, indeed_platform=mock_in)
        res = router.route("indeed")

        mock_in.initialize.assert_called_once()
        mock_in.login.assert_called_once()
        mock_in.search_and_apply.assert_called_once()
        mock_in.close.assert_called_once()
        mock_li.search_and_apply.assert_not_called()
        mock_nk.search_and_apply.assert_not_called()
        self.assertEqual(res["platform"], "indeed")
        self.assertEqual(res["jobs_applied"], 4)

    def test_router_dispatch_foundit(self):
        mock_li = MagicMock()
        mock_nk = MagicMock()
        mock_in = MagicMock()
        mock_fo = MagicMock()
        mock_fo.login.return_value = True
        mock_fo.search_and_apply.return_value = {"platform": "foundit", "jobs_applied": 2}

        router = PlatformRouter(
            linkedin_platform=mock_li,
            naukri_platform=mock_nk,
            indeed_platform=mock_in,
            foundit_platform=mock_fo,
        )
        res = router.route("foundit")

        mock_fo.initialize.assert_called_once()
        mock_fo.login.assert_called_once()
        mock_fo.search_and_apply.assert_called_once()
        mock_fo.close.assert_called_once()
        mock_li.search_and_apply.assert_not_called()
        mock_nk.search_and_apply.assert_not_called()
        mock_in.search_and_apply.assert_not_called()
        self.assertEqual(res["platform"], "foundit")
        self.assertEqual(res["jobs_applied"], 2)

    def test_router_dispatch_glassdoor(self):
        mock_li = MagicMock()
        mock_nk = MagicMock()
        mock_in = MagicMock()
        mock_fo = MagicMock()
        mock_gd = MagicMock()
        mock_gd.login.return_value = True
        mock_gd.search_and_apply.return_value = {"platform": "glassdoor", "submitted": 1}

        router = PlatformRouter(
            linkedin_platform=mock_li,
            naukri_platform=mock_nk,
            indeed_platform=mock_in,
            foundit_platform=mock_fo,
            glassdoor_platform=mock_gd,
        )
        res = router.route("glassdoor")

        mock_gd.initialize.assert_called_once()
        mock_gd.login.assert_called_once()
        mock_gd.search_and_apply.assert_called_once()
        mock_gd.close.assert_called_once()
        mock_li.search_and_apply.assert_not_called()
        mock_nk.search_and_apply.assert_not_called()
        mock_in.search_and_apply.assert_not_called()
        mock_fo.search_and_apply.assert_not_called()
        self.assertEqual(res["platform"], "glassdoor")
        self.assertEqual(res["submitted"], 1)

    def test_router_dispatch_all(self):
        mock_li = MagicMock()
        mock_li.login.return_value = True
        mock_li.search_and_apply.return_value = {"platform": "linkedin", "applied": 5}

        mock_nk = MagicMock()
        mock_nk.login.return_value = True
        mock_nk.search_and_apply.return_value = {"platform": "naukri", "applied": 2}

        mock_in = MagicMock()
        mock_in.login.return_value = True
        mock_in.search_and_apply.return_value = {"platform": "indeed", "applied": 3}

        mock_fo = MagicMock()
        mock_fo.login.return_value = True
        mock_fo.search_and_apply.return_value = {"platform": "foundit", "applied": 1}

        mock_gd = MagicMock()
        mock_gd.login.return_value = True
        mock_gd.search_and_apply.return_value = {"platform": "glassdoor", "applied": 4}

        router = PlatformRouter(
            linkedin_platform=mock_li,
            naukri_platform=mock_nk,
            indeed_platform=mock_in,
            foundit_platform=mock_fo,
            glassdoor_platform=mock_gd,
        )
        res = router.route("all")

        self.assertIn("linkedin", res)
        self.assertIn("naukri", res)
        self.assertIn("indeed", res)
        self.assertIn("foundit", res)
        self.assertIn("glassdoor", res)
        mock_li.search_and_apply.assert_called_once()
        mock_nk.search_and_apply.assert_called_once()
        mock_in.search_and_apply.assert_called_once()
        mock_fo.search_and_apply.assert_called_once()
        mock_gd.search_and_apply.assert_called_once()

    def test_router_unknown_platform_raises_value_error(self):
        router = PlatformRouter()
        with self.assertRaises(ValueError):
            router.route("unknown_portal")


    def test_naukri_platform_lifecycle(self):
        mock_browser = MagicMock()
        mock_browser.is_logged_in.return_value = True

        mock_tracker = MagicMock()
        mock_config = MagicMock()
        mock_config.run_non_stop = False

        nk_plat = NaukriPlatform(
            browser=mock_browser,
            tracker=mock_tracker,
            config=mock_config,
        )

        with patch("platforms.naukri.rotator.SearchRotationEngine") as mock_rot_cls:
            mock_rot_instance = MagicMock()
            mock_rot_stats = MagicMock()
            mock_rot_stats.terms_searched = 2
            mock_rot_stats.pages_processed = 4
            mock_rot_stats.jobs_evaluated = 10
            mock_rot_stats.jobs_qualified = 5
            mock_rot_stats.jobs_skipped = 5
            mock_rot_stats.jobs_applied = 2
            mock_rot_stats.jobs_manual_required = 1
            mock_rot_stats.jobs_failed = 0
            mock_rot_stats.consecutive_skips_triggered = 0
            mock_rot_instance.run.return_value = mock_rot_stats
            mock_rot_cls.return_value = mock_rot_instance

            nk_plat.initialize()
            logged_in = nk_plat.login()
            self.assertTrue(logged_in)

            stats = nk_plat.search_and_apply()
            self.assertEqual(stats["platform"], "naukri")
            self.assertEqual(stats["jobs_applied"], 2)

            nk_plat.close()
            mock_browser.close.assert_called_once()

    def test_foundit_platform_lifecycle(self):
        mock_browser = MagicMock()
        mock_browser.is_logged_in.return_value = True

        mock_tracker = MagicMock()
        mock_config = MagicMock()
        mock_config.run_non_stop = False

        fo_plat = FounditPlatform(
            browser=mock_browser,
            tracker=mock_tracker,
            config=mock_config,
        )

        with patch("platforms.foundit.rotator.FounditRotator") as mock_rot_cls:
            mock_rot_instance = MagicMock()
            mock_rot_instance.run.return_value = {
                "platform": "foundit",
                "terms_searched": 1,
                "jobs_applied": 2,
            }
            mock_rot_cls.return_value = mock_rot_instance

            fo_plat.initialize()
            logged_in = fo_plat.login()
            self.assertTrue(logged_in)

            stats = fo_plat.search_and_apply()
            self.assertEqual(stats["platform"], "foundit")
            self.assertEqual(stats["jobs_applied"], 2)

            fo_plat.close()
            mock_browser.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
