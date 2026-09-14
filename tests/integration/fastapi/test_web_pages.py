import os
import subprocess
import time
import urllib.error
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

    if not os.environ.get("MMQP_CHROMIUM_EXECUTABLE_PATH"):
        pytest.skip("MMQP_CHROMIUM_EXECUTABLE_PATH is not configured")

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

        expected_pages = ["总览", "数据", "因子", "回测", "数据源", "行情"]

        headings = {

            "总览": ["研究总览", "新建工作区", "已注册工作区"],

            "数据": ["数据查询"],

            "因子": ["多市场日历与规则"],

            "回测": ["研究运行"],

            "数据源": ["外部数据源"],
            "行情": ["行情快照"],

        }

        heading_counts = {

            "总览": 3,

            "数据": 1,

            "因子": 1,

            "回测": 1,

            "数据源": 1,
            "行情": 0,

        }

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(

                headless=True,

                executable_path=os.environ.get("MMQP_CHROMIUM_EXECUTABLE_PATH") or None,

            )

            page = browser.new_page(viewport={"width": 1512, "height": 982})

            page.goto(web_url, wait_until="domcontentloaded")

            page.wait_for_selector("button.nav-item")

            layout = page.evaluate(

                """

                () => {

                    const sidebar = document.querySelector('aside.sidebar');

                    const content = document.querySelector('main.content');

                    return {

                        sidebar: {left: Math.round(sidebar.getBoundingClientRect().x), width: Math.round(sidebar.getBoundingClientRect().width)},

                        content: {left: Math.round(content.getBoundingClientRect().x), width: Math.round(content.getBoundingClientRect().width)},

                    };

                }

                """

            )

            assert layout["sidebar"]["left"] == 22

            assert 200 <= layout["sidebar"]["width"] <= 280

            assert layout["content"]["left"] >= 280

            assert layout["content"]["width"] >= 900

            page.screenshot(path="/tmp/mmqp-page-overview.png", full_page=True)

            page.screenshot(path="/tmp/mmqp-viewport-overview.png")

            for page_name in expected_pages:

                page.locator("aside.sidebar nav").get_by_role("button", name=page_name, exact=True).click()

                page.wait_for_timeout(100)
                new_page_h2s = page.locator("main h2")
                assert new_page_h2s.count() == heading_counts[page_name]

                expected_headings = headings[page_name]

                unexpected_headings = (

                    {

                        heading

                        for page_headings in headings.values()

                        for heading in page_headings

                    }

                    - set(expected_headings)

                )

                page.screenshot(path=f"/tmp/mmqp-viewport-{page_name}.png", full_page=True)

                assert page.get_by_role("button", name=page_name, exact=True).get_attribute("aria-current") == "page"

                assert page.locator("main.content").inner_text().strip()

                assert page.locator("main h1").inner_text() == expected_headings[0]

                assert page.get_by_role("contentinfo").count() == 0

                for heading in unexpected_headings:

                    assert page.get_by_role("heading", name=heading).count() == 0

                assert page.get_by_role("button", name="刷新").is_visible()

                page.screenshot(path=f"/tmp/mmqp-page-{page_name}.png", full_page=True)

            nav = page.locator("aside.sidebar nav")

            nav.get_by_role("button", name="数据源", exact=True).click()

            page.wait_for_timeout(200)

            page.get_by_test_id("source-card").filter(
                has_text="Yahoo Finance"
            ).first.click()
            page.wait_for_selector('[data-testid="quote-source-select"]')
            page.wait_for_selector('.quote-workspace')
            assert (
                page.get_by_role("button", name="行情", exact=True).get_attribute(
                    "aria-current"
                )
                == "page"
            )
            assert (
                page.locator('[data-testid="quote-source-select"]').input_value()
                == "yahoo-finance"
            )
            assert page.locator('[data-testid="quote-symbol"]').input_value() == "600000.SS"
            page.locator('[data-testid="quote-submit"]').click()
            page.wait_for_selector('[data-testid="quote-result"]', timeout=30_000)
            quote_text = page.locator('[data-testid="quote-result"]').inner_text()
            assert (
                "600000.SS"
                in page.locator(".quote-stage-head").inner_text()
            )
            assert "CNY" in quote_text

            nav.get_by_role("button", name="数据源", exact=True).click()
            page.wait_for_selector("[data-testid='source-card']")

            assert page.locator("main.content").inner_text().strip()

            assert len(page.locator("[data-testid='source-card']").all()) == 19

            browser.close()

    finally:

        process.terminate()

        process.wait(timeout=10)
