"""Dedup / collision handling for target filenames."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processor import is_duplicate, unique_destination  # noqa: E402


def test_unique_destination_no_collision(tmp_path: Path):
    assert unique_destination(tmp_path, "LPO_26000553.pdf") == tmp_path / "LPO_26000553.pdf"


def test_unique_destination_first_collision(tmp_path: Path):
    (tmp_path / "LPO_26000553.pdf").write_bytes(b"existing")
    result = unique_destination(tmp_path, "LPO_26000553.pdf")
    assert result == tmp_path / "LPO_26000553_dup1.pdf"


def test_unique_destination_multiple_collisions(tmp_path: Path):
    (tmp_path / "LPO_26000553.pdf").write_bytes(b"x")
    (tmp_path / "LPO_26000553_dup1.pdf").write_bytes(b"x")
    (tmp_path / "LPO_26000553_dup2.pdf").write_bytes(b"x")
    result = unique_destination(tmp_path, "LPO_26000553.pdf")
    assert result == tmp_path / "LPO_26000553_dup3.pdf"


def test_is_duplicate(tmp_path: Path):
    target = tmp_path / "LPO_26000553.pdf"
    assert is_duplicate(target) is False
    target.write_bytes(b"x")
    assert is_duplicate(target) is True


def test_unique_destination_preserves_extension(tmp_path: Path):
    (tmp_path / "scan.pdf").write_bytes(b"x")
    result = unique_destination(tmp_path, "scan.pdf")
    assert result.suffix == ".pdf"
    assert result.stem == "scan_dup1"
