import os
import logging
import subprocess
import argparse
import requests
from dotenv import load_dotenv
from datetime import datetime
import re
import json

# Create an argument parser
parser = argparse.ArgumentParser(description='Download manga chapters from MangaPlus')
parser.add_argument('--config', type=str, default='config.env', help='Path to the config env file')
parser.add_argument('--manga-list', type=str, default='manga_list.json', help='Path to the manga list JSON file')

# Parse the command-line arguments
args = parser.parse_args()

# Load the environment variables from the config file
load_dotenv(dotenv_path=args.config)

# Get common configuration values
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', 'manga_downloads')
REMOTE_HOST = os.getenv('REMOTE_HOST')
REMOTE_USER = os.getenv('REMOTE_USER')
BASE_REMOTE_DIR = os.getenv('BASE_REMOTE_DIR')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Load manga list from JSON file
try:
    with open(args.manga_list, 'r') as f:
        manga_list = json.load(f)
except FileNotFoundError:
    logging.error(f"Manga list file not found: {args.manga_list}")
    exit(1)
except json.JSONDecodeError:
    logging.error(f"Invalid JSON in manga list file: {args.manga_list}")
    exit(1)

now = datetime.now()
dt_string = now.strftime("%d-%m-%Y")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"manga_downloader-{dt_string}.txt"),
        logging.StreamHandler()
    ]
)


def send_discord_message(content):
    """Send a message to Discord via webhook"""
    if not DISCORD_WEBHOOK_URL:
        logging.warning("Discord webhook URL not configured, skipping notification")
        return
    
    data = {"content": content}
    response = requests.post(DISCORD_WEBHOOK_URL, json=data)
    if response.status_code != 204:
        logging.error(f"Failed to send message to Discord: {response.status_code}, {response.text}")


def download_manga(manga_name, manga_id):
    """Download and process a single manga chapter"""
    try:
        logging.info(f"Downloading the latest chapter for {manga_name} (Title ID: {manga_id})")

        # Download the latest chapter of the manga using mloader command
        command = f".venv/bin/mloader -t {manga_id} -l -o {DOWNLOAD_DIR}"
        subprocess.run(command, shell=True, check=True)

        logging.info(f"Successfully downloaded the latest chapter of {manga_name}!")

        # Reassigning download directory variable because mloader will make a new folder to save the cbz into
        # mloader uses the official manga title, which might differ from our manga_name
        manga_download_dir = os.path.join(DOWNLOAD_DIR, manga_name)
        
        # Check if the expected directory exists, if not, find what mloader actually created
        if not os.path.exists(manga_download_dir):
            logging.warning(f"Expected directory not found: {manga_download_dir}")
            # List all directories in DOWNLOAD_DIR to find what mloader created
            downloaded_dirs = [d for d in os.listdir(DOWNLOAD_DIR) if os.path.isdir(os.path.join(DOWNLOAD_DIR, d))]
            logging.info(f"Available directories in {DOWNLOAD_DIR}: {downloaded_dirs}")
            
            # Try to find a directory that was recently created (within the last minute)
            import time
            current_time = time.time()
            recent_dirs = []
            for d in downloaded_dirs:
                dir_path = os.path.join(DOWNLOAD_DIR, d)
                dir_mtime = os.path.getmtime(dir_path)
                if current_time - dir_mtime < 60:  # Created within last 60 seconds
                    recent_dirs.append(d)
            
            if len(recent_dirs) == 1:
                actual_manga_name = recent_dirs[0]
                manga_download_dir = os.path.join(DOWNLOAD_DIR, actual_manga_name)
                logging.info(f"Found recently created directory: {manga_download_dir}")
                logging.info(f"NOTE: mloader uses '{actual_manga_name}' but your manga_list.json has '{manga_name}'")
            else:
                logging.error(f"Could not determine which directory mloader created. Recent directories: {recent_dirs}")
                send_discord_message(f"Error: Could not find download directory for {manga_name}")
                return False

        # Find the cbz file for renaming
        cbz_files = [f for f in os.listdir(manga_download_dir) if f.endswith(".cbz")]

        if not cbz_files:
            logging.warning(f"No CBZ file found for {manga_name} (Title ID: {manga_id})")
            send_discord_message(f"No CBZ file found for {manga_name} (Title ID: {manga_id})")
            return False

        latest_cbz = max(cbz_files)

        # Extract chapter number using regex
        match = re.search(r'(c(\d+)|ch\.\s*(\d+[a-zA-Z]*))', latest_cbz)
        if not match:
            logging.error(f"Failed to extract chapter number from {latest_cbz}, using 'Unknown'")
            send_discord_message(f"Failed to extract chapter number from {latest_cbz}, using 'Unknown'")
            chapter_number = "Unknown"
        else:
            # Check which group matched
            if match.group(2):  # If the match was for 'c' followed by digits
                chapter_number = match.group(2)
            else:  # If the match was for 'ch.' followed by a number (possibly with a suffix)
                chapter_number = match.group(3)

        # Renaming cbz to match the syntax "{MANGA_NAME} ch. {chapter_number}.cbz"
        old_file_path = os.path.join(manga_download_dir, latest_cbz)
        new_file_name = f"{manga_name} ch. {chapter_number}.cbz"
        new_file_path = os.path.join(manga_download_dir, new_file_name)
        os.rename(old_file_path, new_file_path)

        logging.info(f"Renamed file to {new_file_name} for {manga_name}!")

        # Transfer the file to another PC using rsync
        try:
            # Dynamically construct the remote directory path
            remote_dir = os.path.join(BASE_REMOTE_DIR, manga_name)
            remote_file_path = f"{remote_dir}/{new_file_name}"
            
            logging.info(f"Checking if file exists on server: {REMOTE_USER}@{REMOTE_HOST}:{remote_file_path}")
            
            # Check if file already exists on server using ssh
            # Properly escape the path for the remote test command
            import shlex
            # We need to quote the path for the remote shell
            check_command = f'ssh {REMOTE_USER}@{REMOTE_HOST} "test -f {shlex.quote(remote_file_path)} && echo exists || echo not_exists"'
            
            logging.info(f"Running check command: {check_command}")
            check_result = subprocess.run(check_command, shell=True, capture_output=True, text=True)
            logging.info(f"Check result return code: {check_result.returncode}")
            logging.info(f"Check result stdout: '{check_result.stdout.strip()}'")
            logging.info(f"Check result stderr: '{check_result.stderr.strip()}'")
            
            if check_result.stdout.strip() == "exists":
                logging.info(f"File already exists on server, skipping transfer: {new_file_name}")
                send_discord_message(f"⏭️ Skipped: {new_file_name} already exists on server")
                
                # Delete the local CBZ file since it already exists on the server
                os.remove(new_file_path)
                logging.info(f"Local CBZ file deleted: {new_file_path}")
                
                return "skipped"
            
            # File doesn't exist, proceed with transfer
            logging.info(f"File does not exist on server, proceeding with transfer to: {REMOTE_USER}@{REMOTE_HOST}:{remote_dir}")
            
            # Ensure the remote directory exists before transferring
            mkdir_command = f'ssh {REMOTE_USER}@{REMOTE_HOST} "mkdir -p {shlex.quote(remote_dir)}"'
            logging.info(f"Ensuring remote directory exists: {mkdir_command}")
            subprocess.run(mkdir_command, shell=True, check=True)
            
            rsync_command = f'rsync -avz --progress "{new_file_path}" "{REMOTE_USER}@{REMOTE_HOST}:{remote_dir}"'
            logging.info(f"Running rsync command: {rsync_command}")
            subprocess.run(rsync_command, shell=True, check=True)

            logging.info(f"File transfer complete! Transferred to: {REMOTE_USER}@{REMOTE_HOST}:{remote_dir}")
            send_discord_message(f"✅ File transfer complete! {new_file_name} transferred to server")

            # Delete the CBZ file from the main PC after successful transfer
            os.remove(new_file_path)
            logging.info(f"CBZ file deleted from host: {new_file_path}")
            
            return True

        except subprocess.CalledProcessError as e:
            logging.error(f"File transfer failed for {manga_name}: {str(e)}")
            send_discord_message(f"File transfer failed for {manga_name}: {str(e)}")
            return False

    except subprocess.CalledProcessError as e:
        logging.error(f"Error during download: {str(e)}")
        send_discord_message(f"Error downloading {manga_name}: {str(e)}")
        return False


def main():
    """Main function to process all manga in the list"""
    logging.info(f"Starting manga download process for {len(manga_list)} manga series")
    
    successful = 0
    failed = 0
    skipped = 0
    
    for manga in manga_list:
        manga_name = manga.get('name')
        manga_id = manga.get('id')
        
        if not manga_name or not manga_id:
            logging.error(f"Invalid manga entry: {manga}")
            failed += 1
            continue
        
        result = download_manga(manga_name, manga_id)
        if result == "skipped":
            skipped += 1
        elif result:
            successful += 1
        else:
            failed += 1
        
        logging.info("-" * 50)
    
    logging.info(f"Download process complete! Successful: {successful}, Skipped: {skipped}, Failed: {failed}")
    send_discord_message(f"Manga download batch complete! ✅ {successful} transferred, ⏭️ {skipped} skipped, ❌ {failed} failed")


if __name__ == "__main__":
    main()