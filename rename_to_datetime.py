"""Image Date Renamer (ISO Format)
Renames image files based on their EXIF DateTimeOriginal tag
to an ISO-like format: 'YYYY-MM-DDTHH-MM-SS'.
If the tag is missing, the original filename is retained.
Recursive directory scanning is supported but optional.

Dependencies:
- Pillow (PIL Fork) for EXIF data extraction.
- Tkinter for GUI components.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ExifTags
import shutil

# -------------------------------------------------------
# Global cancellation flag
# -------------------------------------------------------
cancel_processing = False


# -------------------------------------------------------
# Helper Functions
# -------------------------------------------------------

def get_iso_datetime(path):
    """
    Reads EXIF DateTimeOriginal and returns ISO-based filename:
    'YYYY-MM-DDTHH-MM-SS'
    Returns None if unavailable.
    """
    try:
        img = Image.open(path)
        exif_data = img._getexif()
        if not exif_data:
            return None

        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag == "DateTimeOriginal":
                # Example EXIF: "2022:05:14 13:47:59"
                date_part, time_part = value.split()

                yyyy, mm, dd = date_part.split(":")
                hh, mi, ss = time_part.split(":")

                # Create ISO-like filename:
                # 2022-05-14T13-47-59
                return f"{yyyy}-{mm}-{dd}T{hh}-{mi}-{ss}"

    except Exception:
        return None

    return None


def find_images(folder, recursive=False):
    """
    Returns a list of image file paths.
    """
    image_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
    collected = []

    if recursive:
        for root, dirs, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in image_exts:
                    collected.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            full = os.path.join(folder, f)
            if os.path.isfile(full):
                ext = os.path.splitext(f)[1].lower()
                if ext in image_exts:
                    collected.append(full)

    return collected


def unique_name(path):
    """
    Prevent overwriting. Adds suffix _1, _2, …
    """
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path

    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1

    return new_path


# -------------------------------------------------------
# Processing Logic
# -------------------------------------------------------

def start_processing():
    global cancel_processing
    cancel_processing = False  # reset on each run

    input_dir = input_path_var.get()
    output_dir = output_path_var.get()
    recursive = recursive_var.get()

    if not input_dir or not os.path.isdir(input_dir):
        messagebox.showerror("Error", "Please select a valid input directory.")
        return

    if not output_dir:
        messagebox.showerror("Error", "Please select an output directory.")
        return

    images = find_images(input_dir, recursive)
    total = len(images)

    if total == 0:
        messagebox.showinfo("Info", "No images found.")
        return

    progress["value"] = 0
    progress["maximum"] = total
    root.update_idletasks()

    renamed_count = 0
    skipped_count = 0

    for idx, img_path in enumerate(images, start=1):

        if cancel_processing:
            messagebox.showinfo("Cancelled", "Processing was cancelled.")
            return

        _, filename = os.path.split(img_path)
        name, ext = os.path.splitext(filename)

        date_str = get_iso_datetime(img_path)

        if date_str:
            new_filename = f"{date_str}{ext.lower()}"
        else:
            new_filename = filename
            skipped_count += 1

        dest_path = os.path.join(output_dir, new_filename)
        dest_path = unique_name(dest_path)

        shutil.copy2(img_path, dest_path)

        if date_str:
            renamed_count += 1

        progress["value"] = idx
        root.update_idletasks()

    messagebox.showinfo(
        "Done",
        f"Copied images: {total}\n"
        f"Renamed using EXIF: {renamed_count}\n"
        f"Kept original names: {skipped_count}"
    )


def cancel():
    global cancel_processing
    cancel_processing = True


# -------------------------------------------------------
# GUI Setup
# -------------------------------------------------------

root = tk.Tk()
root.title("Image Date Renamer (ISO Format)")
root.geometry("680x300")
root.resizable(False, False)

input_path_var = tk.StringVar()
output_path_var = tk.StringVar()
recursive_var = tk.BooleanVar()

# ------------------ Input Folder ------------------
frame1 = tk.Frame(root)
frame1.pack(pady=10, fill="x", padx=10)

tk.Label(frame1, text="Input Folder:").pack(anchor="w")
entry1 = tk.Entry(frame1, textvariable=input_path_var, width=60)
entry1.pack(side="left", padx=5)

tk.Button(frame1, text="Browse", command=lambda: input_path_var.set(filedialog.askdirectory())).pack(side="left")


# ------------------ Output Folder ------------------
frame2 = tk.Frame(root)
frame2.pack(pady=10, fill="x", padx=10)

tk.Label(frame2, text="Output Folder:").pack(anchor="w")
entry2 = tk.Entry(frame2, textvariable=output_path_var, width=60)
entry2.pack(side="left", padx=5)

tk.Button(frame2, text="Browse", command=lambda: output_path_var.set(filedialog.askdirectory())).pack(side="left")


# ------------------ Options ------------------
frame3 = tk.Frame(root)
frame3.pack(pady=5, fill="x", padx=10)

tk.Checkbutton(frame3, text="Scan recursively", variable=recursive_var).pack(anchor="w")


# ------------------ Progress Bar ------------------
frame4 = tk.Frame(root)
frame4.pack(pady=15, fill="x", padx=10)

progress = ttk.Progressbar(frame4, orient="horizontal", length=460, mode="determinate")
progress.pack()


# ------------------ Buttons ------------------
frame5 = tk.Frame(root)
frame5.pack(pady=10)

tk.Button(frame5, text="Start", command=start_processing, width=18).pack(side="left", padx=10)
tk.Button(frame5, text="Cancel", command=cancel, width=18).pack(side="left", padx=10)


root.mainloop()
