import os
import yt_dlp
import glob
import re

SUPPORTED_DOMAINS = [
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com"
]

def extract_url(message_content: str) -> str | None:
    """
    Finds the first supported URL in the message content.
    """
    # Simple regex to find URLs
    url_pattern = re.compile(r'https?://\S+')
    urls = url_pattern.findall(message_content)
    
    for url in urls:
        for domain in SUPPORTED_DOMAINS:
            if domain in url:
                return url
    return None

def download_media(url: str):
    """
    Downloads media from the URL.
    Returns a dictionary with metadata and file path, or error.
    """
    # Configure yt-dlp
    ydl_opts = {
        'outtmpl': 'temp_downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best', # Avoid merging if ffmpeg is missing
        'noplaylist': True,
        # 'restrictfilenames': True, 
    }
    
    # Check for cookies.txt
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"
        print("🍪 [MediaDownloader] Používám cookies.txt")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first
            info = ydl.extract_info(url, download=True)
            
            # Determine the filename
            filename = ydl.prepare_filename(info)
            
            # Sometimes the extension changes after merging (e.g. mkv)
            if not os.path.exists(filename):
                base_name = os.path.splitext(filename)[0]
                # Look for any file starting with this ID
                possible_files = [f for f in os.listdir('.') if f.startswith(base_name)]
                # Filter out likely false positives if any? usually ID is unique enough.
                # But prefer exact match of ID if possible.
                if possible_files:
                    # Pick the one that was most recently modified or just the first one?
                    # usually just one.
                    filename = possible_files[0]
                else:
                    return {"error": "Soubor nebyl po stažení nalezen."}

            filesize_bytes = os.path.getsize(filename)
            filesize_mb = filesize_bytes / (1024 * 1024)

            # Metadata
            stats = {
                "filename": filename,
                "title": info.get("title", "Unknown"),
                "uploader": info.get("uploader", "Unknown"),
                "duration": info.get("duration"), # seconds
                "resolution": f"{info.get('width', '?')}x{info.get('height', '?')}",
                "filesize_mb": round(filesize_mb, 2),
                "is_video": info.get('_type') == 'video' or info.get('ext') in ['mp4', 'mkv', 'webm', 'mov'],
                "view_count": info.get("view_count", 0),
                "like_count": info.get("like_count", 0)
            }
            return stats

    except Exception as e:
        return {"error": str(e)}

def delete_file(filename: str):
    """Deletes the file if it exists."""
    if filename and os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception as e:
            print(f"Chyba při mazání souboru {filename}: {e}")
