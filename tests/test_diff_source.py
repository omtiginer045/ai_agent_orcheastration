import subprocess

import pytest

from pr_reviewer.diff_source import Diff, DiffError, from_file, from_git

SAMPLE = """diff --git a/app/x.py b/app/x.py
--- a/app/x.py
+++ b/app/x.py
@@ -1 +1 @@
-a
+b
diff --git a/README.md b/docs/README.md
"""


def test_files_parsed(tmp_path):
    assert Diff(SAMPLE, tmp_path).files == ["app/x.py", "docs/README.md"]


def test_from_file(tmp_path):
    p = tmp_path / "p.diff"
    p.write_text(SAMPLE)
    d = from_file(p, tmp_path)
    assert not d.is_empty and d.repo_path == tmp_path.resolve()


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


async def test_from_git(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    _git(tmp_path, "checkout", "-qb", "feat")
    (tmp_path / "f.py").write_text("x = 2\n")
    _git(tmp_path, "commit", "-qam", "change")

    d = await from_git(tmp_path, "main", "feat")
    assert d.files == ["f.py"]
    assert "+x = 2" in d.text


async def test_from_git_bad_ref(tmp_path):
    _git(tmp_path, "init", "-q")
    with pytest.raises(DiffError):
        await from_git(tmp_path, "nope")
