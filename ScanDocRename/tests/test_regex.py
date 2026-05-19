"""Regex coverage for the P.O No: <8 digits>/L<n> header."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processor import find_lpos  # noqa: E402


class TestFindLpos:
    def test_canonical_format(self):
        assert find_lpos("Supplier: 140023 P.O No: 26000553/L2") == ["26000553"]

    def test_with_trailing_underscores_like_ocr_artifacts(self):
        # OCR often appends underscores or stray glyphs after the L<n>.
        assert find_lpos("P.O No: 26000553/L2__") == ["26000553"]

    def test_l4_variant(self):
        assert find_lpos("Supplier: 546075 P.O No: 26000008/L4") == ["26000008"]

    def test_lowercase_and_extra_spaces(self):
        text = "p o no : 26001451 / l9"
        assert find_lpos(text) == ["26001451"]

    def test_no_dots_in_p_o(self):
        assert find_lpos("P O No 26001451/L9") == ["26001451"]

    def test_with_colon_or_hash(self):
        assert find_lpos("P.O No # 26001451/L9") == ["26001451"]

    def test_no_match_for_order_number_label(self):
        # Insurance Estimate uses "Order Number" -> must NOT be treated as an LPO.
        text = "Order Number : 26003160 /B6"
        assert find_lpos(text) == []

    def test_no_match_for_seven_digits(self):
        assert find_lpos("P.O No: 2600055/L2") == []

    def test_no_match_for_nine_digits(self):
        # Greedy capture would still take exactly 8 -- but the /L suffix must
        # follow immediately after the 8th digit.
        assert find_lpos("P.O No: 260005533/L2") == []

    def test_no_match_when_suffix_missing(self):
        assert find_lpos("P.O No: 26000553") == []

    def test_multi_po_returns_distinct_ordered_list(self):
        text = """
        Page 1 P.O No: 26000553/L2
        Page 2 P.O No: 26000008/L4
        """
        assert find_lpos(text) == ["26000553", "26000008"]

    def test_repeated_header_deduplicated(self):
        # Same LPO appearing twice (header repeats on every page) is one match.
        text = """
        Page 1 of 3   P.O No: 26000553/L2
        Page 2 of 3   P.O No: 26000553/L2
        Page 3 of 3   P.O No: 26000553/L2
        """
        assert find_lpos(text) == ["26000553"]

    def test_empty_input(self):
        assert find_lpos("") == []
        assert find_lpos(None) == []  # type: ignore[arg-type]
