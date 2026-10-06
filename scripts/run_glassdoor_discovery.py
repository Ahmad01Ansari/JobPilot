#!/usr/bin/env python3
"""
CLI Runner for Glassdoor UI Discovery Mode
Launches the persistent Glassdoor browser profile, navigates to search,
captures comprehensive DOM snapshots, and prints the human-readable discovery report.
Does NOT apply or submit to any jobs.
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from platforms.glassdoor.browser import GlassdoorBrowser
from platforms.glassdoor.search import GlassdoorSearch
from platforms.glassdoor.discovery import GlassdoorDiscoveryRunner
from modules.helpers import print_lg


def main():
    parser = argparse.ArgumentParser(description="Glassdoor UI Discovery Runner")
    parser.add_argument("--keyword", default="RPA Developer", help="Search keyword")
    parser.add_argument("--location", default="India", help="Location filter")
    parser.add_argument("--url", default=None, help="Direct URL to navigate to (optional)")
    parser.add_argument("--out-dir", default="debug/glassdoor", help="Artifacts directory")
    args = parser.parse_args()

    print_lg("=" * 60)
    print_lg("LAUNCHING GLASSDOOR UI DISCOVERY MODE")
    print_lg("=" * 60)

    browser = GlassdoorBrowser()
    try:
        browser.start()
        driver = browser.driver

        if args.url:
            print_lg(f"[Discovery] Navigating to URL: {args.url}")
            driver.get(args.url)
        else:
            print_lg(f"[Discovery] Navigating to search: '{args.keyword}' in '{args.location}'")
            search = GlassdoorSearch(browser=browser)
            search.navigate_to_search(keyword=args.keyword, location=args.location, easy_apply_only=True)

        browser.dismiss_overlays()

        print_lg("[Discovery] Observing runtime DOM and generating diagnostics...")
        runner = GlassdoorDiscoveryRunner(browser=browser, base_debug_dir=args.out_dir)
        report = runner.run_discovery(custom_name=args.keyword.replace(" ", "_"))

        print("\n" + report.to_human_readable() + "\n")
        print_lg(f"[Discovery] Successfully generated discovery report in: {report.artifacts_dir}")
        return 0
    except Exception as e:
        print_lg(f"[Discovery] Error during discovery: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        pass


if __name__ == "__main__":
    sys.exit(main())
