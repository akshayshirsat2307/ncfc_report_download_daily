#!/usr/bin/env python3
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.ncfc.gov.in"
OUTPUT = Path(__file__).resolve().parent.parent / "reports" / "LatestAgriculturalCondAsses.pdf"

def wait_for_pdf_download(page):
    # Try the official resource page first
    candidates = [
        "https://www.ncfc.gov.in/resources.html",
        "https://www.ncfc.gov.in/resources/agri-condition-assessment",
        "https://www.ncfc.gov.in",
        "https://www.ncfc.gov.in/downloads/LatestAgriculturalCondAsses.pdf",
    ]

    for url in candidates:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # Try direct PDF URL in browser context
            if url.endswith(".pdf") or ".pdf" in url:
                with page.context.expect_page() as page_info:
                    # open the PDF URL in a new tab
                    page.evaluate(f"window.open('{url}', '_blank');")
                new_page = page_info.value
                new_page.wait_for_timeout(20000)
                if new_page.url.lower().endswith(".pdf") or "pdf" in new_page.url.lower():
                    # Try saving by browser download event
                    with page.context.expect_download() as download_info:
                        # if the page triggers a download, this fires
                        try:
                            new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        except Exception:
                            pass
                    download = download_info.value
                    file_name = download.suggested_filename
                    download.save_as(str(OUTPUT))
                    print(f"Downloaded via browser: {file_name}")
                    return True
        except Exception:
            pass

    return False


def download_pdf():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1200},
            locale="en-US",
        )

        page = context.new_page()
        browser_ok = wait_for_pdf_download(page)

        if not browser_ok:
            raise RuntimeError("Could not download PDF via browser automation.")

        browser.close()

    if not OUTPUT.exists() or OUTPUT.stat().st_size < 1024:
        raise RuntimeError("Downloaded file is missing or too small")

    print(f"Saved PDF to {OUTPUT}")
    print(f"Size: {OUTPUT.stat().st_size} bytes")


if __name__ == "__main__":
    try:
        download_pdf()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
