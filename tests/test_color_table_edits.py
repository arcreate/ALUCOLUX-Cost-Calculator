import unittest

from app import apply_color_table_edits


def _row(code: str, face: float = 140.0) -> dict:
    return {
        "color_code": code,
        "coating_type": "PVDF2",
        "embossing_passes": 0,
        "face_paint_price": face,
        "clear_paint_price": 160.0,
        "updated_at": "2026-01-01T00:00:00",
    }


class TestColorTableEdits(unittest.TestCase):
    def test_partial_view_keeps_hidden_rows(self) -> None:
        full = [_row("A"), _row("B"), _row("C")]
        base = [_row("A")]
        edited = [_row("A", 150.0)]
        out = apply_color_table_edits(full, base, edited, partial_view=True, allow_delete=False)
        codes = [r["color_code"] for r in out]
        self.assertEqual(codes, ["A", "B", "C"])
        self.assertAlmostEqual(out[0]["face_paint_price"], 150.0)

    def test_full_view_allows_delete_for_admin(self) -> None:
        full = [_row("A"), _row("B")]
        edited = [_row("A")]
        out = apply_color_table_edits(full, full, edited, partial_view=False, allow_delete=True)
        self.assertEqual([r["color_code"] for r in out], ["A"])

    def test_full_view_blocks_delete_for_advanced(self) -> None:
        full = [_row("A"), _row("B")]
        edited = [_row("A")]
        with self.assertRaises(ValueError):
            apply_color_table_edits(full, full, edited, partial_view=False, allow_delete=False)


if __name__ == "__main__":
    unittest.main()
