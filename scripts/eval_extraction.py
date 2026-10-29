"""Score complaint extraction against the scenario's labels, per language.

Runs every scenario complaint through the extractor (Muse Spark by default, or a local
Glimmer server with --glimmer) and reports field accuracy by language. Results are
written to eval/extraction-<model>.json for the README and the demo video.

Usage:  python scripts/eval_extraction.py [--glimmer]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gridmedic import config  # noqa: E402
from gridmedic.customers import CustomerDB  # noqa: E402
from gridmedic.extract import Extractor  # noqa: E402
from gridmedic.models import ModelClient  # noqa: E402
from gridmedic.scenario import load  # noqa: E402

FIELDS = ["street", "house_no", "symptom", "hazard", "junk"]


def main() -> None:
    glimmer = "--glimmer" in sys.argv
    client = ModelClient(mode="live")
    ex = (Extractor(client, model=config.GLIMMER_MODEL, base=config.GLIMMER_BASE, label="Muse Glimmer")
          if glimmer else Extractor(client))
    if not glimmer and not config.MODEL_API_KEY:
        sys.exit("MODEL_API_KEY is not set; mock output would just echo the labels.")
    db = CustomerDB()
    sc = load()
    hits: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    rows = []
    for e in sc["events"]:
        if e["type"] != "complaint":
            continue
        truth = e["truth"]
        out = ex.complaint(e["text"], truth, e["language"]).fields
        got_street = db.match_street(out.get("street") or "")[0] if out.get("street") else None
        checks = {
            "street": got_street == truth.get("street") if truth.get("street") else True,
            "house_no": out.get("house_no") == truth.get("house_no") if truth.get("house_no") else True,
            "symptom": out.get("symptom") == truth.get("symptom"),
            "hazard": out.get("hazard") == truth.get("hazard"),
            "junk": bool(out.get("is_junk")) == bool(truth.get("junk")),
        }
        for f, ok in checks.items():
            hits[e["language"]][f].append(ok)
            hits["all"][f].append(ok)
        rows.append({"id": e["id"], "language": e["language"], "checks": checks, "output": out})
        bad = [f for f, ok in checks.items() if not ok]
        print(f"{e['id']:<4} {e['language']}  {'ok' if not bad else 'MISS ' + ','.join(bad)}")

    print(f"\n{'lang':<5} " + " ".join(f"{f:>9}" for f in FIELDS) + "   n")
    summary = {}
    for lang, fs in sorted(hits.items()):
        summary[lang] = {f: round(sum(v) / len(v), 3) for f, v in fs.items()}
        n = len(next(iter(fs.values())))
        print(f"{lang:<5} " + " ".join(f"{summary[lang][f]:>9.0%}" for f in FIELDS) + f"  {n:>2}")
    out_dir = config.ROOT / "eval"
    out_dir.mkdir(exist_ok=True)
    name = "glimmer" if glimmer else config.SPARK_MODEL
    (out_dir / f"extraction-{name}.json").write_text(
        json.dumps({"model": name, "summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
