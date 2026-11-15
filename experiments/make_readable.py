"""
Write a human-readable Markdown copy of every corpus file (view only, data is unchanged).

    data/corpus/<source>.jsonl  ->  data/corpus/readable/<source>.md

Usage:
    uv run python experiments/make_readable.py
"""
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"
OUT = CORPUS / "readable"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for path in sorted(CORPUS.glob("*.jsonl")):
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        lines = [f"# {path.stem} ({len(rows)} rows)", ""]
        current_title = None
        for r in rows:
            if r["title"] != current_title:                    # new page / book / study
                current_title = r["title"]
                lines += [f"## {r['title']}", ""]
            lines.append(f"### {r['section']}")
            details = [f"`{r['id']}`", f"[source]({r['url']})"]
            if r.get("fen"):
                m = r["meta"]
                details.append(f"move {m.get('move_no', '')} {m.get('move', '')}".strip())
                details.append(f"FEN `{r['fen']}`")
            lines += [" · ".join(details), "", r["text"], ""]
        out = OUT / f"{path.stem}.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"{out.relative_to(CORPUS.parent.parent)}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
