# mangaplus-downloader
This Python application automatically downloads the latest chapters from Manga Plus, organizes them with proper naming conventions, and seamlessly transfers them to your media server. Perfect for manga enthusiasts who want to maintain their digital collection without manual intervention.
What It Does
The application handles the entire manga management workflow:

- Smart Downloads: Automatically fetches the latest chapter of specified manga series from Manga Plus  
- Intelligent Naming: Renames files to follow consistent conventions (e.g., "Dandadan ch. 150.cbz")  
- Server Integration: Uses rsync to transfer files to your remote media server  
- Clean Operations: Removes local files after successful transfer to save space  
- Real-time Notifications: Sends Discord webhook notifications for successful downloads or error alerts  
- Comprehensive Logging: Maintains detailed logs for troubleshooting and monitoring  

## Virtual environment creation (if you don't already know) 
1. Install python3-full
```
sudo apt install python3-full
```
2. Make  the virtual environment
```
python3 -m venv path/to/venv
```
3. Activate the venv
```
source path/to/venv/bin/activate
```
4. Finally, install dependencies
```
pip install python-dotenv mloader
```

## Dependencies
```
pip install python-dotenv mloader
```

## Usage
create a file _something_.env and fill with the following. The _something_ should be the name of the manga you want. You will store multiple env files, each for a specific manga you'd like to retireve.
```
MANGA_NAME=
MANGA_ID=
DOWNLOAD_DIR=manga_downloads
REMOTE_HOST=
REMOTE_USER=
REMOTE_DIR=
DISCORD_WEBHOOK_URL=
```
When running the script you must pass the env file as an argument like so
```
python main.py --env something.env
```
## Wrapper script & scheduling a cron job
Because of virtual environment BS, we use a wrapper bash script to run the python script for us. In this script I'm specifying Dandadan.
```
cd
cd /path/to/main.py
venv/bin/python3 main.py --env Dandadan.env
```
Automate this script using a cron job.
Here is an example that runs every Sunday at 11:10am
```
10 11 * * 0 manga_downloader.sh
```
