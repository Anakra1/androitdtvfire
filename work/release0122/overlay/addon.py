"""Kodi entry point for the Stremio protocol bridge (Kodi 20+)."""
import json
import os
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.core import (DEFAULT_URL, PRESETS, Store, aggregate, fetch_json, fetch_resource,
                                playback_url, resource_url, stream_kind)
from resources.lib.library import MovieLibrary
from resources.lib.live_player import LiveAutoplay, probe_stream
from resources.lib.programmes import (ProgrammeGuide, country_for, programme_text, request_refresh,
                                     provider_programmes, settings as programme_settings, save_settings as save_programme_settings)
from resources.lib import pvr
from resources.lib.defaults import ensure_defaults
from resources.lib.live import (GROUPS, GROUP_NAMES, LiveCatalogueCache, LiveLibrary, browse_title, catalogue_group,
                                entry_catalogs, grouped_catalogues, search_only)

ADDON = xbmcaddon.Addon()
BASE = sys.argv[0]
HANDLE = int(sys.argv[1])
DIALOG = xbmcgui.Dialog()
STORE = Store(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')))
LIBRARY = MovieLibrary(STORE)
LIVE_LIBRARY = LiveLibrary(STORE)
LIVE_CATALOGUES = LiveCatalogueCache(STORE)
LIVE_AUTOPLAY = LiveAutoplay(STORE)
PROGRAMMES = ProgrammeGuide(STORE)
ART = os.path.join(ADDON.getAddonInfo('path'), 'resources', 'art')
BRAND = 'Crimson Blood Requiem'


def route(action, **kwargs):
    return BASE + '?' + urlencode(dict(action=action, **kwargs))


def item(label, action, folder=True, meta=None, artwork=None, channel=None, **kwargs):
    li = xbmcgui.ListItem(label=str(label))
    art = {'icon': os.path.join(ART, 'crb-icon.png'), 'fanart': os.path.join(ART, 'crb-fanart.jpg')}
    if artwork:
        art.update({'thumb': os.path.join(ART, 'crb-' + artwork + '.png'),
                    'poster': os.path.join(ART, 'crb-' + artwork + '.png')})
    if meta:
        tag = li.getVideoInfoTag()
        tag.setTitle(str(meta.get('name', label)))
        tag.setPlot(str(meta.get('description', meta.get('overview', ''))))
        kind = meta.get('type', '')
        tag.setMediaType({'movie': 'movie', 'series': 'tvshow'}.get(kind, 'video'))
        year = str(meta.get('releaseInfo', ''))[:4]
        if year.isdigit():
            tag.setYear(int(year))
        if isinstance(meta.get('genres'), list):
            tag.setGenres(meta['genres'])
        try:
            if meta.get('imdbRating'):
                tag.setRating(float(meta['imdbRating']))
        except (TypeError, ValueError):
            pass
        art.update({'poster': meta.get('poster') or os.path.join(ART, 'crb-poster.png'),
                    'thumb': meta.get('thumbnail') or meta.get('poster') or os.path.join(ART, 'crb-poster.png'),
                    'fanart': meta.get('background') or os.path.join(ART, 'crb-fanart.jpg')})
        if meta.get('logo'):
            art['clearlogo'] = meta['logo']
            if channel:
                art.update(icon=meta['logo'], thumb=meta['logo'], poster=meta['logo'])
        if meta.get('type') == 'movie' and action == 'meta':
            li.addContextMenuItems([
                ('Add to Kodi Movies library', 'RunPlugin({})'.format(route('export', key=kwargs['key']))),
                ('Movie information', 'Action(Info)'),
            ])
    if channel:
        bookmark = LIVE_LIBRARY.channel(channel)
        if PROGRAMMES.config.get('enabled', True):
            schedule = PROGRAMMES.lookup(bookmark, meta)
            plot = programme_text(schedule)
            if meta.get('description'):
                plot += '\n\n' + meta['description']
            li.getVideoInfoTag().setPlot(plot)
            now, following = (schedule or {}).get('now'), (schedule or {}).get('next')
            li.setLabel2(now['title'] if now else 'Programme information unavailable')
            li.setProperty('CBR.Now', now['title'] if now else '')
            li.setProperty('CBR.Next', following['title'] if following else '')
        label = 'Remove from CBR favourites' if LIVE_LIBRARY.is_favourite(bookmark) else 'Add to CBR favourites'
        arguments = {'key': kwargs['key']}
        if 'index' in kwargs:
            arguments['index'] = kwargs['index']
        if channel.get('live_group')!='sports':
            li.addContextMenuItems([(label, 'RunPlugin({})'.format(route('live_favourite', **arguments)))])
        li.addContextMenuItems([('Choose stream manually', 'Container.Update({})'.format(route('meta', **arguments)))])
        li.addContextMenuItems([('Programme information', 'RunPlugin({})'.format(route('programme_info', **arguments))),
                                ('Match programme channel', 'RunPlugin({})'.format(route('programme_match', **arguments)))])
    li.setArt(art)
    if not folder:
        li.setProperty('IsPlayable', 'true')
    target_action=action
    if meta and meta.get('type') in ('movie','series'):
        if action=='meta':target_action='command_detail'
        elif action=='streams':target_action='command_episode_detail'
    if channel and channel.get('live_group')=='sports' and kwargs.get('key'):
        favkey=channel['provider']+':'+channel.get('resource_type',meta['type'])+':'+meta['id']
        favlabel='Remove sports favourite' if COMMAND.contains('sports',favkey) else 'Add sports favourite'
        li.addContextMenuItems([(favlabel,'RunPlugin({})'.format(route('command_sport_fav',key=kwargs['key'])))])
    if action=='command_pin_search':
        li.addContextMenuItems([('Unpin team / competition','RunPlugin({})'.format(route('command_pin_remove',query=kwargs['query'])))])
    xbmcplugin.addDirectoryItem(HANDLE, route(target_action, **kwargs), li, isFolder=folder)


def finish(content='videos'):
    PROGRAMMES.close()
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)
    command_set_view(content)


def notify(message):
    DIALOG.notification(BRAND, message, xbmcgui.NOTIFICATION_INFO, 6000)


def request(url):
    try:
        return fetch_json(url)
    except Exception:
        # Do not expose configured endpoint paths, including account tokens.
        raise RuntimeError('The add-on could not be reached or returned invalid data. Check its URL and connection.') from None


def failures(results):
    count = sum(bool(error) for _, _, error in results)
    if count:
        notify('{} provider(s) could not be reached; other results are shown.'.format(count))


def home():
    movie_home()


def tools():
    item('Check, repair and back up CBR', 'maintenance', artwork='settings')
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    item('Search movies', 'search', media_type='movie', artwork='search')
    item('Search TV series', 'search', media_type='series', artwork='search')
    item('Search Live TV', 'search', live_only='true', artwork='search')
    item('Browse all catalogues', 'catalogues', artwork='catalogues')
    item('Manage sources / add manifest URL', 'manage', artwork='settings')
    item('Live TV', 'live', artwork='live')
    item('CBR help, repair, updates and recovery', 'maintenance', artwork='settings')
    item('Kodi TV and guide', 'pvr', artwork='live')
    item('Built-in player settings', 'configure', artwork='settings')
    item('Kodi Movies library setup', 'library', artwork='library')
    item('Play a local video', 'local', artwork='library')
    item('Help and compatibility', 'help', artwork='settings')
    finish()


def movie_catalogs():
    return [(e, c) for e, c in catalogs() if c['type'] == 'movie']


def movie_home():
    item('Continue watching','command_continue',artwork='movies')
    item('Saved titles and sports','command_watchlist',artwork='movies')
    item('CBR Setup','command_setup',artwork='settings')
    item('Exit CBR → Kodi add-ons','command_exit',artwork='settings')
    item('Quit Kodi','command_quit',artwork='settings')
    item('Search movies', 'search', media_type='movie', artwork='search')
    item('Movies', 'catalogues', media_type='movie', artwork='movies')
    item('Search TV series', 'search', media_type='series', artwork='search')
    item('TV series', 'catalogues', media_type='series', artwork='series')
    item('Search Live TV', 'search', live_only='true', artwork='search')
    item('Live TV', 'live', artwork='live')
    item('CBR help, repair, updates and recovery', 'maintenance', artwork='settings')
    item('My Kodi Movies library', 'library', artwork='library')
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    item('Sources and player settings', 'tools', artwork='settings')
    candidates = [(e, c) for e, c in movie_catalogs() if not any(x.get('isRequired') for x in c.get('extra', []))]
    candidates.sort(key=lambda pair: (pair[0]['manifest'].get('id') != 'com.linvo.cinemeta',
                                       pair[1]['id'] != 'top'))
    for entry, cat in candidates[:3]:
        try:
            data = fetch_json(resource_url(entry['url'], 'catalog', 'movie', cat['id']))
            movies = [m for m in data.get('metas', []) if isinstance(m, dict) and m.get('type', 'movie') == 'movie'][:60]
            if not movies:
                continue
            add_metas(movies, entry['key'], 'movie')
            key = STORE.put(cat)
            item('More from ' + cat.get('name', cat['id']), 'catalog', provider=entry['key'], catalog=key,
                 artwork='catalogues')
            item('Add these movies to Kodi Movies library', 'export_page',
                 key=STORE.put(movies), artwork='library')
            break
        except Exception:
            continue
    else:
        notify('Connect a movie catalogue in Sources and player settings to load posters.')
    xbmcplugin.setPluginCategory(HANDLE, BRAND)
    finish('movies')


def new_movies():
    """Poster-only directory for Kodi home widgets and the Movies menu."""
    import datetime
    import time
    year = str(datetime.date.today().year)
    candidates = [(e, c) for e, c in movie_catalogs() if c['id'] == 'year']
    candidates.sort(key=lambda pair: pair[0]['manifest'].get('id') != 'com.linvo.cinemeta')
    for entry, cat in candidates:
        path = os.path.join(STORE.root, 'new-movies-widget.json')
        cached = STORE.read(path, {})
        valid_cache = cached.get('version') == 2 and cached.get('provider') == entry['key'] and cached.get('year') == year and bool(cached.get('movies'))
        try:
            if cached.get('version') == 2 and cached.get('provider') == entry['key'] and cached.get('year') == year and time.time() - cached.get('time', 0) < 900:
                movies = cached['movies']
            else:
                data = fetch_resource(entry, 'catalog', 'movie', cat['id'], {'genre': year})
                movies = [dict(m, type='movie') for m in data.get('metas', [])
                          if isinstance(m, dict) and m.get('id') and m.get('name') and m.get('type', 'movie') == 'movie'
                          and str(m.get('releaseInfo', ''))[:4] == year
                          and (not m.get('released') or str(m['released'])[:10] <= datetime.date.today().isoformat())][:60]
                if not movies:
                    if valid_cache:
                        add_metas(cached['movies'], entry['key'], 'movie');break
                    continue
                STORE.write(path, dict(version=2, provider=entry['key'], year=year, time=time.time(), movies=movies))
            add_metas(movies, entry['key'], 'movie')
            break
        except Exception:
            if valid_cache:
                add_metas(cached['movies'], entry['key'], 'movie');break
            continue
    xbmcplugin.setPluginCategory(HANDLE, 'New movies · CBR')
    finish('movies')


def manage():
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    item('Add another source / manifest URL', 'add')
    item('Import manifest URLs from a text file', 'import')
    item('Add Cinemeta (official movie and series catalogue)', 'cinemeta')
    item('Restore missing default providers', 'defaults')
    for entry in STORE.providers():
        item(('ON  ' if entry.get('enabled', True) else 'OFF  ') + entry['label'],
             'provider', key=entry['key'])
    finish()


def add_provider(live_group=None):
    index = DIALOG.select('Choose add-on (paste its configured Share addon URL next)', PRESETS)
    if index < 0:
        return
    label = PRESETS[index]
    url = DIALOG.input('Paste installed add-on manifest URL', DEFAULT_URL if index == 0 else '')
    if url.strip():
        entry = STORE.add(url, label)
        if live_group in GROUP_NAMES:
            entry['live_group'] = live_group
            STORE.save_providers([entry if e['key'] == entry['key'] else e for e in STORE.providers()])
        notify('Add-on connected')


def live_home():
    item('Check and repair TV / channel status', 'maintenance', artwork='settings')
    for entry in STORE.providers():
        if entry.get('enabled', True) and entry.get('url') == 'https://nocords.xyz/pluto/playlist.m3u':
            item('Pluto TV', 'live_source', provider=entry['key'], group='internet', artwork='live')
    item('Kodi TV and guide', 'pvr', artwork='live')
    item('Favourite channels', 'live_saved', collection='favourites', artwork='live')
    item('Recently watched', 'live_saved', collection='recent', artwork='live')
    item('Search Live TV', 'search', live_only='true', artwork='search')
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    for group, name in GROUPS:
        item(name, 'live_catalogues', group=group, artwork='live')
    item('Programme information settings', 'programme_settings', artwork='settings')
    finish()


def live_catalogues(group):
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


def provider_catalogues(group):
    matches = list(grouped_catalogues(STORE.providers(), group))
    seen = set()
    for entry, catalog in matches:
        if entry['key'] not in seen:
            item(entry['label'], 'live_source', provider=entry['key'], group=group, artwork='live')
            seen.add(entry['key'])
    item('Search Live TV', 'search', live_only='true', artwork='search')
    item('Add another {} source'.format(GROUP_NAMES[group]), 'add', group=group, artwork='settings')
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    item('Manage sources', 'manage', artwork='settings')
    if not matches:
        notify('Add a manifest source to this category to load channels or events.')
    xbmcplugin.setPluginCategory(HANDLE, GROUP_NAMES[group])
    finish()


def live_source(provider, group):
    entry = STORE.provider(provider)
    matches = [(e, c) for e, c in grouped_catalogues([entry], group) if not search_only(c)]
    for _, catalog in sorted(matches, key=lambda pair: browse_title(pair[1]).casefold()):
        item(browse_title(catalog), 'live_categories', provider=provider, catalog=STORE.put(catalog), artwork='live')
    if not matches:
        notify('This source offers search only. Use Search this source.')
    if any(any(x.get('name') == 'search' for x in c.get('extra', [])) for c in entry_catalogs(entry)):
        item('Search this source', 'search', provider=provider, live_only='true', artwork='search')
    xbmcplugin.setPluginCategory(HANDLE, entry['label'])
    finish()


def live_categories(provider, catalog):
    cat = STORE.get(catalog)
    genres = next((x.get('options', []) for x in cat.get('extra', []) if x.get('name') == 'genre'), [])
    if not genres:
        catalog_page(provider, catalog)
        return
    item('All channels', 'catalog', provider=provider, catalog=catalog, artwork='live')
    for genre in sorted(set(genres), key=str.casefold):
        if genre.casefold() in ('all', 'tutti'):
            continue
        item(genre, 'catalog', provider=provider, catalog=catalog,
             extras=json.dumps({'genre': genre}), artwork='live')
    xbmcplugin.setPluginCategory(HANDLE, browse_title(cat))
    finish()


def live_saved(collection):
    if collection not in ('favourites', 'recent'):
        raise ValueError('Unknown channel collection.')
    entries = LIVE_LIBRARY.entries(collection)
    LIVE_LIBRARY.begin_listing()
    for channel in entries:
        saved = LIVE_LIBRARY.resolve(channel)
        if saved:
            item(channel['meta'].get('name', 'Channel'), 'live_play', folder=False, key=STORE.put(saved),
                 meta=channel['meta'], channel=saved)
        else:
            item(channel['meta'].get('name', 'Channel') + ' — source disabled or removed',
                 'live_unavailable', key=STORE.put(channel), meta=channel['meta'])
    if not entries:
        notify('Long-press a channel to add a favourite.' if collection == 'favourites'
               else 'Channels appear here after playback starts.')
    xbmcplugin.setPluginCategory(HANDLE, 'Favourite channels' if collection == 'favourites' else 'Recently watched')
    finish()


def import_providers():
    path = DIALOG.browse(1, 'Choose text file: one manifest URL per line', 'files', '.txt|.json')
    if not path:
        return
    with xbmcvfs.File(path) as file:
        raw = file.read()
    if len(raw) > 1024 * 1024:
        raise ValueError('Import file is too large.')
    if raw.lstrip().startswith('['):
        urls = json.loads(raw)
        if not isinstance(urls, list) or not all(isinstance(x, str) for x in urls):
            raise ValueError('JSON imports must be a list of manifest URL strings.')
    else:
        urls = [x.strip() for x in raw.splitlines() if x.strip() and not x.lstrip().startswith('#')]
    success, failed = 0, 0
    for url in urls[:100]:
        try:
            STORE.add(url)
            success += 1
        except Exception:
            failed += 1
    DIALOG.ok('Import complete', '{} connected; {} failed. Maximum 100 URLs per import.'.format(success, failed))


def web_setup():
    import secrets
    import time
    from engine import read_json, write_json
    root = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    request_path = os.path.join(root, 'web-setup-request.json')
    endpoint_path = os.path.join(root, 'web-setup-endpoint.json')
    nonce = secrets.token_hex(16)
    monitor = xbmc.Monitor()
    write_json(request_path, {'nonce': nonce, 'time': time.time()})
    progress = xbmcgui.DialogProgress()
    progress.create(BRAND, 'Opening source setup for your phone or PC…')
    deadline, endpoint = time.monotonic() + 12, {}
    try:
        while time.monotonic() < deadline and not monitor.abortRequested():
            if progress.iscanceled():
                return home()
            endpoint = read_json(endpoint_path)
            if endpoint.get('nonce') == nonce:
                break
            monitor.waitForAbort(0.2)
        progress.close()
        if endpoint.get('nonce') != nonce:
            DIALOG.ok(BRAND, 'The CBR setup service did not answer. Restart Kodi and open Source setup again.')
        elif endpoint.get('error'):
            DIALOG.ok(BRAND, endpoint['error'])
        else:
            DIALOG.ok('CBR source setup',
                      'On a phone or PC connected to the same home network, open:\n[B]{}[/B]\n\n'
                      'Pairing code: [B]{}[/B]\n\n'
                      'Leave this screen open while you add or edit sources. Setup closes after ten minutes. '
                      'Select OK when finished.'.format(endpoint['url'], endpoint['code']))
    finally:
        progress.close()
        write_json(request_path, {'nonce': nonce, 'stop': True})
    home()


def provider_menu(key):
    entry = STORE.provider(key)
    options = ['Disable' if entry.get('enabled', True) else 'Enable', 'Refresh manifest', 'Rename', 'Remove',
               'Live TV category: ' + GROUP_NAMES.get(entry.get('live_group'), 'Automatic')]
    index = DIALOG.select(entry['label'], options)
    if index == 1:
        refreshed = STORE.add(entry['url'], entry['label'])
        refreshed['enabled'] = entry.get('enabled', True)
        entries = STORE.providers()
        STORE.save_providers([refreshed if x['key'] == key else x for x in entries])
        return
    entries = STORE.providers()
    if index == 0:
        for x in entries:
            if x['key'] == key:
                x['enabled'] = not x.get('enabled', True)
    elif index == 2:
        label = DIALOG.input('Add-on display name', entry['label'])
        if label.strip():
            for x in entries:
                if x['key'] == key:
                    x['label'] = label.strip()
    elif index == 3:
        entries = [x for x in entries if x['key'] != key]
    elif index == 4:
        selected = DIALOG.select('Live TV category', ['Automatic'] + [label for _, label in GROUPS])
        if selected >= 0:
            for x in entries:
                if x['key'] == key:
                    x.pop('live_group', None)
                    if selected:
                        x['live_group'] = GROUPS[selected - 1][0]
    STORE.save_providers(entries)


def catalogs(search=None):
    for entry in STORE.providers():
        if not entry.get('enabled', True):
            continue
        for catalog in entry_catalogs(entry):
            if not isinstance(catalog, dict) or not catalog.get('id') or not catalog.get('type'):
                continue
            extra = catalog.get('extra', [])
            if search is not None and not any(x.get('name') == 'search' for x in extra):
                continue
            yield entry, catalog


def catalogues(media_type=None):
    for entry, catalog in catalogs():
        if media_type and catalog['type'] != media_type:
            continue
        key = STORE.put(catalog)
        item('{} / {} ({})'.format(entry['label'], catalog.get('name', catalog['id']), catalog['type']),
             'catalog', provider=entry['key'], catalog=key, artwork='catalogues')
    finish()


def add_metas(metas, provider, media_type, seen=None, live_group=None, live_country=''):
    records = []
    for meta in metas:
        if not isinstance(meta, dict) or not meta.get('id'):
            continue
        meta = dict(meta)
        meta.setdefault('type', media_type)
        identity = (meta['type'], meta['id'])
        if seen is not None:
            if identity in seen:
                continue
            seen.add(identity)
        saved = {'meta': meta, 'provider': provider}
        if live_group:
            saved.update(live_group=live_group, resource_type=media_type, live_country=live_country)
        if live_group:
            records.append(saved)
        else:
            key = STORE.put(saved)
            item(meta.get('name', meta['id']), 'meta', meta=meta, key=key)
    if records:
        LIVE_LIBRARY.begin_listing()
        key = STORE.put(records)
        for index, saved in enumerate(records):
            meta = saved['meta']
            item(meta.get('name', meta['id']), 'live_play', folder=False,
                 meta=meta, key=key, index=index, channel=saved)


def catalog_page(provider, catalog, extras=None, offset=0, refresh=False):
    entry = STORE.provider(provider)
    cat = STORE.get(catalog)
    live_group = catalogue_group(entry, cat)
    extras = dict(extras or {})
    for spec in cat.get('extra', []):
        name = spec.get('name')
        if name == 'skip' or name in extras:
            continue
        if live_group and name == 'genre' and not spec.get('isRequired'):
            continue
        if not spec.get('isRequired') and name != 'genre':
            continue
        options = spec.get('options', [])
        if options:
            choices = options if spec.get('isRequired') else ['All'] + options
            index = DIALOG.select('Choose ' + name, choices)
            if index < 0:
                finish()
                return
            if spec.get('isRequired') or index > 0:
                extras[name] = choices[index]
        elif spec.get('isRequired'):
            value = DIALOG.input('Enter ' + name)
            if not value:
                finish()
                return
            extras[name] = value
    url = resource_url(entry['url'], 'catalog', cat['type'], cat['id'], extras)
    loader = lambda unused: fetch_resource(entry, 'catalog', cat['type'], cat['id'], extras)
    data = (LIVE_CATALOGUES.get(url, loader, lifetime=60 if live_group == 'sports' else 300, refresh=refresh)
            if live_group else loader(url))
    metas = data.get('metas', [])
    offset = max(0, int(offset)) if live_group else 0
    displayed = metas[offset:offset + 100] if live_group else metas
    hint = country_for({'genres': [cat.get('name', ''), extras.get('genre', '')]}) if live_group else ''
    add_metas(displayed, provider, cat['type'], live_group=live_group, live_country=hint)
    if cat['type'] == 'movie' and metas:
        item('Add this page to Kodi Movies library', 'export_page',
             key=STORE.put([dict(m, type='movie') for m in metas if isinstance(m, dict) and m.get('type', 'movie') == 'movie']),
             artwork='library')
    if live_group and offset + len(displayed) < len(metas):
        item('Next page', 'catalog', provider=provider, catalog=catalog,
             extras=json.dumps(extras), offset=offset + 100, artwork='live')
    elif metas and any(x.get('name') == 'skip' for x in cat.get('extra', [])):
        next_extras = dict(extras, skip=int(extras.get('skip', 0)) + len(metas))
        item('Next page', 'catalog', provider=provider, catalog=catalog, extras=json.dumps(next_extras))
    if live_group:
        item('Refresh channels', 'catalog', provider=provider, catalog=catalog, extras=json.dumps(extras),
             refresh='true', offset=offset, artwork='settings')
    if not metas:
        notify('No results in this catalogue')
    finish('movies' if cat['type'] == 'movie' else 'videos')


def search(media_type=None, live_only=False, provider=None):
    if live_only:
        prompt = 'Search Live TV and sports'
    elif media_type == 'movie':
        prompt = 'Search movies'
    elif media_type == 'series':
        prompt = 'Search TV series'
    else:
        prompt = 'Search movies, series and channels'
    query = DIALOG.input(prompt)
    if not query.strip():
        finish()
        return
    # Each catalogue can have different required filters; skip those that cannot
    # be satisfied by search alone instead of issuing malformed requests.
    from concurrent.futures import ThreadPoolExecutor
    candidates = [(e, c) for e, c in catalogs(query)
                  if (not media_type or c['type'] == media_type)
                  and (not provider or e['key'] == provider)
                  and (not live_only or catalogue_group(e, c) is not None) and not any(
        x.get('isRequired') and x.get('name') != 'search' for x in c.get('extra', []))]
    def run(pair):
        e, c = pair
        try:
            data = fetch_resource(e, 'catalog', c['type'], c['id'], {'search': query.strip()})
            return e, c, data.get('metas', []), False
        except Exception:
            return e, c, [], True
    seen, errors = set(), 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        for entry, cat, metas, error in executor.map(run, candidates):
            errors += int(error)
            add_metas(metas, entry['key'], cat['type'], seen, catalogue_group(entry, cat))
    if errors:
        notify('{} catalogue(s) could not be searched.'.format(errors))
    if not seen:
        notify('No results. Check connected catalogues in Manage sources.')
    finish('movies' if media_type == 'movie' else 'videos')


"""Functions inserted into the Kodi video entry point by the release builder."""
def maintenance_menu():
    item('Check and repair TV (channels and guide)', 'maintenance_tv_repair', artwork='live')
    item('Channel status / find a missing channel', 'maintenance_channels', artwork='live')
    item('Check channel links (small media samples)', 'maintenance_channel_test', artwork='settings')
    item('Check CBR component updates', 'maintenance_updates', artwork='settings')
    item('Check and repair CBR', 'maintenance_repair', artwork='settings')
    item('View CBR status and diagnostics', 'maintenance_report', artwork='settings')
    item('Test sources (catalogues and sample streams)', 'maintenance_test', artwork='settings')
    item('Back up CBR settings', 'maintenance_backup', artwork='settings')
    item('Restore CBR settings backup', 'maintenance_restore', artwork='settings')
    item('Organise channels and favourites on phone / PC', 'web_setup', artwork='live')
    item('Uninstall CBR safely', 'maintenance_uninstall', artwork='settings')
    finish()


def maintenance_action(action):
    from resources.lib import maintenance as care
    if action in ('maintenance_tv_repair','maintenance_channels','maintenance_channel_test','maintenance_updates'):
        from resources.lib import tools_ui
        if action=='maintenance_tv_repair':tools_ui.repair(STORE,ADDON.getAddonInfo('path'),rpc)
        elif action=='maintenance_updates':tools_ui.updates(STORE,ADDON.getAddonInfo('path'),rpc)
        else:tools_ui.channels(STORE,test=action=='maintenance_channel_test')
    elif action == 'maintenance_report':
        data = care.diagnose(STORE, ADDON.getAddonInfo('path'))
        DIALOG.textviewer('CBR status and diagnostics', json.dumps(data, indent=2))
    elif action == 'maintenance_repair':
        ensure_defaults(STORE, ADDON.getAddonInfo('path'))
        repo = 'repository.crb.android' if xbmc.getCondVisibility('System.Platform.Android') else 'repository.crb.windows'
        try:
            rpc('Addons.SetAddonEnabled', {'addonid':repo,'enabled':True})
        except Exception:
            DIALOG.ok(BRAND, 'The CBR repository is missing. Install it from your CBR source before enabling automatic updates. Your existing sources are kept.')
        care.request_repair(STORE)
        xbmc.executebuiltin('UpdateAddonRepos')
        DIALOG.ok('CBR repair requested', 'CBR will refresh public defaults, programme feeds and its TV guide while idle. Disabled sources and personal manifests are kept.\n\nFor automatic installation, select CBR Information → Versions → the CBR repository version once, and keep Kodi automatic updates enabled. Use View CBR status for details.')
    elif action == 'maintenance_test':
        import threading
        progress = xbmcgui.DialogProgress(); progress.create('Check CBR sources', 'Checking catalogues and small stream samples. No torrent downloads are started.')
        result = {}
        def work():
            try: result['data'] = care.test_sources(STORE)
            except Exception: result['error'] = True
        worker = threading.Thread(target=work, daemon=True); worker.start()
        monitor = xbmc.Monitor()
        while worker.is_alive() and not monitor.abortRequested():
            if progress.iscanceled():break
            worker.join(0.2)
        progress.close()
        if result.get('data'):
            labels = {e['key']:e['label'] for e in STORE.providers()}
            DIALOG.textviewer('Source test results', '\n\n'.join('{}: catalogue {} · stream {}'.format(labels.get(k,'Source'),care.status_text(v['catalogue']),care.status_text(v['stream'])) for k,v in result['data'].items())+'\n\nA responding sample is not a full playback or audio-language verification.')
        elif result.get('error'):
            DIALOG.ok(BRAND, 'Source tests could not finish. Your sources were kept.')
    elif action == 'maintenance_backup':
        personal = DIALOG.yesno('Include personal settings?', 'Include manifest URLs and saved channels for transfer to another device? Keep the resulting file private. Choose No for channel layout only.', yeslabel='Include personal settings', nolabel='Layout only')
        folder = DIALOG.browse(3, 'Save CBR backup folder', 'files')
        if folder:
            address = folder.rstrip('/\\') + '/cbr-settings-backup.json'
            data = care.export_backup(STORE, personal)
            with xbmcvfs.File(address, 'w') as target:target.write(json.dumps(data, indent=2))
            DIALOG.ok(BRAND, 'Backup saved. On another device use Restore CBR settings backup, or upload it through the paired PC setup page.')
    elif action == 'maintenance_restore':
        address = DIALOG.browse(1, 'Choose CBR settings backup', 'files', '.json')
        if address:
            with xbmcvfs.File(address) as source:raw = source.read(care.LIMIT + 1)
            if len(raw.encode('utf8')) > care.LIMIT:raise ValueError('Backup exceeds 4 MB.')
            data = json.loads(raw); files = care.validate_backup(data)
            if DIALOG.yesno('Restore CBR settings?', 'Replace these CBR settings: '+', '.join(files)+'. A copy of the current settings will be kept. Personal provider links may require renewal at the new location.'):
                care.restore_backup(STORE, data)
                DIALOG.ok(BRAND, 'Settings restored. CBR will rebuild its guide while idle. Restart Kodi to refresh all menus and TV listings.')
    elif action == 'maintenance_uninstall':
        try:rpc('Addons.ExecuteAddon', {'addonid':'script.crb.wizard','params':{'mode':'uninstall'}})
        except Exception:DIALOG.ok(BRAND, 'Install the latest CBR Setup Wizard, then choose Uninstall CBR there.')
    maintenance_menu()


def rpc(method, params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    if result.get('error'):
        raise RuntimeError('Kodi could not complete this library or shortcut action.')
    return result.get('result')


def library_setup():
    item('Open Kodi Movies', 'open_movies', artwork='library')
    item('How to show exported movies in the Movies section', 'library_help', artwork='library')
    item('Scan exported movies (after setting up the source)', 'scan_library', artwork='library')
    item('Add Movies shortcut to Kodi Favourites', 'favourite', artwork='library')
    finish()


def library_help():
    DIALOG.textviewer('Show movies on Kodi home → Movies',
        '1. On any movie, open the context menu (right-click / long-press / C) and choose '
        'Add to Kodi Movies library. You can also export a displayed page of movies.\n\n'
        '2. In Kodi open Videos → Files → Add videos → Browse → Add video source. '
        'Use this exact directory as the source:\n\n' + LIBRARY.root + '\n\n'
        'You can type this equivalent Kodi path in the source field:\n'
        'special://profile/addon_data/plugin.video.stremio.bridge/library/Movies/\n\n'
        '3. Set This directory contains to Movies and the information provider to Local information only. '
        'Enable Movies are in separate folders that match the movie title. Confirm and scan.\n\n'
        'Your exported titles then appear in Kodi home → Movies with their posters and descriptions. '
        'Selecting a movie asks you to choose a current stream from your connected providers. '
        'The source setup is needed once per Kodi profile. Use Scan exported movies after adding more titles.\n\n'
        'Video add-ons are installed in Kodi\'s Video add-ons category. Movie library entries use Kodi\'s '
        'native .strm and .nfo files; the bridge does not replace your skin or edit existing library sources.')


def export_movie(key):
    saved = STORE.get(key)
    meta = saved['meta']
    # Enrich the exported NFO when the originating catalogue only provides a preview.
    entries = sorted(STORE.providers(), key=lambda e: e['key'] != saved['provider'])
    for _, data, _ in aggregate(entries, 'meta', 'movie', meta['id']):
        if isinstance(data.get('meta'), dict):
            meta = dict(meta, **data['meta'])
            break
    LIBRARY.export(meta)
    notify('Added movie export. Scan the Movies source to show it in Kodi Movies.')


def export_page(key):
    movies = STORE.get(key)
    count = 0
    for meta in movies:
        if meta.get('id') and meta.get('type', 'movie') == 'movie':
            LIBRARY.export(dict(meta, type='movie'))
            count += 1
    notify('{} movies exported. Set up or scan the Movies source.'.format(count))
    library_setup()


def library_play(movie):
    meta = LIBRARY.load(movie)
    results = aggregate(STORE.providers(), 'stream', 'movie', meta['id'])
    failures(results)
    options = []
    for entry, data, _ in results:
        for stream in data.get('streams', []):
            if isinstance(stream, dict):
                text = stream.get('description') or stream.get('title') or stream.get('name') or stream_kind(stream)
                label = '{} | {} | {}'.format(entry['label'], stream.get('name', ''), str(text).replace('\n', ' / '))
                options.append((label, stream))
    if not options:
        DIALOG.ok('No streams available', 'Connect a stream provider in Crimson Blood Requiem → Sources and player settings → Manage sources.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    index = DIALOG.select(meta.get('name', 'Choose stream'), [label for label, _ in options])
    if index < 0:
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    key = STORE.put({'stream': options[index][1], 'type': 'movie', 'id': meta['id'], 'meta': meta})
    play(key)


def cached_item(key, index=None):
    saved = STORE.get(key)
    if index is not None:
        index = int(index)
        if not isinstance(saved, list) or not 0 <= index < len(saved):
            raise ValueError('This channel list has changed. Reopen its catalogue.')
        saved = saved[index]
    return saved


def programme_channel(key, index=None):
    saved = cached_item(key, index)
    return saved if saved.get('provider_id') else LIVE_LIBRARY.channel(saved)


def programme_info(key, index=None):
    channel = programme_channel(key, index)
    result = PROGRAMMES.lookup(channel)
    if result is None:
        entry = STORE.provider(channel['provider'])
        for _, data, _ in aggregate([entry], 'meta', channel['resource_type'], channel['meta']['id']):
            if isinstance(data.get('meta'), dict):
                result = PROGRAMMES.lookup(channel, data['meta'])
                break
    text = programme_text(result)
    if not result or not (result.get('now') or result.get('next')):
        text += '\n\nProgramme data may still be downloading. Use Programme information settings to check updates, '
        text += 'or Match programme channel from the channel menu if an automatic match is unavailable.'
    DIALOG.textviewer(channel['meta'].get('name', 'Programme information'), text)
    PROGRAMMES.close()


def programme_match(key, index=None):
    channel = programme_channel(key, index)
    choices = PROGRAMMES.channels()
    if not choices:
        DIALOG.ok('Programme information', 'No schedule channels are loaded yet. Open Live TV → Programme information settings and request an update.')
        return
    selected = DIALOG.select('Match ' + channel['meta'].get('name', 'channel'),
                             ['Use automatic matching'] + [x['name'] + ' / ' + x['label'] for x in choices])
    if selected >= 0:
        PROGRAMMES.map_channel(channel, choices[selected - 1] if selected else None)
        notify('Programme channel match saved')
        xbmc.executebuiltin('Container.Refresh')
    PROGRAMMES.close()


def programme_options():
    config = programme_settings(STORE)
    selected = DIALOG.select('Programme information', ['Update programmes now', 'Manage schedule feeds on phone / PC',
        'View update status', 'Turn off programme information' if config.get('enabled', True) else 'Turn on programme information'])
    if selected == 0:
        request_refresh(STORE)
        notify('Programme information will update in the background')
    elif selected == 1:
        web_setup()
        return
    elif selected == 2:
        status = STORE.read(os.path.join(STORE.root, 'programme-status.json'), {})
        text = []
        for feed in config['feeds']:
            state = status.get(feed['key'], {})
            updated = state.get('updated')
            from datetime import datetime
            text.append('{}: {}\n{} channels, {} programmes\nLast update: {}'.format(feed['label'],
                state.get('state', 'Waiting for first download'), state.get('channels', 0), state.get('programmes', 0),
                datetime.fromtimestamp(updated).strftime('%d %b %H:%M') if updated else 'Not yet downloaded'))
        DIALOG.textviewer('Programme update status', '\n\n'.join(text) or 'No schedule feeds configured.')
    elif selected == 3:
        config['enabled'] = not config.get('enabled', True)
        save_programme_settings(STORE, config)
    live_home()


def pvr_menu():
    item('Set up Kodi TV / IPTV Simple Client', 'pvr_setup', artwork='settings')
    item('Build / update TV channels and guide', 'pvr_refresh', artwork='live')
    item('Choose sources / edit channel numbers on PC', 'web_setup', artwork='settings')
    item('Open Kodi TV channels', 'pvr_channels', artwork='live')
    item('Open Kodi channel guide', 'pvr_guide', artwork='live')
    item('Use CBR channel numbers in Kodi TV', 'pvr_numbers', artwork='settings')
    item('TV setup status', 'pvr_status', artwork='settings')
    finish()


def pvr_setup():
    import time
    heartbeat = STORE.read(os.path.join(STORE.root, 'pvr-service.json'), {}).get('time', 0)
    if time.time() - heartbeat > 60:
        DIALOG.ok('Restart Kodi', 'Fully close and reopen Kodi to start the new CBR TV service, then run this setup again.')
        pvr_menu()
        return
    if xbmc.Player().isPlaying():
        DIALOG.ok('Kodi TV setup', 'Stop the current video before connecting IPTV Simple Client.')
        pvr_menu()
        return
    if not xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)'):
        xbmc.executebuiltin('InstallAddon(pvr.iptvsimple)', True)
    if not xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)'):
        DIALOG.ok('IPTV Simple Client', 'Install PVR IPTV Simple Client from Kodi Add-on repository → PVR clients, then run this setup again.')
        pvr_menu()
        return
    pvr.refresh(STORE)
    requested = STORE.read(os.path.join(STORE.root, 'pvr-request.json'))['time']
    progress, monitor = xbmcgui.DialogProgress(), xbmc.Monitor()
    progress.create('CBR Kodi TV', 'Preparing channels and programme guide…')
    ready = False
    try:
        for step in range(360):
            state = STORE.read(os.path.join(STORE.root, 'pvr-status.json'), {})
            if state.get('state') == 'ready' and state.get('updated', 0) >= requested:
                ready = True
                break
            if state.get('state') == 'error' and state.get('attempted', 0) >= requested:
                break
            if progress.iscanceled() or monitor.waitForAbort(0.25):
                break
            progress.update(min(95, step // 4), 'Building your TV channels in the background…')
    finally:
        progress.close()
    if not ready:
        DIALOG.ok('CBR Kodi TV', 'The channel build has not completed. Check TV setup status and the selected sources on the PC setup page, then run setup again.')
        pvr_menu()
        return
    root = 'special://profile/addon_data/plugin.video.stremio.bridge/pvr/'
    profile = xbmcvfs.translatePath('special://profile/addon_data/pvr.iptvsimple/')
    pvr.configure_instance(profile, root + 'channels.m3u', root + 'guide.xml')
    other_instances = []
    import xml.etree.ElementTree as ET
    for name in os.listdir(profile):
        if name.startswith('instance-settings-') and name.endswith('.xml'):
            try:
                data = {n.get('id'): n.text for n in ET.parse(os.path.join(profile, name)).getroot()}
                if data.get('kodi_addon_instance_name') != 'CBR TV':
                    other_instances.append(name)
            except (ET.ParseError, OSError):
                continue
    if not other_instances:
        rpc('Settings.SetSettingValue', {'setting': 'pvrmanager.usebackendchannelnumbers', 'value': True})
    rpc('Addons.SetAddonEnabled', {'addonid': 'pvr.iptvsimple', 'enabled': False})
    monitor.waitForAbort(0.5)
    rpc('Addons.SetAddonEnabled', {'addonid': 'pvr.iptvsimple', 'enabled': True})
    DIALOG.ok('CBR Kodi TV', 'CBR TV is connected. Open Kodi → TV → Channels or Guide. If the new instance has not appeared yet, restart Kodi once. Channel numbers can be edited through the PC setup page.')
    pvr_menu()


def pvr_play(identity):
    row, variants = pvr.channel(STORE, identity)
    from resources.lib.playback_memory import retry_context
    context = retry_context(STORE,identity,row['name'],row['number'])
    path = None
    for variant in LIVE_AUTOPLAY.memory.variants(variants):
        entry = STORE.provider(variant['provider'])
        streams = []
        for _, data, _ in aggregate([entry], 'stream', variant['resource_type'], variant['meta']['id']):
            streams.extend(s for s in data.get('streams', []) if isinstance(s, dict))
        path = LIVE_AUTOPLAY.begin(variant['meta'], variant, streams, probe=probe_stream, context=context)
        LIVE_AUTOPLAY.clear()
        if path:
            break
    # PVR owns channel switching and stopping. Select a working URL here but do
    # not let the video add-on's retry service replace PVR with ordinary playback.
    if not path:
        notify('This TV channel is currently unavailable.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    li = xbmcgui.ListItem(path=path)
    if urlsplit(path.split('|', 1)[0]).path.lower().endswith('.mpd'):
        li.setContentLookup(False)
        li.setMimeType('application/dash+xml')
        li.setProperty('inputstream', 'inputstream.adaptive')
    li.getVideoInfoTag().setTitle(row['name'])

    li.getVideoInfoTag().setPlot(programme_text(PROGRAMMES.lookup(variant)))
    li.setArt({'thumb': row['logo']})
    li.setProperty('IsPlayable', 'true')
    import time
    STORE.write(os.path.join(STORE.root, 'live-confirmation.json'), dict(time=time.time(), name=row['name'], channel=variant))
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def metadata(key, index=None, autoplay=False):
    saved = cached_item(key, index)
    if saved.get('sports_variants'):
        sports_streams(saved, autoplay)
        return
    preview = saved['meta']
    providers = sorted(STORE.providers(), key=lambda x: x['key'] != saved['provider'])
    resource_type = saved.get('resource_type', preview['type'])
    origin = STORE.provider(saved['provider'])
    live_group = saved.get('live_group') or catalogue_group(origin, {'type': resource_type})
    if live_group:
        providers = [origin]
        if not autoplay:
            LIVE_AUTOPLAY.clear()
    results = aggregate(providers, 'meta', resource_type, preview['id'])
    meta = next((data['meta'] for _, data, _ in results if isinstance(data.get('meta'), dict) and data['meta']), preview)
    meta = dict(preview, **meta)
    if live_group:
        saved = dict(saved, native_schedule=provider_programmes(meta))
    hints = meta.get('behaviorHints') or {}
    # Cinemeta sets hasScheduledVideos for ongoing series with future episodes.
    # Series still need season/episode selection; that hint only changes the
    # navigation for non-series schedules such as channels.
    if (not live_group and meta.get('videos') and meta['type'] != 'tv' and not hints.get('isLive')
            and (meta['type'] == 'series' or not hints.get('hasScheduledVideos'))):
        seasons = sorted({v.get('season', 0) for v in meta['videos']}, key=lambda x: int(x or 0))
        for season in seasons:
            payload = STORE.put({'meta': meta, 'season': season})
            item('Season {}'.format(season) if season else 'Videos / Specials', 'episodes', key=payload, meta=meta)
        xbmcplugin.setPluginCategory(HANDLE,meta.get('name','Seasons'))
        finish('seasons')
    else:
        video_id = hints.get('defaultVideoId') or meta['id']
        show_streams(resource_type, video_id, meta, meta.get('streams'), channel=saved if live_group else None,
                     autoplay=autoplay)


def episodes(key):
    saved = STORE.get(key)
    meta = saved['meta']
    videos = [v for v in meta['videos'] if v.get('season', 0) == saved['season']]
    videos.sort(key=lambda x: (int(x.get('episode') or 0), str(x.get('released', ''))))
    for video in videos:
        if not video.get('id'):
            continue
        title = video.get('title') or video.get('name') or 'Episode'
        if video.get('episode') is not None:
            title = '{}. {}'.format(video['episode'], title)
        display = dict(meta, seriesName=meta.get('name',''), season=video.get('season'), episode=video.get('episode'), name=title, description=video.get('overview', meta.get('description', '')),
                       thumbnail=video.get('thumbnail', ''))
        payload = STORE.put({'type': meta['type'], 'id': video['id'], 'meta': display, 'inline': video.get('streams')})
        item(title, 'streams', key=payload, meta=display)
    xbmcplugin.setPluginCategory(HANDLE,meta.get('name','Episodes'))
    finish('episodes')


def show_streams(media_type, item_id, meta, inline=None, channel=None, autoplay=False):
    streams = []
    if inline:
        streams = [('Embedded source', s) for s in inline]
    else:
        providers = STORE.providers()
        if channel and channel.get('provider'):
            providers = [entry for entry in providers if entry['key'] == channel['provider']]
        results = command_job('Finding playback sources',lambda:aggregate(providers, 'stream', media_type, item_id))
        if results is None:
            finish();return
        failures(results)
        for entry, data, _ in results:
            streams.extend((entry['label'], s) for s in data.get('streams', []) if isinstance(s, dict))
    if autoplay and channel:
        bookmark = LIVE_LIBRARY.channel(channel)
        command_request=command_time.time()
        xbmcgui.Window(10000).setProperty('CBR.PlaybackRequested',str(command_request))
        xbmcgui.Window(10000).setProperty('CBR.PlaybackStatus','Connecting to live TV…')
        path = LIVE_AUTOPLAY.begin(meta, bookmark, [stream for _, stream in streams], probe=probe_stream)
        if STORE.read(os.path.join(STORE.root,'command-cancel.json'),{}).get('time',0)>=command_request:
            LIVE_AUTOPLAY.clear();xbmcgui.Window(10000).clearProperty('CBR.PlaybackStatus')
            xbmcplugin.setResolvedUrl(HANDLE,False,xbmcgui.ListItem());return
        if path:
            li = xbmcgui.ListItem(path=path)
            li.getVideoInfoTag().setTitle(meta.get('name', 'Live TV'))
            li.setArt({'thumb': meta.get('logo') or meta.get('poster', '')})
            li.getVideoInfoTag().setPlot(programme_text(PROGRAMMES.lookup(bookmark, meta))
                                       if PROGRAMMES.config.get('enabled', True) else meta.get('description', ''))
            LIVE_LIBRARY.pending(bookmark, path)
            xbmcplugin.setResolvedUrl(HANDLE, True, li)
        else:
            notify('No compatible automatic link. Long-press the channel and choose a stream manually.')
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    if not channel and media_type in ('movie','series'):
        quality_list(STORE.put(dict(type=media_type,id=item_id,meta=meta,streams=streams)))
        return
    render_stream_links(media_type,item_id,meta,streams,channel)
    if not streams:
        notify('No playback links were returned. The channel or source may be unavailable.'
               if channel else 'No streams were returned by your enabled providers.')
    finish()


def quality_list(key,change=False):
    from resources.lib.stream_quality import OPTIONS,LABELS,mode,select,summary,details
    saved=STORE.get(key)
    selection=mode(ADDON.getSetting('vod_quality'))
    if change:
        selected=DIALOG.select('Movie / series link quality',[label for _,label in OPTIONS],preselect=[k for k,_ in OPTIONS].index(selection))
        if selected>=0:
            selection=OPTIONS[selected][0];ADDON.setSetting('vod_quality',LABELS[selection])
    candidates=[];notices=[]
    for source,stream in saved['streams']:
        (candidates if stream_kind(stream) in ('torrent','direct','youtube') else notices).append((source,stream))
    streams,counts=select(candidates,selection)
    message=summary(selection,len(streams),counts)
    item('Quality: '+LABELS[selection]+' · Change','quality_change',key=key,artwork='settings')
    item(message+' · Details','quality_info',key=key,artwork='settings')
    if not streams and candidates:notify('No links match '+LABELS[selection]+'. Change the quality filter to see other links.')
    elif counts.get('cam') and selection not in ('cam','all'):notify(message)
    render_stream_links(saved['type'],saved['id'],saved['meta'],streams+notices)
    if not saved['streams']:notify('No streams were returned by your enabled providers.')
    xbmcplugin.setPluginCategory(HANDLE,LABELS[selection]+' · '+saved['meta'].get('name','Playback links'))
    finish()


def quality_info(key):
    from resources.lib.stream_quality import mode,select,details
    saved=STORE.get(key);selection=mode(ADDON.getSetting('vod_quality'))
    candidates=[(source,stream) for source,stream in saved['streams'] if stream_kind(stream) in ('torrent','direct','youtube')]
    streams,counts=select(candidates,selection)
    DIALOG.textviewer('Movie / series source quality',details(selection,len(streams),counts))
    quality_list(key)


def render_stream_links(media_type,item_id,meta,streams,channel=None):
    for source, stream in streams:
        kind = stream_kind(stream)
        title = stream.get('description') or stream.get('title') or stream.get('name') or kind
        quality = stream.get('name', '')
        label = '{} | {} | {}'.format(source, quality, str(title).replace('\n', ' / '))
        if kind == 'torrent':
            label = '[Built-in torrent player] ' + label
        elif kind not in ('direct', 'youtube'):
            label = '[{}] '.format({'external': 'External service', 'configuration': 'Setup required',
                                    'unavailable': 'Source unavailable'}.get(kind, 'Unsupported')) + label
        saved = {'stream': stream, 'type': media_type, 'id': item_id, 'meta': meta}
        if channel:
            saved['channel'] = LIVE_LIBRARY.channel(channel)
        payload = STORE.put(saved)
        item(label, 'play', folder=False, key=payload, meta=meta)




def play(key):
    LIVE_AUTOPLAY.clear()
    saved = STORE.get(key)
    stream = saved['stream']
    kind = stream_kind(stream)
    if kind in ('external', 'unsupported', 'configuration', 'unavailable'):
        messages = {
            'external': 'This source opens a subscription service or webpage. Open it in the service app or browser:\n\n' + str(stream.get('externalUrl', '')),
            'unsupported': 'This stream transport is not supported by this bridge.',
            'configuration': 'This provider requires a new configured manifest URL. Update it in Sources and player settings → Manage sources.',
            'unavailable': str(stream.get('description') or stream.get('title') or 'The provider reports that this source is not currently available.')[:600],
        }
        DIALOG.ok('Source needs attention' if kind in ('configuration', 'unavailable') else 'Source needs another player', messages[kind])
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    if kind == 'youtube' and not xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)'):
        DIALOG.ok('YouTube playback', 'Install the YouTube add-on from the Kodi add-on repository, then select this video again.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    if kind == 'torrent':
        from torrent_player import prepare_item
        li = prepare_item(ADDON, stream, saved['meta'])
        if li is None:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
    else:
        li = xbmcgui.ListItem(path=playback_url(stream))
    li.getVideoInfoTag().setTitle(saved['meta'].get('name', 'Video'))
    subtitles = list(stream.get('subtitles') or [])
    hints = stream.get('behaviorHints') or {}
    extras = {k: hints[k] for k in ('videoHash', 'videoSize', 'filename') if hints.get(k) is not None}
    results = aggregate(STORE.providers(), 'subtitles', saved['type'], saved['id'], extras)
    for _, data, _ in results:
        subtitles.extend(data.get('subtitles', []))
    subtitles = [s for s in subtitles if isinstance(s, dict) and urlsplit(s.get('url', '')).scheme in ('https', 'http')]
    if subtitles:
        # Pick a subtitle explicitly, preserving the provider's language/variant labels.
        choices = ['No external subtitles'] + [s.get('label') or '{} ({})'.format(s.get('lang', '?'), i + 1) for i, s in enumerate(subtitles)]
        selected = DIALOG.select('Subtitles', choices)
        if selected > 0:
            li.setSubtitles([subtitles[selected - 1]['url']])
    if saved.get('channel'):
        LIVE_LIBRARY.pending(saved['channel'], li.getPath())
    if not command_prepare(saved,li):
        xbmcplugin.setResolvedUrl(HANDLE,False,xbmcgui.ListItem());return
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def local_video():
    path = DIALOG.browse(1, 'Select a local video', 'video', '.mp4|.mkv|.avi|.mov|.webm|.ts|.m4v')
    if path:
        xbmc.Player().play(path)
    home()


def help_dialog():
    DIALOG.textviewer('Crimson Blood Requiem — setup and compatibility',
        'Manage sources > Add another source / manifest URL, then paste each installed Stremio Share addon URL. '
        'You may import a .txt file with one manifest URL per line. Configured URLs can contain tokens; '
        'they are stored in Kodi\'s local add-on profile and should be kept private.\n\n'
        'Browse catalogues or Search, choose a title/episode, then select a stream. '
        'Cinemeta and Streaming Catalogs provide discovery, not playback. '
        'Cinemeta and Torrentio are included as public defaults. Torrent results use the bundled Windows x64 '
        'download and buffering engine. Player settings control its memory cache. No Elementum or separate '
        'Stream Bridge add-on is required. Personalised debrid or other provider URLs can be added in Manage sources.\n\n'
        'YouTube requires Kodi\'s YouTube add-on. WatchHub subscription links open in their own services; '
        'the bridge displays their URLs. M3U/EPG and PlavioLive work only when their manifests return '
        'compatible direct streams. There is no Kodi PVR/EPG integration. '
        'OpenSubtitles providers are queried before playback; choose a subtitle if available. '
        'Use Play a local video for files on this device.\n\n'
        'This is an independent community bridge, not an official Stremio or Kodi product. '
        'Provider availability, authentication, DRM and response-header proxy requirements can limit playback.')
    home()


def prototype_search():
    item('Search movies','search',media_type='movie',artwork='search')
    item('Search series','search',media_type='series',artwork='search')
    item('Search live TV','search',live_only='true',artwork='search')
    finish()


def prototype_series():
    candidates = [(e,c) for e,c in catalogs() if c['type']=='series' and not any(x.get('isRequired') for x in c.get('extra',[]))]
    candidates.sort(key=lambda pair: (pair[0]['manifest'].get('id')!='com.linvo.cinemeta',pair[1]['id']!='top'))
    for entry,cat in candidates:
        try:
            data=fetch_resource(entry,'catalog','series',cat['id'])
            metas=[m for m in data.get('metas',[]) if isinstance(m,dict) and m.get('id') and m.get('name')][:18]
            if metas:
                add_metas(metas,entry['key'],'series');break
        except Exception: pass
    finish('tvshows')


"""Sports Streams discovery, preserving provider metadata and IDs."""
def prototype_sports_entry():
    return next((e for e in STORE.providers() if e.get('enabled',True)
                 and e.get('manifest',{}).get('id')=='community.sports.fly'),None)


def prototype_sports_view():
    if xbmc.getSkinDir() not in ('skin.crimsonbloodrequiem','skin.cbr.prototype'):return
    # endOfDirectory releases the directory result before the Videos window is ready.
    # Wait briefly for that window so its remembered view cannot override the card grid.
    for unused in range(20):
        if xbmcgui.getCurrentWindowId()==10025:break
        xbmc.sleep(50)
    xbmc.sleep(150)
    xbmc.executebuiltin('Container.SetViewMode(560)')


def prototype_sports_categories():
    entry=prototype_sports_entry()
    if not entry:
        item('Connect Sports Streams in source setup','web_setup',artwork='settings')
    else:
        item('Sports favourites','command_sport_favourites',artwork='live')
        item('Teams & leagues','command_pins',artwork='live')
        item('Upcoming','command_upcoming',artwork='live')
        for cat in entry_catalogs(entry):
            if catalogue_group(entry,cat)=='sports':
                item(cat.get('name',cat['id']),'prototype_sports_catalog',catalog=cat['id'],artwork='live')
    finish()


def prototype_sports_cards(entry,metas,resource_type=None):
    LIVE_LIBRARY.begin_listing()
    for raw in metas:
        if not isinstance(raw,dict) or not raw.get('id') or not raw.get('name'):continue
        meta=dict(raw)
        meta.setdefault('type','sport')
        # Provider posters contain event/channel graphics. A clearlogo must not replace them.
        if meta.get('poster'):meta.pop('logo',None)
        saved=dict(provider=entry['key'],provider_id=entry['manifest']['id'],
                   provider_label=entry['label'],resource_type=resource_type or meta['type'],live_group='sports',meta=meta)
        item(meta['name'],'live_play',folder=False,meta=meta,channel=saved,key=STORE.put(saved))


def prototype_sports_catalog(identity=None,widget=False,refresh=False):
    entry=prototype_sports_entry()
    if not entry:
        if not widget:item('Connect Sports Streams','web_setup',artwork='settings')
        finish();return
    cats=[c for c in entry_catalogs(entry) if catalogue_group(entry,c)=='sports']
    cat=next((c for c in cats if c['id']==identity),None) if identity else next((c for c in cats if c['id']=='sports_live'),cats[0] if cats else None)
    if not cat:
        if not widget:notify('That catalogue is not enabled in your Sports Streams manifest.')
        finish();return
    from resources.lib.live import LiveCatalogueCache
    from resources.lib.core import resource_url
    try:
        path=resource_url(entry['url'],'catalog',cat['type'],cat['id'])
        data=LiveCatalogueCache(STORE).get(path,lambda unused:fetch_resource(entry,'catalog',cat['type'],cat['id']),refresh=refresh)
        prototype_sports_cards(entry,data.get('metas',[]),cat['type'])
        if not data.get('metas') and not widget:notify('No events or channels in this catalogue right now.')
    except Exception:
        if not widget:notify('Sports Streams could not be reached. Try Search other sports sources.')
    xbmcplugin.setPluginCategory(HANDLE,'Sports Streams / '+cat.get('name',cat['id']))
    finish()
    if not widget:prototype_sports_view()


def prototype_other_sports_search():
    query=DIALOG.input('Search other sports sources').strip()
    if not query:finish();return
    from concurrent.futures import ThreadPoolExecutor
    from resources.lib.sports import classifications
    candidates=[(e,c) for e,c in catalogs(query)
                if e.get('manifest',{}).get('id')!='community.sports.fly'
                and catalogue_group(e,c) is not None
                and not any(x.get('isRequired') and x.get('name')!='search' for x in c.get('extra',[]))]
    def run(pair):
        e,c=pair
        try:return e,c,fetch_resource(e,'catalog',c['type'],c['id'],{'search':query}).get('metas',[]),False
        except Exception:return e,c,[],True
    errors=count=0;seen=set()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for entry,cat,metas,error in pool.map(run,candidates):
            errors+=int(error)
            rows=[]
            for raw in metas:
                if not isinstance(raw,dict) or not classifications(raw,'all' if catalogue_group(entry,cat)=='sports' else '')[2]:continue
                marker=(entry['key'],raw.get('type',cat['type']),raw.get('id'))
                if marker in seen:continue
                seen.add(marker);rows.append(dict(raw,type=raw.get('type',cat['type']),description='Source: '+entry['label']+'\n\n'+raw.get('description','')))
            prototype_sports_cards(entry,rows,cat['type']);count+=len(rows)
    # Keep The Crew's maintained sports browser available when installed.
    crew_sport_link('all')
    if errors:notify('{} other catalogue(s) could not be searched.'.format(errors))
    if not count:notify('No matches in other sources. Try a channel, team or sport name.')
    xbmcplugin.setPluginCategory(HANDLE,'Other sports sources / '+query)
    finish();prototype_sports_view()


"""Command browsing and playback routes, injected into the existing CBR addon entry point."""
from resources.lib.command_state import CommandState,clean_meta,next_episode,episode_meta,identity,fingerprint
import time as command_time
import os

COMMAND=CommandState(STORE.root)

def command_job(title,fn):
    import threading,queue
    box=queue.Queue();monitor=xbmc.Monitor();dialog=xbmcgui.DialogProgress()
    def run():
        try:box.put((True,fn()))
        except Exception:box.put((False,None))
    dialog.create(BRAND,title)
    worker=threading.Thread(target=run,daemon=True);worker.start();started=command_time.monotonic()
    try:
        while box.empty():
            if dialog.iscanceled() or monitor.abortRequested():return None
            dialog.update(0,title+' · {}s'.format(int(command_time.monotonic()-started)))
            monitor.waitForAbort(.05)
        okay,value=box.get()
        if not okay:notify('The source could not be reached. Try another source or open Setup.');return None
        return value
    finally:dialog.close()


def command_set_view(content):
    if xbmc.getSkinDir() not in ('skin.crimsonbloodrequiem','skin.cbr.prototype'):return
    p=dict(parse_qsl(sys.argv[2][1:] if len(sys.argv)>2 else ''))
    if p.get('widget')=='true' or p.get('action')=='prototype_sports_categories':return
    view=561 if content in ('movies','tvshows') else (560 if content=='episodes' else 562)
    if p.get('action') in ('prototype_sports_catalog','prototype_other_sports_search','command_sport_favourites','command_upcoming','command_pin_search'):view=560
    for unused in range(20):
        if xbmcgui.getCurrentWindowId()==10025:break
        xbmc.sleep(50)
    xbmc.sleep(100);xbmc.executebuiltin('Container.SetViewMode({})'.format(view))


class CommandDetail(xbmcgui.WindowXMLDialog):
    def __init__(self,*a,**kw):
        self.meta=kw.pop('meta');self.caption=kw.pop('caption');self.resume=kw.pop('resume');self.following=kw.pop('following');self.favourite=kw.pop('favourite')
        self.choice='back';super().__init__(*a,**kw)
    def onInit(self):
        self.getControl(10).setImage(self.meta.get('background') or os.path.join(ART,'crb-fanart.jpg'))
        self.getControl(11).setImage(self.meta.get('poster') or os.path.join(ART,'crb-poster.png'))
        self.getControl(12).setText(self.meta.get('name','Title'))
        parts=[str(self.meta.get('releaseInfo',''))]
        if self.meta.get('imdbRating'):parts.append('IMDb '+str(self.meta['imdbRating']))
        if self.meta.get('runtime'):parts.append(str(self.meta['runtime']))
        if self.meta.get('genres'):parts.append(' · '.join(self.meta['genres'][:4]))
        self.getControl(13).setLabel('  |  '.join(x for x in parts if x))
        self.getControl(14).setText(self.meta.get('description') or self.meta.get('overview') or 'No description is available for this title.')
        self.getControl(1201).setLabel(self.caption)
        self.getControl(1202).setLabel('Remove from watchlist' if self.favourite else 'Add to watchlist')
        xbmcgui.Window(10000).setProperty('CBR.Detail.Resume','true' if self.resume>0 else '')
        xbmcgui.Window(10000).setProperty('CBR.Detail.Next','true' if self.following else '')
        self.setFocusId(1201)
    def onClick(self,id):
        self.choice={1201:'play',1202:'favourite',1203:'back',1204:'restart',1205:'next'}.get(id,'back');self.close()
    def onAction(self,action):
        if action.getId() in (9,10,92):self.close()


def command_detail(key,episode=False):
    saved=STORE.get(key);preview=saved['meta'];meta=dict(preview)
    kind=saved.get('type') or meta.get('type','movie');media_id=saved.get('id') or meta['id']
    if not episode:
        origin=next((e for e in STORE.providers() if e['key']==saved.get('provider')),None)
        origin=origin or next((e for e in STORE.providers() if e.get('manifest',{}).get('id')=='com.linvo.cinemeta'),None)
        if origin:
            result=command_job('Loading title information',lambda:fetch_resource(origin,'meta',kind,meta['id']))
            if result is None:
                finish();xbmc.executebuiltin('Action(Back)');return
            if result and isinstance(result.get('meta'),dict):meta.update(result['meta'])
    row=COMMAND.get(kind,media_id)
    if kind=='series' and not episode:
        row=next((r for r in COMMAND.continuing() if r['kind']=='series' and r['meta'].get('id')==meta['id']),None)
    resume=row['position'] if row and not row['completed'] and row['position']>=30 else 0
    following=next_episode(meta,media_id) if kind=='series' and episode else None
    if row and row.get('next_ready'):following=next((v for v in meta.get('videos',[]) if v['id']==row['media_id']),None)
    caption='Resume · {} min'.format(int(resume/60)) if resume else ('Seasons and episodes' if kind=='series' and not episode else ('Play episode' if episode else 'Play movie'))
    favkey=identity(kind,meta['id'])
    while True:
        if xbmc.getSkinDir() in ('skin.crimsonbloodrequiem','skin.cbr.prototype'):
            detail=CommandDetail('CBRCommandDetail.xml',ADDON.getAddonInfo('path'),'Default','1080i',meta=meta,caption=caption,resume=resume,following=following,favourite=COMMAND.contains('watchlist',favkey))
            detail.doModal();choice=detail.choice;del detail
        else:
            options=[caption,'Remove from watchlist' if COMMAND.contains('watchlist',favkey) else 'Add to watchlist','Title information']
            choices=['play','favourite','information']
            if resume:options.append('Start from beginning');choices.append('restart')
            if following:options.append('Play next episode');choices.append('next')
            selected=DIALOG.select(meta.get('name','CBR title'),options)
            choice=choices[selected] if selected>=0 else 'back'
            if choice=='information':
                DIALOG.textviewer(meta.get('name','Title'),meta.get('description') or meta.get('overview') or 'No description available.');continue
        if choice=='favourite':
            COMMAND.toggle('watchlist',favkey,dict(meta=clean_meta(meta),provider=saved.get('provider','')));continue
        if choice=='back':
            finish();xbmc.executebuiltin('Action(Back)');return
        if choice=='next' and following:
            target=following['id'];display=episode_meta(meta,following)
            STORE.write(os.path.join(STORE.root,'command-resume.json'),dict(kind=kind,id=target,seconds=0,time=command_time.time()))
            show_streams(kind,target,display);return
        if kind=='series' and not episode and not (resume and choice=='play'):
            payload=STORE.put(dict(saved,meta=meta));metadata(payload);return
        if kind=='series' and not episode and row:
            media_id=row['media_id'];meta=dict(row['meta'],videos=meta.get('videos',[]))
        STORE.write(os.path.join(STORE.root,'command-resume.json'),dict(kind=kind,id=media_id,seconds=0 if choice=='restart' else resume,time=command_time.time()))
        show_streams(kind,media_id,meta);return


def command_continue():
    xbmcplugin.setPluginCategory(HANDLE,'Continue watching')
    for row in COMMAND.continuing():
        meta=dict(row['meta']);name=meta.get('seriesName') or meta.get('name','Title')
        if row['kind']=='series':name+=' · S{} E{}'.format(meta.get('season','?'),meta.get('episode','?'))
        name+= ' · Next episode' if row.get('next_ready') else ' · {} min watched'.format(int(row['position']/60))
        meta['name']=name
        payload=STORE.put(dict(type=row['kind'],id=row['media_id'],meta=row['meta']))
        item(name,'command_episode_detail' if row['kind']=='series' else 'command_detail',key=payload,meta=meta)
    finish('movies')


def command_watchlist():
    xbmcplugin.setPluginCategory(HANDLE,'Saved')
    for saved in COMMAND.saved('watchlist'):
        payload=saved['payload'];meta=payload['meta'];key=STORE.put(payload)
        item(meta.get('name','Title'),'command_detail',meta=meta,key=key)
    item('Sports favourites','command_sport_favourites',artwork='live')
    finish('movies')


def command_prepare(saved,li):
    status=xbmcgui.Window(10000)
    if saved.get('channel'):
        status.setProperty('CBR.PlaybackStatus','Connecting to live TV…');return True
    kind=saved.get('type');media_id=saved.get('id')
    if kind not in ('movie','series') or not media_id:return True
    request=STORE.read(os.path.join(STORE.root,'command-resume.json'),{})
    row=COMMAND.get(kind,media_id)
    seconds=row['position'] if row and not row['completed'] else 0
    if request.get('id')==media_id and command_time.time()-request.get('time',0)<600:seconds=request.get('seconds',0)
    cancelled=STORE.read(os.path.join(STORE.root,'command-cancel.json'),{}).get('time',0)
    started=float(status.getProperty('CBR.PlaybackRequested') or 0)
    if started and cancelled>=started:status.clearProperty('CBR.PlaybackStatus');return False
    path=li.getPath()
    pending=dict(kind=kind,media_id=media_id,meta=clean_meta(saved['meta']),fingerprint=fingerprint(path),resume=seconds,created=command_time.time())
    STORE.write(os.path.join(STORE.root,'command-pending.json'),pending)
    if seconds>0:li.setProperty('StartOffset',str(seconds))
    status.setProperty('CBR.PlaybackStatus','Connecting to your video…')
    return True


def command_cancel():
    window=xbmcgui.Window(10000)
    pending=STORE.read(os.path.join(STORE.root,'command-pending.json'),{})
    live=STORE.read(os.path.join(STORE.root,'live-pending.json'),{})
    owned={v for v in (window.getProperty('CBR.PlaybackFingerprint'),pending.get('fingerprint'),live.get('fingerprint')) if v}
    player=xbmc.Player()
    try:stop=player.isPlaying() and fingerprint(player.getPlayingFile()) in owned
    except Exception:stop=False
    STORE.write(os.path.join(STORE.root,'command-cancel.json'),{'time':command_time.time()})
    STORE.write(os.path.join(STORE.root,'command-pending.json'),{})
    STORE.write(os.path.join(STORE.root,'pvr-retry.json'),{})
    LIVE_AUTOPLAY.clear()
    if stop:player.stop()
    window.clearProperty('CBR.PlaybackStatus')
    if HANDLE>=0:finish();xbmc.executebuiltin('Action(Back)')


def command_play(key):
    window=xbmcgui.Window(10000)
    window.setProperty('CBR.PlaybackRequested',str(command_time.time()))
    window.setProperty('CBR.PlaybackStatus','Preparing playback…')
    try:_command_original_play(key)
    finally:
        pending=STORE.read(os.path.join(STORE.root,'command-pending.json'),{})
        if not pending and not STORE.get(key).get('channel'):window.clearProperty('CBR.PlaybackStatus')


def command_sport_fav(key):
    saved=STORE.get(key)
    safe={k:saved[k] for k in ('provider','provider_id','provider_label','resource_type','live_group') if k in saved}
    safe['meta']=clean_meta(saved['meta'])
    token=safe['provider']+':'+safe.get('resource_type',safe['meta']['type'])+':'+safe['meta']['id']
    added=COMMAND.toggle('sports',token,safe)
    notify('Added to sports favourites' if added else 'Removed from sports favourites')
    xbmc.executebuiltin('Container.Refresh')


def command_sport_favourites():
    xbmcplugin.setPluginCategory(HANDLE,'Sports favourites')
    for row in COMMAND.saved('sports'):
        saved=row['payload'];entry=next((e for e in STORE.providers() if e['key']==saved.get('provider') and e.get('enabled',True)),None)
        if entry:prototype_sports_cards(entry,[saved['meta']],saved.get('resource_type'))
    finish();prototype_sports_view()


def command_pins():
    xbmcplugin.setPluginCategory(HANDLE,'Teams and competitions')
    item('Pin a team or competition','command_pin_add',artwork='search')
    for row in COMMAND.saved('pins'):
        item(row['payload']['query'],'command_pin_search',query=row['payload']['query'],artwork='live')
    finish()

def command_pin_remove(query):
    if COMMAND.contains('pins',query.casefold()):COMMAND.toggle('pins',query.casefold(),{})
    notify('Pin removed');xbmc.executebuiltin('Container.Refresh')


def command_pin_add():
    name=DIALOG.input('Team or competition name').strip()
    if name:
        key=name.casefold()
        if not COMMAND.contains('pins',key):COMMAND.toggle('pins',key,dict(query=name))
    command_pins()


def command_primary_events():
    entry=prototype_sports_entry()
    if not entry:return None,[]
    cats=list(entry_catalogs(entry));cat=next((c for c in cats if c['id']=='sports_today'),None) or next((c for c in cats if c['id']=='sports_live'),None)
    if not cat:return entry,[]
    result=command_job('Loading Sports Streams events',lambda:fetch_resource(entry,'catalog',cat['type'],cat['id']))
    return entry,(result or {}).get('metas',[])


def command_pin_search(query):
    entry,rows=command_primary_events();words=query.casefold().split()
    matches=[m for m in rows if all(w in (m.get('name','')+' '+m.get('description','')+' '+' '.join(m.get('genres',[]))).casefold() for w in words)]
    if entry:prototype_sports_cards(entry,matches,'sport')
    if not matches:notify('No matching Sports Streams events. Try Search other sources.')
    finish();prototype_sports_view()


def command_upcoming():
    xbmcplugin.setPluginCategory(HANDLE,'Upcoming sports')
    from resources.lib.command_state import upcoming
    entry,rows=command_primary_events()
    matches=[m for m in rows if upcoming(m)]
    if entry:prototype_sports_cards(entry,matches,'sport')
    if not matches:notify('No readable future start times. Use Today to see the provider schedule artwork.')
    finish();prototype_sports_view()


def command_setup():
    xbmcplugin.setPluginCategory(HANDLE,'CBR Setup')
    providers=STORE.providers();enabled=sum(e.get('enabled',True) for e in providers)
    tv=STORE.read(os.path.join(STORE.root,'pvr-status.json'),{})
    guide=STORE.read(os.path.join(STORE.root,'programme-status.json'),{})
    item('Setup status · {} sources enabled · {} TV channels'.format(enabled,tv.get('channels',0)),'command_setup_status',artwork='settings')
    item('Connect a phone or PC / edit sources','web_setup',artwork='settings')
    item('Refresh provider catalogues','command_sources_refresh',artwork='live')
    item('Refresh TV channels and programme guide','command_tv_refresh',artwork='live')
    item('Check and repair TV','maintenance_tv_repair',artwork='settings')
    item('Check CBR component updates','maintenance_updates',artwork='settings')
    item('Advanced CBR tools and settings','tools',artwork='settings')
    item('Kodi settings','command_kodi_settings',artwork='settings')
    item('Exit CBR → Kodi add-ons','command_exit',artwork='settings')
    item('Quit Kodi','command_quit',artwork='settings')
    finish()


def command_setup_status():
    tv=STORE.read(os.path.join(STORE.root,'pvr-status.json'),{})
    guide=STORE.read(os.path.join(STORE.root,'programme-status.json'),{})
    health=STORE.read(os.path.join(STORE.root,'source-health.json'),{})
    text='Sources: {} enabled / {} configured\n'.format(sum(e.get('enabled',True) for e in STORE.providers()),len(STORE.providers()))
    text+='Kodi TV: {} · {} channels\nProgramme guide: {}\n\n'.format(tv.get('state','Not set up'),tv.get('channels',0),guide.get('state','Not checked'))
    refreshed=STORE.read(os.path.join(STORE.root,'command-source-refresh.json'),{})
    if refreshed:text+='Last source refresh: {} refreshed / {} unavailable\n\n'.format(refreshed.get('refreshed',0),refreshed.get('unavailable',0))
    text+='Stored status is not a new playback test. Use Check and repair TV for a fresh check.\n\n'
    for e in STORE.providers():text+=('On · ' if e.get('enabled',True) else 'Off · ')+e['label']+'\n'
    DIALOG.textviewer('CBR setup status',text);command_setup()


def command_sources_refresh():
    from resources.lib.core import load_manifest
    originals=STORE.providers()
    def work():
        from concurrent.futures import ThreadPoolExecutor
        def one(e):
            if not e.get('enabled',True):return e,None
            try:return e,load_manifest(e['url'])
            except Exception:return e,False
        with ThreadPoolExecutor(max_workers=4) as pool:return list(pool.map(one,originals))
    results=command_job('Refreshing source catalogues',work)
    if results is not None:
        updates={e['key']:m for e,m in results if isinstance(m,dict)}
        current=STORE.providers()
        for e in current:
            if e['key'] in updates and any(o['key']==e['key'] and o['url']==e['url'] for o in originals):e['manifest']=updates[e['key']]
        STORE.save_providers(current)
        failed=sum(m is False for e,m in results)
        STORE.write(os.path.join(STORE.root,'command-source-refresh.json'),dict(time=command_time.time(),refreshed=len(updates),unavailable=failed))
        notify('{} sources refreshed; {} unavailable. Previous settings retained.'.format(len(updates),failed))
    command_setup()


def command_tv_refresh():
    pvr.refresh(STORE);request_refresh(STORE)
    notify('TV channels and programme refresh queued. Kodi will update in the background.')
    command_setup()



def command_leave(quit_kodi=False):
    if quit_kodi:
        confirmed=DIALOG.yesno('Quit Kodi?', 'Close Kodi and return to Windows or your device home screen?',yeslabel='Quit Kodi',nolabel='Stay in Kodi')
        if not confirmed:
            if HANDLE>=0:
                finish();xbmc.executebuiltin('Action(Back)')
            return
    if HANDLE>=0:finish()
    xbmc.executebuiltin('Quit' if quit_kodi else 'ActivateWindow(AddonBrowser)')


def command_dispatch(action,params):
    if action=='command_exit':command_leave()
    elif action=='command_quit':command_leave(True)
    elif action=='quality_list':quality_list(params['key'])
    elif action=='quality_change':quality_list(params['key'],True)
    elif action=='quality_info':quality_info(params['key'])
    elif action=='command_detail':command_detail(params['key'])
    elif action=='command_episode_detail':command_detail(params['key'],True)
    elif action=='command_continue':command_continue()
    elif action=='command_watchlist':command_watchlist()
    elif action=='command_sport_fav':command_sport_fav(params['key'])
    elif action=='command_sport_favourites':command_sport_favourites()
    elif action=='command_pins':command_pins()
    elif action=='command_pin_add':command_pin_add()
    elif action=='command_pin_remove':command_pin_remove(params['query'])
    elif action=='command_pin_search':command_pin_search(params['query'])
    elif action=='command_upcoming':command_upcoming()
    elif action=='command_setup':command_setup()
    elif action=='command_setup_status':command_setup_status()
    elif action=='command_sources_refresh':command_sources_refresh()
    elif action=='command_tv_refresh':command_tv_refresh()
    elif action=='command_kodi_settings':
        finish();xbmc.executebuiltin('ActivateWindow(Settings)')
    elif action=='command_cancel':command_cancel()
    else:return False
    return True

_command_original_play=play
play=command_play


def main():
    params = dict(parse_qsl(sys.argv[2][1:] if len(sys.argv) > 2 else ''))
    action = params.get('action', 'home')
    try:
        STORE.prune()
        ensure_defaults(STORE, ADDON.getAddonInfo('path'))
        if command_dispatch(action,params):
            pass
        elif action == 'prototype_sports_categories':
            prototype_sports_categories()
        elif action == 'prototype_sports_catalog':
            prototype_sports_catalog(params.get('catalog'),params.get('widget')=='true',params.get('refresh')=='true')
        elif action == 'prototype_other_sports_search':
            prototype_other_sports_search()
        elif action == 'prototype_series':
            prototype_series()
        elif action == 'prototype_search':
            prototype_search()
        elif action == 'home':
            home()
        elif action == 'new_movies':
            new_movies()
        elif action == 'tools':
            tools()
        elif action == 'live':
            live_home()
        elif action == 'pvr':
            pvr_menu()
        elif action == 'pvr_setup':
            pvr_setup()
        elif action == 'pvr_refresh':
            pvr.refresh(STORE)
            notify('Kodi TV channels and guide will update in the background')
            pvr_menu()
        elif action == 'pvr_channels':
            xbmc.executebuiltin('ActivateWindow(TVChannels)')
            pvr_menu()
        elif action == 'pvr_guide':
            xbmc.executebuiltin('ActivateWindow(TVGuide)')
            pvr_menu()
        elif action == 'pvr_status':
            state = STORE.read(os.path.join(STORE.root, 'pvr-status.json'), {})
            DIALOG.textviewer('CBR Kodi TV status', '{}\n{} channels\n{} channels with guide data\n{} programmes\n{}'.format(
                state.get('state', 'Not configured'), state.get('channels', 0), state.get('guide_channels', 0),
                state.get('programmes', 0), state.get('message', '')))
            pvr_menu()
        elif action == 'pvr_numbers':
            rpc('Settings.SetSettingValue', {'setting': 'pvrmanager.usebackendchannelnumbers', 'value': True})
            notify('Kodi TV will use channel numbers supplied by its TV clients')
            pvr_menu()
        elif action == 'pvr_play':
            pvr_play(params['channel'])
        elif action == 'sports_category':
            sports_category(params['sport'], params.get('channels') == 'true', params.get('refresh') == 'true')
        elif action == 'sports_sources':
            sports_sources()
        elif action == 'live_catalogues':
            live_catalogues(params['group'])
        elif action == 'live_source':
            live_source(params['provider'], params['group'])
        elif action == 'live_categories':
            live_categories(params['provider'], params['catalog'])
        elif action == 'live_saved':
            live_saved(params['collection'])
        elif action == 'live_favourite':
            saved = cached_item(params['key'], params.get('index'))
            channel = saved if saved.get('provider_id') else LIVE_LIBRARY.channel(saved)
            added = LIVE_LIBRARY.toggle(channel)
            notify('Added to CBR favourites' if added else 'Removed from CBR favourites')
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'live_unavailable':
            channel = STORE.get(params['key'])
            DIALOG.ok('Channel source unavailable', 'Enable or reconnect this source in Manage sources.')
            if LIVE_LIBRARY.is_favourite(channel) and DIALOG.select('Saved channel', ['Keep favourite', 'Remove favourite']) == 1:
                LIVE_LIBRARY.toggle(channel)
            live_home()
        elif action == 'library':
            library_setup()
        elif action == 'library_help':
            library_help()
            library_setup()
        elif action == 'export':
            export_movie(params['key'])
        elif action == 'export_page':
            export_page(params['key'])
        elif action == 'library_play':
            library_play(params['movie'])
        elif action == 'scan_library':
            rpc('VideoLibrary.Scan', {'directory': LIBRARY.root})
            notify('Library scan requested. The folder must be configured as a Movies source.')
            library_setup()
        elif action == 'open_movies':
            library_setup()
            xbmc.executebuiltin('ActivateWindow(Videos,videodb://movies/titles/,return)')
        elif action == 'favourite':
            rpc('Favourites.AddFavourite', {'title': 'Stremio Movies', 'type': 'window', 'window': 'videos',
                'windowparameter': 'plugin://plugin.video.stremio.bridge/',
                'thumbnail': os.path.join(ART, 'icon.png')})
            notify('Movies shortcut added to Kodi Favourites')
            library_setup()
        elif action == 'manage':
            manage()
        elif action == 'maintenance':
            maintenance_menu()
        elif action.startswith('maintenance_'):
            maintenance_action(action)
        elif action == 'web_setup':
            web_setup()
        elif action == 'defaults':
            ensure_defaults(STORE, ADDON.getAddonInfo('path'), force=True)
            manage()
        elif action == 'configure':
            ADDON.openSettings()
            tools()
        elif action in ('add', 'import', 'cinemeta', 'provider'):
            if action == 'add':
                add_provider(params.get('group'))
            elif action == 'import':
                import_providers()
            elif action == 'cinemeta':
                STORE.add(DEFAULT_URL, 'Cinemeta')
            else:
                provider_menu(params['key'])
            if action == 'add' and params.get('group') in GROUP_NAMES:
                live_catalogues(params['group'])
            else:
                manage()
        elif action == 'catalogues':
            catalogues(params.get('media_type'))
        elif action == 'catalog':
            catalog_page(params['provider'], params['catalog'], json.loads(params.get('extras', '{}')),
                         params.get('offset', 0), params.get('refresh') == 'true')
        elif action == 'search':
            search(params.get('media_type'), params.get('live_only') == 'true', params.get('provider'))
        elif action == 'meta':
            metadata(params['key'], params.get('index'))
        elif action == 'live_play':
            metadata(params['key'], params.get('index'), autoplay=True)
        elif action == 'programme_info':
            programme_info(params['key'], params.get('index'))
        elif action == 'programme_match':
            programme_match(params['key'], params.get('index'))
        elif action == 'programme_settings':
            programme_options()
        elif action == 'episodes':
            episodes(params['key'])
        elif action == 'streams':
            saved = STORE.get(params['key'])
            show_streams(saved['type'], saved['id'], saved['meta'], saved.get('inline'))
        elif action == 'play':
            play(params['key'])
        elif action == 'local':
            local_video()
        elif action == 'help':
            help_dialog()
        else:
            home()
    except Exception as error:
        # Only controlled, user-safe messages; never log raw URLs or response bodies.
        text = str(error) if isinstance(error, (ValueError, RuntimeError)) else 'Unable to complete this action. Refresh the provider manifest or reopen the catalogue.'
        try:
            import time
            recent = STORE.read(os.path.join(STORE.root, 'recent-errors.json'), [])
            summary = text if '://' not in text and len(text) < 240 else 'This action could not finish. Check the source status.'
            STORE.write(os.path.join(STORE.root, 'recent-errors.json'), [dict(time=time.time(), action=action, summary=summary)] + recent[:19])
        except Exception:
            pass
        DIALOG.ok(BRAND, text)
        if action in ('play', 'library_play', 'live_play', 'pvr_play'):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        elif HANDLE >= 0:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False, cacheToDisc=False)


if __name__ == '__main__':
    main()
