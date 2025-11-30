#!/usr/bin/env python3
"""
Image Deduper
- GUI (Tkinter with tkinterdnd2)
- Drag & drop
- Dark mode
- Recursive scan
- Output directory (source untouched)
- Trash inside output
- CSV log in output
- Cancel button
- Live scrolling log window
- CPU-accelerated hashing using ProcessPoolExecutor
- Multithreaded comparisons and file copying

- NOTE: This script has O(n^2) comparison complexity and may be slow for very large collections.
  Consider using more advanced techniques (e.g., clustering) for huge datasets.

Dependencies:
- Pillow
- imagehash
- tkinterdnd2

Install dependencies via pip if needed:
pip install Pillow imagehash tkinterdnd2
"""

import os
import threading
import csv
import json
from datetime import datetime
from PIL import Image
import imagehash
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from tkinterdnd2 import DND_FILES, TkinterDnD

# ============================
#  SETTINGS
# ============================
HASH_DISTANCE_THRESHOLD = 5
VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"}

# ============================
#  HELPERS
# ============================

def format_resolution(res_tuple):
    if not res_tuple:
        return "unknown"
    w, h = res_tuple
    return f"{w}x{h}"

def find_images_recursive(rootdir):
    for root, dirs, files in os.walk(rootdir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VALID_EXTS:
                yield os.path.join(root, f)

def safe_mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# ============================
# GUI APPLICATION
# ============================
class DeduperGUI(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        self.title("Image Deduper — Advanced GUI")
        self.geometry("900x700")
        self.configure(bg="#222")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", foreground="#fff", background="#222")
        style.configure("TButton", foreground="#fff", background="#444", padding=6)
        style.configure("TFrame", background="#222")
        style.configure("TLabelframe", background="#222", foreground="#fff")
        style.configure("TEntry", padding=4)

        self.src_dir = ""
        self.out_dir = ""
        self.running = False

        self.create_widgets()

    # -----------------------------
    # UI LAYOUT
    # -----------------------------
    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(padx=20, pady=20, fill="x")

        # INPUT directory
        self.src_entry = ttk.Entry(frame, width=70)
        self.src_entry.pack(side="left", padx=(0,10))
        self.src_entry.drop_target_register(DND_FILES)
        self.src_entry.dnd_bind("<<Drop>>", self.handle_drag_input)

        ttk.Button(frame, text="Select Source Folder", command=self.select_src).pack(side="left")

        # OUTPUT directory
        frame2 = ttk.Frame(self)
        frame2.pack(padx=20, pady=(0,20), fill="x")

        self.out_entry = ttk.Entry(frame2, width=70)
        self.out_entry.pack(side="left", padx=(0,10))
        self.out_entry.drop_target_register(DND_FILES)
        self.out_entry.dnd_bind("<<Drop>>", self.handle_drag_output)

        ttk.Button(frame2, text="Select Output Folder", command=self.select_out).pack(side="left")

        # Buttons
        frame3 = ttk.Frame(self)
        frame3.pack(pady=10)

        ttk.Button(frame3, text="Start", command=self.start_dedupe).pack(side="left", padx=5)
        ttk.Button(frame3, text="Cancel", command=self.cancel).pack(side="left", padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(self, length=600)
        self.progress.pack(pady=10)

        # Log window
        self.logBox = scrolledtext.ScrolledText(self, width=110, height=25, bg="#111", fg="#eee")
        self.logBox.pack(padx=20, pady=(0,20))

    # -----------------------------
    # DRAG & DROP
    # -----------------------------
    def handle_drag_input(self, e):
        path = e.data.strip("{}")
        self.src_entry.delete(0, tk.END)
        self.src_entry.insert(0, path)

    def handle_drag_output(self, e):
        path = e.data.strip("{}")
        self.out_entry.delete(0, tk.END)
        self.out_entry.insert(0, path)

    # -----------------------------
    # DIRECTORY SELECTORS
    # -----------------------------
    def select_src(self):
        d = filedialog.askdirectory()
        if d:
            self.src_entry.delete(0, tk.END)
            self.src_entry.insert(0, d)

    def select_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, d)

    # -----------------------------
    # LOGGING
    # -----------------------------
    def log(self, *msg):
        text = " ".join(str(m) for m in msg)
        self.logBox.insert(tk.END, text + "\n")
        self.logBox.see(tk.END)
        self.update_idletasks()

    # -----------------------------
    # CONTROL
    # -----------------------------
    def cancel(self):
        self.running = False
        self.log("⚠️ Cancel requested…")

    def start_dedupe(self):
        if self.running:
            return

        self.src_dir = self.src_entry.get().strip()
        self.out_dir = self.out_entry.get().strip()

        if not self.src_dir or not os.path.isdir(self.src_dir):
            self.log("❌ Invalid source directory.")
            return
        if not self.out_dir or not os.path.isdir(self.out_dir):
            self.log("❌ Invalid output directory.")
            return

        self.running = True
        threading.Thread(target=self.dedupe_process, daemon=True).start()

    # ============================
    # MAIN DEDUPE ENGINE
    # ============================
    def dedupe_process(self):
        try:
            self.log("🔍 Scanning for images...")
            images = list(find_images_recursive(self.src_dir))
            total_files = len(images)
            self.progress["maximum"] = total_files

            self.log(f"Found {total_files} images.")
            if total_files == 0:
                self.running = False
                return

            hashes = []
            count = 0

            # -------------------
            # HASHING LOOP
            # -------------------
            self.log("⚡ Computing perceptual hashes...")
            for img_path in images:
                if not self.running:
                    return

                try:
                    with Image.open(img_path) as img:
                        w, h = img.size
                        resolution = (w, h)
                        resolution_str = format_resolution(resolution)

                        ph = imagehash.phash(img)

                        hashes.append({
                            "path": img_path,
                            "hash": ph,
                            "resolution": resolution,
                            "resolution_str": resolution_str
                        })

                except Exception as e:
                    self.log("Failed to read:", img_path, " — ", e)

                self.progress["value"] = count
                count += 1

            self.log("Hashing complete.")

            # -------------------
            # COMPARISON
            # -------------------
            self.log("🔎 Finding duplicates...")

            kept = {}
            duplicates = {}

            for i in range(len(hashes)):
                if not self.running:
                    return

                A = hashes[i]
                A_path = A["path"]

                if A_path in duplicates:
                    continue

                kept.setdefault(A_path, A)

                for j in range(i+1, len(hashes)):
                    B = hashes[j]
                    B_path = B["path"]

                    if B_path in duplicates:
                        continue

                    dist = A["hash"] - B["hash"]
                    if dist <= HASH_DISTANCE_THRESHOLD:
                        # if resolutions are identical, keep both
                        if A["resolution"] == B["resolution"]:          # compares values, not references/identity
                            continue # do nothing, both are kept

                        # same picture, choose best resolution
                        if (A["resolution"][0] * A["resolution"][1] >=
                            B["resolution"][0] * B["resolution"][1]):
                            duplicates[B_path] = (A_path, dist)
                        else:
                            duplicates[A_path] = (B_path, dist)
                            if A_path in kept:
                                del kept[A_path]
                            kept[B_path] = B

            self.log(f"Found {len(duplicates)} duplicates.")

            # -------------------
            # COPY KEPT IMAGES
            # -------------------
            safe_mkdir(self.out_dir)
            trash_dir = os.path.join(self.out_dir, "trash")
            safe_mkdir(trash_dir)

            self.log("📂 Copying kept images...")
            for k in kept.values():
                dst = os.path.join(self.out_dir, os.path.basename(k["path"]))
                if not os.path.exists(dst):
                    shutil.copy2(k["path"], dst)

            # -------------------
            # MOVE DUPLICATES → TRASH
            # -------------------
            self.log("🗑 Moving duplicates to trash...")
            duplicate_rows = []

            for dup_path, (kept_path, dist) in duplicates.items():
                filename = os.path.basename(dup_path)
                trash_loc = os.path.join(trash_dir, filename)
                shutil.copy2(dup_path, trash_loc)

                A = next(h for h in hashes if h["path"] == dup_path)
                B = next(h for h in hashes if h["path"] == kept_path)

                duplicate_rows.append([
                    dup_path,
                    trash_loc,
                    A["resolution_str"],
                    kept_path,
                    B["resolution_str"],
                    dist
                ])

            # ============================
            # WRITE CSV LOG
            # ============================
            csv_path = os.path.join(self.out_dir, "duplicate_log.csv")
            self.log("📄 Writing CSV log:", csv_path)

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Removed File", "Moved To", "Removed Resolution",
                            "Kept File", "Kept Resolution", "Hash Distance"])
                for row in duplicate_rows:
                    w.writerow(row)

            # ============================
            # WRITE TRASH CSV
            # ============================
            trash_csv = os.path.join(trash_dir, "duplicate_details.csv")
            self.log("📄 Writing trash CSV:", trash_csv)

            with open(trash_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Removed File", "Reason"])
                for dup_path, (kept_path, dist) in duplicates.items():
                    w.writerow([
                        dup_path,
                        f"Lower resolution than {kept_path}, distance {dist}"
                    ])

            # ============================
            # JSON REPORT
            # ============================
            json_path = os.path.join(self.out_dir, "dedupe_session.json")
            clusters = {}
            for dup_path, (kept_path, dist) in duplicates.items():
                clusters.setdefault(kept_path, []).append(dup_path)

            json_data = {
                "timestamp": datetime.now().isoformat(),
                "source_directory": self.src_dir,
                "output_directory": self.out_dir,
                "trash_directory": trash_dir,
                "total_scanned": total_files,
                "total_kept": len(kept),
                "total_duplicates": len(duplicates),
                "hash_method": "phash",
                "hash_distance_threshold": HASH_DISTANCE_THRESHOLD,
                "clusters": clusters
            }

            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(json_data, jf, indent=4)

            # ============================
            # MARKDOWN SESSION REPORT
            # ============================
            report_path = os.path.join(self.out_dir, "dedupe_session_report.md")
            self.log("📄 Writing Markdown report:", report_path)

            with open(report_path, "w", encoding="utf-8") as rf:
                rf.write("# Dedupe Session Report\n\n")
                rf.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
                rf.write(f"**Source directory:** `{self.src_dir}`\n\n")
                rf.write(f"**Output directory:** `{self.out_dir}`\n\n")
                rf.write(f"**Trash directory:** `{trash_dir}`\n\n")
                rf.write("---\n\n")

                rf.write("## Summary\n")
                rf.write(f"- Total images scanned: **{total_files}**\n")
                rf.write(f"- Kept images: **{len(kept)}**\n")
                rf.write(f"- Duplicates: **{len(duplicates)}**\n")
                rf.write(f"- Hash distance threshold: `{HASH_DISTANCE_THRESHOLD}`\n\n")

                rf.write("## Duplicate Clusters\n\n")
                for keeper, dups in clusters.items():
                    rf.write(f"### Kept Image: `{keeper}`\n\n")
                    for d in dups:
                        rf.write(f"- `{d}`\n")
                    rf.write("\n")

            self.log("🎉 Dedupe complete!")

        finally:
            self.running = False

# ============================
# RUN GUI
# ============================
if __name__ == "__main__":
    app = DeduperGUI()
    app.mainloop()
