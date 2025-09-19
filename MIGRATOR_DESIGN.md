Migration Script Design
=======================

Goal
----
Provide a single Python CLI that migrates a folder of iOS-style photos/videos into Android-compatible Motion Photos. It should:
- Scan an input directory (optionally recursive).
- Identify image/video pairs that share a basename (e.g., IMG_0001.HEIC + IMG_0001.MOV).
- Convert the photo to JPEG when needed (HEIC/PNG/etc → JPEG) for muxing.
- Mux the JPEG + video into a Motion Photo (JPEG with XMP GCamera tags and appended video bytes).
- Copy all remaining, unpaired files to the output directory as-is.
- Run an initial dry run that summarizes what will happen and supports interactive options.

Supported inputs
----------------
- Images: .jpg, .jpeg, .heic, .png (case-insensitive)
- Videos: .mov, .mp4 (case-insensitive)
- Others: copied as-is but not paired/muxed.

Pairing rules
-------------
- Basename match: files are paired if they share the same filename stem (e.g., IMG_1234.*).
- If multiple image candidates exist for a basename, priority is: jpeg > heic > png.
- If multiple video candidates exist, priority is: mov > mp4.
- Ambiguous cases are reported; the highest-priority pair is used for muxing.

Behavior
--------
1) Dry run (always first):
   - Counts by extension.
   - Count of pairable basenames and the final number of pairs.
   - Counts of images-without-video, videos-without-image, ambiguous basenames, and unsupported files.

2) Interactive options after the summary:
   - Option 1: Proceed with migration.
     - For each selected pair:
       - If photo is JPEG: use directly.
       - If photo is HEIC/PNG: convert to temporary JPEG and use that.
       - Mux JPEG + video into Motion Photo via existing `MotionPhotoMuxer.convert()` (uses exiftool fallback).
       - Output filename: `<basename>.jpg` in output directory.
     - Copy all unpaired files to output directory unchanged.
   - Option 2: List detailed file paths by category; then re-prompt.
   - Option 3: (reserved/ignored).

3) Non-interactive flags:
   - `--dry-run` to print the summary and exit.
   - `--yes` to proceed without prompts (useful for scripts).

Conversion strategy
-------------------
- HEIC/PNG → JPEG for muxing:
  - Prefer macOS `sips` when available (best for HEIC).
  - Fallback to Pillow if available for PNG/JPEG (may not support HEIC).
  - Fallback to `ffmpeg` if available.
  - Report a clear error if none of the above work for a given image.

Output policy
-------------
- Output directory is provided via `--output` (defaults to `./output`).
- Motion Photos overwrite existing files with the same name unless `--no-overwrite` is set (default is overwrite for simplicity).
- Unpaired files are copied as-is, preserving filenames.

Dependencies
------------
- Python 3.8+
- For muxing, this project’s `MotionPhotoMuxer.py` (with exiftool fallback).
- exiftool (recommended): `brew install exiftool` on macOS.
- Optional for conversion: `sips` (macOS), Pillow, or `ffmpeg`.

Edge cases and notes
--------------------
- Videos encoded with HEVC may be less reliable as Motion Photos; H.264 tends to work better.
- Extremely large batches: the tool processes sequentially and reports progress; no parallelism by default.
- Ambiguous basenames: the chosen pair is reported; alternates are listed under details.

