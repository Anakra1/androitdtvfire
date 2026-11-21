"""Publish Pluto UK channel metadata only; never copy session-bearing stream URLs."""
from pathlib import Path
from urllib.request import Request, urlopen
from html import escape
from datetime import date
from collections import Counter
import argparse
import csv
import io
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'website'
SOURCE = 'https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_gb.m3u'


def parse(raw):
    if not raw.lstrip('\ufeff\r\n ').startswith('#EXTM3U'):
        raise ValueError('Expected a channel playlist')
    rows = {}
    for line in raw.splitlines():
        if not line.startswith('#EXTINF:'):
            continue
        match = re.match(r'#EXTINF:(?:[^",]|"[^"]*")*,(.*)', line)
        attributes = dict(re.findall(r'([\w-]+)="([^"]*)"', line))
        identity = attributes.get('tvg-id', '')
        if not match or not re.fullmatch('[a-f0-9]{24}', identity):
            continue
        name = re.sub(r'\s+', ' ', match.group(1)).strip()[:200]
        group = attributes.get('group-title', 'Other').strip()[:100] or 'Other'
        if name:
            rows.setdefault(identity, {'id': identity, 'name': name, 'group': group})
    if not rows:
        raise ValueError('No valid Pluto channel records')
    return sorted(rows.values(), key=lambda item: item['name'].casefold())


def build(stamp):
    date.fromisoformat(stamp)
    with urlopen(Request(SOURCE, headers={'User-Agent': 'CBR-channel-list/1.0'}), timeout=30) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Playlist exceeded metadata limit')
    rows = parse(raw.decode('utf-8-sig'))
    groups = Counter(item['group'] for item in rows)
    assets = SITE / 'assets'
    metadata = {'region': 'UK', 'updated': stamp, 'source': SOURCE, 'count': len(rows), 'channels': rows}
    (assets / 'pluto-uk-channels.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['Channel', 'Category', 'Pluto channel ID'])
    for row in rows:
        values = [row['name'], row['group'], row['id']]
        writer.writerow(["'" + value if value.startswith(('=', '+', '-', '@')) else value for value in values])
    (assets / 'pluto-uk-channels.csv').write_text(buffer.getvalue(), encoding='utf-8-sig', newline='')
    home = (SITE / 'index.html').read_text(encoding='utf-8')
    head = home[:home.index('<main id="main">')].replace('aria-current="page"', '')
    head = re.sub(r'<title>.*?</title>', '<title>Pluto TV UK channel listing | CBR</title>', head)
    head = re.sub(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="https://anakra1.github.io/androitdtvfire/website/pluto-channels.html">', head)
    head = re.sub(r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="https://anakra1.github.io/androitdtvfire/website/pluto-channels.html">', head)
    head = re.sub(r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="Pluto TV UK channel listing | CBR">', head)
    head = re.sub(r'<meta property="og:description" content="[^"]*">', '<meta property="og:description" content="Search Pluto TV UK channels, filter by category and download the channel list.">', head)
    head = re.sub(r'<meta (?:name="description"|property="og:description") content="[^"]*">', '<meta name="description" content="Search Pluto TV UK channels by name and category, download the channel list and add the playlist to CBR.">', head, count=1)
    footer = home[home.index('<footer class="site-footer">'):]
    options = ''.join('<option value="{0}">{0} ({1})</option>'.format(escape(group, quote=True), count) for group, count in sorted(groups.items(), key=lambda pair: pair[0].casefold()))
    table = ''.join('<tr data-channel-name="{0}" data-channel-group="{1}"><td>{2}</td><td>{3}</td></tr>'.format(
        escape(row['name'], quote=True), escape(row['group'], quote=True), escape(row['name']), escape(row['group'])) for row in rows)
    page = '''<main id="main"><section class="page-hero"><div class="wrap"><div class="breadcrumbs"><a href="index.html">Home</a><span>/</span><a href="updates.html">Updates &amp; TV Playlists</a><span>/</span><span>Pluto UK channels</span></div><p class="eyebrow kicker">Pluto TV UK</p><h1>Your channel<br><span class="accent">listing.</span></h1><p class="lead">{count} channels listed in the UK playlist, across {groups} categories. Find a channel by name or choose a category below.</p><div class="actions"><a class="button primary" href="updates.html#pluto-uk">Add Pluto UK to CBR</a><a class="button" href="assets/pluto-uk-channels.csv" download>Download channel list (CSV)</a></div></div></section><section class="section wrap user-guide"><p class="guide-note">Channel names and categories checked {date}. This is a channel directory; programme schedules come from a separate guide feed. The lineup and local availability can change.</p><form id="pluto-channel-filters" class="channel-filters" role="search"><div><label for="pluto-channel-search">Find a channel</label><input id="pluto-channel-search" type="search" placeholder="For example, Movies or Kids" autocomplete="off"></div><div><label for="pluto-channel-group">Category</label><select id="pluto-channel-group"><option value="">All categories</option>{options}</select></div><button class="button" type="reset">Clear filters</button></form><p id="pluto-channel-count" role="status" aria-live="polite">Showing all {count} channels.</p><div class="channel-table-wrap"><table class="channel-list-table"><caption>Pluto TV UK channels — alphabetical order</caption><thead><tr><th scope="col">Channel</th><th scope="col">Category</th></tr></thead><tbody id="pluto-channel-rows">{table}</tbody></table></div><p id="pluto-channel-empty" hidden>No channels match. Clear the filters or try another name.</p><noscript><p>The full alphabetical list is shown above. Enable JavaScript to use the search and category filters.</p></noscript><p><a class="text-link" href="assets/pluto-uk-channels.json" download>Download channel metadata (JSON)</a> · <a class="text-link" href="updates.html#pluto-uk">Playlist link and CBR setup instructions</a></p><p class="source-note">Names and categories are from the <a href="https://github.com/BuddyChewChew/pluto" target="_blank" rel="noopener noreferrer">BuddyChewChew Pluto UK playlist</a>. This is not an official Pluto channel guide. This page does not contain playback-session links.</p></section></main><script src="assets/pluto-channels.js" defer></script>'''.format(count=len(rows), groups=len(groups), date=escape(stamp), options=options, table=table)
    (SITE / 'pluto-channels.html').write_text(head + page + footer, encoding='utf-8')
    for name in ('guide.html', 'updates.html'):
        path = SITE / name
        text = path.read_text(encoding='utf-8')
        if 'href="pluto-channels.html"' not in text:
            anchor = '<h2>Add Pluto UK channels to CBR.</h2>'
            assert anchor in text
            text = text.replace(anchor, anchor + '<p><a class="button primary" href="pluto-channels.html">Browse all Pluto UK channels</a> <a class="text-link" href="assets/pluto-uk-channels.csv" download>Download channel list</a></p>', 1)
        path.write_text(text, encoding='utf-8')
    print(json.dumps({'channels': len(rows), 'categories': dict(groups), 'updated': stamp, 'stream_urls_exported': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True, help='Publication date in YYYY-MM-DD from client context')
    build(parser.parse_args().date)
