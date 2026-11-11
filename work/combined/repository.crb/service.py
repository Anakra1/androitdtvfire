import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import xbmc
import xbmcaddon


PORT = 8765
addon_path = xbmcaddon.Addon().getAddonInfo("path")
handler = functools.partial(SimpleHTTPRequestHandler, directory=addon_path)
server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
monitor = xbmc.Monitor()
try:
    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
finally:
    server.shutdown()
    server.server_close()
