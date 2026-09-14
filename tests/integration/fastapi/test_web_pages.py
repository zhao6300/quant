import subprocess
import time
import urllib.request
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_console_pages_through_headless_browser() -> None:
    web_url = "http://127.0.0.1:8766/"
    process = subprocess.Popen(
        [
            str(PROJECT_ROOT / "scripts" / "start.sh"),
            "--foreground",
            "--host",
            "127.0.0.1",
            "--port",
            "8766",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    try:
        poll_count = 0
        for _ in range(90):
            try:
                with urllib.request.urlopen(web_url) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
                poll_count += 1
        else:
            raise AssertionError(f"web server did not start (poll_count={poll_count})")

        expected_pages = ["总览", "数据", "因子", "回测"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1512, "height": 982})
            page.goto(web_url, wait_until="domcontentloaded")
            page.wait_for_selector("button.nav-item")
            page.screenshot(path="/tmp/mmqp-page-overview.png", full_page=True)

            for page_name in expected_pages:
                page.get_by_role("button", name=page_name).click()
                page.wait_for_timeout(100)
                assert page.get_by_role("button", name=page_name).get_attribute("aria-current") == "page"
                assert page.locator("main.content").inner_text().strip()
                page.screenshot(path=f"/tmp/mmqp-page-{page_name}.png", full_page=True)

            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
