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

from resources.lib.core import (DEFAULT_URL, PRESETS, Store, aggregate, fetch_json,
                                playback_url, resource_url, stream_kind, fetch_resource)
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
        li.addContextMenuItems([(label, 'RunPlugin({})'.format(route('live_favourite', **arguments)))])
        li.addContextMenuItems([('Choose stream manually', 'Container.Update({})'.format(route('meta', **arguments)))])
        li.addContextMenuItems([('Programme information', 'RunPlugin({})'.format(route('programme_info', **arguments))),
                                ('Match programme channel', 'RunPlugin({})'.format(route('programme_match', **arguments)))])
    li.setArt(art)
    if not folder:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, route(action, **kwargs), li, isFolder=folder)


def finish(content='videos'):
    PROGRAMMES.close()
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


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
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    item('Search movies', 'search', media_type='movie', artwork='search')
    item('Search TV series', 'search', media_type='series', artwork='search')
    item('Search Live TV', 'search', live_only='true', artwork='search')
    item('Browse all catalogues', 'catalogues', artwork='catalogues')
    item('Manage sources / add manifest URL', 'manage', artwork='settings')
    item('Live TV', 'live', artwork='live')
    item('Kodi TV and guide', 'pvr', artwork='live')
    item('Built-in player settings', 'configure', artwork='settings')
    item('Kodi Movies library setup', 'library', artwork='library')
    item('Play a local video', 'local', artwork='library')
    item('Help and compatibility', 'help', artwork='settings')
    finish()


def movie_catalogs():
    return [(e, c) for e, c in catalogs() if c['type'] == 'movie']


def movie_home():
    item('Search movies', 'search', media_type='movie', artwork='search')
    item('Movies', 'catalogues', media_type='movie', artwork='movies')
    item('Search TV series', 'search', media_type='series', artwork='search')
    item('TV series', 'catalogues', media_type='series', artwork='series')
    item('Search Live TV', 'search', live_only='true', artwork='search')
    item('Live TV', 'live', artwork='live')
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
    url = DIALOG.input('Paste manifest or M3U playlist URL', DEFAULT_URL if index == 0 else
                       'https://iptv-org.github.io/iptv/index.m3u' if label == 'M3U IPTV playlist' else '')
    if url.strip():
        entry = STORE.add(url, label)
        if live_group in GROUP_NAMES:
            entry['live_group'] = live_group
            STORE.save_providers([entry if e['key'] == entry['key'] else e for e in STORE.providers()])
        notify('Add-on connected')


def live_home():
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
    for _, catalog in sorted(matches, key=lambda pair: (pair[1].get('country') != 'GB', browse_title(pair[1]).casefold())):
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
    loader = (lambda ignored: fetch_resource(entry, 'catalog', cat['type'], cat['id'], dict(extras, _refresh=refresh))) if entry.get('kind') == 'm3u' else request
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
            if e.get('kind') == 'm3u' and c['id'] != 'm3u_all': return e, c, [], False
            data = fetch_resource(e, 'catalog', c['type'], c['id'], {'search': query.strip()}, fetch=fetch_json)
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
    path, fallback = None, None
    for variant in variants:
        entry = STORE.provider(variant['provider'])
        streams = []
        for _, data, _ in aggregate([entry], 'stream', variant['resource_type'], variant['meta']['id']):
            streams.extend(s for s in data.get('streams', []) if isinstance(s, dict))
        states = {}
        def checked(stream):
            state = probe_stream(stream)
            states[playback_url(stream)] = state
            return state
        path = LIVE_AUTOPLAY.begin(variant['meta'], variant, streams, probe=checked)
        LIVE_AUTOPLAY.clear()
        if path:
            if states.get(path) is True:
                break
            if fallback is None:
                fallback = path, variant
            path = None
    if path is None and fallback:
        path, variant = fallback
    # PVR owns channel switching and stopping. Select a working URL here but do
    # not let the video add-on's retry service replace PVR with ordinary playback.
    if not path:
        notify('This TV channel is currently unavailable.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    li = xbmcgui.ListItem(path=path)
    li.getVideoInfoTag().setTitle(row['name'])
    li.getVideoInfoTag().setPlot(programme_text(PROGRAMMES.lookup(variant)))
    li.setArt({'thumb': row['logo']})
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def metadata(key, index=None, autoplay=False):
    saved = cached_item(key, index)
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
        display = dict(meta, name=title, description=video.get('overview', meta.get('description', '')),
                       thumbnail=video.get('thumbnail', ''))
        payload = STORE.put({'type': meta['type'], 'id': video['id'], 'meta': display, 'inline': video.get('streams')})
        item(title, 'streams', key=payload, meta=display)
    finish('episodes')


def show_streams(media_type, item_id, meta, inline=None, channel=None, autoplay=False):
    streams = []
    if inline:
        streams = [('Embedded source', s) for s in inline]
    else:
        providers = STORE.providers()
        if channel and channel.get('provider'):
            providers = [entry for entry in providers if entry['key'] == channel['provider']]
        results = aggregate(providers, 'stream', media_type, item_id)
        failures(results)
        for entry, data, _ in results:
            streams.extend((entry['label'], s) for s in data.get('streams', []) if isinstance(s, dict))
    if autoplay and channel:
        bookmark = LIVE_LIBRARY.channel(channel)
        path = LIVE_AUTOPLAY.begin(meta, bookmark, [stream for _, stream in streams], probe=probe_stream)
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
    if not streams:
        notify('No playback links were returned. The channel or source may be unavailable.'
               if channel else 'No streams were returned by your enabled providers.')
    finish()


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


def main():
    params = dict(parse_qsl(sys.argv[2][1:] if len(sys.argv) > 2 else ''))
    action = params.get('action', 'home')
    try:
        STORE.prune()
        ensure_defaults(STORE, ADDON.getAddonInfo('path'))
        if action == 'home':
            home()
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
        DIALOG.ok(BRAND, text)
        if action in ('play', 'library_play', 'live_play', 'pvr_play'):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        elif HANDLE >= 0:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False, cacheToDisc=False)


if __name__ == '__main__':
    main()

