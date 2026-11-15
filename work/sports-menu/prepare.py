"""Stage CBR's sport-first browser against the installed Windows trial."""
from pathlib import Path
import ast, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ADDON=Path('C:/Users/Chris/AppData/Roaming/Kodi/addons/plugin.video.stremio.bridge')
BACKUP=ROOT/'outputs/verified-live-daddy-menu-20261115/before-code'
BACKUP.mkdir(exist_ok=True)
for name in ('addon.py','resources/lib/core.py','resources/lib/live.py','resources/lib/pvr.py','resources/lib/defaults.py','resources/lib/setup_web.py'):
    target=BACKUP/name;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(ADDON/name,target)

def write(name,text):
    path=HERE/'overlay'/name;path.parent.mkdir(parents=True,exist_ok=True)
    text='\n'.join(line.rstrip()for line in text.splitlines()).rstrip()+'\n'
    ast.parse(text,feature_version=(3,8));path.write_text(text,encoding='utf8',newline='\n')

s=(BACKUP/'resources/lib/core.py').read_text(encoding='utf8')
s=s.replace('def load_manifest(url, fetch=fetch_json):',"def load_manifest(url, fetch=fetch_json):\n    from . import daddylive\n    if daddylive.is_source(url):return daddylive.manifest()")
s=s.replace("    if entry.get('kind') == 'm3u':", "    if entry.get('kind') == 'daddylive':\n        from . import daddylive\n        return daddylive.resource(entry, resource, media_type, identity, extras)\n    if entry.get('kind') == 'm3u':",1)
s=s.replace("        entries = [entry if x['key'] == key else x for x in entries]", "        if manifest['id'] == 'org.cbr.daddylive':\n            entry.update(kind='daddylive', live_group='tv', scope_types=['tv'], pvr_enabled=False)\n        entries = [entry if x['key'] == key else x for x in entries]",1)
write('resources/lib/core.py',s)
s=(BACKUP/'resources/lib/pvr.py').read_text(encoding='utf8')
s=s.replace("        if not entry.get('enabled', True):", "        if not entry.get('enabled', True) or entry.get('pvr_enabled') is False:",1)
write('resources/lib/pvr.py',s)
s=(BACKUP/'resources/lib/defaults.py').read_text(encoding='utf8')
s=s.replace('def ensure_defaults(store, addon_path, force=False):',"def ensure_defaults(store, addon_path, force=False):\n    from .daddylive import ensure_default\n    ensure_default(store)")
write('resources/lib/defaults.py',s)
s=(BACKUP/'resources/lib/setup_web.py').read_text(encoding='utf8')
s=s.replace("        if 'guide_country' in data:", "        if manifest['id'] == 'org.cbr.daddylive':\n            entry.update(kind='daddylive', scope_types=['tv'], pvr_enabled=False)\n        if 'guide_country' in data:",1)
write('resources/lib/setup_web.py',s)
s=(BACKUP/'resources/lib/live.py').read_text(encoding='utf8')
s=s.replace("live_country=saved.get('live_country', ''), native_schedule=saved.get('native_schedule', []))", "live_country=saved.get('live_country', ''), native_schedule=saved.get('native_schedule', []),\n                    **({'sports_variants': saved['sports_variants']} if saved.get('sports_variants') else {}))")
s=s.replace("        entry = next((e for e in entries if e['key'] == channel['provider']), None)", "        if channel.get('sports_variants'):\n            variants = [v for v in channel['sports_variants'] if any(e['key'] == v['provider'] for e in entries)]\n            if not variants:return None\n            return dict(channel, provider=variants[0]['provider'], sports_variants=variants)\n        entry = next((e for e in entries if e['key'] == channel['provider']), None)",1)
write('resources/lib/live.py',s)

s=(BACKUP/'addon.py').read_text(encoding='utf8')
s=s.replace('def live_catalogues(group):','def provider_catalogues(group):',1)
functions='''def live_catalogues(group):
    if group == 'sports':
        sports_home()
    else:
        provider_catalogues(group)


def sports_home():
    from resources.lib.sports import SPORTS
    for sport, title in SPORTS:
        item(title, 'sports_category', sport=sport, artwork='live')
    item('Browse sports sources', 'sports_sources', artwork='live')
    crew_sport_link('all')
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    xbmcplugin.setPluginCategory(HANDLE, 'Live Sports')
    finish()


def sports_sources():
    from resources.lib.sports import choose
    for entry in STORE.providers():
        if entry.get('enabled', True) and choose(entry, 'all'):
            cat = choose(entry, 'all')[0]
            item(entry['label'], 'live_source', provider=entry['key'], group=catalogue_group(entry, cat), artwork='live')
    finish()


def sports_category(sport, channels=False, refresh=False):
    from resources.lib.sports import listing, SPORTS
    rows, errors = listing(STORE, sport, refresh)
    if not channels and any(row['is_channel'] for row in rows):
        item('Sports channels · schedules vary', 'sports_category', sport=sport, channels='true', artwork='live')
    if not channels:
        crew_sport_link(sport)
    LIVE_LIBRARY.begin_listing()
    for row in rows:
        if bool(row['is_channel']) != channels:
            continue
        item(row['meta']['name'], 'live_play', folder=False, meta=row['meta'], channel=row, key=STORE.put(row))
    item('Refresh listings', 'sports_category', sport=sport, channels=str(channels).lower(), refresh='true', artwork='live')
    item('Browse sports sources', 'sports_sources', artwork='live')
    if errors:
        notify('Some sports sources are unavailable; showing the other results.')
    xbmcplugin.setPluginCategory(HANDLE, dict(SPORTS)[sport] + (' · channels' if channels else ' · events'))
    finish()


def sports_streams(saved, autoplay):
    from resources.lib.sports import streams
    inline = streams(STORE, saved)
    if not inline:
        notify('These sources are not returning a playable link right now.')
        if autoplay:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            finish()
        return
    show_streams(saved['resource_type'], saved['meta']['id'], saved['meta'], inline=inline, channel=saved, autoplay=autoplay)


def crew_sport_link(sport):
    try:
        details = rpc('Addons.GetAddonDetails', {'addonid': 'plugin.video.thecrew', 'properties': ['enabled']})
        if not details.get('addon', {}).get('enabled'):
            return
    except Exception:
        return
    # Use the installed Crew player in its own Kodi context so its maintained
    # resolvers keep working. Never execute downloaded XML/Python in CBR.
    routes = {'football': [('Football', 'fifa')], 'motor_sports': [('Formula 1', 'f1'), ('MotoGP', 'motogp'), ('NASCAR', 'nascar')],
              'basketball': [('Basketball', 'nba')], 'american_football': [('American football', 'nfl')],
              'baseball': [('Baseball', 'mlb')], 'hockey': [('Hockey', 'nhl')],
              'tennis': [('Tennis', 'tennis')], 'golf': [('Golf', 'pga')],
              'fight': [('Boxing', 'boxing'), ('UFC', 'ufc'), ('Wrestling', 'wwe')]}
    for title, action in routes.get(sport, [('Sports', 'bluehat')]):
        li = xbmcgui.ListItem(label='The Crew · ' + title)
        li.setArt({'thumb': os.path.join(ART, 'crb-live.png')})
        xbmcplugin.addDirectoryItem(HANDLE, 'plugin://plugin.video.thecrew/?' + urlencode({'action': action}), li, isFolder=True)


'''
s=s.replace('def provider_catalogues(group):',functions+'def provider_catalogues(group):',1)
s=s.replace("    saved = cached_item(key, index)\n    preview = saved['meta']", "    saved = cached_item(key, index)\n    if saved.get('sports_variants'):\n        sports_streams(saved, autoplay)\n        return\n    preview = saved['meta']",1)
s=s.replace("        elif action == 'live_catalogues':", "        elif action == 'sports_category':\n            sports_category(params['sport'], params.get('channels') == 'true', params.get('refresh') == 'true')\n        elif action == 'sports_sources':\n            sports_sources()\n        elif action == 'live_catalogues':",1)
write('addon.py',s)
print('Sports menus and provider adapters staged; DaddyLive remains excluded from PVR.')
