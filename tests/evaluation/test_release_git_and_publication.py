import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.release_tools.git_source import (
    GitSourceError,
    materialize_commit,
    require_clean_exact_head,
    source_entries,
    write_source_zip,
)
from evaluation.v1.release_tools.publication import PublicationError, external_atomic_stage


class ReleaseGitAndPublicationTests(unittest.TestCase):
    @staticmethod
    def _repository(root: Path) -> tuple[Path, str]:
        repo = root / "repo"
        (repo / "evaluation").mkdir(parents=True)
        (repo / "tests" / "evaluation").mkdir(parents=True)
        (repo / "docs" / "evaluation").mkdir(parents=True)
        (repo / "evaluation" / "module.py").write_text("VALUE = 1\n", encoding="ascii")
        (repo / "tests" / "evaluation" / "test_module.py").write_text("def test_value():\n    assert 1 == 1\n", encoding="ascii")
        (repo / "docs" / "evaluation" / "README.md").write_text("# Evaluation\n", encoding="ascii")
        commands = [
            ["git", "init", "-q", str(repo)],
            ["git", "-C", str(repo), "config", "user.email", "evaluation@example.invalid"],
            ["git", "-C", str(repo), "config", "user.name", "Evaluation Test"],
            ["git", "-C", str(repo), "add", "."],
            ["git", "-C", str(repo), "commit", "-q", "-m", "fixture"],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True)
        commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        return repo, commit

    def test_normal_preflight_rejects_wrong_commit_dirty_and_untracked(self):
        with TemporaryDirectory() as temp:
            repo, commit = self._repository(Path(temp))
            require_clean_exact_head(repo, commit)
            with self.assertRaises(GitSourceError):
                require_clean_exact_head(repo, "0" * 40)
            (repo / "evaluation" / "module.py").write_text("VALUE = 2\n", encoding="ascii")
            with self.assertRaises(GitSourceError):
                require_clean_exact_head(repo, commit)
            subprocess.run(["git", "-C", str(repo), "restore", "evaluation/module.py"], check=True)
            (repo / "evaluation" / "untracked.py").write_text("VALUE = 3\n", encoding="ascii")
            with self.assertRaises(GitSourceError):
                require_clean_exact_head(repo, commit)

    def test_source_zip_and_detached_materialization_ignore_live_drift(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repo, commit = self._repository(root)
            entries = source_entries(repo, commit)
            first = root / "one.zip"
            second = root / "two.zip"
            write_source_zip(entries, first)
            write_source_zip(entries, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            (repo / "evaluation" / "module.py").write_text("VALUE = 999\n", encoding="ascii")
            materialized = root / "materialized"
            materialize_commit(repo, commit, materialized)
            self.assertEqual((materialized / "evaluation" / "module.py").read_text(encoding="ascii"), "VALUE = 1\n")

    def test_external_atomic_publication_has_no_dirty_exception(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            repo, _ = self._repository(root)
            output = root / "release"
            with external_atomic_stage(output, repo) as stage:
                (stage / "artifact.txt").write_text("sealed", encoding="ascii")
                self.assertFalse(output.exists())
            self.assertEqual((output / "artifact.txt").read_text(encoding="ascii"), "sealed")
            with self.assertRaises(PublicationError):
                with external_atomic_stage(output, repo):
                    pass
            with self.assertRaises(PublicationError):
                with external_atomic_stage(repo / "evaluation" / "release", repo):
                    pass
