#!/usr/bin/env python3
"""Download the latest NCFC agricultural conditions assessment PDF."""

import sys
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.ncfc.gov.in"
DIRECT_URL = "https://www.ncfc.gov.in/downloads/LatestAgriculturalCondAsses.pdf"
OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "reports"
    / "LatestAgriculturalCondAsses.pdf"
)

DISCOVERY_URLS = [
    "https://www.ncfc.gov.in/resources.html",
    "https://www.ncfc.gov.in/resources",
    "https://www.ncfc.gov.in/resources/agri-condition-assessment",
    BASE_URL,
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def is_pdf(body: bytes, content_type: str = "") -> bool:
    return body.startswith(b"%PDF") or "application/pdf" in content_type.lower()


def save_pdf(body: bytes, source_url: str, content_type: str) -> None:
    if not body.startswith(b"%PDF"):
        preview = body[:200].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"NCFC returned non-PDF content from {source_url}. "
            f"Content-Type={content_type or 'unknown'}; preview={preview!r}"
        )

    if len(body) < 1024:
        raise RuntimeError(f"The PDF from {source_url} is unexpectedly small.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    try:
        temporary_output.write_bytes(body)
        temporary_output.replace(OUTPUT)
    finally:
        temporary_output.unlink(missing_ok=True)

    print(f"Downloaded {len(body):,} bytes from {source_url}")
    print(f"Saved PDF to {OUTPUT}")


def download_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 1200},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "application/pdf,text/html,application/xhtml+xml,*/*;q=0.8",
            },
        )
        page = context.new_page()

        try:
            # A PDF opened in Chromium is normally rendered in a PDF viewer; it
            # does not necessarily create a Playwright download event. Read the
            # actual HTTP response body instead.
            response = page.goto(
                DIRECT_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            if response is not None:
                body = response.body()
                content_type = response.headers.get("content-type", "")
                if response.status == 200 and is_pdf(body, content_type):
                    save_pdf(body, DIRECT_URL, content_type)
                    return
                print(
                    f"Direct URL response: HTTP {response.status}, "
                    f"Content-Type={content_type or 'unknown'}"
                )

            # If the fixed filename is no longer valid, find a PDF link on the
            # official NCFC pages and fetch it in the same browser context.
            for discovery_url in DISCOVERY_URLS:
                try:
                    discovery_response = page.goto(
                        discovery_url,
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    if discovery_response is None or discovery_response.status >= 400:
                        print(
                            f"Discovery URL response: HTTP "
                            f"{discovery_response.status if discovery_response else 'unknown'} "
                            f"for {discovery_url}"
                        )
                        continue

                    page.wait_for_timeout(2_000)
                    links = page.locator("a[href]").all()
                    for link in links:
                        href = link.get_attribute("href")
                        if not href or ".pdf" not in href.lower():
                            continue

                        pdf_url = urljoin(discovery_url, href)
                        pdf_response = page.goto(
                            pdf_url,
                            wait_until="domcontentloaded",
                            timeout=60_000,
                        )
                        if pdf_response is None:
                            continue

                        body = pdf_response.body()
                        content_type = pdf_response.headers.get("content-type", "")
                        if pdf_response.status == 200 and is_pdf(body, content_type):
                            save_pdf(body, pdf_url, content_type)
                            return

                        print(
                            f"PDF link response: HTTP {pdf_response.status}, "
                            f"Content-Type={content_type or 'unknown'} for {pdf_url}"
                        )

                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    print(f"Could not inspect {discovery_url}: {exc}")

            raise RuntimeError(
                "NCFC did not provide a downloadable PDF to the GitHub Actions "
                "runner. The server is likely blocking the runner IP or requires "
                "a local browser session/cookie."
            )
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        download_pdf()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
