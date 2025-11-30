# Image-Processing-Python-Scripts

Implements a suite of python scripts for post data recovery processing.
It is designed with [TestDisk/PhotoRec](https://www.cgsecurity.org/wiki/TestDisk_Download) in mind as the data recovery tool.
Use PhotoRec specifically for image recovery.

## Dependencies

You need to have Python 3 installed on your system to run these scripts. You can download it from [python.org](https://www.python.org/downloads/).
Some scripts may require additional Python packages. You can install them using pip. For example:

```bash
pip install Pillow imagehash tkinterdnd2 ttkbootstrap PyQt5 pandas
```

Make sure to check the individual script files for any specific dependencies or instructions.
Refer to the comments at the top of each script for detailed usage instructions and dependencies.
Feel free to modify and use these scripts as needed for your image processing tasks!

## Scripts Included

- `sort_by_file_size.py`: Image copier and sorter with a GUI.
- `check_for_duplicates.py`: Identifies and removes duplicate images based on perceptual hashing.
- `duplicate_details_parser.py`: GUI for reviewing duplicate image pairs based on CSV output of `check_for_duplicates.py`.
- `rename_images_according_to_exif.py`: Batch renames image files according to their EXIF metadata (date etc.).

## Usage

Each script can be run from the command line. For example:

```bash
python3 sort_by_file_size.py
```

Make sure to navigate to the directory containing the script before running the command.

The scripts are meant to be run in the following order:

1. `sort_by_file_size.py` - to organize and copy images.
2. It is recommended to manually inspect the sorted images for any obvious issues (e.g., corrupted files) before proceeding.
3. `check_for_duplicates.py` - to identify and remove duplicates.
4. `duplicate_details_parser.py` - to review duplicates if needed.
5. `rename_to_datetime.py` - to rename images based on EXIF data and finalize the organization.
