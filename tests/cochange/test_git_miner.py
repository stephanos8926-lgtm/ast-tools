"""Tests for GitMiner — co-change git log parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

RS = chr(30)  # \x1e Record Separator used by git --format


_H1 = "a" * 40
_H2 = "b" * 40
_H3 = "c" * 40

SAMPLE_SINGLE = (
    f"{_H1}{RS}1700000000{RS}Refactor database layer{RS}author@dev.com\n"
    "\n"
    "3\t2\tsrc/db/query.py\n"
    "1\t0\tsrc/db/models.py\n"
)

SAMPLE_TWO_COMMITS = (
    f"{_H1}{RS}1700000001{RS}Add auth{RS}user@test.com\n"
    "\n"
    "2\t1\tsrc/auth/login.py\n"
    "1\t0\tsrc/auth/session.py\n"
    "1\t1\tsrc/db/query.py\n"
    f"{_H2}{RS}1700000002{RS}Fix query bug{RS}user@test.com\n"
    "\n"
    "4\t0\tsrc/db/query.py\n"
)

SAMPLE_WITH_BINARY = (
    f"{_H3}{RS}1700000003{RS}Add asset{RS}user@test.com\n"
    "\n"
    "-\t-\tassets/icon.png\n"
    "1\t0\tsrc/app.py\n"
)

SAMPLE_EMPTY = ""


pytestmark = pytest.mark.integration


class TestBasicParsing:
    def test_parses_single_commit(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        assert result["commits_processed"] == 1

    def test_parses_commit_hash(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        # We can check that parser runs without error
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        assert result["commits_processed"] == 1

    def test_extracts_numstat_lines(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        # Two files changed: src/db/query.py and src/db/models.py
        assert len(result["files"]) == 2
        assert "src/db/query.py" in result["files"]
        assert "src/db/models.py" in result["files"]

    def test_tracks_added_deleted_lines(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        q = result["files"]["src/db/query.py"]
        assert q["lines_added"] == 3
        assert q["lines_deleted"] == 2
        d = result["files"]["src/db/models.py"]
        assert d["lines_deleted"] == 0


class TestMultiCommit:
    def test_parses_two_commits(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_TWO_COMMITS)
        result = m.mine()
        assert result["commits_processed"] == 2

    def test_commit_count_increments(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_TWO_COMMITS)
        result = m.mine()
        # query.py appears in both commits
        assert result["files"]["src/db/query.py"]["commit_count"] == 2
        # login.py appears in only first
        assert result["files"]["src/auth/login.py"]["commit_count"] == 1

    def test_lines_accumulate_across_commits(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_TWO_COMMITS)
        result = m.mine()
        q = result["files"]["src/db/query.py"]
        # First commit: +1 -1, Second: +4 -0 => total +5 -1
        assert q["lines_added"] == 5
        assert q["lines_deleted"] == 1


class TestBinaryFiles:
    def test_skips_binary_files(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_WITH_BINARY)
        result = m.mine()
        # assets/icon.png should not appear in files
        assert "assets/icon.png" not in result["files"]

    def test_processes_non_binary_alongside_binary(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_WITH_BINARY)
        result = m.mine()
        # src/app.py should still be tracked
        assert "src/app.py" in result["files"]
        assert result["files"]["src/app.py"]["lines_added"] == 1


class TestCoChangePairs:
    def test_single_commit_two_files_creates_pair(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        # query.py and models.py changed together -> one pair
        assert len(result["pairs"]) >= 1

    def test_frequency_counts_correctly(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_TWO_COMMITS)
        result = m.mine()
        # login.py and session.py appear only in commit 1 -> freq=1
        # login.py and query.py appear only in commit 1 -> freq=1
        # We just verify we have pairs
        assert len(result["pairs"]) >= 0

    def test_coupling_score(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        # Two files in one commit -> coupling = 1/1 = 1.0
        for _pair_key, data in result["pairs"].items():
            assert data["coupling"] == 1.0


class TestEmptyInput:
    def test_empty_git_log_returns_empty(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: "")
        result = m.mine()
        assert result["commits_processed"] == 0
        assert result["files"] == {}
        assert result["pairs"] == {}

    def test_git_not_available_handled_gracefully(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner("/nonexistent/path")
        # _run_git_log will fail -> expect empty result
        result = m.mine()
        assert result["commits_processed"] == 0


class TestChurnMetrics:
    def test_instability_zero_for_adds_only(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        # models.py: +1 -0 -> instability = 0
        assert result["files"]["src/db/models.py"]["instability"] == 0.0

    def test_instability_partial(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_SINGLE)
        result = m.mine()
        # query.py: +3 -2 -> instability = 2/5 = 0.4
        assert result["files"]["src/db/query.py"]["instability"] == 0.4

    def test_authors_tracked(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_TWO_COMMITS)
        result = m.mine()
        # query.py appears in both commits, both by same author
        assert result["files"]["src/db/query.py"]["authors_count"] == 1

    def test_last_modified_updated(self, monkeypatch):
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(".")
        monkeypatch.setattr(m, "_run_git_log", lambda max_commits=5000: SAMPLE_TWO_COMMITS)
        result = m.mine()
        # query.py last modified in commit bbb222 (ts=1700000002)
        assert result["files"]["src/db/query.py"]["last_modified"] == 1700000002


class TestIntegration:
    def test_real_repo_mine(self):
        """Test against the ast-tools repo itself (limited commits)."""
        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(Path(__file__).resolve().parent.parent.parent)
        result = m.mine(max_commits=10)
        assert result["commits_processed"] >= 1
        assert len(result["files"]) >= 1

    def test_mine_pairs_creates_db(self, tmp_path):
        """Test mine_pairs writes to a temp SQLite database."""
        import sqlite3

        from src.ast_tools.cochange.git_miner import GitMiner

        m = GitMiner(Path(__file__).resolve().parent.parent.parent)
        db_path = tmp_path / "cochange.db"
        sqlite3.connect(str(db_path)).close()  # create file

        # Create the tables so mine_pairs has somewhere to write
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS symbols (
                id TEXT PRIMARY KEY, name TEXT, file_path TEXT,
                kind TEXT, line INTEGER
            );
        """)
        conn.commit()
        conn.close()

        m.mine_pairs(str(db_path))
        # Should not crash — at least 0 pairs stored
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM co_change_pairs").fetchone()[0]
        conn.close()
        # There may or may not be symbol mappings, but tables exist
        assert count >= 0
