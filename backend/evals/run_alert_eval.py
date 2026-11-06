"""Run the alert evaluation against the real AI and save the result.

From backend/ (reads OPENAI_API_KEY from backend/.env; 34 short calls, about $0.01):
    ./venv/bin/python -m evals.run_alert_eval --label baseline

Prints accuracy per field, critical errors and every failure, and writes
evals/results/<UTC timestamp>-<label>.json, including the model and a hash of the
prompt, so runs before and after a prompt change can be compared.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from evals.metrics import evaluate, render

HERE = Path(__file__).parent


def load_cases(path: Path = HERE / "alerts.jsonl") -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default="run", help="short name for this run, e.g. baseline or prompt-v2")
    args = parser.parse_args()

    load_dotenv()
    from building_coords import mentions_campus
    from nlp_summarizer import MODEL, SYSTEM_PROMPT, summarize

    cases = load_cases()
    answers = {}
    for i, case in enumerate(cases, 1):
        summary, ai_available = summarize(case["text"])
        if not ai_available:
            print("OpenAI is unavailable (network, key or outage); stopping without a result.", file=sys.stderr)
            return 2
        answers[case["id"]] = None if summary is None else {
            "severity": summary.severity, "scope": summary.scope, "building": summary.building_name,
        }
        print(f"\r{i}/{len(cases)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    report = evaluate(cases, answers, mentions_campus)
    print(render(report))

    run_at = datetime.now(timezone.utc)
    result = {
        "label": args.label,
        "run_at": run_at.isoformat(),
        "model": MODEL,
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12],
        "report": report,
        "answers": answers,
    }
    out = HERE / "results" / f"{run_at:%Y%m%d-%H%M}-{args.label}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved {out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
