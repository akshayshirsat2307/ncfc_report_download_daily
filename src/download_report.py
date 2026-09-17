#!/usr/bin/env python3
"""Download the latest NCFC agricultural conditions assessment PDF."""

from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://www.ncfc.gov.in/downloads/LatestAgriculturalCondAsses.pdf"
OUTPUT = Path(__file__).resolve().parent.parent / "reports" / "LatestAgriculturalCondAsses.pdf"


def download_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")

    request = Request(
        URL,
        headers={
            "User-Agent": "ncfc-report-download-daily/1.0",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )

    try:
        with urlopen(request, timeout=60) as response:
            status = getattr(response, "status", response.getcode())
            if status != 200:
                raise RuntimeError(f"NCFC returned HTTP {status}")

            content_type = response.headers.get("Content-Type", "").lower()
            data = response.read()

        if not data.startswith(b"%PDF"):
            raise RuntimeError(
                f"Downloaded content is not a PDF (Content-Type: {content_type or 'unknown'})"
            )

        if len(data) < 1024:
            raise RuntimeError("Downloaded PDF is unexpectedly small")

        temporary_output.write_bytes(data)
        temporary_output.replace(OUTPUT)
        print(f"Downloaded {len(data):,} bytes to {OUTPUT}")
    finally:
        temporary_output.unlink(missing_ok=True)


if __name__ == "__main__":
    download_pdf()
