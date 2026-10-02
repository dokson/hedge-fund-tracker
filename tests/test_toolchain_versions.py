"""
Runtime versions are declared once (Node in .nvmrc, Python in the Pipfile); the
Dockerfile must spell its images out for Dependabot, so this pins them together.
"""

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NodeVersionTest(unittest.TestCase):
    """
    Every place that picks a Node version agrees with .nvmrc.
    """

    def setUp(self):
        """
        Read the single declared Node major version.
        """
        self.major = (ROOT / ".nvmrc").read_text(encoding="utf-8").strip()

    def test_dockerfile_builds_with_the_declared_major(self):
        """
        The frontend build stage uses the .nvmrc major.
        """
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        majors = re.findall(r"^FROM node:(\d+)[.\-]", dockerfile, flags=re.MULTILINE)
        self.assertEqual(majors, [self.major])

    def test_workflows_read_the_version_from_nvmrc(self):
        """
        No workflow hardcodes a Node version; each reads .nvmrc.
        """
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            with self.subTest(workflow=workflow.name):
                self.assertNotIn("node-version:", text)
                if "actions/setup-node" in text:
                    self.assertIn("node-version-file: .nvmrc", text)


class PythonVersionTest(unittest.TestCase):
    """
    The Docker images run the Python version the Pipfile requires.
    """

    def test_dockerfile_python_images_match_the_pipfile(self):
        """
        Every python base image is a final release of the Pipfile's major.minor.
        """
        with (ROOT / "Pipfile").open("rb") as pipfile:
            required = tomllib.load(pipfile)["requires"]["python_version"]
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        versions = re.findall(r"^FROM python:([^-@\s]+)", dockerfile, flags=re.MULTILINE)
        self.assertTrue(versions)
        for version in versions:
            with self.subTest(version=version):
                self.assertRegex(version, rf"^{re.escape(required)}\.\d+$")


if __name__ == "__main__":
    unittest.main()
