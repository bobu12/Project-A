"""wait_until_stable: returns True once the file size stops growing."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processor import wait_until_stable  # noqa: E402


def test_returns_true_for_already_stable_file(tmp_path: Path):
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"PDFDATA")
    assert wait_until_stable(f, stable_seconds=0.3, timeout=3.0) is True


def test_returns_false_for_missing_file(tmp_path: Path):
    f = tmp_path / "missing.pdf"
    assert wait_until_stable(f, stable_seconds=0.3, timeout=1.0) is False


def test_returns_false_for_empty_file_until_data_arrives(tmp_path: Path):
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"")
    # File exists but is empty -> caller should keep waiting; with a tight
    # timeout we expect False (size==0 is not considered "stable + ready").
    assert wait_until_stable(f, stable_seconds=0.3, timeout=1.0) is False


def test_waits_for_growth_to_stop(tmp_path: Path):
    """Simulate a scanner writing the file in chunks, then stopping."""
    f = tmp_path / "scan.pdf"
    f.write_bytes(b"start")

    def grow():
        for i in range(3):
            time.sleep(0.2)
            with f.open("ab") as fh:
                fh.write(b"x" * 100)
        # Then writer stops; the watcher should detect stability shortly after.

    t = threading.Thread(target=grow)
    t.start()
    started = time.monotonic()
    result = wait_until_stable(f, stable_seconds=0.4, timeout=5.0)
    elapsed = time.monotonic() - started
    t.join()

    assert result is True
    # The growth phase takes ~0.6s; with stable_seconds=0.4 the function
    # cannot return earlier than ~1.0s. Use a generous floor to avoid flakiness.
    assert elapsed >= 0.6
