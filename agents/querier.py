import json
from dataclasses import dataclass
from pathlib import Path

from agent import Agent


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERIER_PROMPT_PATH = PROJECT_ROOT / ".prompts" / "Querier.md"
CISB_DEFINITION_PATH = PROJECT_ROOT / "rag" / "knowledge_base" / "cisb_definition.md"
CONCEPT_DISTINCTIONS_PATH = PROJECT_ROOT / "rag" / "knowledge_base" / "concept_distinctions.md"


def load_querier_prompt(prompt_path=QUERIER_PROMPT_PATH):
    base_prompt = Path(prompt_path).read_text(encoding="utf-8").strip()
    output_contract = """

You must return one JSON object with exactly these top-level fields:
{
  "query_id": "string",
  "query_name": "string",
  "summary": "string",
  "severity": "string",
  "precision": "string",
  "tags": ["string"],
  "rationale": "string",
  "semantic_units": {
    "root_cause_unit": "string",
    "control_flow_unit": "string",
    "environment_unit": "string"
  },
  "qll_code": "string",
  "ql_code": "string"
}

Rules:
- `qll_code` must be a complete `.qll` library file.
- `ql_code` must be a complete `.ql` query file.
- The generated `.qll` should contain reusable semantic units as predicates and/or classes.
- The generated `.ql` should remain thin and use the `.qll` library.
- Do not output Markdown or explanations outside the JSON object.
"""
    return base_prompt + "\n\n" + output_contract


def extract_source_id(path):
    stem = Path(path).stem
    return stem[:-5] if stem.endswith("_spec") else stem


def parse_code_pattern_json(text):
    marker = "## Code Pattern"
    if marker not in text:
        return None
    _, tail = text.split(marker, 1)
    start = tail.find("```json")
    if start == -1:
        return None
    start = tail.find("\n", start)
    if start == -1:
        return None
    end = tail.find("```", start + 1)
    if end == -1:
        return None
    return json.loads(tail[start:end].strip())


def parse_section(text, section_name):
    marker = f"**{section_name}**"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    lines = tail.lstrip().splitlines()
    collected = []
    for line in lines:
        if line.startswith("**") or line.startswith("---") or line.startswith("## "):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def parse_spec_bundle(path):
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    return {
        "source_id": extract_source_id(path),
        "source_spec_path": str(path.resolve()),
        "spec_markdown": raw,
        "description_fields": {
            "source": parse_section(raw, "Source"),
            "description": parse_section(raw, "Description"),
            "evidence": parse_section(raw, "Evidence"),
            "requirement": parse_section(raw, "Requirement"),
            "mitigation": parse_section(raw, "Mitigation"),
        },
        "pattern_json": parse_code_pattern_json(raw),
    }


def collect_spec_targets(input_dir="specs", spec_file=None):
    if spec_file:
        return [str(Path(spec_file).resolve())]

    root = Path(input_dir)
    return [str(path.resolve()) for path in sorted(root.glob("*_spec.md"))]


def build_knowledge_context():
    return {
        "cisb_definition": CISB_DEFINITION_PATH.read_text(encoding="utf-8"),
        "concept_distinctions": CONCEPT_DISTINCTIONS_PATH.read_text(encoding="utf-8"),
    }


def build_querier_payload(bundle, knowledge):
    return {
        "source_id": bundle["source_id"],
        "description_fields": bundle["description_fields"],
        "pattern_json": bundle["pattern_json"],
        "cisb_knowledge": knowledge,
    }


def query_output_paths(bundle, output_dir="queries/cpp"):
    base = Path(output_dir)
    return {
        "qll": base / f"{bundle['source_id']}.qll",
        "ql": base / f"{bundle['source_id']}.ql",
    }


def render_qll_file(result_json):
    return result_json.get("qll_code", "").strip() + "\n"


def render_ql_file(result_json):
    return result_json.get("ql_code", "").strip() + "\n"


@dataclass
class QuerierResult:
    source_spec_path: str
    source_id: str
    qll_path: str
    ql_path: str
    skipped: bool = False
    reason: str = ""


class QuerierAgent(Agent):
    def __init__(self, model, api_key, url, prompt_path=QUERIER_PROMPT_PATH):
        super().__init__()
        self.model = model
        self.API_KEY = api_key
        self.URL = url
        self.prompt = load_querier_prompt(prompt_path)
        self.knowledge = build_knowledge_context()

    def can_call_model(self):
        return bool(self.model and self.API_KEY and self.URL)

    def generate_query_json(self, bundle):
        if not self.can_call_model():
            raise ValueError("QuerierAgent requires model/api configuration.")

        payload = build_querier_payload(bundle, self.knowledge)
        text = self.complete_chat(
            [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            json_mode=True,
            temperature=0.2,
            max_tokens=4200,
        )
        return self.extract_json_payload(text)

    def process_bundle(self, bundle, output_dir="queries/cpp", skip_existing=False):
        paths = query_output_paths(bundle, output_dir=output_dir)
        if skip_existing and paths["qll"].exists() and paths["ql"].exists():
            return QuerierResult(
                source_spec_path=bundle["source_spec_path"],
                source_id=bundle["source_id"],
                qll_path=str(paths["qll"]),
                ql_path=str(paths["ql"]),
                skipped=True,
                reason="skip_existing",
            )

        result_json = self.generate_query_json(bundle)
        qll_text = render_qll_file(result_json)
        ql_text = render_ql_file(result_json)

        paths["qll"].parent.mkdir(parents=True, exist_ok=True)
        paths["qll"].write_text(qll_text, encoding="utf-8")
        paths["ql"].write_text(ql_text, encoding="utf-8")

        return QuerierResult(
            source_spec_path=bundle["source_spec_path"],
            source_id=bundle["source_id"],
            qll_path=str(paths["qll"]),
            ql_path=str(paths["ql"]),
        )
