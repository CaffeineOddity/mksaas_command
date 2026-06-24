"""tests.test_repo_url — repo_url 清洗测试。"""

import pytest

from mksaas.repo_url import clean_repo_url


def test_strip_https_auth_segment():
    url, stripped = clean_repo_url("https://user:token@github.com/o/r.git")
    assert url == "https://github.com/o/r.git"
    assert stripped is True


def test_keep_ssh_url():
    url, stripped = clean_repo_url("git@github.com:o/r.git")
    assert url == "git@github.com:o/r.git"
    assert stripped is False


def test_keep_clean_https():
    url, stripped = clean_repo_url("https://github.com/o/r.git")
    assert url == "https://github.com/o/r.git"
    assert stripped is False


def test_invalid_url_raises():
    with pytest.raises(ValueError):
        clean_repo_url("not a url at all")


def test_empty_raises():
    with pytest.raises(ValueError):
        clean_repo_url("")
