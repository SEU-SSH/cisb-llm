"""
Standalone entrypoint for the Querier agent.

Examples:
    .venv/bin/python run_querier.py
    .venv/bin/python run_querier.py --input-dir specs
    .venv/bin/python run_querier.py --spec-file specs/02828845dd_spec.md
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import dotenv
except ImportError:  # pragma: no cover - optional dependency in tests.
    dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent
AGENTS_DIR = PROJECT_ROOT / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from querier import QuerierAgent, collect_spec_targets, parse_spec_bundle


def load_env_file(path):
    path = Path(path)
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_environment(project_root=PROJECT_ROOT):
    if dotenv is not None:
        dotenv.load_dotenv(project_root / ".env")
    else:
        load_env_file(project_root / ".env")


def build_querier():
    return QuerierAgent(
        os.getenv("QWEN_MODEL_NAME"),
        os.getenv("QWEN_API_KEY"),
        os.getenv("QWEN_API_URL"),
    )


def write_error_log(path, failures):
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")


def run_targets(agent, targets, output_dir="queries/cpp", skip_existing=False, debug=False):
    summaries = []
    failures = []

    for path in targets:
        bundle = parse_spec_bundle(path)
        try:
            result = agent.process_bundle(
                bundle,
                output_dir=output_dir,
                skip_existing=skip_existing,
            )
            summary = {
                "source_spec_path": bundle["source_spec_path"],
                "source_id": bundle["source_id"],
                "qll_path": result.qll_path,
                "ql_path": result.ql_path,
                "skipped": result.skipped,
                "reason": result.reason,
            }
            summaries.append(summary)
            if debug:
                label = "SKIP" if result.skipped else "OK"
                print(f"[{label}] {bundle['source_id']} -> {result.qll_path}, {result.ql_path}")
        except Exception as exc:
            failure = {
                "source_spec_path": bundle["source_spec_path"],
                "source_id": bundle["source_id"],
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            failures.append(failure)
            summaries.append(
                {
                    "source_spec_path": bundle["source_spec_path"],
                    "source_id": bundle["source_id"],
                    "error": str(exc),
                }
            )
            if debug:
                print(f"[FAIL] {bundle['source_id']} {type(exc).__name__}: {exc}")

    return summaries, failures


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate CodeQL .qll + .ql files from CISB spec markdown files.",
    )
    parser.add_argument(
        "--input-dir",
        default="specs",
        help="Directory containing *_spec.md files. Default: specs",
    )
    parser.add_argument(
        "--spec-file",
        help="Process a single _spec.md file.",
    )
    parser.add_argument(
        "--output-dir",
        default="queries/cpp",
        help="Directory for generated .qll and .ql files. Default: queries/cpp",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip generation if both the target .qll and .ql already exist.",
    )
    parser.add_argument(
        "--errors-log",
        default="querier_errors.json",
        help="Path for JSON failure log. Default: querier_errors.json",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print per-file processing details.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    load_environment(PROJECT_ROOT)

    targets = collect_spec_targets(
        input_dir=args.input_dir,
        spec_file=args.spec_file,
    )
    if not targets:
        print("No spec targets found.")
        return 1

    agent = build_querier()
    summaries, failures = run_targets(
        agent,
        targets,
        output_dir=args.output_dir,
        skip_existing=args.skip_existing,
        debug=args.debug,
    )
    write_error_log(args.errors_log, failures)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
