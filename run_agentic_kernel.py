"""
Standalone entrypoint for the kernel agentic pipeline.

Examples:
    .venv/bin/python run_agentic_kernel.py
    .venv/bin/python run_agentic_kernel.py --commits-file commits.txt
    .venv/bin/python run_agentic_kernel.py --commit-id <commit_hash>
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import dotenv
except ImportError:  # pragma: no cover - optional dependency in tests.
    dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent
AGENTS_DIR = PROJECT_ROOT / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from agentic_kernel import AgenticKernelOrchestrator
from kernel_api import KernelApiScheduler


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


def read_commit_ids(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def resolve_commit_targets(commit_id=None, commits_file=None):
    if commit_id and commits_file:
        raise ValueError("Use either --commit-id or --commits-file, not both.")
    if commit_id:
        return [commit_id]

    target_file = commits_file or "commits.txt"
    return read_commit_ids(target_file)


def build_runner(args):
    scheduler = KernelApiScheduler(
        token=os.getenv("GITHUB_TOKEN"),
        max_ssl_retries=args.max_ssl_retries,
        ssl_retry_backoff=args.ssl_retry_backoff,
    )
    return AgenticKernelOrchestrator(
        os.getenv("DS_MODEL_NAME"),
        os.getenv("QWEN_MODEL_NAME"),
        os.getenv("DS_API_KEY"),
        os.getenv("QWEN_API_KEY"),
        os.getenv("DS_API_URL"),
        os.getenv("QWEN_API_URL"),
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        scheduler=scheduler,
        max_steps=args.stall_limit,
        total_action_limit=args.total_action_limit,
        persist_options=resolve_persistence_options(args),
    )


def resolve_persistence_options(args):
    analysis = True if args.persist_analysis is None else args.persist_analysis
    trace = (True if args.debug else False) if args.persist_trace is None else args.persist_trace
    digest = False if args.persist_digest is None else args.persist_digest
    return {
        "analysis": analysis,
        "trace": trace,
        "digest": digest,
    }


def write_error_log(path, failures):
    if not path:
        return

    if failures:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2, ensure_ascii=False)
    else:
        Path(path).write_text("[]\n", encoding="utf-8")


def run_targets(runner, commit_ids, sleep_seconds=0, errors_log=None):
    failures = []
    summaries = []

    for index, commit_id in enumerate(commit_ids, start=1):
        print(f"[{index}/{len(commit_ids)}] Running {commit_id}...")
        try:
            state = runner.run(commit_id, seed_report={"id": commit_id}, persist=True)
            summary = {
                "commit": commit_id,
                "termination_reason": state.termination_reason,
                "cisb_status": state.final_decision.get("cisb_status"),
                "errors": state.errors,
            }
            summaries.append(summary)
            print(
                f"[OK] {commit_id[:10]} "
                f"cisb={summary['cisb_status']} "
                f"termination={summary['termination_reason']}"
            )
        except Exception as exc:
            failure = {
                "commit": commit_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            failures.append(failure)
            summaries.append({"commit": commit_id, "error": str(exc)})
            print(f"[FAIL] {commit_id[:10]} {type(exc).__name__}: {exc}")

        if sleep_seconds and index < len(commit_ids):
            time.sleep(sleep_seconds)

    write_error_log(errors_log, failures)
    return summaries, failures


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run the standalone kernel agentic pipeline.",
    )
    parser.add_argument(
        "--commit-id",
        help="Run a single commit id.",
    )
    parser.add_argument(
        "--commits-file",
        help="Read commit ids from a file. Defaults to commits.txt when omitted.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for analysis/trace/spec outputs. Default: current directory.",
    )
    parser.add_argument(
        "--cache-dir",
        default=".kernel_cache",
        help="Directory for prepared kernel caches. Default: .kernel_cache",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0,
        help="Sleep seconds between commits. Default: 0.",
    )
    parser.add_argument(
        "--errors-log",
        default="errors.log",
        help="Path for JSON failure log. Default: errors.log",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug defaults. In debug mode, analysis and trace persistence default to on.",
    )
    parser.add_argument(
        "--persist-analysis",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable analysis markdown persistence.",
    )
    parser.add_argument(
        "--persist-trace",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable trace JSON persistence.",
    )
    parser.add_argument(
        "--persist-digest",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable standalone digest JSON persistence.",
    )
    parser.add_argument(
        "--stall-limit",
        type=int,
        default=12,
        help="Maximum consecutive no-progress actions before stopping a run.",
    )
    parser.add_argument(
        "--total-action-limit",
        type=int,
        default=40,
        help="Absolute upper bound on reasoner actions in a run.",
    )
    parser.add_argument(
        "--max-ssl-retries",
        type=int,
        default=5,
        help="Maximum SSL retry count for GitHub API requests.",
    )
    parser.add_argument(
        "--ssl-retry-backoff",
        type=float,
        default=1.0,
        help="Base backoff seconds for SSL retry handling.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    load_environment(PROJECT_ROOT)
    commit_ids = resolve_commit_targets(
        commit_id=args.commit_id,
        commits_file=args.commits_file,
    )
    if not commit_ids:
        print("No commit ids found.")
        return 1

    runner = build_runner(args)
    print(f"Using Retriever: {type(runner.retriever).__name__ if runner.retriever else 'None'}")
    print(f"Persistence: {json.dumps(resolve_persistence_options(args), ensure_ascii=False)}")
    summaries, failures = run_targets(
        runner,
        commit_ids,
        sleep_seconds=args.sleep,
        errors_log=args.errors_log,
    )
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
