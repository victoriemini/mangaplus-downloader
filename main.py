import os
import re
import sys
import json
import shutil
import logging
import argparse
import subprocess
from datetime import datetime

from dotenv import load_dotenv


parser = argparse.ArgumentParser(
    description="Download available Manga Plus chapters"
)

parser.add_argument(
    "--config",
    type=str,
    default="/config/config.env",
    help="Path to config.env",
)

parser.add_argument(
    "--manga-list",
    type=str,
    default="/config/manga_list.json",
    help="Path to manga_list.json",
)

args = parser.parse_args()

load_dotenv(dotenv_path=args.config)

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/downloads")
MANGA_LIBRARY = os.getenv("MANGA_LIBRARY", "/manga")
LOG_DIR = os.getenv("LOG_DIR", "/logs")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(MANGA_LIBRARY, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


try:
    with open(args.manga_list, "r", encoding="utf-8") as file:
        manga_list = json.load(file)

except FileNotFoundError:
    print(f"Manga list not found: {args.manga_list}")
    sys.exit(1)

except json.JSONDecodeError as error:
    print(f"Invalid manga JSON: {error}")
    sys.exit(1)


date_string = datetime.now().strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(
                LOG_DIR,
                f"manga-downloader-{date_string}.log",
            )
        ),
        logging.StreamHandler(),
    ],
)


def find_cbz_files(directory):
    files = []

    if not os.path.exists(directory):
        return files

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(".cbz"):
                files.append(
                    os.path.join(root, filename)
                )

    return files


def extract_chapter_number(filename):
    patterns = [
        r"ch\.\s*(\d+(?:\.\d+)?[a-zA-Z]*)",
        r"\bc(\d+(?:\.\d+)?[a-zA-Z]*)",
        r"chapter[\s_-]*(?:#\s*)?(\d+(?:\.\d+)?[a-zA-Z]*)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            filename,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def cleanup_empty_directories(directory):
    if not os.path.exists(directory):
        return

    for root, dirs, files in os.walk(
        directory,
        topdown=False,
    ):
        if root == directory:
            continue

        if not dirs and not files:
            try:
                os.rmdir(root)
            except OSError:
                pass


def download_manga(manga_name, manga_id):
    logging.info(
        f"Checking {manga_name} "
        f"(Manga Plus title ID: {manga_id})"
    )

    # Keep each MangaPlus Title ID isolated.
    #
    # This prevents different language editions or titles
    # with identical official names from sharing the same
    # mloader manifest.
    manga_work_dir = os.path.join(
        DOWNLOAD_DIR,
        str(manga_id),
    )

    os.makedirs(
        manga_work_dir,
        exist_ok=True,
    )

    cbz_before = set(
        find_cbz_files(manga_work_dir)
    )

    # No "-l" here.
    #
    # mloader will inspect all currently available chapters
    # for this title. Its resume manifest prevents already
    # completed chapters from being downloaded again.
    command = [
        "mloader",
        "-t",
        str(manga_id),
        "-o",
        manga_work_dir,
    ]

    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    # Reprint mloader output so it remains visible
    # in Docker / API / n8n logs.
    if process.stdout:
        print(
            process.stdout,
            end="",
        )

    if process.stderr:
        print(
            process.stderr,
            end="",
            file=sys.stderr,
        )

    output = (
        (process.stdout or "")
        + (process.stderr or "")
    )

    # Read mloader-ng's own download summary.
    summary_match = re.search(
        r"Download summary:\s*"
        r"downloaded=(\d+),\s*"
        r"skipped_manifest=(\d+),\s*"
        r"failed=(\d+)",
        output,
        re.IGNORECASE,
    )

    mloader_downloaded = 0
    mloader_skipped = 0
    mloader_failed = 0

    if summary_match:
        mloader_downloaded = int(
            summary_match.group(1)
        )

        mloader_skipped = int(
            summary_match.group(2)
        )

        mloader_failed = int(
            summary_match.group(3)
        )

    cbz_after = set(
        find_cbz_files(manga_work_dir)
    )

    new_cbz_files = list(
        cbz_after - cbz_before
    )

    manga_directory = os.path.join(
        MANGA_LIBRARY,
        manga_name,
    )

    os.makedirs(
        manga_directory,
        exist_ok=True,
    )

    downloaded_chapters = []
    downloaded_files = []

    skipped_chapters = []
    skipped_files = []

    # Process EVERY new CBZ instead of only the newest one.
    new_cbz_files.sort(
        key=os.path.getmtime
    )

    for downloaded_file in new_cbz_files:
        original_filename = os.path.basename(
            downloaded_file
        )

        chapter_number = extract_chapter_number(
            original_filename
        )

        if chapter_number:
            final_filename = (
                f"{manga_name} ch. "
                f"{chapter_number}.cbz"
            )
        else:
            logging.warning(
                "Could not determine chapter number "
                f"from {original_filename}"
            )

            final_filename = original_filename

        destination = os.path.join(
            manga_directory,
            final_filename,
        )

        if os.path.exists(destination):
            logging.info(
                f"Already exists in library: "
                f"{destination}"
            )

            os.remove(downloaded_file)

            skipped_files.append(
                final_filename
            )

            if chapter_number:
                skipped_chapters.append(
                    chapter_number
                )

            continue

        shutil.move(
            downloaded_file,
            destination,
        )

        logging.info(
            f"Saved: {destination}"
        )

        downloaded_files.append(
            final_filename
        )

        if chapter_number:
            downloaded_chapters.append(
                chapter_number
            )

    cleanup_empty_directories(
        manga_work_dir
    )

    downloaded_count = len(
        downloaded_files
    )

    skipped_existing_count = len(
        skipped_files
    )

    # mloader can occasionally complete some chapters
    # while reporting failures for others.
    if (
        process.returncode != 0
        or mloader_failed > 0
    ):
        if (
            downloaded_count > 0
            or skipped_existing_count > 0
        ):
            logging.warning(
                f"{manga_name} completed partially: "
                f"{downloaded_count} new, "
                f"{mloader_failed} failed"
            )

            return {
                "name": manga_name,
                "id": str(manga_id),
                "status": "partial",
                "downloaded_count": downloaded_count,
                "chapters": downloaded_chapters,
                "files": downloaded_files,
                "skipped_existing": skipped_existing_count,
                "skipped_manifest": mloader_skipped,
                "failed_chapters": mloader_failed,
                "exit_code": process.returncode,
            }

        logging.error(
            f"mloader failed for {manga_name}"
        )

        return {
            "name": manga_name,
            "id": str(manga_id),
            "status": "failed",
            "downloaded_count": 0,
            "skipped_manifest": mloader_skipped,
            "failed_chapters": (
                mloader_failed
                if mloader_failed > 0
                else 1
            ),
            "exit_code": process.returncode,
        }

    # At least one new chapter was successfully moved
    # into the final manga library.
    if downloaded_count > 0:
        logging.info(
            f"{manga_name}: "
            f"{downloaded_count} new chapter(s) saved"
        )

        return {
            "name": manga_name,
            "id": str(manga_id),
            "status": "downloaded",
            "downloaded_count": downloaded_count,
            "chapters": downloaded_chapters,
            "files": downloaded_files,
            "skipped_existing": skipped_existing_count,
            "skipped_manifest": mloader_skipped,
        }

    # Files were generated, but they already existed
    # in the final library.
    if skipped_existing_count > 0:
        logging.info(
            f"{manga_name}: "
            f"{skipped_existing_count} chapter(s) "
            f"already existed in library"
        )

        return {
            "name": manga_name,
            "id": str(manga_id),
            "status": "skipped",
            "downloaded_count": 0,
            "skipped_existing": skipped_existing_count,
            "chapters": skipped_chapters,
            "files": skipped_files,
            "skipped_manifest": mloader_skipped,
        }

    # Nothing new was generated because every currently
    # available chapter is already in the manifest.
    if mloader_skipped > 0:
        logging.info(
            f"{manga_name} is already up to date "
            f"({mloader_skipped} chapter(s) "
            f"skipped by manifest)"
        )

        return {
            "name": manga_name,
            "id": str(manga_id),
            "status": "up_to_date",
            "downloaded_count": 0,
            "skipped_manifest": mloader_skipped,
        }

    # mloader completed successfully but did not produce
    # or skip any chapter.
    logging.warning(
        f"No available CBZ detected for {manga_name}"
    )

    return {
        "name": manga_name,
        "id": str(manga_id),
        "status": "no_file",
        "downloaded_count": 0,
        "mloader_downloaded": mloader_downloaded,
    }


def main():
    results = []

    for manga in manga_list:
        manga_name = manga.get("name")
        manga_id = manga.get("id")

        if not manga_name or not manga_id:
            results.append(
                {
                    "name": (
                        manga_name
                        or "Unknown"
                    ),
                    "status": "failed",
                    "downloaded_count": 0,
                    "error": "Missing name or id",
                }
            )

            continue

        result = download_manga(
            manga_name,
            manga_id,
        )

        results.append(result)

    # "downloaded" is now the number of NEW CHAPTERS,
    # rather than the number of manga series.
    #
    # Your n8n condition:
    #
    # result.downloaded > 0
    #
    # continues to work exactly as before.
    downloaded_total = sum(
        result.get(
            "downloaded_count",
            0,
        )
        for result in results
    )

    up_to_date_total = sum(
        1
        for result in results
        if result["status"] == "up_to_date"
    )

    skipped_total = sum(
        result.get(
            "skipped_existing",
            0,
        )
        for result in results
    )

    no_file_total = sum(
        1
        for result in results
        if result["status"] == "no_file"
    )

    partial_total = sum(
        1
        for result in results
        if result["status"] == "partial"
    )

    failed_total = sum(
        1
        for result in results
        if result["status"] == "failed"
    )

    failed_chapters_total = sum(
        result.get(
            "failed_chapters",
            0,
        )
        for result in results
    )

    summary = {
        "downloaded": downloaded_total,
        "up_to_date": up_to_date_total,
        "skipped": skipped_total,
        "no_file": no_file_total,
        "partial": partial_total,
        "failed": failed_total,
        "failed_chapters": failed_chapters_total,
        "results": results,
    }

    # Structured output consumed by api.py / n8n.
    print(
        "MANGAPLUS_RESULT="
        + json.dumps(
            summary,
            ensure_ascii=False,
        )
    )

    if (
        summary["failed"] > 0
        or summary["partial"] > 0
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
