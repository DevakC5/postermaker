import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageTk
from reportlab.lib.pagesizes import A3, A4, A5
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from tkinter import filedialog, messagebox

MM_TO_POINTS = 2.83465
POINTS_PER_INCH = 72
TARGET_DPI = 300
PREVIEW_SLICE_HEIGHT = 220
PREVIEW_SPACING_PX = 18
STAGGER_OFFSET_MM = 8

PAGE_SIZES = {
    "A5": A5,
    "A4": A4,
    "A3": A3,
}

LAYOUT_MODES = [
    "Centered vertically",
    "Top aligned",
    "Bottom aligned",
    "Staggered",
]


@dataclass
class ExportSettings:
    slices: int
    margin_mm: float
    page_size: str
    layout_mode: str


def mm_to_points(mm: float) -> float:
    return mm * MM_TO_POINTS


def slice_image_vertically(image: Image.Image, count: int) -> List[Image.Image]:
    """Split an image into equal vertical slices."""
    if count < 1:
        raise ValueError("Slice count must be at least 1.")

    width, height = image.size
    boundaries = [round(i * width / count) for i in range(count + 1)]

    slices = []
    for i in range(count):
        left = boundaries[i]
        right = boundaries[i + 1]
        if right <= left:
            right = min(width, left + 1)
        slices.append(image.crop((left, 0, right, height)))
    return slices


def _compute_fit_dimensions(
    img_w: int,
    img_h: int,
    max_w_pt: float,
    max_h_pt: float,
) -> Tuple[float, float]:
    scale = min(max_w_pt / img_w, max_h_pt / img_h)
    scale = max(scale, 0.01)
    return img_w * scale, img_h * scale


def _vertical_position(
    page_h_pt: float,
    draw_h_pt: float,
    margin_pt: float,
    layout_mode: str,
    index: int,
) -> float:
    top_y = page_h_pt - margin_pt - draw_h_pt
    bottom_y = margin_pt
    centered_y = (page_h_pt - draw_h_pt) / 2

    if layout_mode == "Top aligned":
        y = top_y
    elif layout_mode == "Bottom aligned":
        y = bottom_y
    else:
        y = centered_y

    if layout_mode == "Staggered":
        offset = mm_to_points(STAGGER_OFFSET_MM)
        y += offset if index % 2 == 0 else -offset

    max_y = page_h_pt - margin_pt - draw_h_pt
    min_y = margin_pt
    return max(min_y, min(y, max_y))


def export_slices_to_pdf(
    slices: List[Image.Image],
    output_pdf: str,
    settings: ExportSettings,
) -> None:
    page_w_pt, page_h_pt = PAGE_SIZES[settings.page_size]
    margin_pt = mm_to_points(settings.margin_mm)

    c = canvas.Canvas(output_pdf, pagesize=(page_w_pt, page_h_pt))

    available_w_pt = page_w_pt - (margin_pt * 2)
    available_h_pt = page_h_pt - (margin_pt * 2)
    if available_w_pt <= 0 or available_h_pt <= 0:
        raise ValueError("Margin is too large for the selected page size.")

    for idx, section in enumerate(slices):
        rgb_slice = section.convert("RGB")

        # High-resolution mapping at 300 DPI to preserve printable quality.
        src_w_px, src_h_px = rgb_slice.size
        natural_w_pt = (src_w_px / TARGET_DPI) * POINTS_PER_INCH
        natural_h_pt = (src_h_px / TARGET_DPI) * POINTS_PER_INCH

        draw_w_pt, draw_h_pt = _compute_fit_dimensions(
            natural_w_pt,
            natural_h_pt,
            available_w_pt,
            available_h_pt,
        )

        x = (page_w_pt - draw_w_pt) / 2
        y = _vertical_position(
            page_h_pt,
            draw_h_pt,
            margin_pt,
            settings.layout_mode,
            idx,
        )

        c.drawImage(
            ImageReader(rgb_slice),
            x,
            y,
            width=draw_w_pt,
            height=draw_h_pt,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto",
        )
        c.showPage()

    c.save()


def render_live_preview(
    slices: List[Image.Image],
    layout_mode: str,
    background=(34, 34, 34),
) -> Image.Image:
    if not slices:
        return Image.new("RGB", (900, 280), background)

    scaled = []
    for item in slices:
        scale = PREVIEW_SLICE_HEIGHT / item.height
        preview_w = max(1, int(item.width * scale))
        scaled.append(item.resize((preview_w, PREVIEW_SLICE_HEIGHT), Image.Resampling.LANCZOS))

    stagger_px = max(6, int(mm_to_points(STAGGER_OFFSET_MM) * 0.3))

    total_w = sum(im.width for im in scaled) + PREVIEW_SPACING_PX * (len(scaled) + 1)
    canvas_h = PREVIEW_SLICE_HEIGHT + 60 + stagger_px * 2
    preview = Image.new("RGB", (total_w, canvas_h), background)

    x = PREVIEW_SPACING_PX
    for idx, item in enumerate(scaled):
        if layout_mode == "Top aligned":
            y = 20
        elif layout_mode == "Bottom aligned":
            y = canvas_h - item.height - 20
        elif layout_mode == "Staggered":
            base = (canvas_h - item.height) // 2
            y = base + (stagger_px if idx % 2 == 0 else -stagger_px)
        else:
            y = (canvas_h - item.height) // 2

        preview.paste(item.convert("RGB"), (x, y))
        x += item.width + PREVIEW_SPACING_PX

    return preview


class PosterMakerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Wall Art Slicer Pro")
        self.geometry("1280x780")
        self.minsize(1040, 680)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.source_image: Optional[Image.Image] = None
        self.slices: List[Image.Image] = []
        self.preview_tk: Optional[ImageTk.PhotoImage] = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        control_panel = ctk.CTkFrame(self, corner_radius=12)
        control_panel.grid(row=0, column=0, sticky="ns", padx=(16, 8), pady=16)
        control_panel.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            control_panel,
            text="Wall Art Layout Tool",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.grid(row=0, column=0, padx=18, pady=(18, 14), sticky="w")

        self.import_button = ctk.CTkButton(
            control_panel,
            text="Import Image (PNG/JPG)",
            command=self.import_image,
            height=38,
        )
        self.import_button.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="ew")

        self.file_label = ctk.CTkLabel(
            control_panel,
            text="No file selected",
            text_color="#B8B8B8",
            wraplength=260,
            justify="left",
        )
        self.file_label.grid(row=2, column=0, padx=18, pady=(0, 16), sticky="w")

        self.slice_count_var = ctk.IntVar(value=3)
        self.margin_var = ctk.DoubleVar(value=15.0)
        self.page_size_var = ctk.StringVar(value="A4")
        self.layout_var = ctk.StringVar(value="Centered vertically")

        controls = [
            ("Number of slices", ctk.CTkOptionMenu(control_panel, variable=self.slice_count_var, values=[str(i) for i in range(1, 13)], command=self._on_controls_changed)),
            ("Gap / Margin (mm)", ctk.CTkSlider(control_panel, from_=0, to=50, variable=self.margin_var, number_of_steps=100, command=self._on_controls_changed)),
            ("Page size", ctk.CTkOptionMenu(control_panel, variable=self.page_size_var, values=list(PAGE_SIZES.keys()), command=self._on_controls_changed)),
            ("Layout mode", ctk.CTkOptionMenu(control_panel, variable=self.layout_var, values=LAYOUT_MODES, command=self._on_controls_changed)),
        ]

        row = 3
        for label_text, widget in controls:
            lbl = ctk.CTkLabel(control_panel, text=label_text)
            lbl.grid(row=row, column=0, padx=18, pady=(0, 6), sticky="w")
            row += 1
            widget.grid(row=row, column=0, padx=18, pady=(0, 14), sticky="ew")
            row += 1

        self.margin_readout = ctk.CTkLabel(control_panel, text="15.0 mm")
        self.margin_readout.grid(row=6, column=0, padx=18, pady=(-8, 14), sticky="e")

        self.export_button = ctk.CTkButton(
            control_panel,
            text="Export 300 DPI PDF",
            command=self.export_pdf,
            height=42,
            fg_color="#2979FF",
            hover_color="#1E5FCC",
        )
        self.export_button.grid(row=row, column=0, padx=18, pady=(8, 20), sticky="ew")

        self.status_label = ctk.CTkLabel(
            control_panel,
            text="Ready",
            text_color="#9AD8A6",
            wraplength=260,
            justify="left",
        )
        self.status_label.grid(row=row + 1, column=0, padx=18, pady=(0, 18), sticky="w")

        preview_frame = ctk.CTkFrame(self, corner_radius=12)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        preview_title = ctk.CTkLabel(
            preview_frame,
            text="Live Slice Preview",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        preview_title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        canvas_wrap = ctk.CTkFrame(preview_frame, fg_color="#1E1E1E")
        canvas_wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)

        self.preview_canvas = ctk.CTkCanvas(
            canvas_wrap,
            bg="#222222",
            highlightthickness=0,
            height=420,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        self.h_scroll = ctk.CTkScrollbar(
            canvas_wrap,
            orientation="horizontal",
            command=self.preview_canvas.xview,
        )
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.configure(xscrollcommand=self.h_scroll.set)

        self.preview_canvas.create_text(
            20,
            30,
            fill="#AAAAAA",
            anchor="nw",
            text="Import an image to begin previewing your wall art slices.",
            font=("Segoe UI", 14),
        )

    def _on_controls_changed(self, _=None) -> None:
        self.margin_readout.configure(text=f"{self.margin_var.get():.1f} mm")
        if self.source_image is not None:
            self.recompute_preview()

    def import_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg")],
        )
        if not path:
            return

        try:
            img = Image.open(path).convert("RGB")
        except Exception as err:
            messagebox.showerror("Import error", f"Could not load image:\n{err}")
            return

        self.source_image = img
        self.file_label.configure(text=os.path.basename(path))
        self.status_label.configure(text="Image loaded. Configure slices and export.")
        self.recompute_preview()

    def recompute_preview(self) -> None:
        if self.source_image is None:
            return

        try:
            self.slices = slice_image_vertically(self.source_image, int(self.slice_count_var.get()))
        except Exception as err:
            messagebox.showerror("Slicing error", str(err))
            return

        preview_image = render_live_preview(self.slices, self.layout_var.get())
        self.preview_tk = ImageTk.PhotoImage(preview_image)

        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, image=self.preview_tk, anchor="nw")
        self.preview_canvas.configure(
            scrollregion=(0, 0, preview_image.width, preview_image.height),
            width=min(preview_image.width, 860),
            height=min(preview_image.height, 460),
        )

    def export_pdf(self) -> None:
        if self.source_image is None:
            messagebox.showwarning("No image", "Please import an image first.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return

        settings = ExportSettings(
            slices=int(self.slice_count_var.get()),
            margin_mm=float(self.margin_var.get()),
            page_size=self.page_size_var.get(),
            layout_mode=self.layout_var.get(),
        )

        try:
            slices = slice_image_vertically(self.source_image, settings.slices)
            export_slices_to_pdf(slices, save_path, settings)
        except Exception as err:
            messagebox.showerror("Export error", f"Could not export PDF:\n{err}")
            return

        self.status_label.configure(text=f"Export complete: {os.path.basename(save_path)}")
        messagebox.showinfo("Success", "High-resolution 300 DPI PDF exported successfully.")


def main() -> None:
    app = PosterMakerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
