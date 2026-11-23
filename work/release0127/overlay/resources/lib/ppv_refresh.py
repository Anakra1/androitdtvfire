"""One-shot Kodi refresh, cancelled naturally when the PPV directory is left."""
from urllib.parse import urlsplit, parse_qs
import xbmc
import xbmcgui
if __name__=='__main__':
    path=xbmc.getInfoLabel('Container.FolderPath')
    route=urlsplit(path)
    if (route.scheme=='plugin' and route.netloc=='plugin.video.stremio.bridge'
            and parse_qs(route.query).get('action')==['sports_ppv']
            and xbmcgui.getCurrentWindowId()==10025 and not xbmc.Player().isPlaying()):
        xbmc.executebuiltin('Container.Refresh')
