import os
import urllib.request

VIDEO_URL = "https://github.com/astrofra/pLLMdered_hearts/releases/download/videofile/abriggs-itw.mp4"
OUTPUT_DIR = os.path.join("www", "static", "video")
OUTPUT_FILENAME = os.path.join(OUTPUT_DIR, "abriggs-itw.mp4")

def download_video(url, filename):
    """Download a video file from the given URL and save it locally."""
    print(f"Downloading video from {url}...")
    urllib.request.urlretrieve(url, filename)
    print("Download complete.")

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if os.path.exists(OUTPUT_FILENAME):
        print(f"'{OUTPUT_FILENAME}' already exists. Nothing to do.")
    else:
        try:
            download_video(VIDEO_URL, OUTPUT_FILENAME)
        except Exception as e:
            print(f"Error: {e}")
