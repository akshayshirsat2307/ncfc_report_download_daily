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
OUTPUT = Path(__file__).resolve().parent.parent / "reports" / "LatestAgriculturalCondAsses.pdf"
DISCOVERY_URLS = [
    "https://www.ncfc.gov.in/resources.html",
    "https://www.ncfc.gov.in/resources",
    "https://www.ncfc.gov.in/resources/agri-condition-assessment",
    BASE_URL,
]
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def save_pdf(body: bytes, source_url: str, content_type: str) -> None:
    if not body.startswith(b"%PDF"):
        preview = body[:200].decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Non-PDF response from {source_url}; content type "
            f"{content_type or 'unknown'}; preview {preview!r}"
        )
    if len(body) < 1024:
        raise RuntimeError("Downloaded PDF is unexpectedly small")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    try:
        temporary.write_bytes(body)
        temporary.replace(OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)

    print(f"Downloaded {len(body):,} bytes from {source_url}")
    print(f"Saved PDF to {OUTPUT}")


def download_pdf() -> bool:
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
            urls_to_try = [DIRECT_URL, *DISCOVERY_URLS]
            for page_url in urls_to_try:
                try:
                    response = page.goto(
                        page_url, wait_until="domcontentloaded", timeout=60_000
                    )
                    if response is None:
                        continue

                    content_type = response.headers.get("content-type", "")
                    body = response.body()
                    print(f"{page_url}: HTTP {response.status} ({content_type or 'unknown'})")

                    if response.status == 200 and body.startswith(b"%PDF"):
                        save_pdf(body, page_url, content_type)
                        return True

                    if response.status != 200 or ".pdf" in page_url.lower():
                        continue

                    page.wait_for_timeout(1_000)
                    hrefs = page.locator("a[href]").evaluate_all(
                        "elements => elements.map(element => element.href)"
                    )
                    for href in hrefs:
                        if ".pdf" not in href.lower():
                            continue
                        pdf_url = urljoin(page_url, href)
                        pdf_response = page.goto(
                            pdf_url, wait_until="domcontentloaded", timeout=60_000
                        )
                        if pdf_response is None:
                            continue
                        pdf_body = pdf_response.body()
                        pdf_type = pdf_response.headers.get("content-type", "")
                        print(
                            f"{pdf_url}: HTTP {pdf_response.status} "
                            f"({pdf_type or 'unknown'})"
                        )
                        if pdf_response.status == 200 and pdf_body.startswith(b"%PDF"):
                            save_pdf(pdf_body, pdf_url, pdf_type)
                            return True

                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    print(f"Could not inspect {page_url}: {exc}")

            return False
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        if not download_pdf():
            # NCFC returns 403 to GitHub-hosted runners. Keep the existing
            # checked-in report and let the workflow finish successfully.
            print(
                "WARNING: NCFC denied the GitHub Actions runner (HTTP 403). "
                "Keeping the existing report; no file was replaced."
            )
            sys.exit(0)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
