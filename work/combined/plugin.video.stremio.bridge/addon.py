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
                                playback_url, resource_url, stream_kind)
from resources.lib.library import MovieLibrary
from resources.lib.defaults import ensure_defaults
from resources.lib.live import GROUPS, GROUP_NAMES, catalogue_group, entry_catalogs, grouped_catalogues

ADDON = xbmcaddon.Addon()
BASE = sys.argv[0]
HANDLE = int(sys.argv[1])
DIALOG = xbmcgui.Dialog()
STORE = Store(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')))
LIBRARY = MovieLibrary(STORE)
ART = os.path.join(ADDON.getAddonInfo('path'), 'resources', 'art')
BRAND = 'Crimson Blood Requiem'


def route(action, **kwargs):
    return BASE + '?' + urlencode(dict(action=action, **kwargs))


def item(label, action, folder=True, meta=None, artwork=None, **kwargs):
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
        if meta.get('type') == 'movie' and action == 'meta':
            li.addContextMenuItems([
                ('Add to Kodi Movies library', 'RunPlugin({})'.format(route('export', key=kwargs['key']))),
                ('Movie information', 'Action(Info)'),
            ])
    li.setArt(art)
    if not folder:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, route(action, **kwargs), li, isFolder=folder)


def finish(content='videos'):
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
    url = DIALOG.input('Paste installed add-on manifest URL', DEFAULT_URL if index == 0 else '')
    if url.strip():
        entry = STORE.add(url, label)
        if live_group in GROUP_NAMES:
            entry['live_group'] = live_group
            STORE.save_providers([entry if e['key'] == entry['key'] else e for e in STORE.providers()])
        notify('Add-on connected')


def live_home():
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    for group, name in GROUPS:
        item(name, 'live_catalogues', group=group, artwork='live')
    finish()


def live_catalogues(group):
    matches = list(grouped_catalogues(STORE.providers(), group))
    for entry, catalog in matches:
        item('{} / {}'.format(entry['label'], catalog.get('name', catalog['id'])), 'catalog',
             provider=entry['key'], catalog=STORE.put(catalog), artwork='catalogues')
    item('Add another {} source'.format(GROUP_NAMES[group]), 'add', group=group, artwork='settings')
    item('Source setup (phone / PC)', 'web_setup', artwork='settings')
    item('Manage sources', 'manage', artwork='settings')
    if not matches:
        notify('Add a manifest source to this category to load channels or events.')
    xbmcplugin.setPluginCategory(HANDLE, GROUP_NAMES[group])
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


def add_metas(metas, provider, media_type, seen=None, live_group=None):
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
            saved.update(live_group=live_group, resource_type=media_type)
        key = STORE.put(saved)
        item(meta.get('name', meta['id']), 'meta', meta=meta, key=key)


def catalog_page(provider, catalog, extras=None):
    entry = STORE.provider(provider)
    cat = STORE.get(catalog)
    extras = dict(extras or {})
    for spec in cat.get('extra', []):
        name = spec.get('name')
        if name == 'skip' or name in extras:
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
    data = request(resource_url(entry['url'], 'catalog', cat['type'], cat['id'], extras))
    metas = data.get('metas', [])
    live_group = catalogue_group(entry, cat)
    add_metas(metas, provider, cat['type'], live_group=live_group)
    if cat['type'] == 'movie' and metas:
        item('Add this page to Kodi Movies library', 'export_page',
             key=STORE.put([dict(m, type='movie') for m in metas if isinstance(m, dict) and m.get('type', 'movie') == 'movie']),
             artwork='library')
    if metas and any(x.get('name') == 'skip' for x in cat.get('extra', [])):
        extras['skip'] = int(extras.get('skip', 0)) + len(metas)
        item('Next page', 'catalog', provider=provider, catalog=catalog, extras=json.dumps(extras))
    if not metas:
        notify('No results in this catalogue')
    finish('movies' if cat['type'] == 'movie' else 'videos')


def search(media_type=None, live_only=False):
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
                  and (not live_only or catalogue_group(e, c) is not None) and not any(
        x.get('isRequired') and x.get('name') != 'search' for x in c.get('extra', []))]
    def run(pair):
        e, c = pair
        try:
            data = fetch_json(resource_url(e['url'], 'catalog', c['type'], c['id'], {'search': query.strip()}))
            return e, c, data.get('metas', []), False
        except Exception:
            return e, c, [], True
    seen, errors = set(), 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        for entry, cat, metas, error in executor.map(run, candidates):
            errors += int(error)
            add_metas(metas, entry['key'], cat['type'], seen)
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


def metadata(key):
    saved = STORE.get(key)
    preview = saved['meta']
    providers = sorted(STORE.providers(), key=lambda x: x['key'] != saved['provider'])
    resource_type = saved.get('resource_type', preview['type'])
    origin = STORE.provider(saved['provider'])
    live_group = saved.get('live_group') or catalogue_group(origin, {'type': resource_type})
    results = aggregate(providers, 'meta', resource_type, preview['id'])
    meta = next((data['meta'] for _, data, _ in results if isinstance(data.get('meta'), dict) and data['meta']), preview)
    meta = dict(preview, **meta)
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
        show_streams(resource_type, video_id, meta, meta.get('streams'))


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


def show_streams(media_type, item_id, meta, inline=None):
    streams = []
    if inline:
        streams = [('Embedded source', s) for s in inline]
    else:
        results = aggregate(STORE.providers(), 'stream', media_type, item_id)
        failures(results)
        for entry, data, _ in results:
            streams.extend((entry['label'], s) for s in data.get('streams', []) if isinstance(s, dict))
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
        payload = STORE.put({'stream': stream, 'type': media_type, 'id': item_id, 'meta': meta})
        item(label, 'play', folder=False, key=payload, meta=meta)
    if not streams:
        notify('No streams. Add configured stream providers in Manage sources.')
    finish()


def play(key):
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
        elif action == 'live_catalogues':
            live_catalogues(params['group'])
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
            catalog_page(params['provider'], params['catalog'], json.loads(params.get('extras', '{}')))
        elif action == 'search':
            search(params.get('media_type'), params.get('live_only') == 'true')
        elif action == 'meta':
            metadata(params['key'])
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
        if action in ('play', 'library_play'):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        elif HANDLE >= 0:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False, cacheToDisc=False)


if __name__ == '__main__':
    main()

