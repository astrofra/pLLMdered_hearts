import os
import zipfile
import urllib.request

# URL to the ZIP archive containing the Infocom games
ZIP_URL = "https://archive.org/download/msdos_Plundered_Hearts_1987/Plundered_Hearts_1987.zip"
ZIP_FILENAME = "roms/Infocom_Games.zip"
TARGET_GAME_FILENAME = "phearts/PLUNDERE.DAT"
OUTPUT_FILENAME = "roms/PLUNDERE.z3"

def download_zip(url, filename):
    """Download a ZIP file from the given URL and save it locally."""
    print(f"Downloading archive from {url}...")
    urllib.request.urlretrieve(url, filename)
    print("Download complete.")

def extract_game(zip_path, target_file, output_file):
    """Extract the target file from the ZIP archive and rename it."""
    print(f"Extracting '{target_file}' from {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as archive:
        # List all files in the archive
        file_list = archive.namelist()
        # Normalize file names (in case)
        normalized_files = [f.strip() for f in file_list]
        if target_file not in normalized_files:
            raise FileNotFoundError(f"'{target_file}' not found in archive.")

        # Extract the file and rename it
        archive.extract(target_file)
        os.rename(target_file, output_file)
        print(f"Saved as '{output_file}'.")

if __name__ == "__main__":
    if os.path.exists(OUTPUT_FILENAME):
        print(f"'{OUTPUT_FILENAME}' already exists. Nothing to do.")
    else:
        try:
            download_zip(ZIP_URL, ZIP_FILENAME)
            extract_game(ZIP_FILENAME, TARGET_GAME_FILENAME, OUTPUT_FILENAME)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Optionally delete the archive to save space
            if os.path.exists(ZIP_FILENAME):
                os.remove(ZIP_FILENAME)
