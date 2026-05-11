"""
Build CodeQL databases for categorized CISB query/source directories.

Examples:
    .venv/bin/python build_codeql_databases.py
    .venv/bin/python build_codeql_databases.py --category l-13__ub_pointer_offset_overflow
    .venv/bin/python build_codeql_databases.py --input-dir queries --output-dir codeql-databases --skip-existing
"""

import argparse
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path


SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".c++"}
PACK_VERSION = "7.0.0"
PACK_LOCK_DEPENDENCIES = {
    "codeql/cpp-all": "7.0.0",
    "codeql/controlflow": "2.0.24",
    "codeql/dataflow": "2.0.24",
    "codeql/mad": "1.0.40",
    "codeql/quantum": "0.0.18",
    "codeql/rangeanalysis": "1.0.40",
    "codeql/ssa": "2.0.16",
    "codeql/tutorial": "1.0.40",
    "codeql/typeflow": "1.0.40",
    "codeql/typetracking": "2.0.24",
    "codeql/util": "2.0.27",
    "codeql/xml": "1.0.40",
}


def collect_category_dirs(input_dir="queries", category=None):
    root = Path(input_dir)
    if category:
        target = root / category
        if not target.is_dir():
            raise FileNotFoundError(f"Category directory not found: {target}")
        return [target.resolve()]

    return [path.resolve() for path in sorted(root.iterdir()) if path.is_dir()]


def collect_source_files(category_dir):
    category_dir = Path(category_dir)
    return [
        path.resolve()
        for path in sorted(category_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
    ]


def category_identifier(category_dir):
    category_name = Path(category_dir).name
    return category_name.split("__", 1)[0]


def category_pack_name(category_dir):
    category_name = Path(category_dir).name.lower()
    sanitized = re.sub(r"[^a-z0-9-]+", "-", category_name).strip("-")
    sanitized = re.sub(r"-+", "-", sanitized)
    return f"cisb-llm/{sanitized}"


def compiler_for_source(path, cc="gcc", cxx="g++"):
    path = Path(path)
    if path.suffix.lower() == ".c":
        return cc
    return cxx


def database_output_path(category_dir, output_dir=None):
    category_dir = Path(category_dir)
    identifier = category_identifier(category_dir)
    if output_dir is None:
        return (category_dir / f".codeql-db-{identifier}").resolve()
    return (Path(output_dir) / identifier).resolve()


def build_script_path(category_dir, output_dir=None):
    category_dir = Path(category_dir)
    identifier = category_identifier(category_dir)
    if output_dir is None:
        return (category_dir / ".codeql-build.sh").resolve()
    return (Path(output_dir) / f"{identifier}__build.sh").resolve()


def build_object_root(category_dir, output_dir=None):
    category_dir = Path(category_dir)
    identifier = category_identifier(category_dir)
    if output_dir is None:
        return (category_dir / ".codeql-objs").resolve()
    return (Path(output_dir) / f"{identifier}__objs").resolve()


def qlpack_path(category_dir):
    return (Path(category_dir) / "qlpack.yml").resolve()


def codeql_pack_lock_path(category_dir):
    return (Path(category_dir) / "codeql-pack.lock.yml").resolve()


def render_qlpack_file(category_dir):
    return (
        f"name: {category_pack_name(category_dir)}\n"
        "version: 0.0.0\n"
        "dependencies:\n"
        f"  codeql/cpp-all: {PACK_VERSION}\n"
    )


def render_codeql_pack_lock_file():
    lines = ["dependencies:"]
    for name, version in PACK_LOCK_DEPENDENCIES.items():
        lines.append(f"  {name}:")
        lines.append(f"    version: {version}")
    return "\n".join(lines) + "\n"


def ensure_pack_files(category_dir):
    category_dir = Path(category_dir)
    pack_path = qlpack_path(category_dir)
    lock_path = codeql_pack_lock_path(category_dir)
    pack_path.write_text(render_qlpack_file(category_dir), encoding="utf-8")
    lock_path.write_text(render_codeql_pack_lock_file(), encoding="utf-8")
    return pack_path, lock_path


def render_build_script(category_dir, source_files, object_root, cc="gcc", cxx="g++", extra_cflags=""):
    category_dir = Path(category_dir)
    object_root = Path(object_root)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"mkdir -p {shlex.quote(str(object_root))}",
    ]

    for source in source_files:
        compiler = compiler_for_source(source, cc=cc, cxx=cxx)
        obj_name = source.with_suffix(".o").name
        obj_path = object_root / obj_name
        extra = f" {extra_cflags.strip()}" if extra_cflags.strip() else ""
        lines.append(
            f"{compiler}{extra} -c {shlex.quote(source.name)} -o {shlex.quote(str(obj_path))}"
        )

    return "\n".join(lines) + "\n"


def write_build_script(category_dir, source_files, output_dir=None, cc="gcc", cxx="g++", extra_cflags=""):
    script_path = build_script_path(category_dir, output_dir=output_dir)
    object_root = build_object_root(category_dir, output_dir=output_dir)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        render_build_script(
            category_dir,
            source_files,
            object_root,
            cc=cc,
            cxx=cxx,
            extra_cflags=extra_cflags,
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path


def build_database(
    category_dir,
    output_dir=None,
    codeql_bin="codeql",
    skip_existing=False,
    overwrite=False,
    cc="gcc",
    cxx="g++",
    extra_cflags="",
    debug=False,
):
    category_dir = Path(category_dir).resolve()
    ensure_pack_files(category_dir)
    sources = collect_source_files(category_dir)
    if not sources:
        raise ValueError(f"No C/C++ source files found in {category_dir}")

    db_path = database_output_path(category_dir, output_dir=output_dir)
    script_path = write_build_script(
        category_dir,
        sources,
        output_dir=output_dir,
        cc=cc,
        cxx=cxx,
        extra_cflags=extra_cflags,
    )

    if db_path.exists():
        if skip_existing or not overwrite:
            return {
                "category": category_dir.name,
                "database_path": str(db_path),
                "sources": [str(source) for source in sources],
                "skipped": True,
                "reason": "skip_existing" if skip_existing else "already_exists",
            }
        shutil.rmtree(db_path)

    command = [
        codeql_bin,
        "database",
        "create",
        str(db_path),
        "--language=cpp",
        f"--command=/bin/bash {script_path}",
        f"--source-root={category_dir}",
    ]

    if debug:
        print(f"[BUILD] {category_dir.name}")
        print(f"  sources: {[source.name for source in sources]}")
        print(f"  script: {script_path}")
        print(f"  database: {db_path}")

    subprocess.run(
        command,
        check=True,
    )

    return {
        "category": category_dir.name,
        "database_path": str(db_path),
        "sources": [str(source) for source in sources],
        "skipped": False,
        "reason": "",
    }


def write_error_log(path, failures):
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")


def run_targets(category_dirs, **kwargs):
    summaries = []
    failures = []
    for category_dir in category_dirs:
        try:
            result = build_database(category_dir, **kwargs)
            summaries.append(result)
        except Exception as exc:
            failures.append(
                {
                    "category": Path(category_dir).name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            summaries.append(
                {
                    "category": Path(category_dir).name,
                    "error": str(exc),
                }
            )
            if kwargs.get("debug"):
                print(f"[FAIL] {Path(category_dir).name} {type(exc).__name__}: {exc}")
    return summaries, failures


def build_parser():
    parser = argparse.ArgumentParser(
        description="Build CodeQL databases for categorized CISB query/source directories.",
    )
    parser.add_argument(
        "--input-dir",
        default="queries",
        help="Root directory containing categorized query/source directories. Default: queries",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for generated CodeQL databases. Default: create .codeql-db-<id> inside each category directory.",
    )
    parser.add_argument(
        "--category",
        help="Build only one CISB category directory by name.",
    )
    parser.add_argument(
        "--codeql-bin",
        default="codeql",
        help="CodeQL executable path. Default: codeql",
    )
    parser.add_argument(
        "--cc",
        default="gcc",
        help="C compiler for .c files. Default: gcc",
    )
    parser.add_argument(
        "--cxx",
        default="g++",
        help="C++ compiler for .cc/.cpp/.cxx files. Default: g++",
    )
    parser.add_argument(
        "--extra-cflags",
        default="",
        help="Extra flags appended to each compile command.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip categories whose database already exists.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing databases.",
    )
    parser.add_argument(
        "--errors-log",
        default="codeql_database_build_errors.json",
        help="Path for JSON failure log. Default: codeql_database_build_errors.json",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print per-category build details.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    category_dirs = collect_category_dirs(
        input_dir=args.input_dir,
        category=args.category,
    )
    if not category_dirs:
        print("No category directories found.")
        return 1

    summaries, failures = run_targets(
        category_dirs,
        output_dir=args.output_dir,
        codeql_bin=args.codeql_bin,
        skip_existing=args.skip_existing,
        overwrite=args.overwrite,
        cc=args.cc,
        cxx=args.cxx,
        extra_cflags=args.extra_cflags,
        debug=args.debug,
    )
    write_error_log(args.errors_log, failures)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
