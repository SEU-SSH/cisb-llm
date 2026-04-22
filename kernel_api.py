import base64
import json
import os
import re
import time
from pathlib import Path

import requests


GITHUB_REPO = "torvalds/linux"
GITHUB_API_BASE = "https://api.github.com"
COMMIT_LIST_PATH = "commits.txt"
OUTPUT_PATH = "commits.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEFAULT_CACHE_DIR = ".kernel_cache"
DEFAULT_TIMEOUT = 30
DEFAULT_MIN_INTERVAL = 1.0

REDUNDANT_TAG_RE = re.compile(
    r"^\s*(Signed-off-by|Reviewed-by|Tested-by|Acked-by|Cc|Co-authored-by|"
    r"Debugged-by|Suggested-by|Reported-by):"
)
HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_len>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_len>\d+))? @@(?P<header>.*)$"
)
FUNCTION_NAME_RE = re.compile(r"([A-Za-z_]\w*)\s*\(")


def read_commit_ids(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def strip_redundant_lines(commit_msg: str) -> str:
    return "\n".join(
        line
        for line in commit_msg.splitlines()
        if not REDUNDANT_TAG_RE.match(line)
    ).strip()


def count_patch_lines(patch_text):
    return len([line for line in (patch_text or "").splitlines() if line.strip()])


def _safe_key(file_path):
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", file_path or "unknown")


def _normalize_file_entry(filename, patch_text="", metadata=None):
    metadata = metadata or {}
    patch_text = patch_text or ""
    return {
        "filename": filename,
        "status": metadata.get("status", "modified"),
        "patch": patch_text,
        "changes": metadata.get("changes", count_patch_lines(patch_text)),
        "additions": metadata.get("additions"),
        "deletions": metadata.get("deletions"),
        "raw_url": metadata.get("raw_url"),
        "blob_url": metadata.get("blob_url"),
    }


def normalize_seed_commit(seed_data, commit_sha=None):
    if not seed_data:
        return None
    patch_map = (
        seed_data.get("patches")
        or seed_data.get("patch context")
        or seed_data.get("patch_context")
        or {}
    )
    message = strip_redundant_lines(seed_data.get("message", ""))
    if not message and not patch_map:
        return None
    files = []
    for filename, patch_text in patch_map.items():
        files.append(_normalize_file_entry(filename, patch_text))

    return {
        "id": commit_sha or seed_data.get("id"),
        "year": seed_data.get("year"),
        "message": message,
        "files": files,
        "source": "seed",
    }


def normalize_commit_bundle(commit_data):
    commit_date = commit_data.get("commit", {}).get("committer", {}).get("date", "")
    commit_year = commit_date[:4] if commit_date else None
    files = []
    for file_data in commit_data.get("files", []):
        files.append(
            _normalize_file_entry(
                file_data.get("filename"),
                patch_text=file_data.get("patch", ""),
                metadata=file_data,
            )
        )

    return {
        "id": commit_data.get("sha"),
        "year": commit_year,
        "message": strip_redundant_lines(
            commit_data.get("commit", {}).get("message", "")
        ),
        "files": files,
        "source": "github",
    }


def merge_commit_bundles(primary, fallback):
    if not primary:
        return fallback
    if not fallback:
        return primary

    merged = dict(primary)
    merged["message"] = primary.get("message") or fallback.get("message", "")
    merged["year"] = primary.get("year") or fallback.get("year")

    file_map = {}
    for source_bundle in (fallback, primary):
        for file_entry in source_bundle.get("files", []):
            key = file_entry.get("filename")
            if key not in file_map:
                file_map[key] = dict(file_entry)
                continue
            current = file_map[key]
            for field, value in file_entry.items():
                if value not in (None, "", []):
                    current[field] = value

    merged["files"] = list(file_map.values())
    if fallback.get("source") and primary.get("source") != fallback.get("source"):
        merged["source"] = f"{primary.get('source')}+{fallback.get('source')}"
    return merged


class KernelApiScheduler:
    def __init__(
        self,
        token=None,
        repo=GITHUB_REPO,
        api_base=GITHUB_API_BASE,
        min_interval=DEFAULT_MIN_INTERVAL,
        timeout=DEFAULT_TIMEOUT,
        max_ssl_retries=2,
        ssl_retry_backoff=1.0,
        session=None,
        sleep_fn=None,
        time_fn=None,
    ):
        self.token = token or GITHUB_TOKEN
        self.repo = repo
        self.api_base = api_base.rstrip("/")
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_ssl_retries = max_ssl_retries
        self.ssl_retry_backoff = ssl_retry_backoff
        self.session = session or requests.Session()
        self.sleep_fn = sleep_fn or time.sleep
        self.time_fn = time_fn or time.time
        self.last_request_at = None
        self.rate_limit = {}

    def _headers(self):
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _build_url(self, path):
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("/"):
            return f"{self.api_base}{path}"
        return f"{self.api_base}/{path}"

    def _wait_for_slot(self):
        if self.last_request_at is None:
            return
        elapsed = self.time_fn() - self.last_request_at
        if elapsed < self.min_interval:
            self.sleep_fn(self.min_interval - elapsed)

    def _record_rate_limit(self, response):
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_at = response.headers.get("X-RateLimit-Reset")
        self.rate_limit = {
            "remaining": int(remaining) if remaining else None,
            "reset_at": int(reset_at) if reset_at else None,
            "last_status": response.status_code,
        }

    def _backoff_if_needed(self, response):
        remaining = self.rate_limit.get("remaining")
        reset_at = self.rate_limit.get("reset_at")
        if remaining is None or reset_at is None:
            return
        if response.status_code == 403 and remaining == 0:
            wait_seconds = max(0, reset_at - int(self.time_fn())) + 1
            self.sleep_fn(wait_seconds)

    def _backoff_for_ssl_retry(self, attempt_index):
        wait_seconds = self.ssl_retry_backoff * (2 ** max(0, attempt_index - 1))
        self.sleep_fn(wait_seconds)

    def request_json(self, path, params=None):
        url = self._build_url(path)
        ssl_attempts = 0
        while True:
            self._wait_for_slot()
            try:
                response = self.session.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout,
                )
            except requests.exceptions.SSLError:
                self.last_request_at = self.time_fn()
                ssl_attempts += 1
                if ssl_attempts > self.max_ssl_retries:
                    raise
                self._backoff_for_ssl_retry(ssl_attempts)
                continue

            self.last_request_at = self.time_fn()
            ssl_attempts = 0
            self._record_rate_limit(response)
            self._backoff_if_needed(response)

            if response.status_code == 403 and self.rate_limit.get("remaining") == 0:
                continue

            response.raise_for_status()
            return response.json()

    def fetch_commit_info(self, commit_sha):
        path = f"/repos/{self.repo}/commits/{commit_sha}"
        return self.request_json(path)

    def fetch_file_snapshot(self, commit_sha, file_path):
        path = f"/repos/{self.repo}/contents/{file_path}"
        payload = self.request_json(path, params={"ref": commit_sha})
        if payload.get("type") != "file":
            return ""
        encoded = payload.get("content", "")
        if not encoded:
            return ""
        return base64.b64decode(encoded).decode("utf-8", errors="replace")


def fetch_commit_bundle(commit_sha, scheduler=None, seed_data=None):
    network_bundle = None
    network_error = None

    if scheduler is not None:
        try:
            network_bundle = normalize_commit_bundle(scheduler.fetch_commit_info(commit_sha))
        except Exception as exc:
            network_error = str(exc)

    seed_bundle = normalize_seed_commit(seed_data, commit_sha) if seed_data else None
    bundle = merge_commit_bundles(network_bundle, seed_bundle)
    if bundle is None:
        raise ValueError(f"Unable to build commit bundle for {commit_sha}.")
    if network_error:
        bundle["network_error"] = network_error
    return bundle


def parse_patch_hunks(patch_text):
    hunks = []
    current = None

    for line in (patch_text or "").splitlines():
        match = HUNK_HEADER_RE.match(line)
        if match:
            if current is not None:
                current["body_text"] = "\n".join(current["body_lines"])
                hunks.append(current)
            current = {
                "old_start": int(match.group("old_start")),
                "old_len": int(match.group("old_len") or "1"),
                "new_start": int(match.group("new_start")),
                "new_len": int(match.group("new_len") or "1"),
                "header": (match.group("header") or "").strip(),
                "body_lines": [line],
            }
        elif current is not None:
            current["body_lines"].append(line)

    if current is not None:
        current["body_text"] = "\n".join(current["body_lines"])
        hunks.append(current)

    return hunks


def _looks_like_function_signature(line):
    stripped = line.strip()
    if not stripped or "(" not in stripped:
        return False
    if stripped.endswith(";") or stripped.startswith(("if ", "if(", "for ", "for(", "while ", "while(", "switch ", "switch(")):
        return False
    name_match = FUNCTION_NAME_RE.search(stripped)
    if not name_match:
        return False
    if name_match.group(1) in {"if", "for", "while", "switch", "return", "sizeof"}:
        return False
    return True


def _find_signature_start(lines, index, search_limit=120):
    lower_bound = max(0, index - search_limit)
    for idx in range(index, lower_bound - 1, -1):
        if _looks_like_function_signature(lines[idx]):
            return idx
    return None


def _find_block_end(lines, start_index, lookahead=400):
    brace_balance = 0
    seen_open_brace = False
    upper_bound = min(len(lines), start_index + lookahead)

    for idx in range(start_index, upper_bound):
        brace_balance += lines[idx].count("{")
        if lines[idx].count("{"):
            seen_open_brace = True
        brace_balance -= lines[idx].count("}")
        if seen_open_brace and brace_balance <= 0:
            return idx
    return None


def _compress_block_lines(line_numbers, lines, max_lines, focus_line):
    if len(lines) <= max_lines:
        return line_numbers, lines

    selected = []
    head = list(range(0, min(4, len(lines))))
    tail = list(range(max(len(lines) - 3, 0), len(lines)))
    center = max(0, min(len(lines) - 1, focus_line))
    center_band = list(range(max(0, center - 6), min(len(lines), center + 7)))
    keyword_hits = [
        idx
        for idx, line in enumerate(lines)
        if any(token in line for token in ("if", "for", "while", "switch", "goto", "return"))
    ]

    for idx in head + center_band + keyword_hits + tail:
        if idx not in selected:
            selected.append(idx)
        if len(selected) >= max_lines:
            break

    selected = sorted(selected[:max_lines])
    return [line_numbers[idx] for idx in selected], [lines[idx] for idx in selected]


def _format_numbered_lines(line_numbers, lines):
    return "\n".join(
        f"{line_no:>5} {line}"
        for line_no, line in zip(line_numbers, lines)
    )


def _compress_patch_preview(text, max_lines):
    lines = (text or "").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    head = lines[: max(1, max_lines // 2)]
    tail = lines[-max(1, max_lines // 3) :]
    return "\n".join(head + ["..."] + tail)


def build_file_focus_slice(
    commit_sha,
    file_path,
    patch_text,
    line_budget=160,
    file_content=None,
    context_lines=20,
    max_slices=3,
):
    hunks = parse_patch_hunks(patch_text)
    if not hunks:
        preview = _compress_patch_preview(patch_text, max(12, min(line_budget, 40)))
        return [
            {
                "source_type": "patch_hunk",
                "file_path": file_path,
                "commit_sha": commit_sha,
                "line_hint": "patch",
                "slice_id": f"{commit_sha}:{_safe_key(file_path)}:patch:0",
                "content": preview,
                "header": "",
            }
        ]

    lines = file_content.splitlines() if file_content else None
    slices = []

    for idx, hunk in enumerate(hunks[:max_slices]):
        if lines:
            center_line = max(1, hunk["new_start"])
            window_start = max(1, center_line - context_lines)
            window_end = min(
                len(lines),
                center_line + max(hunk["new_len"], 1) + context_lines,
            )

            signature_start = _find_signature_start(lines, window_start - 1)
            if signature_start is not None:
                block_end = _find_block_end(lines, signature_start)
                if block_end is not None and (block_end - signature_start + 1) <= line_budget:
                    window_start = signature_start + 1
                    window_end = block_end + 1

            line_numbers = list(range(window_start, window_end + 1))
            block_lines = lines[window_start - 1 : window_end]
            relative_focus = max(0, center_line - window_start)
            line_numbers, block_lines = _compress_block_lines(
                line_numbers,
                block_lines,
                line_budget,
                relative_focus,
            )
            content = _format_numbered_lines(line_numbers, block_lines)
            source_type = "focus_slice"
            line_hint = f"L{line_numbers[0]}-L{line_numbers[-1]}"
        else:
            content = _compress_patch_preview(
                hunk["body_text"],
                max(12, min(line_budget, 40)),
            )
            source_type = "patch_hunk"
            line_hint = f"patch:+{hunk['new_start']}"

        slices.append(
            {
                "source_type": source_type,
                "file_path": file_path,
                "commit_sha": commit_sha,
                "line_hint": line_hint,
                "slice_id": f"{commit_sha}:{_safe_key(file_path)}:focus:{idx}",
                "content": content,
                "header": hunk["header"],
            }
        )

    return slices


def _extract_outline_symbols(file_content, max_symbols=12):
    symbols = []
    for line_no, line in enumerate((file_content or "").splitlines(), start=1):
        if not _looks_like_function_signature(line):
            continue
        symbols.append({"line": line_no, "signature": line.strip()})
        if len(symbols) >= max_symbols:
            break
    return symbols


def _extract_changed_symbols(patch_text, outline_symbols):
    changed = []
    for hunk in parse_patch_hunks(patch_text):
        header = hunk.get("header", "").strip()
        if header:
            changed.append(header)

    if not changed and outline_symbols:
        changed = [entry["signature"] for entry in outline_symbols[:3]]
    return changed[:6]


def build_file_outline(commit_sha, file_path, patch_text, file_content=None):
    outline_symbols = _extract_outline_symbols(file_content) if file_content else []
    changed_symbols = _extract_changed_symbols(patch_text, outline_symbols)

    lines = [f"Changed symbols: {', '.join(changed_symbols) if changed_symbols else 'unknown'}"]
    if outline_symbols:
        lines.append("Top signatures:")
        for symbol in outline_symbols[:8]:
            lines.append(f"- L{symbol['line']}: {symbol['signature']}")
    else:
        lines.append("Top signatures: unavailable from patch-only context.")

    return {
        "source_type": "file_outline",
        "file_path": file_path,
        "commit_sha": commit_sha,
        "line_hint": "outline",
        "slice_id": f"{commit_sha}:{_safe_key(file_path)}:outline",
        "content": "\n".join(lines),
        "changed_symbols": changed_symbols,
    }


def build_digest_context(
    commit_sha,
    file_path,
    patch_text,
    focus_slices,
    outline,
    max_focus_entries=2,
    max_patch_lines=24,
):
    changed_symbols = outline.get("changed_symbols", []) if outline else []
    selected_slices = (focus_slices or [])[:max_focus_entries]

    code_contexts = []
    for focus_slice in selected_slices:
        code_contexts.append(
            {
                "slice_id": focus_slice.get("slice_id"),
                "line_hint": focus_slice.get("line_hint"),
                "header": focus_slice.get("header"),
                "content": focus_slice.get("content", ""),
            }
        )

    summary_lines = [
        f"File: {file_path}",
        "Changed symbols: "
        + (", ".join(changed_symbols) if changed_symbols else "unknown"),
    ]
    if selected_slices:
        summary_lines.append(
            "Primary code regions: "
            + "; ".join(
                (
                    f"{entry.get('header') or 'diff region'}"
                    f" ({entry.get('line_hint')})"
                )
                for entry in selected_slices
            )
        )
    else:
        summary_lines.append("Primary code regions: unavailable from cache.")

    return {
        "file_path": file_path,
        "commit_sha": commit_sha,
        "changed_symbols": changed_symbols,
        "primary_symbol": changed_symbols[0] if changed_symbols else None,
        "primary_slice_id": selected_slices[0].get("slice_id") if selected_slices else None,
        "summary": "\n".join(summary_lines),
        "code_contexts": code_contexts,
        "patch_preview": _compress_patch_preview(patch_text, max_patch_lines),
    }


def prioritize_files(message, files, max_files=3):
    message_lower = (message or "").lower()
    ranked = []
    for file_entry in files:
        filename = file_entry.get("filename", "")
        basename = os.path.basename(filename).lower()
        patch_text = file_entry.get("patch", "")
        score = count_patch_lines(patch_text)
        if filename.lower() in message_lower or basename in message_lower:
            score += 80
        if filename.endswith((".c", ".h")):
            score += 20
        ranked.append((score, filename))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    prioritized = [filename for _, filename in ranked[:max_files]]

    file_map = {entry["filename"]: dict(entry) for entry in files}
    for rank, filename in enumerate(prioritized, start=1):
        file_map[filename]["priority_rank"] = rank
    return [file_map[entry["filename"]] for entry in files], prioritized


def _build_commit_overview(bundle, prioritized_files):
    lines = [
        f"Commit: {bundle.get('id')}",
        f"Year: {bundle.get('year') or 'unknown'}",
        f"Priority files: {', '.join(prioritized_files) if prioritized_files else 'none'}",
        "",
        "Message:",
        bundle.get("message", "").strip(),
    ]
    return {
        "source_type": "commit_overview",
        "file_path": None,
        "commit_sha": bundle.get("id"),
        "line_hint": "message",
        "slice_id": f"{bundle.get('id')}:overview",
        "content": "\n".join(lines).strip(),
    }


def load_commit_cache(commit_sha, cache_dir=DEFAULT_CACHE_DIR):
    cache_path = Path(cache_dir) / f"{commit_sha}.json"
    if not cache_path.exists():
        return None
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_commit_cache(commit_sha, policy=None, cache_dir=DEFAULT_CACHE_DIR, seed_data=None, scheduler=None):
    policy = dict(
        {
            "line_budget": 160,
            "context_lines": 20,
            "max_files": 3,
            "max_slices": 3,
            "fetch_snapshots": True,
            "force_refresh": False,
        },
        **(policy or {}),
    )

    cache_path = Path(cache_dir) / f"{commit_sha}.json"
    if cache_path.exists() and not policy.get("force_refresh"):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    bundle = fetch_commit_bundle(commit_sha, scheduler=scheduler, seed_data=seed_data)
    if not bundle.get("message") and not bundle.get("files"):
        network_error = bundle.get("network_error", "No commit data available.")
        raise RuntimeError(
            f"Unable to prepare kernel cache for {commit_sha}: {network_error}"
        )
    files, prioritized_files = prioritize_files(
        bundle.get("message", ""),
        bundle.get("files", []),
        max_files=policy["max_files"],
    )
    bundle["files"] = files

    file_entries = []
    digest_contexts = []
    for file_entry in files:
        filename = file_entry["filename"]
        fetch_snapshot = (
            policy.get("fetch_snapshots", True)
            and scheduler is not None
            and filename in prioritized_files
        )
        snapshot = ""
        snapshot_error = None
        if fetch_snapshot:
            try:
                snapshot = scheduler.fetch_file_snapshot(commit_sha, filename)
            except Exception as exc:
                snapshot_error = str(exc)

        focus_slices = build_file_focus_slice(
            commit_sha,
            filename,
            file_entry.get("patch", ""),
            line_budget=policy["line_budget"],
            file_content=snapshot,
            context_lines=policy["context_lines"],
            max_slices=policy["max_slices"],
        )
        outline = build_file_outline(
            commit_sha,
            filename,
            file_entry.get("patch", ""),
            file_content=snapshot,
        )
        digest_context = build_digest_context(
            commit_sha,
            filename,
            file_entry.get("patch", ""),
            focus_slices,
            outline,
        )

        file_entries.append(
            {
                "file_path": filename,
                "status": file_entry.get("status"),
                "priority_rank": file_entry.get("priority_rank"),
                "patch": file_entry.get("patch", ""),
                "changes": file_entry.get("changes"),
                "cache_keys": {
                    "l0": f"{commit_sha}:{filename}:l0",
                    "l1": f"{commit_sha}:{filename}:l1",
                    "l2": f"{commit_sha}:{filename}:l2",
                    "l3": f"{commit_sha}:{filename}:l3",
                },
                "focus_slices": focus_slices,
                "outline": outline,
                "digest_context": digest_context,
                "snapshot": snapshot,
                "snapshot_error": snapshot_error,
            }
        )
        if filename in prioritized_files:
            digest_contexts.append(digest_context)

    cache_payload = {
        "id": bundle.get("id"),
        "year": bundle.get("year"),
        "message": bundle.get("message", ""),
        "source": bundle.get("source"),
        "overview": _build_commit_overview(bundle, prioritized_files),
        "prioritized_files": prioritized_files,
        "files": file_entries,
        "digest_contexts": digest_contexts,
        "rate_limit": getattr(scheduler, "rate_limit", {}) if scheduler is not None else {},
        "network_error": bundle.get("network_error"),
        "policy": policy,
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_payload, f, indent=2, ensure_ascii=False)

    return cache_payload


def get_cached_file_entry(cache_payload, file_path):
    for entry in cache_payload.get("files", []):
        if entry.get("file_path") == file_path:
            return entry
    raise KeyError(f"Unknown cached file path: {file_path}")


def save_output(output_dir, data):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, OUTPUT_PATH)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    commit_ids = read_commit_ids(COMMIT_LIST_PATH)
    scheduler = KernelApiScheduler()
    commits = {}

    for sha in commit_ids:
        print(f"[INFO] Fetching {sha}...")
        try:
            bundle = fetch_commit_bundle(sha, scheduler=scheduler)
        except Exception as exc:
            print(f"[ERROR] {sha}: {exc}")
            continue
        commits[sha] = {
            "id": bundle.get("id"),
            "year": bundle.get("year"),
            "message": bundle.get("message"),
            "patches": {
                file_entry["filename"]: file_entry.get("patch", "")
                for file_entry in bundle.get("files", [])
            },
        }

    save_output(".", commits)
    print(f"[DONE] Wrote to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
