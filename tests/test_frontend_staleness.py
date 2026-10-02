import os
import tempfile
import unittest
from pathlib import Path

from app.main import _frontend_sources_changed


class TestFrontendSourcesChanged(unittest.TestCase):
    """
    The dev server rebuilds dist when any build input is newer than dist/index.html.
    """

    def setUp(self):
        """
        Build a fake frontend tree whose dist marker is newer than every source.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.frontend = Path(tmp.name)
        self.dist = self.frontend / "dist"
        (self.frontend / "src").mkdir()
        self.dist.mkdir()
        for name in (
            "package.json",
            "index.html",
            "vite.config.ts",
            "tailwind.config.ts",
            "postcss.config.js",
            "tsconfig.json",
            "tsconfig.node.json",
            ".oxfmtrc.json",
            "README.md",
        ):
            self._touch(self.frontend / name, 1_000)
        self._touch(self.frontend / "src" / "main.tsx", 1_000)
        self._touch(self.dist / "index.html", 2_000)

    @staticmethod
    def _touch(path: Path, mtime: float) -> None:
        """
        Create a file and pin its modification time.
        """
        path.write_text("x", encoding="utf-8")
        os.utime(path, (mtime, mtime))

    def test_up_to_date_dist_is_not_stale(self):
        """
        No source newer than the marker means no rebuild.
        """
        self.assertFalse(_frontend_sources_changed(self.frontend, self.dist))

    def test_missing_marker_is_stale(self):
        """
        A dist without index.html must be rebuilt.
        """
        (self.dist / "index.html").unlink()
        self.assertTrue(_frontend_sources_changed(self.frontend, self.dist))

    def test_root_build_inputs_trigger_rebuild(self):
        """
        Every root-level build input, whatever its extension, triggers a rebuild.
        """
        for name in (
            "tailwind.config.ts",
            "postcss.config.js",
            "index.html",
            "tsconfig.node.json",
            "vite.config.ts",
            "package.json",
        ):
            with self.subTest(name=name):
                self._touch(self.frontend / name, 3_000)
                self.assertTrue(_frontend_sources_changed(self.frontend, self.dist))
                self._touch(self.frontend / name, 1_000)

    def test_src_change_triggers_rebuild(self):
        """
        A source file newer than the marker triggers a rebuild.
        """
        self._touch(self.frontend / "src" / "main.tsx", 3_000)
        self.assertTrue(_frontend_sources_changed(self.frontend, self.dist))

    def test_non_build_files_are_ignored(self):
        """
        Formatter config and docs do not affect the bundle.
        """
        for name in (".oxfmtrc.json", "README.md"):
            with self.subTest(name=name):
                self._touch(self.frontend / name, 3_000)
                self.assertFalse(_frontend_sources_changed(self.frontend, self.dist))
                self._touch(self.frontend / name, 1_000)


if __name__ == "__main__":
    unittest.main()
