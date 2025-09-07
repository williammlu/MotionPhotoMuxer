import argparse
import collections
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import logging

# Local muxer
import MotionPhotoMuxer as mux


IMAGE_EXTS = {".jpg", ".jpeg", ".heic", ".png"}
VIDEO_EXTS = {".mov", ".mp4"}

IMG_PRIORITY = [".jpg", ".jpeg", ".heic", ".png"]
VID_PRIORITY = [".mov", ".mp4"]


@dataclass
class Pair:
    base: str
    image: Path
    video: Path
    alternates_images: List[Path]
    alternates_videos: List[Path]


def is_image(p: Path) -> bool:
    return p.suffix.lower() in IMAGE_EXTS


def is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS


def scan_directory(root: Path, recurse: bool) -> List[Path]:
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Input directory invalid: {root}")
    return list(root.rglob("*")) if recurse else [p for p in root.iterdir()]


def group_by_basename(paths: List[Path]):
    by_base: Dict[str, Dict[str, List[Path]]] = {}
    others: List[Path] = []
    for p in paths:
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        base = p.stem
        if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
            d = by_base.setdefault(base, {"images": [], "videos": []})
            if ext in IMAGE_EXTS:
                d["images"].append(p)
            else:
                d["videos"].append(p)
        else:
            others.append(p)
    return by_base, others


def choose_candidate(paths: List[Path], priority: List[str]) -> Tuple[Optional[Path], List[Path]]:
    if not paths:
        return None, []
    # Sort by priority, keep first
    prio_map = {ext: i for i, ext in enumerate(priority)}
    sorted_paths = sorted(paths, key=lambda p: prio_map.get(p.suffix.lower(), 999))
    chosen = sorted_paths[0]
    alternates = [p for p in sorted_paths[1:]]
    return chosen, alternates


def build_pairs(by_base: Dict[str, Dict[str, List[Path]]]) -> Tuple[List[Pair], List[Path], List[Path], Dict[str, List[Path]]]:
    pairs: List[Pair] = []
    images_only: List[Path] = []
    videos_only: List[Path] = []
    ambiguous: Dict[str, List[Path]] = {}

    for base, buckets in by_base.items():
        imgs = buckets["images"]
        vids = buckets["videos"]
        img, img_alts = choose_candidate(imgs, IMG_PRIORITY)
        vid, vid_alts = choose_candidate(vids, VID_PRIORITY)
        if img and vid:
            pairs.append(Pair(base=base, image=img, video=vid, alternates_images=img_alts, alternates_videos=vid_alts))
            if img_alts or vid_alts:
                ambiguous[base] = [*img_alts, *vid_alts]
        elif img and not vid:
            images_only.extend(imgs)
        elif vid and not img:
            videos_only.extend(vids)
        else:
            # No valid image/video for this base (shouldn't happen since only bases with one of them are present)
            pass

    return pairs, images_only, videos_only, ambiguous


def summarize(paths: List[Path], pairs: List[Pair], images_only: List[Path], videos_only: List[Path], others: List[Path], ambiguous: Dict[str, List[Path]]):
    by_ext = collections.Counter(p.suffix.lower() for p in paths if p.is_file())
    print("Summary:")
    print(f"  Total files: {len(paths)}")
    print("  By extension:")
    for ext, cnt in sorted(by_ext.items()):
        print(f"    {ext or '<noext>'}: {cnt}")
    print(f"  Pairable basenames: {len(pairs)}")
    print(f"  Images without video: {len(images_only)}")
    print(f"  Videos without image: {len(videos_only)}")
    print(f"  Other files: {len(others)}")
    print(f"  Ambiguous basenames (multiple candidates): {len(ambiguous)}")


def list_details(pairs: List[Pair], images_only: List[Path], videos_only: List[Path], others: List[Path], ambiguous: Dict[str, List[Path]]):
    def _print_list(title: str, items: List[Path]):
        print(f"\n{title} ({len(items)}):")
        for p in sorted(items):
            print(f"  {p}")

    print("\nPairs (image + video):")
    for pr in pairs:
        print(f"  {pr.base}: {pr.image.name} + {pr.video.name}")
        if pr.alternates_images:
            print(f"    alt images: {[p.name for p in pr.alternates_images]}")
        if pr.alternates_videos:
            print(f"    alt videos: {[p.name for p in pr.alternates_videos]}")

    _print_list("Images without video", images_only)
    _print_list("Videos without image", videos_only)
    _print_list("Other files", others)

    print(f"\nAmbiguous basenames ({len(ambiguous)}):")
    for base, alts in sorted(ambiguous.items()):
        print(f"  {base}: {[p.name for p in alts]}")


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def has_cmd(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None


def convert_image_to_jpeg(src: Path, dest_dir: Path) -> Path:
    ensure_dir(dest_dir)
    out = dest_dir / (src.stem + ".jpg")
    ext = src.suffix.lower()

    if ext in {".jpg", ".jpeg"}:
        # Already JPEG; just copy to dest and use that path
        shutil.copy2(src, out)
        return out

    # Prefer macOS sips for HEIC/PNG
    if has_cmd("sips"):
        rc = os.system(f"sips -s format jpeg {src.as_posix()} --out {out.as_posix()} >/dev/null 2>&1")
        if rc == 0 and out.exists():
            return out

    # Fallback to Pillow (PNG likely; HEIC may not be supported)
    try:
        from PIL import Image  # type: ignore
        with Image.open(src) as im:
            rgb = im.convert("RGB")
            rgb.save(out, format="JPEG", quality=95)
            return out
    except Exception:
        pass

    # Fallback to ffmpeg
    if has_cmd("ffmpeg"):
        rc = os.system(f"ffmpeg -y -i {src.as_posix()} -q:v 2 {out.as_posix()} >/dev/null 2>&1")
        if rc == 0 and out.exists():
            return out

    raise RuntimeError(f"Failed to convert {src} to JPEG; install 'sips' (macOS), Pillow, or ffmpeg.")


def perform_migration(pairs: List[Pair], images_only: List[Path], videos_only: List[Path], others: List[Path], output: Path, overwrite: bool = True):
    ensure_dir(output)
    log = logging.getLogger("migrator")
    migrated = 0
    copied = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for pr in pairs:
            # Convert image to JPEG (if needed) into temp
            try:
                jpeg = convert_image_to_jpeg(pr.image, tmp)
            except Exception as e:
                log.error(f"Skipping pair {pr.base}: cannot convert image to JPEG: {e}")
                continue

            # Output motion photo filename will be basename.jpg
            out_file = output / (pr.base + ".jpg")
            if out_file.exists() and not overwrite:
                log.info(f"Skipping existing: {out_file}")
                continue
            mux.convert(jpeg, pr.video, output)
            migrated += 1

    # Copy remaining files as-is
    def _copy_all(paths: List[Path]):
        nonlocal copied
        for p in paths:
            dest = output / p.name
            if dest.exists():
                # Avoid clobbering a just-created Motion Photo; if names collide, keep existing
                continue
            shutil.copy2(p, dest)
            copied += 1

    _copy_all(images_only)
    _copy_all(videos_only)
    _copy_all(others)

    return migrated, copied


def main():
    parser = argparse.ArgumentParser(description="Batch migrate a folder into Motion Photos with dry-run and interactive options.")
    parser.add_argument("--input", type=Path, required=True, help="Input directory to scan")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for migrated files")
    parser.add_argument("--recurse", action="store_true", help="Recurse into subdirectories")
    parser.add_argument("--dry-run", action="store_true", help="Only analyze and print summary")
    parser.add_argument("--yes", action="store_true", help="Proceed without prompts")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing outputs")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=(logging.INFO if args.verbose else logging.WARNING), stream=sys.stdout)

    paths = scan_directory(args.input, args.recurse)
    by_base, others = group_by_basename(paths)
    pairs, images_only, videos_only, ambiguous = build_pairs(by_base)

    summarize(paths, pairs, images_only, videos_only, others, ambiguous)

    if args.dry_run and not args.yes:
        return 0

    def prompt_choice() -> str:
        print("\nOptions:")
        print("  1) Proceed with migration (copy all, mux pairs)")
        print("  2) List detailed file categories")
        print("  3) Exit")
        return input("Choose an option [1/2/3]: ").strip()

    if not args.yes:
        while True:
            choice = prompt_choice()
            if choice == "1":
                break
            elif choice == "2":
                list_details(pairs, images_only, videos_only, others, ambiguous)
            elif choice == "3" or choice.lower() in {"q", "quit", "exit"}:
                return 0
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    migrated, copied = perform_migration(
        pairs,
        images_only,
        videos_only,
        others,
        output=args.output,
        overwrite=not args.no_overwrite,
    )

    print("\nMigration complete:")
    print(f"  Motion Photos created: {migrated}")
    print(f"  Files copied (unpaired/other): {copied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

