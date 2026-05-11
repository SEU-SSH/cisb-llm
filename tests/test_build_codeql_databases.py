import os
import tempfile
import unittest
from pathlib import Path

from build_codeql_databases import (
    build_database,
    build_object_root,
    build_script_path,
    category_identifier,
    collect_category_dirs,
    collect_source_files,
    compiler_for_source,
    ensure_pack_files,
    database_output_path,
    qlpack_path,
    render_build_script,
    render_codeql_pack_lock_file,
    render_qlpack_file,
)


class BuildCodeqlDatabasesTests(unittest.TestCase):
    def test_collect_category_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "cat_a").mkdir()
            (root / "cat_b").mkdir()
            (root / "file.txt").write_text("x", encoding="utf-8")
            dirs = collect_category_dirs(input_dir=tmpdir)
            self.assertEqual(
                [Path(d).name for d in dirs],
                ["cat_a", "cat_b"],
            )

    def test_collect_source_files_filters_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.c").write_text("int main(){return 0;}", encoding="utf-8")
            (root / "b.cpp").write_text("int main(){return 0;}", encoding="utf-8")
            (root / "c.ql").write_text("query", encoding="utf-8")
            sources = collect_source_files(root)
            self.assertEqual([p.name for p in sources], ["a.c", "b.cpp"])

    def test_compiler_for_source(self):
        self.assertEqual(compiler_for_source("x.c"), "gcc")
        self.assertEqual(compiler_for_source("x.cpp"), "g++")

    def test_category_identifier_uses_prefix_before_separator(self):
        self.assertEqual(category_identifier("l-13__ub_pointer_offset_overflow"), "l-13")
        self.assertEqual(category_identifier("custom"), "custom")

    def test_database_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            category = Path(tmpdir) / "l-13__ub_pointer_offset_overflow"
            category.mkdir()
            path = database_output_path(category)
            self.assertEqual(path, (category / ".codeql-db-l-13").resolve())
            self.assertTrue(path.is_absolute())

            output_path = database_output_path(category, output_dir=Path(tmpdir) / "out")
            self.assertEqual(output_path, (Path(tmpdir) / "out" / "l-13").resolve())

    def test_build_paths_default_inside_category_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            category = Path(tmpdir) / "cat"
            category.mkdir()
            self.assertEqual(
                build_script_path(category),
                (category / ".codeql-build.sh").resolve(),
            )
            self.assertEqual(
                build_object_root(category),
                (category / ".codeql-objs").resolve(),
            )

    def test_build_paths_use_identifier_when_output_dir_is_external(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            category = Path(tmpdir) / "l-13__ub_pointer_offset_overflow"
            category.mkdir()
            out = Path(tmpdir) / "out"
            self.assertEqual(
                build_script_path(category, output_dir=out),
                (out / "l-13__build.sh").resolve(),
            )
            self.assertEqual(
                build_object_root(category, output_dir=out),
                (out / "l-13__objs").resolve(),
            )

    def test_render_build_script_contains_compile_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "l-13.c"
            source.write_text("int main(){return 0;}", encoding="utf-8")
            script = render_build_script(
                category_dir=root,
                source_files=[source],
                object_root=root / "objs",
                cc="gcc",
                cxx="g++",
                extra_cflags="-O2 -Wall",
            )
            self.assertIn("gcc -O2 -Wall -c l-13.c", script)
            self.assertIn("mkdir -p", script)

    def test_render_and_write_pack_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            category = Path(tmpdir) / "l-9__dse_memset"
            category.mkdir()

            self.assertIn("name: cisb-llm/l-9-dse-memset", render_qlpack_file(category))
            self.assertIn("codeql/cpp-all", render_codeql_pack_lock_file())

            ensure_pack_files(category)
            self.assertTrue(qlpack_path(category).exists())
            self.assertIn("dependencies:", qlpack_path(category).read_text(encoding="utf-8"))

    def test_build_database_skips_existing_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            category = Path(tmpdir) / "cat"
            category.mkdir()
            (category / "sample.c").write_text("int main(){return 0;}", encoding="utf-8")
            output_dir = Path(tmpdir) / "out"
            db_path = output_dir / "cat"
            db_path.mkdir(parents=True)

            result = build_database(category, output_dir=output_dir)

            self.assertTrue(result["skipped"])
            self.assertEqual(result["reason"], "already_exists")


if __name__ == "__main__":
    unittest.main()
