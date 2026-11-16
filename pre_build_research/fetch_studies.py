"""
Download Lichess studies as PGN (with comments) into pre_build_research/raw/studies/.

Usage:
    uv run python fetch_studies.py <studyId> [<studyId> ...]

Public endpoint, no auth. Lichess rate-limits: on HTTP 429 we wait 60 s and retry once.
"""
import sys
import time
from pathlib import Path

import httpx

URL = "https://lichess.org/api/study/{id}.pgn"
PARAMS = {"comments": "true", "variations": "false", "clocks": "false"}
HEADERS = {"User-Agent": "BlunderTrace corpus builder"}
OUT_DIR = Path(__file__).resolve().parent / "raw" / "studies"


def fetch(client: httpx.Client, study_id: str) -> Path:
    for attempt in range(2):
        resp = client.get(URL.format(id=study_id), params=PARAMS)
        if resp.status_code == 429 and attempt == 0:
            print(f"  {study_id}: rate limited, waiting 60 s...")
            time.sleep(60)
            continue
        resp.raise_for_status()
        break
    path = OUT_DIR / f"{study_id}.pgn"
    path.write_text(resp.text, encoding="utf-8")
    return path


def main(ids: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for i, study_id in enumerate(ids):
            if i:
                time.sleep(1)  # be polite between requests
            try:
                path = fetch(client, study_id)
            except httpx.HTTPStatusError as e:   # 403 = author disabled export / private study
                print(f"{study_id}: SKIPPED (HTTP {e.response.status_code})")
                continue
            text = path.read_text(encoding="utf-8")
            chapters = text.count("[Event ")
            print(f"{study_id}: {len(text):,} bytes, {chapters} chapters -> {path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
