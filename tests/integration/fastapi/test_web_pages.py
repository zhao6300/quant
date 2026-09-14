import os
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
        headings = {
            "总览": ["研究总览", "新建工作区", "已注册工作区"],
            "数据": ["数据查询", "数据查询"],
            "因子": ["多市场日历与规则", "多市场日历与规则"],
            "回测": ["研究运行", "研究运行"],
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

            for page_name in expected_pages:
                page.get_by_role("button", name=page_name).click()
                page.wait_for_timeout(100)
                expected_headings = headings[page_name]
                unexpected_headings = {
                    heading
                    for page_headings in headings.values()
                    for heading in page_headings
                } - set(expected_headings)
                assert (
                    page.get_by_role("button", name=page_name).get_attribute(
                        "aria-current"
                    )
                    == "page"
                )
                assert page.locator("main.content").inner_text().strip()
                assert page.locator("main h1").inner_text() == expected_headings[0]
                assert page.locator("main h2").count() == len(expected_headings) - 1
                assert page.get_by_role("contentinfo").count() == 0
                for heading in unexpected_headings:
                    assert page.get_by_role("heading", name=heading).count() == 0
                assert page.get_by_role("button", name="刷新").is_visible()
                page.screenshot(path=f"/tmp/mmqp-page-{page_name}.png", full_page=True)

            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
