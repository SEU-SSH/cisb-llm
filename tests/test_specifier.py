import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "agents"))

from specifier import (
    collect_analysis_targets,
    parse_analysis_bundle,
    render_spec_markdown,
    spec_output_path,
)


class SpecifierTests(unittest.TestCase):
    def test_parse_analysis_bundle_with_digest_json(self):
        content = (
            "# CISB Analysis Report\n\n"
            "**Title**\nDemo\n\n"
            "## Digest JSON\n\n"
            "```json\n"
            '{"function_contexts":[{"file_path":"a.c"}],"focused_contexts":[{"file_path":"a.c","slice_content":"if(x)"}]}\n'
            "```\n"
        )
        with tempfile.NamedTemporaryFile("w+", suffix="_analysis.md", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name

        try:
            bundle = parse_analysis_bundle(path)
            self.assertEqual(bundle["source_id"], Path(path).stem[:-9])
            self.assertTrue(bundle["digest_available"])
            self.assertIn("function_contexts", bundle["digest_json"])
        finally:
            os.remove(path)

    def test_parse_analysis_bundle_without_digest_json(self):
        with tempfile.NamedTemporaryFile("w+", suffix="_analysis.md", delete=False, encoding="utf-8") as f:
            f.write("# CISB Analysis Report\n\nNo digest attached.\n")
            path = f.name

        try:
            bundle = parse_analysis_bundle(path)
            self.assertFalse(bundle["digest_available"])
            self.assertIsNone(bundle["digest_json"])
        finally:
            os.remove(path)

    def test_collect_analysis_targets_only_scans_p_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_dir = Path(tmpdir) / "P"
            n_dir = Path(tmpdir) / "N"
            p_dir.mkdir()
            n_dir.mkdir()
            (p_dir / "abc_analysis.md").write_text("x", encoding="utf-8")
            (n_dir / "def_analysis.md").write_text("x", encoding="utf-8")

            targets = collect_analysis_targets(input_dir=tmpdir)
            self.assertEqual(targets, [str((p_dir / "abc_analysis.md").resolve())])

    def test_spec_output_path_maps_to_specs_directory(self):
        bundle = {"source_id": "83aec96c63"}
        path = spec_output_path(bundle, output_dir="specs")
        self.assertEqual(str(path), "specs/83aec96c63_spec.md")

    def test_render_spec_markdown_contains_sections_and_json(self):
        bundle = {
            "source_path": "/tmp/P/83aec96c63_analysis.md",
            "source_id": "83aec96c63",
            "digest_available": True,
        }
        spec_json = {
            "source": "Commit 83aec96c63",
            "description": "Compiler optimization removed a memory-ordering assumption.",
            "evidence": "Inline asm lacked memory clobber.",
            "requirement": "Clang or GCC with optimization.",
            "mitigation": "Add memory clobber or explicit barrier.",
            "triggers": ["missing memory clobber", "optimized build"],
            "vulnerable_pattern": "asm volatile without memory clobber before shared-memory access",
            "ql_constraints": "exists(AsmStmt a | ...)",
            "equivalence_notes": ["memory barrier macro and inline asm barrier are equivalent in this case"],
            "scope_assumptions": ["within the same helper function"],
            "control_flow_assumptions": ["the barrier must precede the shared-memory access"],
            "environment_assumptions": ["optimized build", "compiler sees inline asm"],
        }

        markdown = render_spec_markdown(spec_json, bundle, model_name="qwen-demo")

        self.assertIn("# CISB Specification", markdown)
        self.assertIn("**Source**", markdown)
        self.assertIn("## Code Pattern", markdown)
        self.assertIn('"triggers": [', markdown)
        self.assertIn('"equivalence_notes": [', markdown)
        self.assertIn('"scope_assumptions": [', markdown)
        self.assertIn('"control_flow_assumptions": [', markdown)
        self.assertIn('"environment_assumptions": [', markdown)
        self.assertIn("Digest: available", markdown)


if __name__ == "__main__":
    unittest.main()
