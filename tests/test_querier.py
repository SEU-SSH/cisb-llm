import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "agents"))

from querier import (
    collect_spec_targets,
    parse_spec_bundle,
    query_output_paths,
    render_qll_file,
    render_ql_file,
)


class QuerierTests(unittest.TestCase):
    def test_parse_spec_bundle_extracts_description_and_pattern(self):
        content = (
            "# CISB Specification\n\n"
            "## Vulnerability Description\n\n"
            "**Source**\nCommit abc\n\n"
            "**Description**\nDesc\n\n"
            "**Evidence**\nEv\n\n"
            "**Requirement**\nReq\n\n"
            "**Mitigation**\nMit\n\n"
            "---\n\n"
            "## Code Pattern\n\n"
            "```json\n"
            '{"triggers":["x"],"vulnerable_pattern":"vp","ql_constraints":"qc","equivalence_notes":[],"scope_assumptions":[],"control_flow_assumptions":[],"environment_assumptions":[]}\n'
            "```\n"
        )
        with tempfile.NamedTemporaryFile("w+", suffix="_spec.md", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        try:
            bundle = parse_spec_bundle(path)
            self.assertEqual(bundle["source_id"], Path(path).stem[:-5])
            self.assertEqual(bundle["description_fields"]["source"], "Commit abc")
            self.assertEqual(bundle["pattern_json"]["vulnerable_pattern"], "vp")
        finally:
            os.remove(path)

    def test_collect_spec_targets_supports_single_file(self):
        targets = collect_spec_targets(spec_file="specs/example_spec.md")
        self.assertTrue(targets[0].endswith("specs/example_spec.md"))

    def test_query_output_paths_returns_qll_and_ql(self):
        bundle = {"source_id": "02828845dd"}
        paths = query_output_paths(bundle, output_dir="queries/cpp")
        self.assertEqual(str(paths["qll"]), "queries/cpp/02828845dd.qll")
        self.assertEqual(str(paths["ql"]), "queries/cpp/02828845dd.ql")

    def test_render_qll_and_ql_files(self):
        result = {
            "qll_code": "import cpp\nmodule Demo { predicate p() { any() } }\n",
            "ql_code": "/** @name Demo */\nimport cpp\nimport Demo\nfrom int i where i = 1 select i\n",
        }
        self.assertIn("import cpp", render_qll_file(result))
        self.assertIn("import cpp", render_ql_file(result))
        self.assertIn("select", render_ql_file(result))


if __name__ == "__main__":
    unittest.main()
