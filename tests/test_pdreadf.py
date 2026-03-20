"""
tests/test_pdreadf.py
=====================
Unit tests for the PDREADF PDF Reader & Editor application.

All tests create in-memory / temporary PDF files using fitz so that no
external PDF is required.  GUI widget tests are skipped when a display
is not available (e.g. in headless CI).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import List

import fitz
import pytest

# ---------------------------------------------------------------------------
# Insert project root onto sys.path so that ``pdreadf`` is importable even
# when pytest is run from any directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pdreadf import (
    Annotator,
    Editor,
    Manager,
    PDFDocument,
    PageRenderer,
    Settings,
    Utils,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_test_pdf(path: str, page_count: int = 3, text: str = "Hello PDREADF") -> str:
    """Create a minimal PDF with *page_count* pages at *path*.

    Each page contains *text* so that search and extraction tests work.
    Returns *path* for convenience.
    """
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"{text} page {i + 1}")
    doc.save(path)
    doc.close()
    return path


@pytest.fixture()
def tmp_pdf(tmp_path: Path) -> str:
    """Pytest fixture that provides a temporary 3-page PDF path."""
    return make_test_pdf(str(tmp_path / "test.pdf"))


@pytest.fixture()
def tmp_pdf_multi(tmp_path: Path) -> str:
    """Pytest fixture that provides a temporary 5-page PDF path."""
    return make_test_pdf(str(tmp_path / "multi.pdf"), page_count=5)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    """Tests for the Settings class."""

    def test_defaults_on_fresh_instance(self, tmp_path: Path, monkeypatch) -> None:
        """A new Settings object should have sensible default values."""
        monkeypatch.setattr(
            Settings, "_FILE", tmp_path / ".test_settings.json"
        )
        s = Settings()
        assert s.theme in ("dark", "light")
        assert isinstance(s.zoom, float)
        assert s.zoom > 0
        assert isinstance(s.recent_files, list)

    def test_set_persists_and_loads(self, tmp_path: Path, monkeypatch) -> None:
        """Values written with set() must survive a new Settings instance."""
        settings_file = tmp_path / ".test_settings.json"
        monkeypatch.setattr(Settings, "_FILE", settings_file)

        s1 = Settings()
        s1.set("theme", "light")
        s1.set("zoom", 1.75)

        s2 = Settings()
        assert s2.get("theme") == "light"
        assert float(s2.get("zoom")) == pytest.approx(1.75)

    def test_add_recent_deduplicates(self, tmp_path: Path, monkeypatch) -> None:
        """add_recent() should move an existing path to the front."""
        monkeypatch.setattr(Settings, "_FILE", tmp_path / ".s.json")
        s = Settings()
        s.add_recent("/a/b/c.pdf")
        s.add_recent("/x/y/z.pdf")
        s.add_recent("/a/b/c.pdf")  # duplicate
        assert s.recent_files[0] == "/a/b/c.pdf"
        assert s.recent_files.count("/a/b/c.pdf") == 1

    def test_max_recent_trimmed(self, tmp_path: Path, monkeypatch) -> None:
        """The recent-files list must not exceed max_recent entries."""
        monkeypatch.setattr(Settings, "_FILE", tmp_path / ".s.json")
        s = Settings()
        s.set("max_recent", 3)
        for i in range(10):
            s.add_recent(f"/file{i}.pdf")
        assert len(s.recent_files) <= 3

    def test_theme_property(self, tmp_path: Path, monkeypatch) -> None:
        """The theme property setter must persist the value."""
        monkeypatch.setattr(Settings, "_FILE", tmp_path / ".s.json")
        s = Settings()
        s.theme = "light"
        s2 = Settings()
        assert s2.theme == "light"

    def test_load_gracefully_ignores_corrupt_file(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A corrupt settings file must not crash the application."""
        settings_file = tmp_path / ".s.json"
        settings_file.write_text("NOT JSON {{{{", encoding="utf-8")
        monkeypatch.setattr(Settings, "_FILE", settings_file)
        s = Settings()  # must not raise
        assert s.theme in ("dark", "light")


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------

class TestUtils:
    """Tests for the Utils static utility class."""

    def test_fitz_matrix_identity_at_zoom_one(self) -> None:
        """fitz_matrix(1.0) should be the identity-scale matrix."""
        mat = Utils.fitz_matrix(1.0)
        assert mat.a == pytest.approx(1.0)
        assert mat.d == pytest.approx(1.0)

    def test_fitz_matrix_zoom_doubles_scale(self) -> None:
        """fitz_matrix(2.0) should double the scale components."""
        mat = Utils.fitz_matrix(2.0)
        assert mat.a == pytest.approx(2.0)
        assert mat.d == pytest.approx(2.0)

    def test_pixmap_from_page_returns_qpixmap(self, tmp_pdf: str) -> None:
        """pixmap_from_page must return a non-null QPixmap."""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        doc = fitz.open(tmp_pdf)
        pix = Utils.pixmap_from_page(doc[0], zoom=1.0)
        assert not pix.isNull()
        assert pix.width() > 0
        doc.close()

    def test_fitz_rect_to_qrect_no_zoom(self) -> None:
        """fitz_rect_to_qrect at zoom=1 should produce integer pixel values."""
        from PyQt6.QtCore import QRect
        r = fitz.Rect(10, 20, 110, 70)
        qr = Utils.fitz_rect_to_qrect(r, zoom=1.0)
        assert qr.x() == 10
        assert qr.y() == 20
        assert qr.width() == 100
        assert qr.height() == 50

    def test_fitz_rect_round_trip(self) -> None:
        """Converting fitz→QRect→fitz should give the original rectangle."""
        orig = fitz.Rect(15.0, 25.0, 115.0, 75.0)
        zoom = 1.5
        qr = Utils.fitz_rect_to_qrect(orig, zoom=zoom)
        restored = Utils.qrect_to_fitz_rect(qr, zoom=zoom)
        assert restored.x0 == pytest.approx(orig.x0, abs=1)
        assert restored.y0 == pytest.approx(orig.y0, abs=1)

    def test_ensure_dir_creates_path(self, tmp_path: Path) -> None:
        """ensure_dir must create nested directories."""
        new_dir = str(tmp_path / "a" / "b" / "c")
        result = Utils.ensure_dir(new_dir)
        assert os.path.isdir(new_dir)
        assert result == new_dir

    def test_human_size_bytes(self) -> None:
        """human_size should format values in the correct unit."""
        assert "B" in Utils.human_size(500)
        assert "KB" in Utils.human_size(1500)
        assert "MB" in Utils.human_size(2_000_000)


# ---------------------------------------------------------------------------
# PDFDocument
# ---------------------------------------------------------------------------

class TestPDFDocument:
    """Tests for the PDFDocument wrapper class."""

    def test_page_count(self, tmp_pdf: str) -> None:
        """page_count() must match the number of pages in the file."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        assert doc.page_count() == 3
        doc.close()

    def test_render_page_returns_pixmap(self, tmp_pdf: str) -> None:
        """render_page must return a valid QPixmap."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        pix = doc.render_page(0, zoom=1.0)
        assert not pix.isNull()
        doc.close()

    def test_render_page_is_cached(self, tmp_pdf: str) -> None:
        """render_page called twice with same args should return the same object."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        p1 = doc.render_page(0, zoom=1.0)
        p2 = doc.render_page(0, zoom=1.0)
        assert p1 is p2  # cached
        doc.close()

    def test_invalidate_cache_single_page(self, tmp_pdf: str) -> None:
        """invalidate_cache(n) must remove cached entries only for page n."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        doc.render_page(0, zoom=1.0)
        doc.render_page(1, zoom=1.0)
        doc.invalidate_cache(0)
        assert (0, 1.0) not in doc._cache
        assert (1, 1.0) in doc._cache
        doc.close()

    def test_invalidate_cache_all(self, tmp_pdf: str) -> None:
        """invalidate_cache() with no args must clear the entire cache."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        doc.render_page(0, zoom=1.0)
        doc.render_page(1, zoom=1.0)
        doc.invalidate_cache()
        assert len(doc._cache) == 0
        doc.close()

    def test_get_text_contains_content(self, tmp_pdf: str) -> None:
        """get_text should return text that was inserted into the page."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        text = doc.get_text(0)
        assert "Hello PDREADF" in text
        doc.close()

    def test_search_finds_text(self, tmp_pdf: str) -> None:
        """search() must return non-empty list when the query is present."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        rects = doc.search("Hello", 0)
        assert len(rects) > 0
        doc.close()

    def test_search_all_finds_across_pages(self, tmp_pdf: str) -> None:
        """search_all() must find matches on every page that has the text."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        results = doc.search_all("Hello")
        assert len(results) == 3  # all three pages have the text
        doc.close()

    def test_page_size_returns_positive_dimensions(self, tmp_pdf: str) -> None:
        """page_size must return positive width and height."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        w, h = doc.page_size(0)
        assert w > 0 and h > 0
        doc.close()

    def test_save_creates_file(self, tmp_pdf: str, tmp_path: Path) -> None:
        """save(new_path) must create a new file at the given path."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        new_path = str(tmp_path / "saved.pdf")
        doc.save(new_path)
        assert os.path.isfile(new_path)
        doc.close()

    def test_is_modified_initially_false(self, tmp_pdf: str) -> None:
        """is_modified should be False immediately after opening."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        assert not doc.is_modified
        doc.close()


# ---------------------------------------------------------------------------
# PageRenderer
# ---------------------------------------------------------------------------

class TestPageRenderer:
    """Tests for the PageRenderer façade."""

    def test_render_returns_pixmap(self, tmp_pdf: str) -> None:
        """render() must delegate to PDFDocument and return a QPixmap."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        doc = PDFDocument(tmp_pdf)
        renderer = PageRenderer(doc)
        pix = renderer.render(0, zoom=1.0)
        assert not pix.isNull()
        doc.close()


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------

class TestEditor:
    """Tests for the Editor static page-editing operations."""

    def test_add_blank_page_increases_count(self, tmp_pdf: str) -> None:
        """add_blank_page must increase the page count by exactly 1."""
        import fitz as _fitz
        orig_count = len(_fitz.open(tmp_pdf))
        Editor.add_blank_page(tmp_pdf, after_index=0)
        new_count = len(_fitz.open(tmp_pdf))
        assert new_count == orig_count + 1

    def test_add_blank_page_appends_at_end(self, tmp_pdf: str) -> None:
        """add_blank_page with after_index=-1 should append to the end."""
        import fitz as _fitz
        orig = len(_fitz.open(tmp_pdf))
        Editor.add_blank_page(tmp_pdf, after_index=-1)
        assert len(_fitz.open(tmp_pdf)) == orig + 1

    def test_delete_page_decreases_count(self, tmp_pdf: str) -> None:
        """delete_page must reduce the page count by exactly 1."""
        import fitz as _fitz
        orig = len(_fitz.open(tmp_pdf))
        Editor.delete_page(tmp_pdf, 0)
        assert len(_fitz.open(tmp_pdf)) == orig - 1

    def test_delete_page_out_of_range_is_safe(self, tmp_pdf: str) -> None:
        """delete_page with an out-of-range index must not crash."""
        import fitz as _fitz
        orig = len(_fitz.open(tmp_pdf))
        Editor.delete_page(tmp_pdf, 999)  # no-op
        assert len(_fitz.open(tmp_pdf)) == orig

    def test_rotate_page_sets_rotation(self, tmp_pdf: str) -> None:
        """rotate_page must set a non-zero rotation on the page."""
        import pikepdf as _pikepdf
        Editor.rotate_page(tmp_pdf, 0, 90)
        with _pikepdf.open(tmp_pdf) as pdf:
            rotation = int(pdf.pages[0].get("/Rotate", 0))
        assert rotation == 90

    def test_rotate_page_cumulative(self, tmp_pdf: str) -> None:
        """Two 90° rotations should result in 180°."""
        Editor.rotate_page(tmp_pdf, 0, 90)
        Editor.rotate_page(tmp_pdf, 0, 90)
        import pikepdf as _pikepdf
        with _pikepdf.open(tmp_pdf) as pdf:
            rotation = int(pdf.pages[0].get("/Rotate", 0))
        assert rotation == 180

    def test_reorder_pages_changes_order(self, tmp_pdf_multi: str) -> None:
        """reorder_pages must produce a file with the specified page order."""
        import fitz as _fitz
        # reverse order: 4,3,2,1,0
        new_order = [4, 3, 2, 1, 0]
        Editor.reorder_pages(tmp_pdf_multi, new_order)
        doc = _fitz.open(tmp_pdf_multi)
        assert "page 5" in doc[0].get_text()
        doc.close()

    def test_move_page_changes_position(self, tmp_pdf_multi: str) -> None:
        """move_page must relocate the page to the target position."""
        import fitz as _fitz
        # move page 0 to position 4
        doc_before = _fitz.open(tmp_pdf_multi)
        first_text = doc_before[0].get_text()
        doc_before.close()

        Editor.move_page(tmp_pdf_multi, from_index=0, to_index=4)

        doc_after = _fitz.open(tmp_pdf_multi)
        assert first_text not in doc_after[0].get_text()
        doc_after.close()


# ---------------------------------------------------------------------------
# Annotator
# ---------------------------------------------------------------------------

class TestAnnotator:
    """Tests for the Annotator static annotation methods."""

    def _open_fitz(self, path: str) -> fitz.Document:
        return fitz.open(path)

    def test_add_highlight_creates_annotation(self, tmp_pdf: str) -> None:
        """add_highlight must add at least one annotation to the page."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        rect = fitz.Rect(50, 80, 200, 110)
        Annotator.add_highlight(doc, 0, rect, QColor("#FFFF00"))
        annots = list(doc[0].annots())
        assert len(annots) >= 1
        doc.close()

    def test_add_underline_creates_annotation(self, tmp_pdf: str) -> None:
        """add_underline must add at least one annotation to the page."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        rect = fitz.Rect(50, 90, 200, 110)
        Annotator.add_underline(doc, 0, rect, QColor("#FF0000"))
        annots = list(doc[0].annots())
        assert len(annots) >= 1
        doc.close()

    def test_add_strikeout_creates_annotation(self, tmp_pdf: str) -> None:
        """add_strikeout must add at least one annotation to the page."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        rect = fitz.Rect(50, 90, 200, 110)
        Annotator.add_strikeout(doc, 0, rect, QColor("#FF0000"))
        annots = list(doc[0].annots())
        assert len(annots) >= 1
        doc.close()

    def test_add_freehand_creates_ink_annotation(self, tmp_pdf: str) -> None:
        """add_freehand must add an ink annotation with the given points."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        pts = [(50.0, 100.0), (100.0, 150.0), (150.0, 100.0)]
        Annotator.add_freehand(doc, 0, pts, QColor("#0000FF"))
        annots = list(doc[0].annots())
        assert len(annots) >= 1
        doc.close()

    def test_add_text_note_creates_annotation(self, tmp_pdf: str) -> None:
        """add_text_note must add a sticky-note annotation."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        rect = fitz.Rect(72, 72, 200, 100)
        Annotator.add_text_note(doc, 0, rect, "Test note", QColor("#00FF00"))
        annots = list(doc[0].annots())
        assert len(annots) >= 1
        doc.close()

    def test_apply_annotation_highlight_dispatch(self, tmp_pdf: str) -> None:
        """apply_annotation with 'highlight' must add an annotation."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        rect = fitz.Rect(50, 80, 200, 110)
        result = Annotator.apply_annotation(doc, 0, "highlight", rect, QColor("#FFFF00"))
        assert result is True
        assert len(list(doc[0].annots())) >= 1
        doc.close()

    def test_apply_annotation_unknown_tool_returns_false(self, tmp_pdf: str) -> None:
        """apply_annotation with an unknown tool name should return False."""
        from PyQt6.QtGui import QColor
        doc = self._open_fitz(tmp_pdf)
        rect = fitz.Rect(50, 80, 200, 110)
        result = Annotator.apply_annotation(doc, 0, "laser_beam", rect, QColor("#FF0000"))
        assert result is False
        doc.close()


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class TestManager:
    """Tests for the Manager file-operation utilities."""

    def test_merge_pdfs_creates_output(self, tmp_path: Path) -> None:
        """merge_pdfs must create an output file containing all source pages."""
        p1 = make_test_pdf(str(tmp_path / "a.pdf"), page_count=2)
        p2 = make_test_pdf(str(tmp_path / "b.pdf"), page_count=3)
        out = str(tmp_path / "merged.pdf")
        Manager.merge_pdfs([p1, p2], out)
        assert os.path.isfile(out)
        doc = fitz.open(out)
        assert len(doc) == 5
        doc.close()

    def test_split_pdf_creates_one_file_per_page(self, tmp_path: Path) -> None:
        """split_pdf must create exactly page_count output files."""
        src = make_test_pdf(str(tmp_path / "src.pdf"), page_count=4)
        out_dir = str(tmp_path / "split_out")
        paths = Manager.split_pdf(src, out_dir)
        assert len(paths) == 4
        for p in paths:
            assert os.path.isfile(p)
            single = fitz.open(p)
            assert len(single) == 1
            single.close()

    def test_extract_text_creates_txt_file(self, tmp_path: Path) -> None:
        """extract_text must create a UTF-8 text file."""
        src = make_test_pdf(str(tmp_path / "src.pdf"))
        out = str(tmp_path / "out.txt")
        Manager.extract_text(src, out)
        assert os.path.isfile(out)
        content = Path(out).read_text(encoding="utf-8")
        assert "Hello PDREADF" in content

    def test_extract_text_contains_all_pages(self, tmp_path: Path) -> None:
        """extract_text output must mention every page."""
        src = make_test_pdf(str(tmp_path / "src.pdf"), page_count=3)
        out = str(tmp_path / "out.txt")
        Manager.extract_text(src, out)
        content = Path(out).read_text(encoding="utf-8")
        for i in range(1, 4):
            assert f"Page {i}" in content

    def test_extract_images_returns_zero_for_text_only_pdf(
        self, tmp_path: Path
    ) -> None:
        """extract_images on a text-only PDF should return 0."""
        src = make_test_pdf(str(tmp_path / "src.pdf"))
        out_dir = str(tmp_path / "imgs")
        count = Manager.extract_images(src, out_dir)
        assert count == 0

    def test_export_page_as_image_creates_png(self, tmp_path: Path) -> None:
        """export_page_as_image must create a PNG file for the given page."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        src = make_test_pdf(str(tmp_path / "src.pdf"))
        doc = PDFDocument(src)
        out = str(tmp_path / "page1.png")
        Manager.export_page_as_image(doc, 0, out, zoom=1.0)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 0
        doc.close()

    def test_export_all_pages_creates_correct_count(self, tmp_path: Path) -> None:
        """export_all_pages must create one image per page."""
        from PyQt6.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication(sys.argv)
        src = make_test_pdf(str(tmp_path / "src.pdf"), page_count=3)
        doc = PDFDocument(src)
        out_dir = str(tmp_path / "pages")
        n = Manager.export_all_pages(doc, out_dir, zoom=1.0, fmt="png")
        assert n == 3
        assert len(list(Path(out_dir).glob("*.png"))) == 3
        doc.close()
