#!/usr/bin/env python3
"""Download the latest NCFC agricultural conditions assessment PDF."""

import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE_URL = "https://www.ncfc.gov.in"
PDF_URLS = [
    "https://www.ncfc.gov.in/downloads/LatestAgriculturalCondAsses.pdf",
    "https://www.ncfc.gov.in/downloads/latestagriculturalcondasses.pdf",
    "https://www.ncfc.gov.in/latestagriculturalcondasses.pdf",
]

OUTPUT = Path(__file__).resolve().parent.parent / "reports" / "LatestAgriculturalCondAsses.pdf"


def browser_headers(extra_headers=None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/pdf,application/octet-stream, "
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE_URL + "/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def fetch_url(url, timeout=60):
    last_error = None
    for attempt in range(3):
        request = Request(url, headers=browser_headers())
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", response.getcode())
                if status >= 400:
                    raise HTTPError(
                        url,
                        status,
                        f"HTTP {status}",
                        response.headers,
                        None,
                    )

                return response.read(), response.headers
        except HTTPError as exc:
            last_error = exc
            if exc.code in (403, 429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise
        except URLError as exc:
            last_error = exc
            time.sleep(2 ** attempt)
            continue

    raise RuntimeError(f"Request failed for {url}: {last_error}")


def find_pdf_link_on_site():
    candidates = [
        BASE_URL,
        BASE_URL + "/downloads",
        BASE_URL + "/download",
        BASE_URL + "/downloads/",
    ]

    seen = set()

    for page_url in candidates:
        if page_url in seen:
            continue
        seen.add(page_url)

        try:
            content, _ = fetch_url(page_url)
        except Exception:
            continue

        text = content.decode("utf-8", errors="ignore")
        matches = re.findall(r'href=[\'"]([^\'"]+\.pdf(?:\?[^\'"]*)?)[\'"]', text, flags=re.I)
        for href in matches:
            if href.startswith("http"):
                return href
            return urljoin(page_url, href)

        for candidate in re.findall(r'https?://[^\\s\'"<>]+\\.pdf(?:\\?[^\\s\'"<>]*)?', text, flags=re.I):
            return candidate

    return None


def download_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp_output = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")

    pdf_url = None
    for candidate in PDF_URLS:
        try:
            data, headers = fetch_url(candidate)
            if data.startswith(b"%PDF") or b"%PDF" in data[:1024]:
                pdf_url = candidate
                break
        except Exception:
            continue

    if pdf_url is None:
        # Fallback: scrape the site for a PDF link
        pdf_url = find_pdf_link_on_site()

    if pdf_url is None:
        raise RuntimeError(
            "Could not find a working NCFC PDF URL. "
            "The site may be blocking automated requests from GitHub Actions."
        )

    try:
        data, headers = fetch_url(pdf_url)
    except Exception as exc:
        raise RuntimeError(f"Failed to download NCFC PDF from {pdf_url}: {exc}") from exc

    content_type = (headers.get("Content-Type", "") if headers else "").lower()

    if not data.startswith(b"%PDF"):
        text_sample = data[:200].decode("utf-8", errors="replace")
        raise RuntimeError(
            "Downloaded content is not a PDF. "
            f"Content-Type: {content_type or 'unknown'}; sample: {text_sample!r}"
        )

    if len(data) < 1024:
        raise RuntimeError("Downloaded PDF is unexpectedly small.")

    try:
        temp_output.write_bytes(data)
        temp_output.replace(OUTPUT)
        print(f"Downloaded {len(data):,} bytes to {OUTPUT}")
    finally:
        temp_output.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        download_pdf()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
