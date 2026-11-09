"""Regression checks for verified CI tool downloads; no network is used."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / ".github/scripts"


class TestWindowsToolDownload(unittest.TestCase):
    def exercise(self, valid):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("bd.exe", b"fixture executable")
            actual = hashlib.sha256(archive.read_bytes()).hexdigest()
            source = (SCRIPTS / "install-windows-beads.py").read_text()
            self.assertIn("e59cb7742278185493e30c2eb97cb318db8d7a58c28ee5e88c2a30c7630c0975", source)
            # Use a known fixture digest instead of downloading a release binary.
            source = source.replace("e59cb7742278185493e30c2eb97cb318db8d7a58c28ee5e88c2a30c7630c0975",
                                    actual if valid else "0" * 64)
            calls = []

            def invoke(command, check=False):
                calls.append(command)
                if command[0] == "curl.exe":
                    if "api.github.com" in command[-1]:
                        return subprocess.CompletedProcess(command, 22)
                    shutil.copyfile(archive, command[command.index("--output") + 1])
                return subprocess.CompletedProcess(command, 0)

            with patch.dict(os.environ, {"RUNNER_TEMP": str(root), "GITHUB_PATH": str(root / "path")}), \
                    patch("subprocess.run", side_effect=invoke):
                if valid:
                    exec(compile(source, str(SCRIPTS / "install-windows-beads.py"), "exec"), {})
                    self.assertEqual((root / "keel-windows-beads/bd.exe").read_bytes(), b"fixture executable")
                    self.assertEqual(calls[-1][-1], "--version")
                    self.assertTrue((root / "path").is_file())
                else:
                    with self.assertRaisesRegex(SystemExit, "SHA-256 mismatch"):
                        exec(compile(source, str(SCRIPTS / "install-windows-beads.py"), "exec"), {})
                    self.assertFalse((root / "keel-windows-beads/bd.exe").exists())
                    self.assertFalse((root / "path").exists())
            self.assertIn("api.github.com", calls[0][-1])
            self.assertEqual(calls[1][-1], "https://github.com/gastownhall/beads/releases/download/v1.3.2/beads_1.3.2_windows_amd64.zip")

    def test_api_failure_uses_verified_release_before_execution(self):
        self.exercise(True)

    def test_digest_failure_blocks_extraction_and_execution(self):
        self.exercise(False)


@unittest.skipUnless(sys.platform.startswith("linux"), "Bash installer requires Linux CI utilities")
class TestLinuxToolDownload(unittest.TestCase):
    def exercise(self, valid):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "fixture.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                content = b"#!/bin/sh\nexit 0\n"
                entry = tarfile.TarInfo("fixture")
                entry.size = len(content)
                entry.mode = 0o755
                package.addfile(entry, io.BytesIO(content))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest() if valid else "0" * 64
            binary = root / "fake-bin"
            binary.mkdir()
            curl = binary / "curl"
            curl.write_text('#!/bin/bash\nfor arg do url="$arg"; done\n'
                            'printf "%s\\n" "$url" >> "$CI_DOWNLOAD_CALLS"\n'
                            '[[ "$url" != *api.github.com* ]] || exit 22\n'
                            'while [[ "$1" != --output ]]; do shift; done\n'
                            'cp "$CI_DOWNLOAD_FIXTURE" "$2"\n')
            curl.chmod(0o755)
            source = (SCRIPTS / "install-test-tools.sh").read_text().split("# Pin immutable release asset IDs", 1)[0]
            command = source + '\nfetch_tool fixture https://api.github.com/repos/example/tool/releases/assets/1 https://github.com/example/tool/releases/download/v1/fixture.tar.gz "$CI_DOWNLOAD_DIGEST" fixture\n'
            env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                   "RUNNER_TEMP": str(root), "CI_DOWNLOAD_FIXTURE": str(archive),
                   "CI_DOWNLOAD_CALLS": str(root / "calls"), "CI_DOWNLOAD_DIGEST": digest}
            result = subprocess.run(["bash", "-c", command], env=env, capture_output=True, text=True)
            calls = (root / "calls").read_text().splitlines()
            self.assertEqual(calls, ["https://api.github.com/repos/example/tool/releases/assets/1",
                                    "https://github.com/example/tool/releases/download/v1/fixture.tar.gz"])
            if valid:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((root / "keel-test-tools/bin/fixture").is_file())
            else:
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "keel-test-tools/fixture/fixture").exists())
                self.assertFalse((root / "keel-test-tools/bin/fixture").exists())

    def test_api_failure_uses_verified_release_before_installing(self):
        self.exercise(True)

    def test_digest_failure_blocks_extraction_and_installing(self):
        self.exercise(False)
