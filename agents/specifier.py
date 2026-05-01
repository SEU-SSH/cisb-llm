import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent import Agent


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPECIFIER_PROMPT_PATH = PROJECT_ROOT / ".prompts" / "Specifier.md"
PATTERN_PROMPT_PATH = PROJECT_ROOT / ".prompts" / "pattern_generate.md"


def load_specifier_prompt(
    prompt_path=SPECIFIER_PROMPT_PATH,
    pattern_prompt_path=PATTERN_PROMPT_PATH,
):
    base_prompt = Path(prompt_path).read_text(encoding="utf-8").strip()
    pattern_prompt = Path(pattern_prompt_path).read_text(encoding="utf-8").strip()
    output_contract = """

You must return one JSON object, and the top-level keys must be exactly:
{
  "source": "string",
  "description": "string",
  "evidence": "string",
  "requirement": "string",
  "mitigation": "string",
  "triggers": ["string"],
  "vulnerable_pattern": "string",
  "ql_constraints": "string",
  "equivalence_notes": ["string"],
  "scope_assumptions": ["string"],
  "control_flow_assumptions": ["string"],
  "environment_assumptions": ["string"]
}

Additional rules:
- All descriptive fields must be concise and directly reusable in a vulnerability specification document.
- If digest data is unavailable, still produce a result, but do not invent code details that are not present in the report.
- The code-pattern fields must follow the separate pattern-generation constraints below.

Pattern-generation constraints:
"""
    return base_prompt + "\n\n" + output_contract + "\n" + pattern_prompt


def extract_source_id(path):
    stem = Path(path).stem
    return stem[:-9] if stem.endswith("_analysis") else stem


def split_analysis_sections(text):
    marker = "## Digest JSON"
    if marker not in text:
        return text.strip(), None

    analysis_markdown, digest_block = text.split(marker, 1)
    return analysis_markdown.strip(), digest_block


def parse_digest_json_block(digest_block):
    if not digest_block:
        return None

    start = digest_block.find("```json")
    if start == -1:
        return None
    start = digest_block.find("\n", start)
    if start == -1:
        return None
    end = digest_block.find("```", start + 1)
    if end == -1:
        return None

    json_text = digest_block[start:end].strip()
    if not json_text:
        return None

    return json.loads(json_text)


def parse_analysis_bundle(path):
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    analysis_markdown, digest_block = split_analysis_sections(raw)
    digest_json = parse_digest_json_block(digest_block)
    return {
        "source_id": extract_source_id(path),
        "source_path": str(path.resolve()),
        "analysis_markdown": analysis_markdown,
        "digest_json": digest_json,
        "digest_available": digest_json is not None,
    }


def is_positive_bundle(bundle):
    path = Path(bundle["source_path"])
    if "P" in path.parts:
        return True

    text = bundle["analysis_markdown"].lower()
    if "**cisb status**" in text and "\nyes" in text:
        return True
    if "**cisb status**: cisb" in text:
        return True
    return False


def collect_analysis_targets(input_dir=".", analysis_file=None):
    if analysis_file:
        return [str(Path(analysis_file).resolve())]

    root = Path(input_dir)
    targets = []
    for path in sorted(root.rglob("*_analysis.md")):
        if "P" in path.parts:
            targets.append(str(path.resolve()))
    return targets


def build_specifier_payload(bundle):
    payload = {
        "source_id": bundle["source_id"],
        "analysis_report": bundle["analysis_markdown"],
        "digest_available": bundle["digest_available"],
    }
    if bundle["digest_available"]:
        payload["digest_json"] = bundle["digest_json"]
    else:
        payload["digest_json"] = "Digest unavailable"
    return payload


def spec_output_path(bundle, output_dir="specs"):
    return Path(output_dir) / f"{bundle['source_id']}_spec.md"


def render_spec_markdown(spec_json, bundle, model_name):
    pattern_json = {
        "triggers": spec_json.get("triggers", []),
        "vulnerable_pattern": spec_json.get("vulnerable_pattern", ""),
        "ql_constraints": spec_json.get("ql_constraints", ""),
        "equivalence_notes": spec_json.get("equivalence_notes", []),
        "scope_assumptions": spec_json.get("scope_assumptions", []),
        "control_flow_assumptions": spec_json.get("control_flow_assumptions", []),
        "environment_assumptions": spec_json.get("environment_assumptions", []),
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    digest_status = "available" if bundle.get("digest_available") else "unavailable"

    return (
        "# CISB Specification\n\n"
        "## Vulnerability Description\n\n"
        f"**Source**\n{spec_json.get('source', '')}\n\n"
        f"**Description**\n{spec_json.get('description', '')}\n\n"
        f"**Evidence**\n{spec_json.get('evidence', '')}\n\n"
        f"**Requirement**\n{spec_json.get('requirement', '')}\n\n"
        f"**Mitigation**\n{spec_json.get('mitigation', '')}\n\n"
        "---\n\n"
        "## Code Pattern\n\n"
        "```json\n"
        f"{json.dumps(pattern_json, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        "---\n\n"
        "## Provenance\n\n"
        f"- Source analysis: {bundle.get('source_path')}\n"
        f"- Source id: {bundle.get('source_id')}\n"
        f"- Digest: {digest_status}\n"
        f"- Generated at: {generated_at}\n"
        f"- Model: {model_name}\n"
    )


@dataclass
class SpecifierResult:
    source_path: str
    source_id: str
    output_path: str
    skipped: bool = False
    reason: str = ""


class SpecifierAgent(Agent):
    def __init__(self, model, api_key, url, prompt_path=SPECIFIER_PROMPT_PATH):
        super().__init__()
        self.model = model
        self.API_KEY = api_key
        self.URL = url
        self.prompt = load_specifier_prompt(prompt_path)

    def can_call_model(self):
        return bool(self.model and self.API_KEY and self.URL)

    def generate_spec_json(self, bundle):
        payload = build_specifier_payload(bundle)
        if not self.can_call_model():
            raise ValueError("SpecifierAgent requires model/api configuration.")

        text = self.complete_chat(
            [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            json_mode=True,
            temperature=0.2,
            max_tokens=3200,
        )
        return self.extract_json_payload(text)

    def process_bundle(self, bundle, output_dir="specs", skip_existing=False):
        output_path = spec_output_path(bundle, output_dir=output_dir)
        if skip_existing and output_path.exists():
            return SpecifierResult(
                source_path=bundle["source_path"],
                source_id=bundle["source_id"],
                output_path=str(output_path),
                skipped=True,
                reason="skip_existing",
            )

        spec_json = self.generate_spec_json(bundle)
        markdown = render_spec_markdown(spec_json, bundle, self.model)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

        return SpecifierResult(
            source_path=bundle["source_path"],
            source_id=bundle["source_id"],
            output_path=str(output_path),
        )
