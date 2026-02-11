# Wall Art Slicer Pro

A modern desktop wall art layout tool built with **CustomTkinter**.

## Features

- Import one PNG/JPG image.
- Split into **N vertical slices** (single row workflow).
- Live horizontal preview with spacing and layout mode.
- Export each slice to its own PDF page using **ReportLab**.
- Configurable margins (mm), page sizes (A5, A4, A3), and layout modes:
  - Centered vertically
  - Top aligned
  - Bottom aligned
  - Staggered
- 300 DPI output pipeline for print-ready exports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python poster_maker_app.py
```

## Notes

- Unit conversion uses `1 mm = 2.83465 points`.
- PDF pages are generated at vector page size with images drawn using a 300-DPI physical mapping.
