# PDREADF – Professional PDF Reader & Editor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)

A full-featured, cross-platform PDF Reader & Editor built with **PyQt6** and **PyMuPDF**.

---

## ✨ Features

| Category | Details |
|---|---|
| **Viewing** | Single page, dual-page, and continuous-scroll modes |
| **Zoom** | Ctrl+/Ctrl−/scroll-wheel zoom, fit-page, preset percentages |
| **Navigation** | Thumbnail sidebar (toggle with Ctrl+B), page-number spin box, keyboard arrows |
| **Search** | Full-text search across all pages with yellow highlight overlays and prev/next navigation |
| **Bookmarks** | Add, list, navigate to, and delete page bookmarks |
| **Annotations** | Highlight · Underline · Strikeout · Freehand ink · Text notes (all via PyMuPDF) |
| **Page editing** | Add blank page · Delete page · Rotate 90/180/270° · Drag-drop reorder in sidebar |
| **File operations** | Open · Save · Save As · Merge PDFs · Split PDF · Extract text · Extract images |
| **Export** | Export current page as PNG/JPEG · Export all pages as images |
| **Productivity** | Copy current/all document text to clipboard · Clear recent files |
| **Document utilities** | Document info dialog (metadata + file size/pages) · Optimize PDF (compressed output) |
| **Print** | System print dialog with full page scaling |
| **UI** | Dark / light theme toggle · Drag-and-drop file open · Multiple tabs · Status bar |
| **Persistence** | Settings (theme, zoom, recent files, window geometry) saved as JSON |

---

## 📋 Requirements

| Package | Version |
|---|---|
| PyQt6 | ≥ 6.4.0 |
| PyMuPDF | ≥ 1.23.0 |
| pikepdf | ≥ 8.0.0 |
| Pillow | ≥ 10.0.0 |

---

## 🚀 Installation

```bash
# 1. Clone the repository
git clone https://github.com/nkVas1/PDREADF.git
cd PDREADF

# 2. Create a virtual environment (optional but recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python pdreadf.py
```

### Opening a PDF directly

```bash
python pdreadf.py /path/to/document.pdf
```

---

## 🖱️ Usage

### Opening files
- **File → Open** (Ctrl+O) – file-open dialog
- **Drag & drop** – drag one or more `.pdf` files onto the window
- **File → Recent Files** – quickly reopen previously opened files

### Navigating
- Click a **thumbnail** in the sidebar to jump to that page
- Use the **page spin box** in the toolbar
- **Arrow keys** (← →) for previous / next page
- **Ctrl+G** – Go to Page dialog

### Searching
- **Ctrl+F** – open the Search panel
- Type your query and press Enter or click **Find**
- Use **◀ ▶** buttons to step through matches

### Productivity actions
- **Ctrl+Shift+C** – copy current page text to clipboard
- **Edit → Copy All Document Text** – copy all extracted text to clipboard
- **View → Toggle Sidebar** (Ctrl+B) – hide/show Pages/Search/Bookmarks sidebar
- **File → Recent Files → Clear Recent Files** – quickly reset recent history

### Document utilities
- **Tools → Document Info** – view path, page count, file size, and PDF metadata
- **Tools → Optimize PDF** – save a cleaned/deflated optimized copy

### Annotating
1. Select an annotation tool from the **Annotation** toolbar at the top of each tab
2. Draw a rectangle over the desired region (or draw freehand for the Ink tool)
3. Save the document (Ctrl+S) to persist annotations

### Editing pages
- **Page → Add Blank Page** – inserts an A4 blank page after the current page
- **Page → Delete Page** – removes the current page (with confirmation)
- **Page → Rotate Page** – rotate 90°, 180°, or 270°
- **Drag thumbnails** in the Pages sidebar to reorder pages

### Merging & splitting
- **Tools → Merge PDFs** – select multiple PDFs and choose an output file
- **Tools → Split PDF** – saves each page as a separate file in a chosen folder

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+W | Close current tab |
| Ctrl+F | Find / Search |
| Ctrl+G | Go to page |
| Ctrl+B | Toggle sidebar |
| Ctrl+Shift+C | Copy current page text |
| Ctrl+= | Zoom in |
| Ctrl+− | Zoom out |
| Ctrl+0 | Fit page |
| Ctrl+P | Print |
| F5 | Refresh / reload |
| F11 | Toggle fullscreen |
| ← / → | Previous / next page |
| Ctrl+Home | First page |
| Ctrl+End | Last page |
| Ctrl+Scroll | Zoom in / out |

---

## 🏗️ Build (Windows Executable)

```bat
build.bat
```

This runs:
```bat
pip install -r requirements.txt
pyinstaller --clean --onefile --windowed --name PDREADF --icon=icon.ico --collect-all fitz pdreadf.py
```

The standalone `PDREADF.exe` is placed in `dist\`.

> **Tip:** Provide an `icon.ico` file in the project root before building.

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/
```

---

## 🏛️ Architecture

```
MainWindow (QMainWindow)
 └── QTabWidget
      └── PDFTab (QWidget)  [one per open document]
           ├── AnnotationToolbar (QToolBar)
           ├── ThumbnailPanel (QWidget)  ─╮
           ├── SearchPanel (QWidget)      ├─ sidebar QTabWidget
           ├── BookmarkPanel (QWidget)   ─╯
           └── PDFViewer (QScrollArea)
                └── PDFCanvas (QWidget)

Support classes:
  Settings      – JSON settings persistence
  Utils         – static helpers (render, coord conversion)
  PDFDocument   – fitz.Document wrapper with render cache
  PageRenderer  – thin rendering facade
  Editor        – pikepdf page-editing operations (static)
  Annotator     – fitz annotation operations (static)
  Manager       – file-level operations (merge, split, extract) (static)
```

---

## 📄 License

MIT © 2024 nkVas1 – see [LICENSE](LICENSE).
