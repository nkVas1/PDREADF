# PDREADF – Copilot Instructions

## Project Overview
PDREADF is a professional PDF Reader & Editor built with **PyQt6** and **PyMuPDF** (`fitz`).
Structural page edits use **pikepdf**. The entire application lives in a single file: `pdreadf.py`.

---

## Architecture (SOLID)

| Class | Responsibility |
|---|---|
| `Settings` | JSON-persisted app preferences (theme, zoom, recent files, window state) |
| `Utils` | Pure static helpers: fitz matrix creation, QPixmap conversion, coordinate mapping |
| `PDFDocument` | Thin wrapper around `fitz.Document` with a `(page, zoom)` → `QPixmap` LRU cache |
| `PageRenderer` | Synchronous page renderer delegating to `PDFDocument` |
| `ThumbnailPanel` | `QWidget` sidebar with a `QListWidget` of page thumbnails; emits `page_selected` and `pages_reordered` signals |
| `SearchPanel` | Full-text search UI; emits `search_requested` and `navigate_result` signals |
| `BookmarkPanel` | Bookmark CRUD UI; emits `navigate_bookmark` signal |
| `AnnotationToolbar` | `QToolBar` with checkable annotation tool buttons and colour picker |
| `PDFCanvas` | Custom `QWidget` inside the scroll area; `paintEvent` draws pages + highlights; handles mouse for annotation drawing |
| `PDFViewer` | `QScrollArea` wrapping `PDFCanvas`; delegates zoom / page / mode changes |
| `PDFTab` | `QWidget` assembling one open document: `PDFViewer` + sidebar panels + `AnnotationToolbar` |
| `Editor` | Static methods for structural page ops via `pikepdf` (add blank, delete, rotate, reorder) |
| `Annotator` | Static methods to add `fitz` annotations (highlight, underline, strikeout, ink, text note) |
| `Manager` | Static file-level ops: merge, split, extract text, extract images, export pages as images |
| `MainWindow` | `QMainWindow`: tabbed interface, menu bar, toolbar, status bar, drag-and-drop |

---

## Coding Standards

- **Type hints** on every function signature (`-> None`, `-> str`, etc.)
- **Docstrings** (one-line summary + elaboration where needed) on every public method and class
- **SOLID**: each class has one clear responsibility; no god-objects
- **No bare `except:`** – catch specific exceptions or `Exception as e`
- **PyQt6 enums** always fully qualified: `Qt.AlignmentFlag.AlignCenter`, `QMessageBox.StandardButton.Yes`, etc.
- **Signals** defined at class level with `pyqtSignal`; never connect lambdas that discard `self`
- **pikepdf** is used only for structural edits (page order, rotation, merge, split); annotation data lives in fitz
- **fitz** is used for rendering, text extraction, search, and annotations

---

## Extending Features

### Adding a new annotation type
1. Add a tuple to `AnnotationToolbar.TOOLS`.
2. Implement `Annotator.add_<type>(doc, page_idx, data, color)` using the appropriate `fitz` annotation API.
3. Add a branch in `Annotator.apply_annotation`.

### Adding a new page editing operation
1. Add a static method to `Editor` using `pikepdf.open(path, allow_overwriting_input=True)`.
2. Expose it via `PDFTab` (instance method that calls `Editor.*` then `_reload_document`).
3. Wire a `QAction` in `MainWindow._setup_menubar`.

### Adding a new sidebar panel
1. Subclass `QWidget`, define signals for navigation/actions.
2. Instantiate in `PDFTab._setup_ui` and add to `self._panel_tabs`.
3. Connect signals to `PDFViewer` / `PDFDocument` methods.

---

## Test Requirements

- All tests in `tests/test_pdreadf.py` using **pytest**
- Use `conftest.py`-style helper or inline fixture to create an in-memory test PDF with `fitz.open()`
- Test every public API of: `Settings`, `Utils`, `PDFDocument`, `Editor`, `Annotator`, `Manager`
- GUI tests (widgets) are optional; use `QApplication` fixture if needed
- No network access, no external PDF files – generate test PDFs with fitz in `tmp_path`

---

## Build

```bat
pyinstaller --onefile --windowed --name PDREADF --icon=icon.ico pdreadf.py
```

Output: `dist/PDREADF.exe`

---

## Dependencies

```
PyQt6>=6.4.0
PyMuPDF>=1.23.0
pikepdf>=8.0.0
Pillow>=10.0.0
```
