# mangaplus-downloader

A Python automation tool that downloads the latest chapters from Manga Plus, organizes them with consistent naming conventions, and seamlessly transfers them to your media server. Perfect for manga enthusiasts who want to maintain their digital collection without manual intervention.

## Features

- **Automated Downloads**: Fetches the latest chapters of specified manga series from Manga Plus  
- **Intelligent Naming**: Renames files to follow consistent conventions (e.g., "Dandadan ch. 150.cbz")  
- **Smart Duplicate Detection**: Checks if files already exist on the server before transferring to save bandwidth
- **Server Integration**: Uses rsync to transfer files to your remote media server  
- **Auto Directory Creation**: Automatically creates manga directories on the server if they don't exist
- **Clean Operations**: Removes local files after successful transfer to save space  
- **Real-time Notifications**: Sends Discord webhook notifications with detailed status updates
- **Comprehensive Logging**: Maintains detailed logs for troubleshooting and monitoring  
- **Batch Processing**: Download multiple manga series in a single run using centralized configuration

## Prerequisites

- Python 3.x
- SSH access to your remote media server
- rsync installed on both local and remote machines
- Discord webhook URL (optional, for notifications)

## Installation

### 1. Install System Dependencies

```bash
sudo apt install python3-full rsync
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
```

### 3. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### 1. Create `config.env`

This file contains common configuration shared across all manga downloads:

```env
DOWNLOAD_DIR=manga_downloads
REMOTE_HOST=192.168.1.28
REMOTE_USER=root
BASE_REMOTE_DIR=/mnt/user/media/manga
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
```

**Configuration Options:**
- `DOWNLOAD_DIR`: Local directory where manga will be downloaded temporarily
- `REMOTE_HOST`: IP address or hostname of your media server
- `REMOTE_USER`: SSH username for your media server
- `BASE_REMOTE_DIR`: Base directory on the server where manga will be stored
- `DISCORD_WEBHOOK_URL`: Discord webhook URL for notifications (optional)

### 2. Create `manga_list.json`

This file contains the list of all manga you want to download:

```json
[
  {
    "name": "Dandadan",
    "id": "100171"
  },
  {
    "name": "Kagurabachi",
    "id": "100274"
  },
  {
    "name": "Chainsaw Man",
    "id": "100037"
  }
]
```

**Important Notes:**
- The `name` field should match the exact title that MangaPlus uses for the manga
- To find the manga ID, visit the manga page on MangaPlus and check the URL (e.g., `https://mangaplus.shueisha.co.jp/titles/100171` → ID is `100171`)
- If the name doesn't match exactly, the script will attempt to find the correct directory and warn you

## Usage

### Basic Usage

Run the script with default configuration files:
```bash
python main.py
```

### Custom Configuration Files

Specify custom paths for configuration and manga list:
```bash
python main.py --config custom_config.env --manga-list custom_manga.json
```

### Command-Line Options

- `--config`: Path to the configuration env file (default: `config.env`)
- `--manga-list`: Path to the manga list JSON file (default: `manga_list.json`)

## How It Works

1. **Initialization**: Reads settings from `config.env` and manga list from `manga_list.json`
2. **Download**: For each manga in the list:
   - Downloads the latest chapter using mloader
   - Renames the file to match standard format (e.g., "Manga Name ch. 123.cbz")
3. **Duplicate Check**: Verifies if the file already exists on the server via SSH
4. **Transfer**: If the file is new:
   - Creates the manga directory on the server if needed
   - Transfers the file using rsync
   - Deletes the local copy after successful transfer
5. **Notification**: Sends Discord notification with batch summary (transferred/skipped/failed)

## Automation with Cron

### 1. Create Wrapper Script

Create a bash script (e.g., `manga_downloader.sh`):

```bash
#!/bin/bash
cd /path/to/mangaplus-downloader
source venv/bin/activate
python main.py
```

### 2. Make Script Executable

```bash
chmod +x manga_downloader.sh
```

### 3. Add Cron Job

Edit your crontab:
```bash
crontab -e
```

Add a schedule (example runs every Sunday at 11:10 AM):
```cron
10 11 * * 0 /path/to/manga_downloader.sh
```

**Common Cron Schedules:**
- Daily at 2 AM: `0 2 * * *`
- Every 6 hours: `0 */6 * * *`
- Twice weekly (Sun & Wed at 10 AM): `0 10 * * 0,3`

## Project Structure

```
mangaplus-downloader/
├── main.py                 # Main script
├── config.env              # Common configuration
├── manga_list.json         # List of manga to download
├── requirements.txt        # Python dependencies
├── manga_downloader.sh     # Wrapper script for automation
├── venv/                   # Virtual environment
├── manga_downloads/        # Temporary download directory
└── *.txt                   # Log files (date-stamped)
```

## Adding New Manga

### Option 1: Manual Addition

Edit `manga_list.json` and add a new entry:

```json
{
  "name": "Your New Manga",
  "id": "MANGA_ID_HERE"
}
```

### Option 2: Find the Manga ID

1. Go to [MangaPlus](https://mangaplus.shueisha.co.jp/)
2. Search for your manga
3. Open the manga page
4. Check the URL for the ID (e.g., `https://mangaplus.shueisha.co.jp/titles/100171`)
5. Add to your `manga_list.json`

The script will automatically:
- Create the appropriate directory on your server (`BASE_REMOTE_DIR/Manga Name/`)
- Download and transfer new chapters
- Skip chapters that already exist

## Discord Notifications

The script sends helpful notifications with emojis:

- ✅ **Successful transfer**: File was successfully transferred to the server
- ⏭️ **Skipped**: File already exists on the server
- ❌ **Failed**: Download or transfer failed
- **Batch Summary**: Total counts of successful/skipped/failed operations

## Logging

Logs are automatically created with date stamps (e.g., `manga_downloader-11-10-2025.txt`) and include:

- Download status for each manga
- File existence checks
- Transfer operations
- Any errors or warnings
- Batch processing summary

## Troubleshooting

### "FileNotFoundError: No such file or directory"

The manga name in your `manga_list.json` doesn't match the official title on MangaPlus. Check the logs for the actual directory name created by mloader and update your JSON file.

### "bash: line 1: test: too many arguments"

This error has been resolved in the current version. Make sure you're using the latest version of the script.

### File transfers but already exists

Ensure you have SSH key authentication set up between your local machine and server. The script uses SSH to check file existence.

### "No CBZ file found"

The manga may not have a new chapter available, or there was an issue with the download. Check the mloader output in the logs.

## Benefits Over Individual Config Files

- **Centralized Management**: All manga in one JSON file instead of scattered `.env` files
- **Less Duplication**: Common settings (webhook, server info) only defined once
- **Batch Processing**: Download all manga in a single run
- **Easy Maintenance**: Add/remove manga by editing a single JSON file
- **Dynamic Directories**: Automatically creates correct server directories for each manga
- **Bandwidth Efficient**: Skips files that already exist on the server

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is provided as-is for personal use.

## Acknowledgments

- [mloader](https://github.com/hurlenko/mloader) - The manga downloader tool that powers this script
- [MangaPlus](https://mangaplus.shueisha.co.jp/) - Official manga platform by Shueisha%   