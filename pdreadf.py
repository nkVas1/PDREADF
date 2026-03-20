#!/usr/bin/env python3
"""
PDREADF - Professional PDF Reader & Editor
==========================================

A feature-rich PDF reader and editor application built with PyQt6 and PyMuPDF.
Supports viewing, annotating, editing, searching, and managing PDF documents.

Author : nkVas1
License: MIT
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import pikepdf
from PyQt6.QtCore import (
    QAbstractItemModel,
    QBuffer,
    QByteArray,
    QIODevice,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QTimer,
    QUrl,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QImage,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# ──────────────────────────────────────────────────────────────
#  Settings
# ──────────────────────────────────────────────────────────────

class Settings:
    """Manages persistent application settings stored as a JSON file.

    The settings file is created in the user's home directory as
    ``.pdreadf_settings.json``.  All public attributes have sensible
    defaults so the application works correctly on first run.
    """

    _FILE: Path = Path.home() / ".pdreadf_settings.json"

    _DEFAULTS: Dict[str, Any] = {
        "theme": "dark",
        "zoom": 1.0,
        "page_mode": "single",
        "recent_files": [],
        "max_recent": 10,
        "window_x": 100,
        "window_y": 100,
        "window_w": 1280,
        "window_h": 800,
        "window_maximized": False,
        "annotation_color": "#FFFF00",
        "last_dir": str(Path.home()),
    }

    def __init__(self) -> None:
        self._data: Dict[str, Any] = dict(self._DEFAULTS)
        self.load()

    # ── persistence ───────────────────────────────────────────

    def load(self) -> None:
        """Load settings from the JSON file, ignoring read errors."""
        try:
            if self._FILE.exists():
                with open(self._FILE, "r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                self._data.update(saved)
        except Exception:
            pass

    def save(self) -> None:
        """Persist current settings to the JSON file."""
        try:
            with open(self._FILE, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
        except Exception:
            pass

    # ── generic accessors ─────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if not set."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set *key* to *value* and immediately persist."""
        self._data[key] = value
        self.save()

    # ── recent files ──────────────────────────────────────────

    def add_recent(self, path: str) -> None:
        """Prepend *path* to the recent-files list (deduplicating)."""
        recent: List[str] = self._data.get("recent_files", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._data["recent_files"] = recent[: self._data.get("max_recent", 10)]
        self.save()

    # ── typed properties ──────────────────────────────────────

    @property
    def theme(self) -> str:
        """Active colour theme: ``'dark'`` or ``'light'``."""
        return self._data.get("theme", "dark")

    @theme.setter
    def theme(self, value: str) -> None:
        self._data["theme"] = value
        self.save()

    @property
    def zoom(self) -> float:
        """Global zoom factor (1.0 = 100 %)."""
        return float(self._data.get("zoom", 1.0))

    @zoom.setter
    def zoom(self, value: float) -> None:
        self._data["zoom"] = value
        self.save()

    @property
    def recent_files(self) -> List[str]:
        """Ordered list of recently opened file paths."""
        return self._data.get("recent_files", [])

    @property
    def page_mode(self) -> str:
        """Page display mode: ``'single'``, ``'dual'``, or ``'continuous'``."""
        return self._data.get("page_mode", "single")

    @page_mode.setter
    def page_mode(self, value: str) -> None:
        self._data["page_mode"] = value
        self.save()


# ──────────────────────────────────────────────────────────────
#  Utils
# ──────────────────────────────────────────────────────────────

class Utils:
    """Static utility functions for file operations and image conversions."""

    @staticmethod
    def fitz_matrix(zoom: float, rotation: int = 0) -> fitz.Matrix:
        """Return a :class:`fitz.Matrix` for *zoom* and *rotation* degrees."""
        mat = fitz.Matrix(zoom, zoom)
        if rotation:
            mat = mat * fitz.Matrix(rotation)
        return mat

    @staticmethod
    def pixmap_from_page(page: fitz.Page, zoom: float = 1.0) -> QPixmap:
        """Render *page* at *zoom* and return a :class:`QPixmap`."""
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format.Format_RGB888,
        )
        return QPixmap.fromImage(img)

    @staticmethod
    def fitz_rect_to_qrect(rect: fitz.Rect, zoom: float = 1.0) -> QRect:
        """Convert *rect* (fitz coordinates) to a :class:`QRect` at *zoom*."""
        return QRect(
            int(rect.x0 * zoom),
            int(rect.y0 * zoom),
            int((rect.x1 - rect.x0) * zoom),
            int((rect.y1 - rect.y0) * zoom),
        )

    @staticmethod
    def qrect_to_fitz_rect(rect: QRect, zoom: float = 1.0) -> fitz.Rect:
        """Convert a :class:`QRect` back to fitz coordinates (dividing by *zoom*)."""
        return fitz.Rect(
            rect.x() / zoom,
            rect.y() / zoom,
            (rect.x() + rect.width()) / zoom,
            (rect.y() + rect.height()) / zoom,
        )

    @staticmethod
    def ensure_dir(path: str) -> str:
        """Create *path* (and parents) if absent; return *path*."""
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def human_size(size_bytes: int) -> str:
        """Return *size_bytes* as a human-readable string (e.g. ``'3.4 MB'``)."""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes //= 1024
        return f"{size_bytes:.1f} TB"


# ──────────────────────────────────────────────────────────────
#  PDFDocument
# ──────────────────────────────────────────────────────────────

class PDFDocument:
    """Wrapper around :class:`fitz.Document` with a render cache.

    Caches rendered :class:`QPixmap` objects keyed on ``(page_index, zoom)``
    to avoid redundant re-renders when navigating between pages.
    """

    def __init__(self, path: str) -> None:
        """Open the PDF at *path*.

        Raises :class:`Exception` (propagated from fitz) if the file cannot
        be opened.
        """
        self.path: str = path
        self._doc: fitz.Document = fitz.open(path)
        self._cache: Dict[Tuple[int, float], QPixmap] = {}
        self._modified: bool = False

    # ── page access ───────────────────────────────────────────

    def page_count(self) -> int:
        """Return the total number of pages in the document."""
        return len(self._doc)

    def get_page(self, index: int) -> fitz.Page:
        """Return the :class:`fitz.Page` at *index*."""
        return self._doc[index]

    def page_size(self, index: int) -> Tuple[float, float]:
        """Return ``(width, height)`` of page *index* in PDF points."""
        r = self._doc[index].rect
        return r.width, r.height

    # ── rendering ─────────────────────────────────────────────

    def render_page(self, index: int, zoom: float = 1.0) -> QPixmap:
        """Render page *index* at *zoom* to a :class:`QPixmap` (cached)."""
        key = (index, round(zoom, 4))
        if key not in self._cache:
            page = self._doc[index]
            self._cache[key] = Utils.pixmap_from_page(page, zoom)
        return self._cache[key]

    def invalidate_cache(self, index: Optional[int] = None) -> None:
        """Clear the render cache for *index*, or all pages if ``None``."""
        if index is None:
            self._cache.clear()
        else:
            for k in [k for k in self._cache if k[0] == index]:
                del self._cache[k]

    # ── text & search ─────────────────────────────────────────

    def search(self, query: str, page_index: int) -> List[fitz.Rect]:
        """Return a list of :class:`fitz.Rect` matching *query* on *page_index*."""
        return self._doc[page_index].search_for(query)

    def search_all(self, query: str) -> Dict[int, List[fitz.Rect]]:
        """Search *query* across all pages; return ``{page_index: [rects]}``."""
        results: Dict[int, List[fitz.Rect]] = {}
        for i in range(self.page_count()):
            rects = self.search(query, i)
            if rects:
                results[i] = rects
        return results

    def get_text(self, page_index: int) -> str:
        """Extract plain text from page *page_index*."""
        return self._doc[page_index].get_text()

    def get_all_text(self) -> str:
        """Extract plain text from every page, separated by page headers."""
        return "\n\n".join(
            f"--- Page {i + 1} ---\n{self.get_text(i)}"
            for i in range(self.page_count())
        )

    def get_toc(self) -> List[Tuple]:
        """Return the document table of contents as ``[(level, title, page)]``."""
        return self._doc.get_toc()

    # ── save / close ──────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> None:
        """Save the document to *path*, or overwrite the original file.

        When saving in-place a temporary file is used so that the original
        is only replaced after a successful write.
        """
        if path and path != self.path:
            self._doc.save(path, garbage=4, deflate=True)
        else:
            tmp = self.path + ".pdreadf_tmp"
            self._doc.save(tmp, garbage=4, deflate=True)
            os.replace(tmp, self.path)
        self._modified = False

    def close(self) -> None:
        """Close the underlying fitz document and clear the cache."""
        self._cache.clear()
        self._doc.close()

    # ── properties ────────────────────────────────────────────

    @property
    def is_modified(self) -> bool:
        """``True`` if the document has unsaved annotation changes."""
        return self._modified

    @property
    def fitz_doc(self) -> fitz.Document:
        """Direct access to the underlying :class:`fitz.Document`."""
        return self._doc


# ──────────────────────────────────────────────────────────────
#  PageRenderer
# ──────────────────────────────────────────────────────────────

class PageRenderer(QObject):
    """Thin façade that renders PDF pages through a :class:`PDFDocument`.

    Keeping rendering behind this class allows future async rendering
    without changing call sites.
    """

    def __init__(self, doc: PDFDocument, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._doc = doc

    def render(self, page_index: int, zoom: float) -> QPixmap:
        """Render *page_index* synchronously and return a :class:`QPixmap`."""
        return self._doc.render_page(page_index, zoom)

    def set_document(self, doc: PDFDocument) -> None:
        """Switch the renderer to a different document."""
        self._doc = doc


# ──────────────────────────────────────────────────────────────
#  ThumbnailPanel
# ──────────────────────────────────────────────────────────────

class ThumbnailPanel(QWidget):
    """Sidebar panel showing page thumbnails in a vertical list.

    Thumbnails can be clicked to navigate to a page, and dragged to
    reorder pages inside the document.
    """

    page_selected: pyqtSignal = pyqtSignal(int)
    """Emitted with the page index when a thumbnail is clicked."""

    pages_reordered: pyqtSignal = pyqtSignal(list)
    """Emitted with the new page-index order after a drag-drop reorder."""

    THUMB_W = 120
    THUMB_H = 155

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._doc: Optional[PDFDocument] = None
        self._setup_ui()

    # ── setup ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Build the thumbnail list UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Pages")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setIconSize(QSize(self.THUMB_W, self.THUMB_H))
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setFlow(QListWidget.Flow.TopToBottom)
        self._list.setWrapping(False)
        self._list.setSpacing(6)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list)

        self.setMinimumWidth(self.THUMB_W + 30)
        self.setMaximumWidth(220)

    # ── public API ────────────────────────────────────────────

    def load_document(self, doc: PDFDocument) -> None:
        """Populate thumbnails from *doc*, storing original page indices."""
        self._doc = doc
        self._list.clear()
        for i in range(doc.page_count()):
            pix = doc.render_page(i, zoom=0.18)
            item = QListWidgetItem(QIcon(pix), f"  {i + 1}")
            item.setSizeHint(QSize(self.THUMB_W + 20, self.THUMB_H + 28))
            item.setData(Qt.ItemDataRole.UserRole, i)  # original index
            self._list.addItem(item)

    def set_current_page(self, index: int) -> None:
        """Highlight the thumbnail row for *index* without emitting signals."""
        self._list.blockSignals(True)
        self._list.setCurrentRow(index)
        self._list.blockSignals(False)

    def refresh_page(self, doc: PDFDocument, index: int) -> None:
        """Re-render the thumbnail for page *index*."""
        if index < self._list.count():
            pix = doc.render_page(index, zoom=0.18)
            self._list.item(index).setIcon(QIcon(pix))

    def clear(self) -> None:
        """Remove all thumbnails."""
        self._list.clear()

    # ── internal slots ────────────────────────────────────────

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.page_selected.emit(row)

    def _on_rows_moved(self, _src, _start, _end, _dst, _dest_row) -> None:
        """Collect the new order from item UserRole data and emit the signal."""
        new_order: List[int] = []
        for i in range(self._list.count()):
            orig = self._list.item(i).data(Qt.ItemDataRole.UserRole)
            new_order.append(orig)
        self.pages_reordered.emit(new_order)


# ──────────────────────────────────────────────────────────────
#  SearchPanel
# ──────────────────────────────────────────────────────────────

class SearchPanel(QWidget):
    """Sidebar panel for full-text search with prev/next navigation."""

    search_requested: pyqtSignal = pyqtSignal(str)
    """Emitted with the query string when the user triggers a search."""

    navigate_result: pyqtSignal = pyqtSignal(int, object)
    """Emitted with ``(page_index, fitz.Rect)`` when navigating results."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._results: List[Tuple[int, fitz.Rect]] = []
        self._current = -1
        self._setup_ui()

    # ── setup ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Build the search form UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Search")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search text…")
        self._input.returnPressed.connect(self._do_search)
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        self._btn_search = QPushButton("Find")
        self._btn_search.clicked.connect(self._do_search)
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedWidth(32)
        self._btn_prev.clicked.connect(self._prev)
        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedWidth(32)
        self._btn_next.clicked.connect(self._next)
        btn_row.addWidget(self._btn_search)
        btn_row.addWidget(self._btn_prev)
        btn_row.addWidget(self._btn_next)
        layout.addLayout(btn_row)

        self._status = QLabel("No results")
        self._status.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(self._status)

        self._result_list = QListWidget()
        self._result_list.itemDoubleClicked.connect(self._on_item_dbl)
        layout.addWidget(self._result_list)

    # ── public API ────────────────────────────────────────────

    def set_results(self, results: Dict[int, List[fitz.Rect]]) -> None:
        """Populate the results list from a search-results dict."""
        self._results.clear()
        self._result_list.clear()
        for page_idx, rects in sorted(results.items()):
            for rect in rects:
                self._results.append((page_idx, rect))
                item = QListWidgetItem(f"Page {page_idx + 1}")
                item.setData(Qt.ItemDataRole.UserRole, len(self._results) - 1)
                self._result_list.addItem(item)
        count = len(self._results)
        self._status.setText(f"{count} result{'s' if count != 1 else ''}")
        self._current = 0 if count > 0 else -1
        if self._current >= 0:
            self._emit_current()

    def clear(self) -> None:
        """Reset search state."""
        self._results.clear()
        self._result_list.clear()
        self._current = -1
        self._status.setText("No results")
        self._input.clear()

    def focus_search(self) -> None:
        """Focus and select-all in the search input."""
        self._input.setFocus()
        self._input.selectAll()

    # ── internal ──────────────────────────────────────────────

    def _do_search(self) -> None:
        text = self._input.text().strip()
        if text:
            self.search_requested.emit(text)

    def _prev(self) -> None:
        if not self._results:
            return
        self._current = (self._current - 1) % len(self._results)
        self._emit_current()

    def _next(self) -> None:
        if not self._results:
            return
        self._current = (self._current + 1) % len(self._results)
        self._emit_current()

    def _emit_current(self) -> None:
        if 0 <= self._current < len(self._results):
            page_idx, rect = self._results[self._current]
            self.navigate_result.emit(page_idx, rect)
            self._status.setText(
                f"Result {self._current + 1} of {len(self._results)}"
            )

    def _on_item_dbl(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None:
            self._current = idx
            self._emit_current()


# ──────────────────────────────────────────────────────────────
#  BookmarkPanel
# ──────────────────────────────────────────────────────────────

class BookmarkPanel(QWidget):
    """Sidebar panel for adding, listing, and navigating bookmarks."""

    navigate_bookmark: pyqtSignal = pyqtSignal(int)
    """Emitted with the page index when the user double-clicks a bookmark."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bookmarks: List[Dict[str, Any]] = []
        self._get_current_page = lambda: 0
        self._setup_ui()

    # ── setup ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Build the bookmarks UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Bookmarks")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_dbl)
        layout.addWidget(self._list)

    # ── public API ────────────────────────────────────────────

    def set_current_page_fn(self, fn) -> None:
        """Register a callable that returns the current page index."""
        self._get_current_page = fn

    def load_bookmarks(self, bookmarks: List[Dict[str, Any]]) -> None:
        """Load a pre-built list of bookmark dicts into the panel."""
        self._list.clear()
        self._bookmarks = list(bookmarks)
        for bm in self._bookmarks:
            self._list.addItem(f"{bm['name']} — p.{bm['page'] + 1}")

    def get_bookmarks(self) -> List[Dict[str, Any]]:
        """Return a copy of the current bookmarks list."""
        return list(self._bookmarks)

    def clear(self) -> None:
        """Remove all bookmarks."""
        self._list.clear()
        self._bookmarks.clear()

    # ── internal ──────────────────────────────────────────────

    def _add(self) -> None:
        page = self._get_current_page()
        name, ok = QInputDialog.getText(
            self, "Add Bookmark", "Bookmark name:", text=f"Page {page + 1}"
        )
        if ok and name:
            self._bookmarks.append({"name": name, "page": page})
            self._list.addItem(f"{name} — p.{page + 1}")

    def _delete(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self._bookmarks.pop(row)

    def _on_dbl(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if 0 <= row < len(self._bookmarks):
            self.navigate_bookmark.emit(self._bookmarks[row]["page"])


# ──────────────────────────────────────────────────────────────
#  AnnotationToolbar
# ──────────────────────────────────────────────────────────────

class AnnotationToolbar(QToolBar):
    """Toolbar that lets the user pick an annotation tool and colour.

    Each tool corresponds to a checkable :class:`QAction`.  Only one tool
    can be active at a time.
    """

    tool_selected: pyqtSignal = pyqtSignal(str)
    """Emitted with the tool name whenever the active tool changes."""

    TOOLS: List[Tuple[str, str, str]] = [
        ("pointer",    "Pointer",    "Normal selection / scroll"),
        ("highlight",  "Highlight",  "Highlight a region in yellow"),
        ("underline",  "Underline",  "Underline a text region"),
        ("strikeout",  "Strikeout",  "Strike through a text region"),
        ("freehand",   "Freehand",   "Draw freehand ink lines"),
        ("text",       "Text Note",  "Add a text-note annotation"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Annotations", parent)
        self._current_tool = "pointer"
        self._annotation_color = QColor("#FFFF00")
        self._actions: Dict[str, QAction] = {}
        self._setup_tools()

    # ── setup ─────────────────────────────────────────────────

    def _setup_tools(self) -> None:
        """Populate the toolbar with tool actions and a colour picker."""
        self.setMovable(False)
        self.addWidget(QLabel("  Annotation: "))

        for name, label, tip in self.TOOLS:
            action = QAction(label, self)
            action.setToolTip(tip)
            action.setCheckable(True)
            action.setData(name)
            action.triggered.connect(
                lambda _checked, n=name: self._select(n)
            )
            self.addAction(action)
            self._actions[name] = action

        self._actions["pointer"].setChecked(True)
        self.addSeparator()

        self.addWidget(QLabel("  Colour: "))
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(24, 24)
        self._color_btn.setToolTip("Pick annotation colour")
        self._color_btn.clicked.connect(self._pick_color)
        self._refresh_color_btn()
        self.addWidget(self._color_btn)

    # ── public API ────────────────────────────────────────────

    @property
    def current_tool(self) -> str:
        """Name of the currently selected annotation tool."""
        return self._current_tool

    @property
    def annotation_color(self) -> QColor:
        """Currently chosen annotation colour."""
        return self._annotation_color

    # ── internal ──────────────────────────────────────────────

    def _select(self, name: str) -> None:
        self._current_tool = name
        for n, act in self._actions.items():
            act.setChecked(n == name)
        self.tool_selected.emit(name)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._annotation_color, self)
        if color.isValid():
            self._annotation_color = color
            self._refresh_color_btn()

    def _refresh_color_btn(self) -> None:
        self._color_btn.setStyleSheet(
            f"background-color: {self._annotation_color.name()};"
            "border: 1px solid #888; border-radius: 2px;"
        )


# ──────────────────────────────────────────────────────────────
#  PDFCanvas  (the actual painting + mouse-input widget)
# ──────────────────────────────────────────────────────────────

class PDFCanvas(QWidget):
    """Custom QWidget that paints PDF pages and handles annotation drawing.

    This widget is placed inside a :class:`PDFViewer` (QScrollArea).
    It supports three page display modes:

    * ``'single'``     – one page centred in the viewport
    * ``'dual'``       – two pages side by side
    * ``'continuous'`` – all pages stacked vertically
    """

    page_changed: pyqtSignal = pyqtSignal(int)
    """Emitted with the new page index after explicit page navigation."""

    annotation_added: pyqtSignal = pyqtSignal(int, str, object)
    """Emitted as ``(page_index, tool_name, data)`` when the user finishes
    drawing an annotation.  *data* is a :class:`fitz.Rect` for rect-based
    tools or a list of ``(x, y)`` tuples for ``'freehand'``."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._doc:              Optional[PDFDocument]        = None
        self._zoom:             float                         = 1.0
        self._current_page:     int                           = 0
        self._page_mode:        str                           = "single"
        self._tool:             str                           = "pointer"
        self._ann_color:        QColor                        = QColor("#FFFF00")
        self._search_results:   Dict[int, List[fitz.Rect]]    = {}

        # annotation-drawing state
        self._drawing:          bool                          = False
        self._freehand_pts:     List[QPoint]                  = []
        self._rect_start:       Optional[QPoint]              = None
        self._rect_end:         Optional[QPoint]              = None

        # computed during paint – maps canvas rects to page indices
        self._page_rects:       List[Tuple[QRect, int]]       = []

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── public setters ────────────────────────────────────────

    def set_document(self, doc: PDFDocument) -> None:
        """Attach a :class:`PDFDocument` and reset the view."""
        self._doc = doc
        self._current_page = 0
        self._recompute_size()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        """Set the zoom factor and trigger a re-paint."""
        self._zoom = max(0.1, min(zoom, 8.0))
        self._recompute_size()
        self.update()

    def set_page_mode(self, mode: str) -> None:
        """Switch between ``'single'``, ``'dual'``, and ``'continuous'``."""
        self._page_mode = mode
        self._recompute_size()
        self.update()

    def goto_page(self, index: int) -> None:
        """Navigate to page *index* and emit :attr:`page_changed`."""
        if self._doc and 0 <= index < self._doc.page_count():
            self._current_page = index
            self._recompute_size()
            self.update()
            self.page_changed.emit(index)

    def set_search_results(self, results: Dict[int, List[fitz.Rect]]) -> None:
        """Replace the current search highlight set and repaint."""
        self._search_results = results
        self.update()

    def set_tool(self, tool: str) -> None:
        """Set the active annotation tool, updating the cursor."""
        self._tool = tool
        cursor = (
            Qt.CursorShape.ArrowCursor
            if tool == "pointer"
            else Qt.CursorShape.CrossCursor
        )
        self.setCursor(cursor)

    def set_annotation_color(self, color: QColor) -> None:
        """Update the colour used for new annotations."""
        self._ann_color = color

    def current_page(self) -> int:
        """Return the index of the currently visible / active page."""
        return self._current_page

    def zoom(self) -> float:
        """Return the current zoom factor."""
        return self._zoom

    # ── size management ───────────────────────────────────────

    def _recompute_size(self) -> None:
        """Resize the canvas to fit all visible pages at the current zoom."""
        if not self._doc:
            return
        if self._page_mode == "continuous":
            max_w = 0
            total_h = 8
            for i in range(self._doc.page_count()):
                w, h = self._doc.page_size(i)
                max_w = max(max_w, int(w * self._zoom))
                total_h += int(h * self._zoom) + 8
            self.setMinimumSize(max_w, total_h)
            self.resize(max_w + 4, total_h)
        elif self._page_mode == "dual":
            w0, h0 = self._doc.page_size(self._current_page)
            pw0, ph0 = int(w0 * self._zoom), int(h0 * self._zoom)
            total_w = pw0 + 8
            if self._current_page + 1 < self._doc.page_count():
                w1, _ = self._doc.page_size(self._current_page + 1)
                total_w += int(w1 * self._zoom) + 8
            self.setMinimumSize(total_w, ph0 + 16)
            self.resize(total_w, ph0 + 16)
        else:
            w, h = self._doc.page_size(self._current_page)
            pw, ph = int(w * self._zoom), int(h * self._zoom)
            self.setMinimumSize(pw + 4, ph + 4)
            self.resize(pw + 4, ph + 4)

    # ── painting ──────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint all visible pages, search highlights, and in-progress annotations."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#3c3c3c"))

        if not self._doc:
            painter.setPen(QColor("#888"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No document loaded"
            )
            return

        self._page_rects = []

        if self._page_mode == "continuous":
            self._paint_continuous(painter)
        elif self._page_mode == "dual":
            self._paint_dual(painter)
        else:
            self._paint_single(painter)

        if self._drawing:
            self._paint_in_progress(painter)

    def _paint_single(self, painter: QPainter) -> None:
        """Paint the current page centred in the widget."""
        if not self._doc or self._doc.page_count() == 0:
            return
        pix = self._doc.render_page(self._current_page, self._zoom)
        x = max(2, (self.width()  - pix.width())  // 2)
        y = max(2, (self.height() - pix.height()) // 2)
        painter.drawPixmap(x, y, pix)
        page_rect = QRect(x, y, pix.width(), pix.height())
        self._page_rects = [(page_rect, self._current_page)]
        self._paint_highlights(painter, self._current_page, x, y)

    def _paint_dual(self, painter: QPainter) -> None:
        """Paint the current page and the next page side by side."""
        if not self._doc:
            return
        pages = [self._current_page]
        if self._current_page + 1 < self._doc.page_count():
            pages.append(self._current_page + 1)
        x_off = 4
        self._page_rects = []
        for pg in pages:
            pix = self._doc.render_page(pg, self._zoom)
            y = max(4, (self.height() - pix.height()) // 2)
            painter.drawPixmap(x_off, y, pix)
            self._page_rects.append((QRect(x_off, y, pix.width(), pix.height()), pg))
            self._paint_highlights(painter, pg, x_off, y)
            x_off += pix.width() + 8

    def _paint_continuous(self, painter: QPainter) -> None:
        """Paint every page stacked vertically."""
        if not self._doc:
            return
        y = 8
        self._page_rects = []
        for i in range(self._doc.page_count()):
            pix = self._doc.render_page(i, self._zoom)
            x = max(2, (self.width() - pix.width()) // 2)
            painter.drawPixmap(x, y, pix)
            self._page_rects.append((QRect(x, y, pix.width(), pix.height()), i))
            self._paint_highlights(painter, i, x, y)
            y += pix.height() + 8

    def _paint_highlights(
        self, painter: QPainter, page_idx: int, ox: int, oy: int
    ) -> None:
        """Draw semi-transparent yellow highlights for search matches."""
        if page_idx not in self._search_results:
            return
        painter.save()
        for rect in self._search_results[page_idx]:
            qr = Utils.fitz_rect_to_qrect(rect, self._zoom)
            qr.translate(ox, oy)
            painter.fillRect(qr, QColor(255, 220, 0, 110))
            painter.setPen(QPen(QColor(255, 165, 0), 1))
            painter.drawRect(qr)
        painter.restore()

    def _paint_in_progress(self, painter: QPainter) -> None:
        """Draw the annotation currently being drawn by the user."""
        painter.save()
        if self._tool == "freehand" and len(self._freehand_pts) > 1:
            painter.setPen(QPen(self._ann_color, 2, Qt.PenStyle.SolidLine))
            for i in range(1, len(self._freehand_pts)):
                painter.drawLine(self._freehand_pts[i - 1], self._freehand_pts[i])
        elif self._rect_start and self._rect_end:
            r = QRect(self._rect_start, self._rect_end).normalized()
            fill = QColor(self._ann_color)
            fill.setAlpha(70)
            painter.fillRect(r, fill)
            painter.setPen(QPen(self._ann_color, 2))
            painter.drawRect(r)
        painter.restore()

    # ── coordinate helpers ────────────────────────────────────

    def _page_at(self, pos: QPoint) -> Tuple[int, int, int]:
        """Return ``(page_index, local_x, local_y)`` for canvas position *pos*.

        Returns ``(-1, 0, 0)`` when *pos* is not inside any page rect.
        """
        for page_rect, pg in self._page_rects:
            if page_rect.contains(pos):
                return pg, pos.x() - page_rect.x(), pos.y() - page_rect.y()
        return -1, 0, 0

    def _page_rect_for(self, page_idx: int) -> Optional[QRect]:
        """Return the canvas QRect that hosts *page_idx*, or ``None``."""
        for page_rect, pg in self._page_rects:
            if pg == page_idx:
                return page_rect
        return None

    # ── mouse events ──────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Begin drawing an annotation when a non-pointer tool is active."""
        if event.button() == Qt.MouseButton.LeftButton and self._tool != "pointer":
            self._drawing = True
            pos = event.pos()
            if self._tool == "freehand":
                self._freehand_pts = [pos]
            else:
                self._rect_start = pos
                self._rect_end = pos
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Extend the in-progress annotation as the mouse moves."""
        if self._drawing:
            pos = event.pos()
            if self._tool == "freehand":
                self._freehand_pts.append(pos)
            else:
                self._rect_end = pos
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finalise the annotation and emit :attr:`annotation_added`."""
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return
        self._drawing = False
        pos = event.pos()

        if self._tool == "freehand":
            if len(self._freehand_pts) < 2:
                self._freehand_pts = []
                self.update()
                return
            # determine page from first point
            page_idx, _, _ = self._page_at(self._freehand_pts[0])
            if page_idx >= 0:
                pr = self._page_rect_for(page_idx)
                if pr:
                    pts = [
                        (
                            (p.x() - pr.x()) / self._zoom,
                            (p.y() - pr.y()) / self._zoom,
                        )
                        for p in self._freehand_pts
                    ]
                    self.annotation_added.emit(page_idx, "freehand", pts)
            self._freehand_pts = []
        else:
            if self._rect_start and self._rect_end:
                page_idx, _, _ = self._page_at(self._rect_start)
                if page_idx >= 0:
                    pr = self._page_rect_for(page_idx)
                    if pr:
                        r = QRect(self._rect_start, self._rect_end).normalized()
                        fitz_rect = fitz.Rect(
                            (r.x()             - pr.x()) / self._zoom,
                            (r.y()             - pr.y()) / self._zoom,
                            (r.x() + r.width() - pr.x()) / self._zoom,
                            (r.y() + r.height() - pr.y()) / self._zoom,
                        )
                        self.annotation_added.emit(page_idx, self._tool, fitz_rect)
            self._rect_start = None
            self._rect_end   = None

        self.update()


# ──────────────────────────────────────────────────────────────
#  PDFViewer
# ──────────────────────────────────────────────────────────────

class PDFViewer(QScrollArea):
    """QScrollArea that hosts a :class:`PDFCanvas`.

    All zoom / navigation / mode changes are forwarded to the canvas.
    Ctrl+Scroll is intercepted to zoom in/out.
    """

    page_changed:    pyqtSignal = pyqtSignal(int)
    annotation_added: pyqtSignal = pyqtSignal(int, str, object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._canvas = PDFCanvas()
        self._canvas.page_changed.connect(self.page_changed)
        self._canvas.annotation_added.connect(self.annotation_added)
        self.setWidget(self._canvas)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # ── public delegates ──────────────────────────────────────

    def load_document(self, doc: PDFDocument) -> None:
        """Load *doc* into the canvas."""
        self._canvas.set_document(doc)

    def set_zoom(self, zoom: float) -> None:
        """Set the zoom factor."""
        self._canvas.set_zoom(zoom)

    def zoom(self) -> float:
        """Return the current zoom factor."""
        return self._canvas.zoom()

    def goto_page(self, index: int) -> None:
        """Navigate to page *index*, scrolling in continuous mode."""
        self._canvas.goto_page(index)
        if self._canvas._page_mode == "continuous":
            pr = self._canvas._page_rect_for(index)
            if pr:
                self.verticalScrollBar().setValue(max(0, pr.y() - 8))

    def current_page(self) -> int:
        """Return the current page index."""
        return self._canvas.current_page()

    def set_page_mode(self, mode: str) -> None:
        """Set the page display mode."""
        self._canvas.set_page_mode(mode)

    def set_search_results(self, results: Dict) -> None:
        """Forward search-result highlights to the canvas."""
        self._canvas.set_search_results(results)

    def set_tool(self, tool: str) -> None:
        """Set the annotation tool."""
        self._canvas.set_tool(tool)

    def set_annotation_color(self, color: QColor) -> None:
        """Set the annotation colour."""
        self._canvas.set_annotation_color(color)

    # ── wheel zoom ────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom on Ctrl+Scroll; otherwise scroll normally."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
            self.set_zoom(self._canvas.zoom() * factor)
            event.accept()
        else:
            super().wheelEvent(event)


# ──────────────────────────────────────────────────────────────
#  Editor
# ──────────────────────────────────────────────────────────────

class Editor:
    """Static page-editing operations backed by pikepdf.

    All methods open the file, mutate the page list, and save back to the
    same path using ``allow_overwriting_input=True``.
    """

    @staticmethod
    def add_blank_page(path: str, after_index: int = -1) -> None:
        """Insert an A4 blank page after *after_index* (append if ``-1``)."""
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            blank = pikepdf.Page(
                pikepdf.Dictionary(
                    Type=pikepdf.Name("/Page"),
                    MediaBox=pikepdf.Array([0, 0, 595, 842]),
                )
            )
            pos = len(pdf.pages) if after_index < 0 else after_index + 1
            pdf.pages.insert(pos, blank)
            pdf.save(path)

    @staticmethod
    def delete_page(path: str, index: int) -> None:
        """Delete the page at *index*."""
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            if 0 <= index < len(pdf.pages):
                del pdf.pages[index]
                pdf.save(path)

    @staticmethod
    def rotate_page(path: str, index: int, degrees: int = 90) -> None:
        """Rotate page *index* by *degrees* (cumulative, mod 360)."""
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            if 0 <= index < len(pdf.pages):
                page = pdf.pages[index]
                current = int(page.get("/Rotate", 0))
                page["/Rotate"] = pikepdf.Integer((current + degrees) % 360)
                pdf.save(path)

    @staticmethod
    def reorder_pages(path: str, new_order: List[int]) -> None:
        """Save *path* with pages reordered according to *new_order*.

        *new_order* is a list of original page indices in the desired output
        order.  A temporary file is used to avoid pikepdf overwrite conflicts.
        """
        tmp = path + ".reorder_tmp"
        with pikepdf.open(path) as src:
            out = pikepdf.Pdf.new()
            for i in new_order:
                out.pages.append(src.pages[i])
            out.save(tmp)
        os.replace(tmp, path)

    @staticmethod
    def move_page(path: str, from_index: int, to_index: int) -> None:
        """Move a single page from *from_index* to *to_index*."""
        with pikepdf.open(path) as src:
            n = len(src.pages)
            if not (0 <= from_index < n and 0 <= to_index < n):
                return
            order = list(range(n))
            order.insert(to_index, order.pop(from_index))
        Editor.reorder_pages(path, order)


# ──────────────────────────────────────────────────────────────
#  Annotator
# ──────────────────────────────────────────────────────────────

class Annotator:
    """Add annotations to a live :class:`fitz.Document` in memory.

    All methods accept a :class:`QColor` and convert it to the 0-1
    float tuple that fitz expects.
    """

    @staticmethod
    def _to_fitz_color(color: QColor) -> Tuple[float, float, float]:
        """Convert a :class:`QColor` to a fitz ``(r, g, b)`` tuple."""
        return color.redF(), color.greenF(), color.blueF()

    @staticmethod
    def add_highlight(
        doc: fitz.Document, page_idx: int, rect: fitz.Rect, color: QColor
    ) -> None:
        """Add a highlight annotation to *rect* on *page_idx*."""
        page = doc[page_idx]
        annot = page.add_highlight_annot(rect)
        annot.set_colors(stroke=Annotator._to_fitz_color(color))
        annot.update()

    @staticmethod
    def add_underline(
        doc: fitz.Document, page_idx: int, rect: fitz.Rect, color: QColor
    ) -> None:
        """Add an underline annotation to *rect* on *page_idx*."""
        page = doc[page_idx]
        annot = page.add_underline_annot(rect)
        annot.set_colors(stroke=Annotator._to_fitz_color(color))
        annot.update()

    @staticmethod
    def add_strikeout(
        doc: fitz.Document, page_idx: int, rect: fitz.Rect, color: QColor
    ) -> None:
        """Add a strikeout annotation to *rect* on *page_idx*."""
        page = doc[page_idx]
        annot = page.add_strikeout_annot(rect)
        annot.set_colors(stroke=Annotator._to_fitz_color(color))
        annot.update()

    @staticmethod
    def add_freehand(
        doc: fitz.Document,
        page_idx: int,
        points: List[Tuple[float, float]],
        color: QColor,
    ) -> None:
        """Add an ink (freehand) annotation from a list of ``(x, y)`` points."""
        page = doc[page_idx]
        # PyMuPDF ≥ 1.23 requires plain float pairs, not fitz.Point objects.
        fitz_pts = [[(float(x), float(y)) for x, y in points]]
        annot = page.add_ink_annot(fitz_pts)
        annot.set_colors(stroke=Annotator._to_fitz_color(color))
        annot.set_border(width=2)
        annot.update()

    @staticmethod
    def add_text_note(
        doc: fitz.Document,
        page_idx: int,
        rect: fitz.Rect,
        text: str,
        color: QColor,
    ) -> None:
        """Add a sticky-note text annotation at the top-left of *rect*."""
        page = doc[page_idx]
        annot = page.add_text_annot(rect.tl, text)
        annot.set_colors(stroke=Annotator._to_fitz_color(color))
        annot.update()

    @staticmethod
    def apply_annotation(
        doc: fitz.Document,
        page_idx: int,
        tool: str,
        data: Any,
        color: QColor,
        parent_widget: Optional[QWidget] = None,
    ) -> bool:
        """Dispatch the annotation to the correct ``add_*`` method.

        Returns ``True`` if an annotation was successfully added.
        """
        if tool == "highlight":
            Annotator.add_highlight(doc, page_idx, data, color)
        elif tool == "underline":
            Annotator.add_underline(doc, page_idx, data, color)
        elif tool == "strikeout":
            Annotator.add_strikeout(doc, page_idx, data, color)
        elif tool == "freehand":
            Annotator.add_freehand(doc, page_idx, data, color)
        elif tool == "text":
            text, ok = QInputDialog.getText(
                parent_widget, "Text Note", "Enter note text:"
            )
            if ok and text:
                Annotator.add_text_note(doc, page_idx, data, text, color)
            else:
                return False
        else:
            return False
        return True


# ──────────────────────────────────────────────────────────────
#  Manager
# ──────────────────────────────────────────────────────────────

class Manager:
    """High-level, stateless file-operation utilities."""

    @staticmethod
    def merge_pdfs(paths: List[str], output_path: str) -> None:
        """Merge all PDFs in *paths* into *output_path*."""
        merger = pikepdf.Pdf.new()
        for path in paths:
            with pikepdf.open(path) as src:
                merger.pages.extend(src.pages)
        merger.save(output_path)

    @staticmethod
    def split_pdf(path: str, output_dir: str) -> List[str]:
        """Split *path* into one file per page, saved in *output_dir*.

        Returns a list of the created file paths.
        """
        Utils.ensure_dir(output_dir)
        out_paths: List[str] = []
        with pikepdf.open(path) as pdf:
            stem = Path(path).stem
            for i, page in enumerate(pdf.pages):
                single = pikepdf.Pdf.new()
                single.pages.append(page)
                out = os.path.join(output_dir, f"{stem}_page_{i + 1:04d}.pdf")
                single.save(out)
                out_paths.append(out)
        return out_paths

    @staticmethod
    def extract_text(path: str, output_path: str) -> None:
        """Extract text from all pages of *path* and write to *output_path*."""
        doc = fitz.open(path)
        with open(output_path, "w", encoding="utf-8") as fh:
            for i, page in enumerate(doc):
                fh.write(f"--- Page {i + 1} ---\n")
                fh.write(page.get_text())
                fh.write("\n\n")
        doc.close()

    @staticmethod
    def extract_images(path: str, output_dir: str) -> int:
        """Extract embedded images from *path* to *output_dir*.

        Returns the number of images saved.
        """
        Utils.ensure_dir(output_dir)
        doc = fitz.open(path)
        count = 0
        for page_num, page in enumerate(doc):
            for img_idx, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                ext  = base_image["ext"]
                data = base_image["image"]
                out  = os.path.join(
                    output_dir, f"page{page_num + 1}_img{img_idx + 1}.{ext}"
                )
                with open(out, "wb") as fh:
                    fh.write(data)
                count += 1
        doc.close()
        return count

    @staticmethod
    def export_page_as_image(
        doc: PDFDocument, page_idx: int, path: str, zoom: float = 2.0
    ) -> None:
        """Render *page_idx* at *zoom* and save to *path* (PNG or JPEG)."""
        pix = doc.render_page(page_idx, zoom)
        pix.save(path)

    @staticmethod
    def export_all_pages(
        doc: PDFDocument, output_dir: str, zoom: float = 2.0, fmt: str = "png"
    ) -> int:
        """Export every page as an image file in *output_dir*.

        Returns the number of pages exported.
        """
        Utils.ensure_dir(output_dir)
        for i in range(doc.page_count()):
            path = os.path.join(output_dir, f"page_{i + 1:04d}.{fmt}")
            Manager.export_page_as_image(doc, i, path, zoom)
        return doc.page_count()


# ──────────────────────────────────────────────────────────────
#  PDFTab
# ──────────────────────────────────────────────────────────────

class PDFTab(QWidget):
    """Widget representing one open PDF document.

    Assembles a :class:`PDFViewer`, sidebar panels
    (:class:`ThumbnailPanel`, :class:`SearchPanel`, :class:`BookmarkPanel`),
    and an :class:`AnnotationToolbar`.
    """

    status_message: pyqtSignal = pyqtSignal(str)
    """Emitted whenever a status-bar message should be shown."""

    title_changed: pyqtSignal = pyqtSignal(str)
    """Emitted with the new tab title when the document path changes."""

    def __init__(
        self,
        path: str,
        settings: Settings,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._path     = path
        self._settings = settings
        self._doc: Optional[PDFDocument] = None
        self._setup_ui()
        self._load_document(path)

    # ── setup ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Assemble viewer, sidebar, and annotation toolbar."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # annotation toolbar along the top
        self._ann_toolbar = AnnotationToolbar()
        self._ann_toolbar.tool_selected.connect(self._on_tool_selected)
        root.addWidget(self._ann_toolbar)

        # main area: sidebar tabs | viewer
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── sidebar ────────────────────────────────
        self._panel_tabs = QTabWidget()
        self._panel_tabs.setMaximumWidth(235)
        self._panel_tabs.setMinimumWidth(50)

        self._thumbnails = ThumbnailPanel()
        self._thumbnails.page_selected.connect(self._on_thumb_selected)
        self._thumbnails.pages_reordered.connect(self._on_pages_reordered)
        self._panel_tabs.addTab(self._thumbnails, "Pages")

        self._search_panel = SearchPanel()
        self._search_panel.search_requested.connect(self._on_search)
        self._search_panel.navigate_result.connect(self._on_navigate_result)
        self._panel_tabs.addTab(self._search_panel, "Search")

        self._bookmarks = BookmarkPanel()
        self._bookmarks.set_current_page_fn(lambda: self._viewer.current_page())
        self._bookmarks.navigate_bookmark.connect(self._on_bookmark_navigate)
        self._panel_tabs.addTab(self._bookmarks, "Bookmarks")

        splitter.addWidget(self._panel_tabs)

        # ── viewer ─────────────────────────────────
        self._viewer = PDFViewer()
        self._viewer.page_changed.connect(self._on_page_changed)
        self._viewer.annotation_added.connect(self._on_annotation_added)
        splitter.addWidget(self._viewer)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    # ── document loading ──────────────────────────────────────

    def _load_document(self, path: str) -> None:
        """Open *path* and populate the viewer and thumbnail panel."""
        try:
            self._doc = PDFDocument(path)
            self._viewer.load_document(self._doc)
            self._viewer.set_zoom(self._settings.zoom)
            self._viewer.set_page_mode(self._settings.page_mode)
            self._thumbnails.load_document(self._doc)
            self.title_changed.emit(Path(path).name)
            self.status_message.emit(
                f"Opened: {Path(path).name}  ·  {self._doc.page_count()} pages"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Open Error", f"Could not open PDF:\n{exc}")

    def _reload_document(self) -> None:
        """Re-open the document from disk after a structural edit."""
        current = self._viewer.current_page()
        if self._doc:
            self._doc.close()
        self._doc = PDFDocument(self._path)
        self._viewer.load_document(self._doc)
        self._viewer.set_zoom(self._settings.zoom)
        self._thumbnails.load_document(self._doc)
        safe_page = min(current, self._doc.page_count() - 1)
        self._viewer.goto_page(safe_page)

    # ── sidebar slots ─────────────────────────────────────────

    def _on_thumb_selected(self, index: int) -> None:
        self._viewer.goto_page(index)

    def _on_pages_reordered(self, new_order: List[int]) -> None:
        """Apply drag-dropped page reorder to the actual PDF file."""
        try:
            Editor.reorder_pages(self._path, new_order)
            self._reload_document()
            self.status_message.emit("Pages reordered")
        except Exception as exc:
            QMessageBox.critical(self, "Reorder Error", str(exc))

    def _on_search(self, query: str) -> None:
        if self._doc:
            results = self._doc.search_all(query)
            self._viewer.set_search_results(results)
            self._search_panel.set_results(results)

    def _on_navigate_result(self, page_idx: int, _rect: Any) -> None:
        self._viewer.goto_page(page_idx)
        self._thumbnails.set_current_page(page_idx)

    def _on_bookmark_navigate(self, page_idx: int) -> None:
        self._viewer.goto_page(page_idx)
        self._thumbnails.set_current_page(page_idx)

    # ── viewer slots ──────────────────────────────────────────

    def _on_page_changed(self, index: int) -> None:
        self._thumbnails.set_current_page(index)
        if self._doc:
            self.status_message.emit(
                f"Page {index + 1} of {self._doc.page_count()}"
                f"  ·  Zoom: {int(self._viewer.zoom() * 100)}%"
            )

    def _on_tool_selected(self, tool: str) -> None:
        self._viewer.set_tool(tool)
        self._viewer.set_annotation_color(self._ann_toolbar.annotation_color)

    def _on_annotation_added(self, page_idx: int, tool: str, data: Any) -> None:
        """Commit an in-progress annotation to the fitz document."""
        if not self._doc:
            return
        color = self._ann_toolbar.annotation_color
        try:
            added = Annotator.apply_annotation(
                self._doc.fitz_doc, page_idx, tool, data, color, parent_widget=self
            )
            if added:
                self._doc.invalidate_cache(page_idx)
                self._doc._modified = True
                self._viewer._canvas.update()
                self._thumbnails.refresh_page(self._doc, page_idx)
        except Exception as exc:
            QMessageBox.warning(self, "Annotation Error", str(exc))

    # ── public tab operations ─────────────────────────────────

    def zoom_in(self) -> None:
        """Increase zoom by ~20 %."""
        self._viewer.set_zoom(self._viewer.zoom() * 1.2)
        self._sync_zoom()

    def zoom_out(self) -> None:
        """Decrease zoom by ~17 %."""
        self._viewer.set_zoom(self._viewer.zoom() / 1.2)
        self._sync_zoom()

    def zoom_fit(self) -> None:
        """Fit the current page width to the available viewport width."""
        if self._doc:
            w, _ = self._doc.page_size(self._viewer.current_page())
            avail = self._viewer.viewport().width() - 20
            self._viewer.set_zoom(avail / w if w > 0 else 1.0)
            self._sync_zoom()

    def _sync_zoom(self) -> None:
        z = self._viewer.zoom()
        self._settings.zoom = z
        if self._doc:
            pg = self._viewer.current_page()
            self.status_message.emit(
                f"Page {pg + 1} of {self._doc.page_count()}"
                f"  ·  Zoom: {int(z * 100)}%"
            )

    def set_page_mode(self, mode: str) -> None:
        """Switch page display mode."""
        self._viewer.set_page_mode(mode)

    def goto_page(self, index: int) -> None:
        """Navigate to page *index*."""
        self._viewer.goto_page(index)
        self._thumbnails.set_current_page(index)

    def save(self) -> None:
        """Save the document in place."""
        if not self._doc:
            return
        try:
            self._doc.save()
            self.status_message.emit(f"Saved: {Path(self._path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def save_as(self, new_path: str) -> None:
        """Save the document to *new_path*."""
        if not self._doc:
            return
        try:
            self._doc.save(new_path)
            self._path = new_path
            self.title_changed.emit(Path(new_path).name)
            self.status_message.emit(f"Saved as: {Path(new_path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Save As Error", str(exc))

    def add_blank_page(self) -> None:
        """Insert a blank A4 page after the current page."""
        if not self._doc:
            return
        try:
            Editor.add_blank_page(self._path, after_index=self._viewer.current_page())
            self._reload_document()
            self.status_message.emit("Blank page added")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def delete_current_page(self) -> None:
        """Delete the currently displayed page (prompts for confirmation)."""
        if not self._doc or self._doc.page_count() <= 1:
            return
        cur = self._viewer.current_page()
        reply = QMessageBox.question(
            self,
            "Delete Page",
            f"Permanently delete page {cur + 1}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                Editor.delete_page(self._path, cur)
                self._reload_document()
                self.status_message.emit(f"Page {cur + 1} deleted")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def rotate_current_page(self, degrees: int = 90) -> None:
        """Rotate the current page by *degrees*."""
        if not self._doc:
            return
        cur = self._viewer.current_page()
        try:
            Editor.rotate_page(self._path, cur, degrees)
            self._reload_document()
            self.status_message.emit(f"Page {cur + 1} rotated {degrees}°")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def print_document(self) -> None:
        """Send the document to the system printer."""
        if not self._doc:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog  = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        painter = QPainter(printer)
        for i in range(self._doc.page_count()):
            if i > 0:
                printer.newPage()
            pix  = self._doc.render_page(i, zoom=2.0)
            rect = painter.viewport()
            scaled = pix.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (rect.width()  - scaled.width())  // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        painter.end()

    def focus_search(self) -> None:
        """Switch to the Search panel and focus the input field."""
        self._panel_tabs.setCurrentWidget(self._search_panel)
        self._search_panel.focus_search()

    # ── properties ────────────────────────────────────────────

    @property
    def path(self) -> str:
        """Absolute path to the currently open PDF file."""
        return self._path

    @property
    def doc(self) -> Optional[PDFDocument]:
        """The underlying :class:`PDFDocument`, or ``None`` if not loaded."""
        return self._doc

    @property
    def is_modified(self) -> bool:
        """``True`` when the document has unsaved annotation changes."""
        return self._doc.is_modified if self._doc else False


# ──────────────────────────────────────────────────────────────
#  MainWindow
# ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Main application window.

    Manages a :class:`QTabWidget` of :class:`PDFTab` instances together
    with the menu bar, main toolbar, status bar, and drag-and-drop support.
    """

    APP_NAME    = "PDREADF"
    APP_VERSION = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._settings = Settings()
        self._setup_window()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_tabs()
        self._setup_statusbar()
        self._apply_theme(self._settings.theme)
        self._restore_geometry()

    # ── initial setup ─────────────────────────────────────────

    def _setup_window(self) -> None:
        """Configure window title, minimum size, and drop acceptance."""
        self.setWindowTitle(self.APP_NAME)
        self.setMinimumSize(900, 600)
        self.setAcceptDrops(True)

    def _setup_tabs(self) -> None:
        """Create the central QTabWidget and a welcome placeholder."""
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

        self._welcome = QLabel(
            "<h2>Welcome to PDREADF</h2>"
            "<p>Open a PDF with <b>File → Open</b> (Ctrl+O)<br>"
            "or drag &amp; drop PDF files onto this window.</p>"
        )
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome.setStyleSheet("color: #888; font-size: 14px;")
        self._tabs.addTab(self._welcome, "Welcome")
        # hide the close button on the welcome tab
        self._tabs.tabBar().setTabButton(
            0, self._tabs.tabBar().ButtonPosition.RightSide, None
        )

    def _setup_statusbar(self) -> None:
        """Create status bar with message and zoom labels."""
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_label = QLabel("Ready")
        bar.addWidget(self._status_label)
        self._zoom_label = QLabel("100%")
        bar.addPermanentWidget(self._zoom_label)

    # ── menu bar ──────────────────────────────────────────────

    def _setup_menubar(self) -> None:
        """Build the full application menu bar by delegating to per-menu helpers."""
        mb = self.menuBar()
        self._setup_file_menu(mb)
        self._setup_edit_menu(mb)
        self._setup_view_menu(mb)
        self._setup_page_menu(mb)
        self._setup_tools_menu(mb)
        self._setup_help_menu(mb)

    def _setup_file_menu(self, mb) -> None:
        """Populate the File menu."""
        m = mb.addMenu("&File")
        self._add_action(m, "&Open…",    "Ctrl+O",       self.open_file)
        self._recent_menu = m.addMenu("Recent Files")
        self._update_recent_menu()
        m.addSeparator()
        self._add_action(m, "&Save",     "Ctrl+S",       self.save_current)
        self._add_action(m, "Save &As…", "Ctrl+Shift+S", self.save_as_current)
        m.addSeparator()
        self._add_action(m, "&Print…",   "Ctrl+P",       self.print_current)
        m.addSeparator()
        self._add_action(m, "Close &Tab", "Ctrl+W",      self._close_current_tab)
        self._add_action(m, "E&xit",      "Alt+F4",      self.close)

    def _setup_edit_menu(self, mb) -> None:
        """Populate the Edit menu."""
        m = mb.addMenu("&Edit")
        self._add_action(m, "&Find…",       "Ctrl+F", self.focus_search)
        self._add_action(m, "Go to &Page…", "Ctrl+G", self.goto_page_dialog)

    def _setup_view_menu(self, mb) -> None:
        """Populate the View menu including page-mode sub-menu and theme toggle."""
        m = mb.addMenu("&View")
        self._add_action(m, "Zoom &In",  "Ctrl+=", self.zoom_in)
        self._add_action(m, "Zoom &Out", "Ctrl+-", self.zoom_out)
        self._add_action(m, "&Fit Page", "Ctrl+0", self.zoom_fit)
        m.addSeparator()

        mode_m = m.addMenu("Page &Mode")
        for mode, label in [
            ("single",     "Single Page"),
            ("dual",       "Dual Page"),
            ("continuous", "Continuous Scroll"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda _, mo=mode: self._set_page_mode(mo))
            mode_m.addAction(act)

        m.addSeparator()
        self._dark_action = QAction("&Dark Theme", self)
        self._dark_action.setCheckable(True)
        self._dark_action.setChecked(self._settings.theme == "dark")
        self._dark_action.triggered.connect(
            lambda checked: self._apply_theme("dark" if checked else "light")
        )
        m.addAction(self._dark_action)
        m.addSeparator()
        self._add_action(m, "&Refresh", "F5", self._refresh_current)
        fs_act = QAction("&Fullscreen", self)
        fs_act.setShortcut(QKeySequence("F11"))
        fs_act.setCheckable(True)
        fs_act.triggered.connect(self._toggle_fullscreen)
        m.addAction(fs_act)
        self._fullscreen_action = fs_act

    def _setup_page_menu(self, mb) -> None:
        """Populate the Page editing menu."""
        m = mb.addMenu("&Page")
        self._add_action(m, "Add &Blank Page", "", self._add_blank_page)
        self._add_action(m, "&Delete Page",    "", self._delete_page)
        m.addSeparator()
        rot_m = m.addMenu("&Rotate Page")
        for deg, label in [
            (90,  "90° Clockwise"),
            (180, "180°"),
            (270, "90° Counter-clockwise"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda _, d=deg: self._rotate_page(d))
            rot_m.addAction(act)

    def _setup_tools_menu(self, mb) -> None:
        """Populate the Tools menu."""
        m = mb.addMenu("&Tools")
        self._add_action(m, "&Merge PDFs…",           "", self.merge_pdfs)
        self._add_action(m, "&Split PDF…",            "", self.split_pdf)
        m.addSeparator()
        self._add_action(m, "Extract &Text…",         "", self.extract_text)
        self._add_action(m, "Extract &Images…",       "", self.extract_images)
        m.addSeparator()
        self._add_action(m, "Export Page as &Image…", "", self.export_page_image)
        self._add_action(m, "Export &All Pages…",     "", self.export_all_images)

    def _setup_help_menu(self, mb) -> None:
        """Populate the Help menu."""
        m = mb.addMenu("&Help")
        self._add_action(m, "&About PDREADF", "", self._show_about)

    def _add_action(
        self, menu, label: str, shortcut: str, slot
    ) -> QAction:
        """Helper: create a QAction, connect it, and add it to *menu*."""
        act = QAction(label, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    # ── main toolbar ──────────────────────────────────────────

    def _setup_toolbar(self) -> None:
        """Build the main toolbar with navigation, zoom, and search buttons."""
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        def btn(label: str, tip: str, slot) -> None:
            act = QAction(label, self)
            act.setToolTip(tip)
            act.triggered.connect(slot)
            tb.addAction(act)

        btn("📂", "Open (Ctrl+O)",  self.open_file)
        btn("💾", "Save (Ctrl+S)",  self.save_current)
        tb.addSeparator()
        btn("⏮", "First page",     self._goto_first)
        btn("◀", "Previous page",  self._goto_prev)

        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setFixedWidth(56)
        self._page_spin.setToolTip("Current page")
        self._page_spin.editingFinished.connect(self._on_page_spin)
        tb.addWidget(self._page_spin)

        self._page_total_lbl = QLabel(" / 1 ")
        tb.addWidget(self._page_total_lbl)

        btn("▶", "Next page",    self._goto_next)
        btn("⏭", "Last page",   self._goto_last)
        tb.addSeparator()
        btn("−", "Zoom out (Ctrl+-)", self.zoom_out)

        self._zoom_combo = QComboBox()
        self._zoom_combo.setEditable(True)
        self._zoom_combo.setFixedWidth(72)
        for z in ("50%", "75%", "100%", "125%", "150%", "200%", "400%"):
            self._zoom_combo.addItem(z)
        self._zoom_combo.setCurrentText("100%")
        self._zoom_combo.currentTextChanged.connect(self._on_zoom_combo)
        tb.addWidget(self._zoom_combo)

        btn("+", "Zoom in (Ctrl+=)",    self.zoom_in)
        btn("⊡", "Fit page (Ctrl+0)",  self.zoom_fit)
        tb.addSeparator()
        btn("🔍", "Find (Ctrl+F)",  self.focus_search)
        btn("🖨",  "Print (Ctrl+P)", self.print_current)

    # ── public file actions ───────────────────────────────────

    def open_file(self, path: Optional[str] = None) -> None:
        """Open a PDF from *path*, or show a file-open dialog."""
        if not path:
            last = self._settings.get("last_dir", str(Path.home()))
            path, _ = QFileDialog.getOpenFileName(
                self, "Open PDF", last, "PDF Files (*.pdf);;All Files (*)"
            )
        if path and os.path.isfile(path):
            self._settings.set("last_dir", str(Path(path).parent))
            self._settings.add_recent(path)
            self._update_recent_menu()
            self._open_tab(path)

    def save_current(self) -> None:
        """Save the active document."""
        tab = self._current_tab()
        if tab:
            tab.save()

    def save_as_current(self) -> None:
        """Save the active document to a new path."""
        tab = self._current_tab()
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", tab.path, "PDF Files (*.pdf)"
        )
        if path:
            tab.save_as(path)

    def print_current(self) -> None:
        """Print the active document."""
        tab = self._current_tab()
        if tab:
            tab.print_document()

    def zoom_in(self) -> None:
        """Zoom in on the active tab."""
        tab = self._current_tab()
        if tab:
            tab.zoom_in()
            self._update_zoom_ui(tab._viewer.zoom())

    def zoom_out(self) -> None:
        """Zoom out on the active tab."""
        tab = self._current_tab()
        if tab:
            tab.zoom_out()
            self._update_zoom_ui(tab._viewer.zoom())

    def zoom_fit(self) -> None:
        """Fit the current page in the active tab."""
        tab = self._current_tab()
        if tab:
            tab.zoom_fit()
            self._update_zoom_ui(tab._viewer.zoom())

    def focus_search(self) -> None:
        """Show the search panel and focus the search input."""
        tab = self._current_tab()
        if tab:
            tab.focus_search()

    def goto_page_dialog(self) -> None:
        """Show an input dialog to jump to a specific page."""
        tab = self._current_tab()
        if not tab or not tab.doc:
            return
        n = tab.doc.page_count()
        page, ok = QInputDialog.getInt(
            self,
            "Go to Page",
            f"Page number (1 – {n}):",
            tab._viewer.current_page() + 1,
            1,
            n,
        )
        if ok:
            tab.goto_page(page - 1)

    # ── tools actions ─────────────────────────────────────────

    def merge_pdfs(self) -> None:
        """Merge selected PDFs into a new output file."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDFs to Merge",
            self._settings.get("last_dir", str(Path.home())),
            "PDF Files (*.pdf)",
        )
        if len(paths) < 2:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Save Merged PDF",
            self._settings.get("last_dir", str(Path.home())),
            "PDF Files (*.pdf)",
        )
        if not out:
            return
        try:
            Manager.merge_pdfs(paths, out)
            QMessageBox.information(self, "Merge Complete", f"Saved to:\n{out}")
            if (
                QMessageBox.question(
                    self, "Open?", "Open the merged PDF?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                self.open_file(out)
        except Exception as exc:
            QMessageBox.critical(self, "Merge Error", str(exc))

    def split_pdf(self) -> None:
        """Split the active PDF into individual pages."""
        tab = self._current_tab()
        if not tab:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Output Directory", self._settings.get("last_dir", str(Path.home()))
        )
        if out_dir:
            try:
                paths = Manager.split_pdf(tab.path, out_dir)
                QMessageBox.information(
                    self, "Split Complete",
                    f"Saved {len(paths)} pages to:\n{out_dir}",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Split Error", str(exc))

    def extract_text(self) -> None:
        """Extract text from the active PDF and save as .txt."""
        tab = self._current_tab()
        if not tab:
            return
        default = str(Path(tab.path).with_suffix(".txt"))
        out, _ = QFileDialog.getSaveFileName(
            self, "Save Text File", default, "Text Files (*.txt)"
        )
        if out:
            try:
                Manager.extract_text(tab.path, out)
                QMessageBox.information(self, "Done", f"Text saved to:\n{out}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def extract_images(self) -> None:
        """Extract embedded images from the active PDF."""
        tab = self._current_tab()
        if not tab:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Output Directory", self._settings.get("last_dir", str(Path.home()))
        )
        if out_dir:
            try:
                count = Manager.extract_images(tab.path, out_dir)
                QMessageBox.information(
                    self, "Done", f"Extracted {count} image(s) to:\n{out_dir}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def export_page_image(self) -> None:
        """Export the current page as a PNG or JPEG."""
        tab = self._current_tab()
        if not tab or not tab.doc:
            return
        pg = tab._viewer.current_page()
        default = f"page_{pg + 1}.png"
        out, _ = QFileDialog.getSaveFileName(
            self, "Export Page as Image", default,
            "PNG (*.png);;JPEG (*.jpg *.jpeg)"
        )
        if out:
            try:
                Manager.export_page_as_image(tab.doc, pg, out, zoom=2.0)
                QMessageBox.information(self, "Done", f"Page saved to:\n{out}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def export_all_images(self) -> None:
        """Export every page of the active document as image files."""
        tab = self._current_tab()
        if not tab or not tab.doc:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Output Directory", self._settings.get("last_dir", str(Path.home()))
        )
        if not out_dir:
            return
        fmt, ok = QInputDialog.getItem(
            self, "Format", "Image format:", ["png", "jpg"], 0, False
        )
        if ok:
            try:
                n = Manager.export_all_pages(tab.doc, out_dir, zoom=2.0, fmt=fmt)
                QMessageBox.information(
                    self, "Done", f"Exported {n} page(s) to:\n{out_dir}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── page operations (menu → PDFTab delegates) ─────────────

    def _add_blank_page(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.add_blank_page()

    def _delete_page(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.delete_current_page()

    def _rotate_page(self, degrees: int) -> None:
        tab = self._current_tab()
        if tab:
            tab.rotate_current_page(degrees)

    def _set_page_mode(self, mode: str) -> None:
        self._settings.page_mode = mode
        tab = self._current_tab()
        if tab:
            tab.set_page_mode(mode)

    # ── navigation helpers ────────────────────────────────────

    def _goto_first(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.goto_page(0)

    def _goto_last(self) -> None:
        tab = self._current_tab()
        if tab and tab.doc:
            tab.goto_page(tab.doc.page_count() - 1)

    def _goto_prev(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.goto_page(max(0, tab._viewer.current_page() - 1))

    def _goto_next(self) -> None:
        tab = self._current_tab()
        if tab and tab.doc:
            tab.goto_page(
                min(tab.doc.page_count() - 1, tab._viewer.current_page() + 1)
            )

    def _on_page_spin(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.goto_page(self._page_spin.value() - 1)

    def _on_zoom_combo(self, text: str) -> None:
        tab = self._current_tab()
        if not tab:
            return
        try:
            pct = float(text.strip("%"))
            tab._viewer.set_zoom(pct / 100.0)
            self._settings.zoom = pct / 100.0
        except ValueError:
            pass

    # ── theme ─────────────────────────────────────────────────

    def _apply_theme(self, theme: str) -> None:
        """Apply dark or light colour palette to the application."""
        self._settings.theme = theme
        app = QApplication.instance()
        if theme == "dark":
            pal = QPalette()
            c = {
                QPalette.ColorRole.Window:          QColor(45, 45, 48),
                QPalette.ColorRole.WindowText:      QColor(220, 220, 220),
                QPalette.ColorRole.Base:            QColor(30, 30, 30),
                QPalette.ColorRole.AlternateBase:   QColor(45, 45, 48),
                QPalette.ColorRole.ToolTipBase:     QColor(45, 45, 48),
                QPalette.ColorRole.ToolTipText:     QColor(220, 220, 220),
                QPalette.ColorRole.Text:            QColor(220, 220, 220),
                QPalette.ColorRole.Button:          QColor(60, 60, 65),
                QPalette.ColorRole.ButtonText:      QColor(220, 220, 220),
                QPalette.ColorRole.BrightText:      QColor(255, 80, 80),
                QPalette.ColorRole.Highlight:       QColor(0, 120, 215),
                QPalette.ColorRole.HighlightedText: Qt.GlobalColor.white,
                QPalette.ColorRole.Link:            QColor(86, 156, 214),
            }
            for role, color in c.items():
                pal.setColor(role, color)
            app.setPalette(pal)
        else:
            app.setPalette(app.style().standardPalette())

        if hasattr(self, "_dark_action"):
            self._dark_action.setChecked(theme == "dark")

    # ── tab helpers ───────────────────────────────────────────

    def _open_tab(self, path: str) -> None:
        """Open *path* in a new tab, or focus the existing tab if already open."""
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, PDFTab) and w.path == path:
                self._tabs.setCurrentIndex(i)
                return
        # remove welcome tab if it's still there
        if self._tabs.count() == 1 and isinstance(self._tabs.widget(0), QLabel):
            self._tabs.removeTab(0)
        tab = PDFTab(path, self._settings)
        tab.status_message.connect(self._show_status)
        tab.title_changed.connect(lambda t, _tab=tab: self._update_tab_title(_tab, t))
        idx = self._tabs.addTab(tab, Path(path).name)
        self._tabs.setCurrentIndex(idx)

    def _current_tab(self) -> Optional[PDFTab]:
        """Return the active :class:`PDFTab`, or ``None`` if none is open."""
        w = self._tabs.currentWidget()
        return w if isinstance(w, PDFTab) else None

    def _close_tab(self, index: int) -> None:
        """Close the tab at *index*, prompting to save if modified."""
        w = self._tabs.widget(index)
        if isinstance(w, PDFTab) and w.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to {Path(w.path).name}?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Save:
                w.save()
        if isinstance(w, PDFTab) and w.doc:
            w.doc.close()
        self._tabs.removeTab(index)
        if self._tabs.count() == 0:
            self._tabs.addTab(self._welcome, "Welcome")
            self._tabs.tabBar().setTabButton(
                0, self._tabs.tabBar().ButtonPosition.RightSide, None
            )

    def _close_current_tab(self) -> None:
        idx = self._tabs.currentIndex()
        if idx >= 0:
            self._close_tab(idx)

    def _on_tab_changed(self, index: int) -> None:
        """Sync toolbar controls when the user switches tabs."""
        w = self._tabs.widget(index)
        if isinstance(w, PDFTab) and w.doc:
            n  = w.doc.page_count()
            pg = w._viewer.current_page()
            self._page_spin.setMaximum(n)
            self._page_spin.setValue(pg + 1)
            self._page_total_lbl.setText(f" / {n} ")
            self._update_zoom_ui(w._viewer.zoom())

    def _update_tab_title(self, tab: PDFTab, title: str) -> None:
        idx = self._tabs.indexOf(tab)
        if idx >= 0:
            self._tabs.setTabText(idx, title)

    def _show_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _update_zoom_ui(self, zoom: float) -> None:
        pct = int(zoom * 100)
        self._zoom_label.setText(f"{pct}%")
        self._zoom_combo.blockSignals(True)
        self._zoom_combo.setCurrentText(f"{pct}%")
        self._zoom_combo.blockSignals(False)

    def _update_recent_menu(self) -> None:
        """Rebuild the Recent Files sub-menu from settings."""
        if not hasattr(self, "_recent_menu"):
            return
        self._recent_menu.clear()
        existing = [p for p in self._settings.recent_files if os.path.isfile(p)]
        for path in existing:
            act = QAction(Path(path).name, self)
            act.setToolTip(path)
            act.triggered.connect(lambda _, p=path: self.open_file(p))
            self._recent_menu.addAction(act)
        if not existing:
            placeholder = QAction("(No recent files)", self)
            placeholder.setEnabled(False)
            self._recent_menu.addAction(placeholder)

    def _refresh_current(self) -> None:
        tab = self._current_tab()
        if tab:
            tab._reload_document()

    def _toggle_fullscreen(self, checked: bool) -> None:
        self.showFullScreen() if checked else self.showNormal()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {self.APP_NAME}",
            f"<h2>{self.APP_NAME} {self.APP_VERSION}</h2>"
            "<p>Professional PDF Reader &amp; Editor</p>"
            "<p>Built with <b>PyQt6</b> and <b>PyMuPDF</b></p>"
            "<p>Author: <b>nkVas1</b> &nbsp;|&nbsp; License: MIT</p>",
        )

    # ── geometry persistence ──────────────────────────────────

    def _restore_geometry(self) -> None:
        """Restore window position and size from settings."""
        self.setGeometry(
            self._settings.get("window_x", 100),
            self._settings.get("window_y", 100),
            self._settings.get("window_w", 1280),
            self._settings.get("window_h", 800),
        )
        if self._settings.get("window_maximized", False):
            self.showMaximized()

    def _save_geometry(self) -> None:
        """Persist window geometry to settings."""
        if not self.isMaximized():
            r = self.geometry()
            self._settings.set("window_x", r.x())
            self._settings.set("window_y", r.y())
            self._settings.set("window_w", r.width())
            self._settings.set("window_h", r.height())
        self._settings.set("window_maximized", self.isMaximized())

    # ── drag & drop ───────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events that include PDF file URLs."""
        if event.mimeData().hasUrls():
            if any(
                u.toLocalFile().lower().endswith(".pdf")
                for u in event.mimeData().urls()
            ):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Open all dropped PDF files."""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf") and os.path.isfile(path):
                self.open_file(path)

    # ── window events ─────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Prompt to save modified documents then persist settings."""
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if not isinstance(w, PDFTab) or not w.is_modified:
                continue
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"Save changes to {Path(w.path).name}?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Save:
                w.save()
        # close all open fitz documents
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, PDFTab) and w.doc:
                w.doc.close()
        self._save_geometry()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle arrow-key page navigation and other global shortcuts."""
        key = event.key()
        mod = event.modifiers()
        if key == Qt.Key.Key_Left and not mod:
            self._goto_prev()
        elif key == Qt.Key.Key_Right and not mod:
            self._goto_next()
        elif key == Qt.Key.Key_Home and mod == Qt.KeyboardModifier.ControlModifier:
            self._goto_first()
        elif key == Qt.Key.Key_End and mod == Qt.KeyboardModifier.ControlModifier:
            self._goto_last()
        else:
            super().keyPressEvent(event)


# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PDREADF")
    app.setOrganizationName("nkVas1")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()

    # open any PDF files passed on the command line
    for arg in sys.argv[1:]:
        if os.path.isfile(arg) and arg.lower().endswith(".pdf"):
            window.open_file(arg)

    window.show()
    sys.exit(app.exec())
