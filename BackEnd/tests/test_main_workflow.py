import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services.main_workflow import repository_status, RepositoryError, validate_delivery_files

class MainWorkflowTests(unittest.TestCase):
    def status(self, *, branch="main", changes="", counts="0 0", environment="development"):
        from app.services.main_workflow import EXPECTED_REMOTE
        with tempfile.TemporaryDirectory() as directory:
            def git(root, *args):
                return {("branch", "--show-current"): branch,
                    ("remote", "get-url", "origin"): EXPECTED_REMOTE,
                    ("status", "--porcelain"): changes,
                    ("rev-parse", "HEAD"): "abc",
                    ("rev-parse", "--verify", "refs/remotes/origin/main"): "abc",
                    ("rev-list", "--left-right", "--count", "HEAD...origin/main"): counts,
                    ("diff", "--name-only", "--diff-filter=U"): "",
                    ("rev-parse", "--absolute-git-dir"): directory}[args]
            with patch("app.services.main_workflow.git", git), patch.dict(os.environ, {"APP_ENV": environment}):
                return repository_status(root=directory)[0]

    def test_main_changes_can_push(self):
        self.assertTrue(self.status(changes=" M README.md")["can_push"])

    def test_other_branch_and_production_cannot_push(self):
        self.assertFalse(self.status(branch="feature/test", changes=" M README.md")["can_push"])
        self.assertFalse(self.status(environment="production", changes=" M README.md")["can_push"])

    def test_divergence_cannot_pull_or_push(self):
        result = self.status(counts="1 1")
        self.assertFalse(result["can_pull"])
        self.assertFalse(result["can_push"])

    def test_dirty_tree_cannot_pull(self):
        self.assertFalse(self.status(changes=" M README.md", counts="0 1")["can_pull"])
        self.assertTrue(self.status(counts="0 1")["can_pull"])

    def test_secret_file_is_rejected(self):
        with patch("app.services.main_workflow.git", return_value="BackEnd/.env"):
            with self.assertRaises(RepositoryError): validate_delivery_files()
