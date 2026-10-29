"""Merge several eval reports (for example from parallel processes) into one.

    uv run python -m evals.combine TAG_A TAG_B TAG_C --out results-2026-10-29
"""

from __future__ import annotations

import argparse
import json

from evals.run import REPORTS, render_markdown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    parts = [json.loads((REPORTS / f"{t}.json").read_text()) for t in args.tags]
    meta = dict(parts[0]["meta"], tag=args.out, sources=args.tags,
                total_model_spend_usd=round(sum(p["meta"]["total_model_spend_usd"]
                                                for p in parts), 4))
    models = sorted({p["meta"]["model"] for p in parts})
    meta["model"] = " + ".join(models)
    scores = [s for p in parts for s in p["scores"]]
    (REPORTS / f"{args.out}.json").write_text(json.dumps({"meta": meta, "scores": scores},
                                                         indent=2))
    md = render_markdown(meta, scores)
    md += f"\nTotal model spend: ${meta['total_model_spend_usd']}\n"
    (REPORTS / f"{args.out}.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
