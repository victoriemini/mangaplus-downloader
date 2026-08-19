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
    description="Download latest Manga Plus chapters"
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
        r"chapter[\s_-]*(\d+(?:\.\d+)?[a-zA-Z]*)",
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

    cbz_before = set(
        find_cbz_files(DOWNLOAD_DIR)
    )

    command = [
        "mloader",
        "-t",
        str(manga_id),
        "-l",
        "-o",
        DOWNLOAD_DIR,
    ]

    try:
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

        # Reprint mloader output so it still appears
        # in Docker and n8n execution logs.
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

    except subprocess.CalledProcessError as error:
        if error.stdout:
            print(
                error.stdout,
                end="",
            )

        if error.stderr:
            print(
                error.stderr,
                end="",
                file=sys.stderr,
            )

        logging.error(
            f"mloader failed for {manga_name}: "
            f"{error}"
        )

        return {
            "name": manga_name,
            "status": "failed",
            "error": str(error),
        }

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

    if mloader_failed > 0:
        logging.error(
            f"mloader reported {mloader_failed} "
            f"failed chapter(s) for {manga_name}"
        )

        return {
            "name": manga_name,
            "status": "failed",
            "error": (
                f"{mloader_failed} chapter(s) failed"
            ),
        }

    cbz_after = set(
        find_cbz_files(DOWNLOAD_DIR)
    )

    new_cbz_files = list(
        cbz_after - cbz_before
    )

    # Nothing new was created, but mloader says
    # chapters were already completed in its manifest.
    if not new_cbz_files and mloader_skipped > 0:
        logging.info(
            f"{manga_name} is already up to date "
            f"({mloader_skipped} chapter(s) "
            f"skipped by manifest)"
        )

        return {
            "name": manga_name,
            "status": "up_to_date",
            "skipped_manifest": mloader_skipped,
        }

    if not new_cbz_files:
        logging.warning(
            f"No new CBZ detected for {manga_name}"
        )

        return {
            "name": manga_name,
            "status": "no_file",
        }

    # Normally -l downloads only one chapter.
    # If more than one candidate appears,
    # use the newest one.
    downloaded_file = max(
        new_cbz_files,
        key=os.path.getmtime,
    )

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

    manga_directory = os.path.join(
        MANGA_LIBRARY,
        manga_name,
    )

    os.makedirs(
        manga_directory,
        exist_ok=True,
    )

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

        cleanup_empty_directories(
            DOWNLOAD_DIR
        )

        return {
            "name": manga_name,
            "chapter": chapter_number,
            "file": final_filename,
            "status": "skipped",
        }

    shutil.move(
        downloaded_file,
        destination,
    )

    cleanup_empty_directories(
        DOWNLOAD_DIR
    )

    logging.info(
        f"Saved: {destination}"
    )

    return {
        "name": manga_name,
        "chapter": chapter_number,
        "file": final_filename,
        "status": "downloaded",
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
                    "error": "Missing name or id",
                }
            )

            continue

        result = download_manga(
            manga_name,
            manga_id,
        )

        results.append(result)

    summary = {
        "downloaded": sum(
            1
            for result in results
            if result["status"] == "downloaded"
        ),
        "up_to_date": sum(
            1
            for result in results
            if result["status"] == "up_to_date"
        ),
        "skipped": sum(
            1
            for result in results
            if result["status"] == "skipped"
        ),
        "no_file": sum(
            1
            for result in results
            if result["status"] == "no_file"
        ),
        "failed": sum(
            1
            for result in results
            if result["status"] == "failed"
        ),
        "results": results,
    }

    # Structured output for n8n.
    print(
        "MANGAPLUS_RESULT="
        + json.dumps(
            summary,
            ensure_ascii=False,
        )
    )

    if summary["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
