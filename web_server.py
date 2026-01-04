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

# Globals for server control
server_runner = None
server_site = None
cleanup_task_handle = None

def get_unique_key():
    return str(uuid.uuid4())

async def handle_download_page(request):
    """
    Serves a simple HTML page with a download button and media player.
    """
    key = request.match_info.get('key')
    file_info = file_storage.get(key)
    
    if not file_info or not os.path.exists(file_info['path']):
        return web.Response(text="Soubor nebyl nalezen nebo vypršela jeho platnost.", status=404)
        
    filename = file_info['filename']
    ext = os.path.splitext(filename)[1].lower()
    
    # Media rendering logic
    media_html = ""
    if ext in ['.mp4', '.webm', '.ogg', '.mov']:
        media_html = f'''
        <div class="media-container">
            <video controls autoplay name="media">
                <source src="/download/{key}" type="video/mp4">
                Tvůj prohlížeč nepodporuje video element.
            </video>
        </div>
        '''
    elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        media_html = f'''
        <div class="media-container">
            <img src="/download/{key}" alt="Preview">
        </div>
        '''

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
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                background-color: #23272a;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                max-width: 90%;
                width: 600px;
            }}
            h2 {{
                margin-bottom: 20px;
                word-wrap: break-word;
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
                margin-top: 20px;
            }}
            .btn:hover {{
                background-color: #5b6eae;
            }}
            .info {{
                margin-top: 15px;
                color: #99aab5;
                font-size: 14px;
            }}
            .media-container {{
                margin-bottom: 20px;
                width: 100%;
                display: flex;
                justify-content: center;
            }}
            video, img {{
                max-width: 100%;
                max-height: 60vh;
                border-radius: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Soubor je připraven</h2>
            {media_html}
            <p style="margin-bottom: 10px;">{filename}</p>
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

async def add_file(filepath):
    """
    Registers a file to be served. Returns the unique key.
    Starts the server if it's not running.
    """
    key = get_unique_key()
    filename = os.path.basename(filepath)
    file_storage[key] = {
        'path': filepath,
        'filename': filename,
        'timestamp': time.time()
    }
    
    # Check if this is the first file, if so start server
    if len(file_storage) == 1 and server_runner is None:
        asyncio.create_task(start_server())
        
    return key

async def cleanup_loop():
    """
    Periodically cleans up old files (older than 24h).
    And stops the server if no files complicate things.
    """
    global file_storage
    while True:
        try:
            await asyncio.sleep(60) # Check every minute to be more responsive to empty state
            
            if not file_storage and server_runner:
                # No files left? Stop server
                print("💤 [WebCleaner] Žádné soubory k obsluze, vypínám server.")
                await stop_server()
                continue

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
            
            # Re-check emptiness after deletion
            if not file_storage and server_runner:
                 print("💤 [WebCleaner] Všechny soubory vypršely/smazány, vypínám server.")
                 await stop_server()

        except Exception as e:
            print(f"❌ [WebCleaner] Chyba v cleanup loopu: {e}")
            await asyncio.sleep(60)

async def start_server():
    """
    Starts the web server.
    """
    global server_runner, server_site, cleanup_task_handle
    
    if server_runner:
        return # Already running

    print(f"⏳ [WebServer] Pokouším se spustit web server na portu {PORT}...")
    
    # Ensure temp directory exists
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    # Clean up ANY leftover files in temp dir on startup/restart
    try:
        count = 0
        for f in os.listdir(TEMP_DIR):
            full_path = os.path.join(TEMP_DIR, f)
            if os.path.isfile(full_path):
                # Also ensure we don't delete files we JUST added to storage map
                # But since we clear storage on memory reset, we should clear files too.
                # However, if we call start_server AFTER adding a file to memory, we must not delete it.
                # Check if file is in storage
                is_active = False
                for k, v in file_storage.items():
                    if v['path'] == full_path:
                        is_active = True
                        break
                
                if not is_active:
                    os.remove(full_path)
                    count += 1
        if count > 0:
            print(f"🧹 [WebServer] Vyčištěno {count} starých dočasných souborů.")
    except Exception as e:
        print(f"❌ [WebServer] Chyba při čištění temp složky: {e}")

    app = web.Application()
    app.router.add_get('/videa-z-discordu/{key}', handle_download_page)
    app.router.add_get('/videa-z-discordu/{key}/', handle_download_page) # redirect slash
    app.router.add_get('/download/{key}', handle_file_download)
    app.router.add_get('/download/{key}/{filename}', handle_file_download) # enable direct link with extension for discord embed
    
    server_runner = web.AppRunner(app)
    await server_runner.setup()
    
    try:
        server_site = web.TCPSite(server_runner, '0.0.0.0', PORT)
        await server_site.start()
        print(f"🌍 [WebServer] Web server ÚSPĚŠNĚ BĚŽÍ na portu {PORT} (http://0.0.0.0:{PORT})")
        
        # Start cleanup task if not running
        if cleanup_task_handle is None or cleanup_task_handle.done():
            cleanup_task_handle = asyncio.create_task(cleanup_loop())
            
    except Exception as e:
        print(f"❌ [WebServer] KRITICKÁ CHYBA: Nepodařilo se spustit server na portu {PORT}!")
        print(f"❌ [WebServer] Detail chyby: {e}")
        server_runner = None
        server_site = None

async def stop_server():
    global server_runner, server_site
    if server_site:
        await server_site.stop()
        server_site = None
    if server_runner:
        await server_runner.cleanup()
        server_runner = None
    print(f"🛑 [WebServer] Web server byl zastaven (není co obsluhovat).")
