"""Live catalogue grouping without changing provider protocol types."""
GROUPS = (('tv', 'TV Channels'), ('internet', 'Internet TV'), ('sports', 'Live Sports'))
GROUP_NAMES = dict(GROUPS)
ON_DEMAND_TYPES = {'movie', 'series', 'anime', 'other'}
LIVE_TYPES = {'tv', 'channel', 'channels', 'live', 'event', 'events', 'sport', 'sports', 'streamsppv'}


def entry_catalogs(entry):
    seen = set()
    for catalog in list(entry.get('manifest', {}).get('catalogs', [])) + entry.get('extra_catalogs', []):
        if not isinstance(catalog, dict) or not catalog.get('id') or not catalog.get('type'):
            continue
        identity = (catalog['type'], catalog['id'])
        if identity not in seen:
            seen.add(identity)
            yield catalog


def catalogue_group(entry, catalog):
    kind = catalog.get('type', '').lower()
    if kind in ON_DEMAND_TYPES:
        return None
    assigned = entry.get('live_group')
    if assigned in GROUP_NAMES:
        return assigned
    identity = str(entry.get('manifest', {}).get('id', '')).lower()
    name = str(catalog.get('name', '')).lower()
    if kind not in LIVE_TYPES and not any(x in identity for x in ('streamsppv', 'plutotv', 'sports')):
        return None
    if kind in ('sport', 'sports', 'event', 'events', 'streamsppv') or 'sport' in name or 'streamsppv' in identity:
        return 'sports'
    if any(x in identity for x in ('pluto', 'plex', 'samsung', 'roku', 'freevee')):
        return 'internet'
    return 'tv'


def grouped_catalogues(entries, group):
    if group not in GROUP_NAMES:
        raise ValueError('Unknown Live TV category.')
    for entry in entries:
        if not entry.get('enabled', True):
            continue
        for catalog in entry_catalogs(entry):
            if catalogue_group(entry, catalog) == group:
                yield entry, catalog
