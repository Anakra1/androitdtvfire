"""Persistent Kodi movie-library exports, independent of expiring stream caches."""
import hashlib
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode


def movie_key(meta):
    if meta.get('type') != 'movie' or not meta.get('id'):
        raise ValueError('Only movies can be added to the Movies library.')
    return hashlib.sha256(('movie:' + str(meta['id'])).encode()).hexdigest()[:32]


def movie_nfo(meta):
    root = ET.Element('movie')
    def field(name, value, **attributes):
        if value is not None and str(value):
            ET.SubElement(root, name, attributes).text = str(value)
    field('title', meta.get('name', meta['id']))
    field('plot', meta.get('description', meta.get('overview', '')))
    year = str(meta.get('releaseInfo', ''))[:4]
    if year.isdigit():
        field('year', year)
    for genre in meta.get('genres') or []:
        field('genre', genre)
    if str(meta['id']).startswith('tt'):
        field('uniqueid', meta['id'], type='imdb', default='true')
    else:
        field('uniqueid', meta['id'], type='stremio', default='true')
        field('tag', 'Crimson Blood Requiem')
    if meta.get('poster'):
        field('thumb', meta['poster'], aspect='poster')
    if meta.get('background'):
        ET.SubElement(ET.SubElement(root, 'fanart'), 'thumb').text = meta['background']
    return ET.tostring(root, encoding='unicode', xml_declaration=True)


class MovieLibrary:
    def __init__(self, store):
        self.store = store
        self.root = os.path.join(store.root, 'library', 'Movies')
        self.records = os.path.join(store.root, 'library', 'records')
        os.makedirs(self.root, exist_ok=True)
        os.makedirs(self.records, exist_ok=True)

    def export(self, meta):
        key = movie_key(meta)
        # Stable ID directory: metadata/title changes update the same entry.
        folder = os.path.join(self.root, key)
        os.makedirs(folder, exist_ok=True)
        url = 'plugin://plugin.video.stremio.bridge/?' + urlencode({'action': 'library_play', 'movie': key})
        record = os.path.join(self.records, key + '.json')
        self.store.write(record, meta)
        for filename, content in [('movie.strm', url + '\n'), ('movie.nfo', movie_nfo(meta))]:
            with open(os.path.join(folder, filename), 'w', encoding='utf-8', newline='\n') as file:
                file.write(content)
        return folder

    def load(self, key):
        if not re.fullmatch('[a-f0-9]{32}', key):
            raise ValueError('Invalid library movie.')
        meta = self.store.read(os.path.join(self.records, key + '.json'))
        if not meta:
            raise ValueError('This movie export is missing. Add it to the library again.')
        return meta
