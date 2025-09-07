MotionPhotoMuxer
================

> **Note**
> I've switched back to Android for the time being. I do have access to an iPhone for testing, but
> likely won't be focusing on developing this much further.

Convert Apple Live Photos into Google Motion Photos commonly found on Android phones.

# Installation

As of right now, this script only has one dependency, `py3exiv2`. Unfortunately
this requires building a C++ library to install, so you need to install a C++ toolchain.

Using Ubuntu as an example:

~~~bash
sudo apt-get install build-essential python-all-dev libexiv2-dev libboost-python-dev python3 python3-pip python3-venv
python3 -m pip install -r requirements.txt
~~~
## Installing with docker

```bash
docker build -t motionphotomuxer .
# Folder
docker run --rm -v /path/to/dir:/data/input motionphotomuxer --dir /data/input --output /data/output --copyall
# Single photo and video
docker run --rm -v /path/to/dir:/data/input motionphotomuxer --photo /data/input/photo.jpg --video /data/input/video.mov --output /data/output
```

## Installing on a Pixel/Android Phone

* Install [Termux from the F-Droid App store](https://f-droid.org/en/packages/com.termux/)
* Install the following packages within Termux in order to satisfy the dependencies for `pyexiv2`:

~~~bash
'pkg install python3'
'pkg install openssl'
'pkg install git'
'pkg install build-essential'
'pkg install exiv2'
'pkg install boost-headers'
git clone https://github.com/mihir-io/MotionPhotoMuxer.git
python3 -m pip install -r MotionPhotoMuxer/requirements.txt
~~~

This should leave you with a working copy of MotionPhotoMuxer directly on your Pixel/other Android phone.
You may want to make sure Termux has the "Storage" permission granted from within the system settings, if
you plan on writing the output files to the `/sdcard/` partition.


# Usage

~~~
usage: MotionPhotoMuxer.py [-h] [--verbose] [--dir DIR] [--recurse] [--photo PHOTO] [--video VIDEO] [--output OUTPUT] [--copyall]

Merges a photo and video into a Microvideo-formatted Google Motion Photo

options:
  -h, --help       show this help message and exit
  --verbose        Show logging messages.
  --dir DIR        Process a directory for photos/videos. Takes precedence over --photo/--video
  --recurse        Recursively process a directory. Only applies if --dir is also provided
  --photo PHOTO    Path to the JPEG photo to add.
  --video VIDEO    Path to the MOV video to add.
  --output OUTPUT  Path to where files should be written out to.
  --copyall        Copy unpaired files to directory.
~~~

A JPEG photo and MOV or MP4 video must be provided. The code only does simple
error checking to see if the file extensions are `.jpg|.jpeg` and `.mov|.mp4`
respectively, so if the actual photo/video encoding is something funky, things
may not work right.

> **Note**
> The output motion photo tends to work more reliably in my experience if the input video is H.264 rather than HEVC.

This has been tested successfully on a couple photos taken on an iPhone 12 and
uploaded to Google Photos through a Pixel XL, but there hasn't been any
extensive testing done yet, so use at your own risk!

# Credit

This wouldn't have been possible without the excellent writeup on the process
of working with Motion Photos [here](https://medium.com/android-news/working-with-motion-photos-da0aa49b50c).

Batch Migration
---------------

In addition to converting a single pair, this repo now includes an interactive migration tool that scans a folder, reports what can be paired, and then migrates everything into an output directory.

Quick start (macOS):
- Install exiftool: `brew install exiftool`
- (Optional) For best HEIC/PNG → JPEG conversion, ensure either `sips` (macOS), Pillow, or `ffmpeg` is available.

Dry run only:
```
python3 motion_photo_migrator.py --input /path/to/input --output /path/to/output --dry-run --verbose
```

Interactive run:
```
python3 motion_photo_migrator.py --input /path/to/input --output /path/to/output
```
Flow:
- Step 1: Prints a summary of files found by extension, how many basenames can be paired (image+video), how many images/videos are unpaired, and how many other files exist.
- Option 1: Proceed with migration (create Motion Photos for pairs, copy all unpaired/other files).
- Option 2: List detailed file paths for each category, then re-prompt.
- Option 3: Exit.

Pairing rules:
- Pair by basename (e.g., `IMG_0001.HEIC` + `IMG_0001.MOV`).
- Images supported: `.jpg`, `.jpeg`, `.heic`, `.png`.
- Videos supported: `.mov`, `.mp4`.
- If multiple candidates exist per basename, priority is `jpeg > heic > png` for images, and `mov > mp4` for videos. The chosen pair is reported; alternates are listed as ambiguous.

Output behavior:
- Motion Photo result uses the basename with `.jpg` (e.g., `IMG_0001.jpg`).
- Unpaired files are copied as-is into the output directory.

Notes:
- The migrator uses `MotionPhotoMuxer.convert()` internally. If `pyexiv2` is not available, it falls back to `exiftool` to write XMP metadata (install with `brew install exiftool`).
