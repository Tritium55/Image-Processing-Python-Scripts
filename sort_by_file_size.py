#!/usr/bin/env python3
"""
Advanced Image Copier & Sorter - Modern UI

Features:
- Modern UI using ttkbootstrap
- Drag & Drop via tkinterdnd2
- Thumbnail preview with simple animation
- Determinate progress bar + indeterminate spinner
- Copies files (preserves timestamps) and recreates the input folder structure
  inside each resolution category (e.g. OUTPUT/FullHD/<relative_path>/image.jpg)
- Background worker thread to keep UI responsive

Dependencies:
- Pillow
- imagehash
- tkinterdnd2
- ttkbootstrap (optional for modern themes)
Install dependencies via pip if needed:
pip install Pillow imagehash tkinterdnd2 ttkbootstrap
"""

import os
import shutil
import threading
import queue
import math
from pathlib import Path
from PIL import Image, ImageTk
import time

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as e:
    raise RuntimeError("Tkinter is required and usually included with Python.") from e

# optional modern theme
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
except Exception:
    tb = None

# drag & drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

# ----------------------
# Configuration
# ----------------------
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
# categories define minimal width,height thresholds. higher categories override lower ones.
RES_CATEGORIES = {
    "Low":      (0,     0),
    "HD":       (1280,  720),
    "FullHD":   (1920, 1080),
    "2K":       (2560, 1440),
    "4K":       (3840, 2160),
    "8K":       (7680, 4320),
}

# ----------------------
# Utility functions
# ----------------------
def get_category_for_resolution(width, height):
    # Choose the highest category whose min_w,min_h are <= width,height
    chosen = "Low"
    for name, (mw, mh) in RES_CATEGORIES.items():
        if width >= mw and height >= mh:
            chosen = name
    return chosen

def safe_copy(src_path: str, dst_path: str):
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_path, dst_path)

# ----------------------
# Worker thread
# ----------------------
class CopyWorker(threading.Thread):
    def __init__(self, task_queue: queue.Queue, control, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_queue = task_queue
        self.control = control
        self._stop_event = threading.Event()
        self.daemon = True

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        total_tasks = self.task_queue.qsize()
        processed = 0
        # iterate tasks
        while not self.task_queue.empty() and not self.stopped():
            try:
                task = self.task_queue.get_nowait()
            except queue.Empty:
                break

            src = task["src"]        # absolute path to file
            input_root = task["input_root"]
            output_root = task["output_root"]

            try:
                with Image.open(src) as img:
                    width, height = img.size
            except Exception as e:
                self.control.log(f"ERROR reading {src}: {e}")
                processed += 1
                self.control.update_progress((processed / total_tasks) * 100)
                continue

            category = get_category_for_resolution(width, height)
            # compute rel path from input_root to file's parent directory
            try:
                rel_parent = os.path.relpath(os.path.dirname(src), input_root)
            except Exception:
                rel_parent = ""

            # build destination path: OUTPUT_ROOT / category / rel_parent / filename
            dst_dir = os.path.join(output_root, category, rel_parent)
            dst_path = os.path.join(dst_dir, os.path.basename(src))

            try:
                safe_copy(src, dst_path)
                self.control.log(f"Copied: {os.path.basename(src)} → {category}/{rel_parent or '.'}")
                self.control.preview_file(dst_path)  # update thumbnail from the copied file
            except Exception as e:
                self.control.log(f"ERROR copying {src} -> {dst_path}: {e}")

            processed += 1
            self.control.update_progress((processed / total_tasks) * 100)
            # small sleep to allow animation/thumbnail transitions to be visible
            time.sleep(0.04)

        self.control.on_worker_done()

# ----------------------
# GUI Application
# ----------------------
class AppUI:
    def __init__(self, root):
        self.root = root
        self.task_queue = queue.Queue()
        self.worker = None

        # UI style
        if tb:
            self.style = tb.Style(theme="darkly")
            self.main = tb.Frame(self.root, padding=(12, 12))
            self.main.pack(fill="both", expand=True)
        else:
            self.style = ttk.Style()
            self.main = ttk.Frame(self.root, padding=(12, 12))
            self.main.pack(fill="both", expand=True)

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        # Header
        header_frame = ttk.Frame(self.main)
        header_frame.pack(fill="x")
        title = ttk.Label(header_frame, text="Image Sorter", font=("Segoe UI", 18, "bold"))
        title.pack(side="left")
        subtitle = ttk.Label(header_frame, text="(Preserves folder structure inside each category)", font=("Segoe UI", 9))
        subtitle.pack(side="left", padx=(10, 0))

        # Input / Output selection
        io_frame = ttk.Frame(self.main)
        io_frame.pack(fill="x", pady=(12, 8))

        # Input
        in_label = ttk.Label(io_frame, text="Input Folder:")
        in_label.grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(io_frame, textvariable=self.input_var, width=60)
        self.input_entry.grid(row=0, column=1, padx=6)
        in_btn = ttk.Button(io_frame, text="Browse", command=self.choose_input)
        in_btn.grid(row=0, column=2)

        # Output
        out_label = ttk.Label(io_frame, text="Output Folder:")
        out_label.grid(row=1, column=0, sticky="w", pady=(6,0))
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(io_frame, textvariable=self.output_var, width=60)
        self.output_entry.grid(row=1, column=1, padx=6, pady=(6,0))
        out_btn = ttk.Button(io_frame, text="Browse", command=self.choose_output)
        out_btn.grid(row=1, column=2, pady=(6,0))

        # Drag & Drop area and options
        drop_frame = ttk.LabelFrame(self.main, text="Drop Files or Folders (explanation below)")
        drop_frame.pack(fill="x", pady=(10, 8))
        self.drop_listbox = tk.Listbox(drop_frame, height=4)
        self.drop_listbox.pack(side="left", fill="both", expand=True, padx=(8,0), pady=8)
        drop_scroll = ttk.Scrollbar(drop_frame, orient="vertical", command=self.drop_listbox.yview)
        drop_scroll.pack(side="left", fill="y", pady=8)
        self.drop_listbox.config(yscrollcommand=drop_scroll.set)
        info = ttk.Label(drop_frame, text="Drop a folder to set input root. Drop files to queue just those files.\n"
                                          "Relative folder structure is preserved inside each category.")
        info.pack(side="right", padx=8)

        # Preview and controls
        ctrl_frame = ttk.Frame(self.main)
        ctrl_frame.pack(fill="x", pady=(10, 6))

        # Thumbnail preview
        # preview_frame = ttk.LabelFrame(ctrl_frame, text="Thumbnail Preview")
        # preview_frame.pack(side="left", padx=(0,10))
        # self.thumb_label = ttk.Label(preview_frame, text="No preview", width=36, anchor="center")
        # self.thumb_label.pack(padx=12, pady=12)

        # Controls area
        right_ctrl = ttk.Frame(ctrl_frame)
        right_ctrl.pack(side="left", fill="both", expand=True)

        # Categories info
        cat_frame = ttk.Frame(right_ctrl)
        cat_frame.pack(fill="x")
        cat_label = ttk.Label(cat_frame, text="Categories (min resolution): ", font=("Segoe UI", 10, "bold"))
        cat_label.pack(anchor="w")
        cats = ", ".join([f"{k}({v[0]}×{v[1]})" for k,v in RES_CATEGORIES.items()])
        ttk.Label(cat_frame, text=cats, wraplength=360).pack(anchor="w")

        # Buttons
        btn_frame = ttk.Frame(right_ctrl)
        btn_frame.pack(fill="x", pady=(10,0))
        self.start_btn = ttk.Button(btn_frame, text="Start Copying", command=self.start_job)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel_job, state="disabled")
        self.cancel_btn.pack(side="left", padx=(8,0))

        # Progress bars
        progress_frame = ttk.Frame(self.main)
        progress_frame.pack(fill="x", pady=(8,0))
        ttk.Label(progress_frame, text="Progress:").pack(anchor="w")
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x")
        # spinner for activity
        self.spinner = ttk.Progressbar(progress_frame, orient="horizontal", mode="indeterminate", maximum=200)
        self.spinner.pack(fill="x", pady=(6,0))
        self.spinner.stop()
        self.spinner_idx = 0

        # Log
        log_frame = ttk.LabelFrame(self.main, text="Log")
        log_frame.pack(fill="both", expand=True, pady=(10,0))
        self.log_text = tk.Text(log_frame, height=10, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _bind_events(self):
        # listbox selection updates thumbnail
        self.drop_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        # drag & drop: try to register if available
        if DND_AVAILABLE:
            # our root is likely TkinterDnD.Tk created by caller
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                # fallback: no drag support
                pass

    # ----------------------
    # UI helpers
    # ----------------------
    def choose_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_var.set(folder)

    def choose_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def _on_drop(self, event):
        # event.data may contain multiple paths; splitlist handles the format
        try:
            paths = self.root.splitlist(event.data)
        except Exception:
            # fallback simple split
            paths = event.data.split()
        for p in paths:
            p = p.strip()
            if not p:
                continue
            self.drop_listbox.insert(tk.END, p)
            if os.path.isdir(p):
                # set input root automatically
                self.input_var.set(p)

    def _on_listbox_select(self, event):
        sel = event.widget.curselection()
        if not sel:
            return
        idx = sel[0]
        path = event.widget.get(idx)
        # if a file path, show preview
        if os.path.isfile(path) and path.lower().endswith(IMAGE_EXTENSIONS):
            self._animate_thumbnail(path)

    def preview_file(self, path):
        # called from background worker to show the most recently copied file
        self.root.after(0, lambda: self._animate_thumbnail(path))

    def _animate_thumbnail(self, path):
        # load thumbnail then perform a simple scale animation
        try:
            img = Image.open(path)
            img.thumbnail((420, 320))
            # create a sequence of scaled images for a simple "pop" animation
            frames = []
            w, h = img.size
            for step in (0.6, 0.8, 1.0):
                sw, sh = max(1, int(w * step)), max(1, int(h * step))
                f = img.resize((sw, sh), Image.LANCZOS)
                frames.append(ImageTk.PhotoImage(f))
        except Exception:
            return

        # display frames quickly
        def play(i=0):
            if i >= len(frames):
                # keep final frame
                self.thumb_label.config(image=frames[-1], text="")
                self.thumb_label.image = frames[-1]
                return
            self.thumb_label.config(image=frames[i], text="")
            self.thumb_label.image = frames[i]
            self.root.after(40, lambda: play(i+1))
        play()

    def log(self, message: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {message}\n")
        self.log_text.see("end")

    def update_progress(self, percent: float):
        # percent: 0..100
        self.progress['value'] = percent
        # ensure UI refresh
        self.root.update_idletasks()

    # ----------------------
    # Job control
    # ----------------------
    def start_job(self):
        input_root = self.input_var.get().strip()
        output_root = self.output_var.get().strip()

        if not input_root or not os.path.isdir(input_root):
            messagebox.showerror("Error", "Please select a valid input folder.")
            return
        if not output_root or not os.path.isdir(output_root):
            messagebox.showerror("Error", "Please select a valid output folder.")
            return

        # build list of files to process
        files_to_process = []

        # Add any files listed in drop listbox first (they may be outside input_root)
        for i in range(self.drop_listbox.size()):
            p = self.drop_listbox.get(i)
            if os.path.isfile(p) and p.lower().endswith(IMAGE_EXTENSIONS):
                files_to_process.append(p)

        # Walk the input_root for all image files
        for root_dir, dirs, files in os.walk(input_root):
            for fname in files:
                if fname.lower().endswith(IMAGE_EXTENSIONS):
                    files_to_process.append(os.path.join(root_dir, fname))

        if not files_to_process:
            messagebox.showinfo("Nothing to do", "No image files found to copy.")
            return

        # populate the queue
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
        for f in files_to_process:
            self.task_queue.put({
                "src": f,
                "input_root": input_root,
                "output_root": output_root
            })

        # disable start, enable cancel
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.spinner.start(10)
        self.log(f"Starting job: {len(files_to_process)} files")

        # start worker thread
        self.worker = CopyWorker(self.task_queue, control=self)
        self.worker.start()

    def cancel_job(self):
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.log("Cancellation requested. Waiting for worker to stop...")
            self.cancel_btn.config(state="disabled")

    def on_worker_done(self):
        self.spinner.stop()
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.log("Job finished.")
        # ensure full progress
        self.update_progress(100)

# ----------------------
# Entry point
# ----------------------
def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    root.title("Image Sorter")
    root.geometry("820x680")
    # choose a modern icon if you want; leave default otherwise

    app = AppUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
    app.mainloop()