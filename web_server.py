import os
import time
import uuid
import asyncio
from aiohttp import web

# File storage mapping: id -> {'path': str, 'filename': str, 'timestamp': float}
file_storage = {}
TEMP_DIR = "temp_downloads"
# Configure port
PORT = 8081

def get_unique_key():
    return str(uuid.uuid4())

async def handle_download_page(request):
    """
    Serves a simple HTML page with a download button.
    """
    key = request.match_info.get('key')
    file_info = file_storage.get(key)
    
    if not file_info or not os.path.exists(file_info['path']):
        return web.Response(text="Soubor nebyl nalezen nebo vypršela jeho platnost.", status=404)
        
    filename = file_info['filename']
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stáhnout {filename}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #2c2f33;
                color: #ffffff;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                background-color: #23272a;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            h2 {{
                margin-bottom: 20px;
            }}
            .btn {{
                display: inline-block;
                padding: 15px 30px;
                background-color: #7289da;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-size: 18px;
                font-weight: bold;
                transition: background-color 0.3s;
            }}
            .btn:hover {{
                background-color: #5b6eae;
            }}
            .info {{
                margin-top: 15px;
                color: #99aab5;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Soubor je připraven ke stažení</h2>
            <p style="margin-bottom: 30px;">{filename}</p>
            <a href="/download/{key}" class="btn">Stáhnout soubor</a>
            <p class="info">Odkaz je platný 24 hodin.</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def handle_file_download(request):
    """
    Serves the actual file.
    """
    key = request.match_info.get('key')
    file_info = file_storage.get(key)
    
    if not file_info or not os.path.exists(file_info['path']):
        return web.Response(text="Soubor nebyl nalezen.", status=404)
        
    return web.FileResponse(file_info['path'], headers={
        'Content-Disposition': f'attachment; filename="{file_info["filename"]}"'
    })

def add_file(filepath):
    """
    Registers a file to be served. Returns the unique key.
    """
    key = get_unique_key()
    filename = os.path.basename(filepath)
    file_storage[key] = {
        'path': filepath,
        'filename': filename,
        'timestamp': time.time()
    }
    return key

async def cleanup_task():
    """
    Periodically cleans up old files (older than 24h).
    """
    while True:
        now = time.time()
        keys_to_delete = []
        
        # Check for expired files
        for key, info in file_storage.items():
            if now - info['timestamp'] > 24 * 3600:
                keys_to_delete.append(key)
                
        # Delete expired
        for key in keys_to_delete:
            info = file_storage.pop(key)
            path = info['path']
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"🗑️ [WebCleaner] Smazán starý soubor: {path}")
                except Exception as e:
                    print(f"❌ [WebCleaner] Chyba při mazání {path}: {e}")
                    
        await asyncio.sleep(3600) # Check every hour

async def start_server():
    """
    Starts the web server.
    """
    # Ensure temp directory exists
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    # Clean up ANY leftover files in temp dir on startup
    # (Assuming we want a clean state on restart as per user request "pokud se vyresetuje tak ten soubor to smaze")
    for f in os.listdir(TEMP_DIR):
        full_path = os.path.join(TEMP_DIR, f)
        try:
            if os.path.isfile(full_path):
                os.remove(full_path)
        except Exception as e:
            print(f"❌ Chyba při čištění temp složky: {e}")

    app = web.Application()
    app.router.add_get('/videa-z-discordu/{key}', handle_download_page)
    app.router.add_get('/videa-z-discordu/{key}/', handle_download_page) # redirect slash
    app.router.add_get('/download/{key}', handle_file_download)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    print(f"🌍 Web server běží na portu {PORT}")
    
    # Start cleanup task
    asyncio.create_task(cleanup_task())

