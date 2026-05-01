"""
Standalone entrypoint for the Specifier agent.

Examples:
    .venv/bin/python run_specifier.py
    .venv/bin/python run_specifier.py --input-dir /path/to/results
    .venv/bin/python run_specifier.py --analysis-file /path/to/P/83aec96c63_analysis.md
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

from specifier import (
    SpecifierAgent,
    collect_analysis_targets,
    is_positive_bundle,
    parse_analysis_bundle,
)


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


def write_error_log(path, failures):
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")


def build_specifier():
    return SpecifierAgent(
        os.getenv("QWEN_MODEL_NAME"),
        os.getenv("QWEN_API_KEY"),
        os.getenv("QWEN_API_URL"),
    )


def run_targets(agent, targets, output_dir="specs", skip_existing=False, debug=False):
    summaries = []
    failures = []

    for path in targets:
        bundle = parse_analysis_bundle(path)
        if not is_positive_bundle(bundle):
            summary = {
                "source_path": bundle["source_path"],
                "source_id": bundle["source_id"],
                "skipped": True,
                "reason": "not_positive",
            }
            summaries.append(summary)
            if debug:
                print(f"[SKIP] {bundle['source_id']} not_positive")
            continue

        try:
            result = agent.process_bundle(
                bundle,
                output_dir=output_dir,
                skip_existing=skip_existing,
            )
            summary = {
                "source_path": bundle["source_path"],
                "source_id": bundle["source_id"],
                "output_path": result.output_path,
                "skipped": result.skipped,
                "reason": result.reason,
                "digest_available": bundle["digest_available"],
            }
            summaries.append(summary)
            if debug:
                label = "SKIP" if result.skipped else "OK"
                print(f"[{label}] {bundle['source_id']} -> {result.output_path}")
        except Exception as exc:
            failure = {
                "source_path": bundle["source_path"],
                "source_id": bundle["source_id"],
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            failures.append(failure)
            summaries.append(
                {
                    "source_path": bundle["source_path"],
                    "source_id": bundle["source_id"],
                    "error": str(exc),
                }
            )
            if debug:
                print(f"[FAIL] {bundle['source_id']} {type(exc).__name__}: {exc}")

    return summaries, failures


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate CISB specifications from persisted positive analysis reports.",
    )
    parser.add_argument(
        "--input-dir",
        default=".",
        help="Root directory to scan for P/**/*_analysis.md. Default: current directory.",
    )
    parser.add_argument(
        "--analysis-file",
        help="Process a single _analysis.md file.",
    )
    parser.add_argument(
        "--output-dir",
        default="specs",
        help="Directory for generated _spec.md files. Default: specs",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip generation if the target _spec.md already exists.",
    )
    parser.add_argument(
        "--errors-log",
        default="specifier_errors.json",
        help="Path for JSON failure log. Default: specifier_errors.json",
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

    targets = collect_analysis_targets(
        input_dir=args.input_dir,
        analysis_file=args.analysis_file,
    )
    if not targets:
        print("No analysis targets found.")
        return 1

    agent = build_specifier()
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
