"""Build the public updates/source directory from published guides and archive metadata."""
from pathlib import Path
from zipfile import ZipFile
from html import escape
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'website'
guide = (SITE / 'guide.html').read_text(encoding='utf-8')
home = (SITE / 'index.html').read_text(encoding='utf-8')


def section(identity):
    start = guide.index('<section id="' + identity + '"')
    return guide[start:guide.index('</section>', start) + len('</section>')]


def history(identity):
    records = {}
    for platform in ('windows', 'android'):
        for path in (ROOT / platform / 'packages' / identity).glob('*.zip'):
            with ZipFile(path) as archive:
                meta = ET.fromstring(archive.read(identity + '/addon.xml'))
            version = meta.get('version')
            if not re.fullmatch(r'\d+(?:\.\d+)+', version):
                continue
            news = meta.findtext("extension[@point='xbmc.addon.metadata']/news") or ''
            news = re.sub(r'https?://\S+', '[provider link]', news)
            news = re.sub(r'\s+', ' ', news).strip()
            records.setdefault(version, {})[platform] = news
    return [(version, records[version]) for version in sorted(records, key=lambda v: tuple(map(int, v.split('.'))), reverse=True)]


def release_rows(records):
    output = []
    for version, notes in records:
        platforms = ' / '.join('Android / Fire TV' if p == 'android' else 'Windows' for p in notes)
        unique = list(dict.fromkeys(notes.values()))
        if len(unique) == 1:
            description = '<p>' + escape(unique[0] or 'Archived release. No separate change summary was included in this package.') + '</p>'
        else:
            description = ''.join('<p><strong>' + ('Android / Fire TV' if p == 'android' else 'Windows') + ':</strong> ' + escape(note or 'No separate change summary in this archive.') + '</p>' for p, note in notes.items())
        output.append('<article class="release-row"><div class="release-number">' + escape(version) + '</div><div><h3>Version ' + escape(version) + '</h3><p class="source-note">' + escape(platforms) + '</p>' + description + '</div></article>')
    return ''.join(output)


cards = re.findall(r'<article class="source-card".*?</article>', guide, re.S)
live_cards = [c for c in cards if 'id="source-pluto-uk"' not in c and 'Torrentio and Cinemeta' not in c]
live_cards = [c.replace('↗', '') for c in live_cards]
for index, card in enumerate(live_cards):
    position = card.rfind('</article>')
    live_cards[index] = card[:position] + '<p><a class="text-link" href="#add-tv">How to add this live TV source</a></p>' + card[position:]
pluto = section('pluto-uk').replace('href="#pair"', 'href="guide.html#pair"').replace('href="#refresh"', 'href="guide.html#refresh"')
pluto = pluto.replace('class="subsection"', 'class="subsection featured-playlist"', 1)
sports = section('sports').replace('id="sports"', 'id="sports-sources"').replace('href="#refresh"', 'href="guide.html#refresh"')
sports = sports.replace('Under <strong>Your sources</strong>', 'Select <strong>Live TV</strong>, then under your sources').replace('↗', '')
movie_sources = '''<section id="movies-series" class="subsection"><p class="eyebrow">Movie and episode sources</p><h2>Movies &amp; TV series.</h2><p>These are Stremio-style provider links rather than live-TV playlists. Add them in <strong>Movies</strong> or <strong>TV Series</strong> on the paired setup page. A shared provider appears in both categories using one saved configuration.</p><div class="source-grid"><article class="source-card"><h3>Cinemeta — film and series catalogue</h3><p>Provides titles, posters, descriptions, seasons and episode information. It does not supply video playback streams.</p><div class="copy-row"><input id="updates-cinemeta-url" aria-label="Public Cinemeta manifest" readonly value="https://v3-cinemeta.strem.io/manifest.json"><button class="button small" type="button" data-copy="updates-cinemeta-url" data-status="updates-cinemeta-status" data-copy-message="Cinemeta manifest copied. Add it in Movies or TV Series on the paired CBR page.">Copy Cinemeta link</button></div><p id="updates-cinemeta-status" class="copy-status" role="status" aria-live="polite"></p><p>Choose <strong>Add a Movies source</strong> or <strong>Add a TV Series source</strong>, name it Cinemeta, paste the link, leave it enabled and save. You can also add Cinemeta directly from the corresponding source folder in Kodi.</p></article><article class="source-card"><h3>Torrentio — movie and episode source results</h3><p>Use its configuration page to choose providers and options. Copy your complete generated manifest link; do not enter the configuration-page address as the manifest.</p><a class="button" href="https://torrentio.strem.fun/configure" target="_blank" rel="noopener noreferrer">Open Torrentio configuration</a><ol><li>Choose and save your settings on the provider page.</li><li>Copy the complete configured addon link.</li><li>On the paired CBR page, open <strong>Movies</strong> or <strong>TV Series</strong> and edit Torrentio, or add it if absent.</li><li>Paste the link, keep the source enabled and save. Reopen the film or episode to refresh its available links.</li></ol><p class="source-note">Configured links can contain account credentials. Keep them private. Source results do not guarantee playback or permission to access an item. Movie and series sources are not added to the PVR channel guide.</p></article></div></section>'''
identities = [('plugin.video.stremio.bridge', 'CBR video add-on'), ('script.crb.wizard', 'Setup Wizard / full installer'),
              ('skin.crimsonbloodrequiem', 'CBR skin'), ('script.module.cbr.engine', 'Playback engine')]
histories = {identity: history(identity) for identity, _ in identities}
video_history = histories['plugin.video.stremio.bridge']
updates = '''<section id="updates" class="subsection"><p class="eyebrow">Newest first</p><h2>Updates &amp; release history.</h2><article class="release-row"><div class="release-number">Website</div><div><h3>21 November 2026 — Updates &amp; TV Playlists page</h3><p>A dedicated page in the main menu, Pluto UK playlist and copy button, live TV and sports setup instructions, movie/series source links, and archived component release notes below.</p></div></article><div class="callout"><h3>Latest install: CBR 0.12.4</h3><p>Full installer / Setup Wizard <strong>0.4.4</strong> · Skin <strong>0.2.1</strong> · Android playback engine <strong>0.1.2</strong>.</p><p>Setup now has separate Live TV, Movies, TV Series, Channel Listings, Programmes and Tools categories in Kodi and on the paired phone / PC page.</p><div class="actions"><a class="button primary" href="../cbrwindows.zip" download>Windows update</a><a class="button primary" href="../cbr0124.zip" download>Android / Fire TV update</a><a class="button" href="../full.zip" download>Windows full install</a><a class="button" href="../fulla044.zip" download>Android full install</a></div></div><h3>Update your existing installation</h3><p>In Kodi, open <strong>Add-ons → My add-ons → Video add-ons → Crimson Blood Requiem → Information → Update / Versions</strong> and choose the release from the CBR repository. Kodi can install updates automatically when the add-on is repository-linked and automatic updates are enabled. For a manual update, install the platform update ZIP above and restart Kodi. Existing source settings are retained.</p><p><a class="text-link" href="windows.html#updating">Windows update instructions</a> · <a class="text-link" href="android.html#updating">Android / Fire TV update instructions</a></p><h3>Video add-on updates</h3>'''
updates += release_rows(video_history[:3])
updates += '<details class="release-archive"><summary>All earlier video add-on updates (' + str(len(video_history[3:])) + ' versions, newest first)</summary>' + release_rows(video_history[3:]) + '</details>'
for identity, title in identities[1:]:
    updates += '<details class="release-archive"><summary>' + escape(title) + ' — all ' + str(len(histories[identity])) + ' archived updates, newest first</summary>' + release_rows(histories[identity]) + '</details>'
updates += '<p class="source-note">History is drawn from version metadata and change notes inside the published package archives. An archive without change notes is labelled accordingly; old packages are retained for reference. Versions are ordered within each component.</p></section>'

prefix = home[:home.index('<main id="main">')]
prefix = prefix.replace('aria-current="page"', '')
prefix = prefix.replace('<title>Crimson Blood Requiem', '<title>Updates &amp; TV Playlists | Crimson Blood Requiem', 1)
prefix = re.sub(r'<title>.*?</title>', '<title>Updates &amp; TV Playlists | CBR</title>', prefix)
prefix = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="Latest CBR updates and release history, Pluto UK and other TV playlists, plus movie and series provider setup instructions.">', prefix)
prefix = prefix.replace('https://anakra1.github.io/androitdtvfire/website/"', 'https://anakra1.github.io/androitdtvfire/website/updates.html"')
prefix = re.sub(r'<meta property="og:title" content="[^"]*">', '<meta property="og:title" content="Updates &amp; TV Playlists | CBR">', prefix)
prefix = re.sub(r'<meta property="og:description" content="[^"]*">', '<meta property="og:description" content="Latest CBR releases, Pluto UK setup, and live TV, movie and series source links.">', prefix)
footer = home[home.index('<footer class="site-footer">'):]
hero = '''<main id="main"><section class="page-hero"><div class="wrap"><div class="breadcrumbs"><a href="index.html">Home</a><span>/</span><span>Updates &amp; TV Playlists</span></div><p class="eyebrow kicker">CBR source directory &amp; release notes</p><h1>Updates &amp;<br><span class="accent">TV Playlists.</span></h1><p class="lead">Copy a playlist, follow the setup steps, or find out what changed in the latest CBR release.</p><div class="actions"><a class="button primary" href="#pluto-uk">Pluto TV UK setup</a><a class="button" href="#updates">Latest updates</a></div></div></section><nav class="wrap jump-links" aria-label="Updates and playlist sections"><a href="#pluto-uk">Pluto UK</a><a href="#live-tv-playlists">Other live TV</a><a href="#sports-sources">Sports</a><a href="#movies-series">Movies &amp; series</a><a href="#updates">All updates</a></nav><div class="wrap user-guide"><p class="guide-note">You are on the public CBR website. Source changes are made on your Kodi device’s paired setup page. <a href="guide.html#pair">Connect your PC or phone first</a>.</p>'''
live = '''<section id="live-tv-playlists" class="subsection"><p class="eyebrow">More live channels</p><h2>Other live TV playlists.</h2><p>These are the public source links documented for CBR. A listed channel or a responding playlist does not guarantee continuous playback, English audio or guide coverage.</p><div class="source-grid">''' + ''.join(live_cards) + '''</div></section><section id="add-tv" class="subsection"><h2>Add or update any live TV playlist.</h2><ol class="guide-steps"><li><a href="guide.html#pair">Pair your PC or phone with Kodi</a> and open the <strong>Live TV</strong> tab.</li><li>Edit the existing source, or choose <strong>Add a Live TV source</strong> if it is new. Copy its playlist URL above and paste it into <strong>Manifest or M3U playlist URL</strong>.</li><li>Give it a recognisable name. Use the category shown on its card: <strong>TV Channels</strong> or <strong>Internet TV</strong>. Leave Programme country on Automatic for mixed-country lists; choose United Kingdom for UK-only sources.</li><li>Keep the source enabled and save. Return to CBR and reopen the source’s live channel catalogue.</li><li>For Kodi’s main TV guide, select the source’s catalogue under <strong>Choose sources for the Kodi TV guide</strong>, save TV sources, then build / refresh TV. Use <strong>Channel Listings</strong> to choose groups, channel numbers, names and favourites.</li></ol><p>Use the URL ending in the actual playlist filename, not the project’s GitHub webpage. Add only the catalogues and countries you need.</p></section>'''
page = prefix + hero + pluto + live + sports + movie_sources + updates + '</div></main>' + footer
(SITE / 'updates.html').write_text(page, encoding='utf-8')

nav_link = '<a href="updates.html">Updates &amp; TV Playlists</a>'
for path in SITE.glob('*.html'):
    text = path.read_text(encoding='utf-8')
    start, end = text.index('<nav class="main-nav"'), text.index('</nav>', text.index('<nav class="main-nav"'))
    nav = text[start:end]
    nav = nav.replace('Help & updates', 'Help')
    if 'href="updates.html"' not in nav:
        nav = nav.replace('<a href="help.html"', nav_link + '<a href="help.html"', 1)
    if path.name == 'updates.html':
        nav = nav.replace(nav_link, nav_link.replace('href="updates.html"', 'href="updates.html" aria-current="page"'))
    text = text[:start] + nav + text[end:]
    text = text.replace('<a href="help.html#updates">Release notes</a>', '<a href="updates.html#updates">Updates &amp; release notes</a>')
    if 'href="updates.html#pluto-uk"' not in text:
        text = text.replace('<a href="guide.html">Using and updating TV sources</a>', '<a href="updates.html#pluto-uk">TV playlists &amp; setup links</a><a href="guide.html">Using and updating TV sources</a>')
    if path.name == 'index.html' and 'id="updates-playlists-banner"' not in text:
        anchor = '<main id="main">'
        # A compact, prominent entry above the normal homepage content.
        banner = '<section id="updates-playlists-banner" class="wrap updates-banner"><div><p class="eyebrow">Latest CBR 0.12.4 · Full installer 0.4.4</p><h2>Updates &amp; TV Playlists</h2><p>Pluto UK setup, live TV and movie sources, plus the latest release notes.</p></div><a class="button primary" href="updates.html">Open updates &amp; playlists</a></section>'
        text = text.replace(anchor, anchor + banner, 1)
    if path.name == 'help.html':
        text = text.replace('<h2>TV playlists and source setup.</h2>', '<h2>Updates &amp; TV Playlists.</h2>')
        text = text.replace('<a class="button primary" href="guide.html">Open the TV sources user guide</a>', '<a class="button primary" href="updates.html">Open updates &amp; TV playlists</a>')
        anchor = '<section class="subsection" id="updates">'
        if anchor in text and 'id="updates-page-pointer"' not in text:
            text = text.replace(anchor, anchor + '<div class="callout" id="updates-page-pointer"><p>For the complete release history with the latest updates first, open <a href="updates.html#updates">Updates &amp; TV Playlists</a>.</p></div>', 1)
        text = text.replace('<a href="#updates">Release notes</a>', '<a href="updates.html#updates">Release notes</a>')
    path.write_text(text, encoding='utf-8')

css_path = SITE / 'assets/site.css'
css = css_path.read_text(encoding='utf-8')
if '/* Updates and playlist hub */' not in css:
    css += '''\n/* Updates and playlist hub */
.updates-banner{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:24px 28px;margin-top:24px;border:1px solid #8e3855;border-radius:14px;background:linear-gradient(110deg,#321320,#161019)}
.updates-banner h2{margin:4px 0 8px;font-size:26px}.updates-banner p{margin:5px 0}.updates-banner .button{flex-shrink:0}
.featured-playlist{padding:26px;border:1px solid #8e3855;border-radius:14px;background:#20111a}
.release-archive{margin:24px 0;padding:18px;border:1px solid #4b2b38;border-radius:10px}.release-archive>summary{cursor:pointer;font-size:17px;font-weight:650;color:#f3c4d1}.release-archive[open]>summary{margin-bottom:24px}
.user-guide .release-row{padding-block:22px}.user-guide .release-row p{overflow-wrap:anywhere}
.main-nav{flex-wrap:wrap;row-gap:0}.main-nav a{white-space:nowrap}
@media(max-width:760px){.updates-banner{display:block;padding:22px}.updates-banner .button{margin-top:16px}.featured-playlist{padding:20px}.main-nav{justify-content:flex-start;column-gap:18px}.user-guide .release-number{font-size:18px}}
'''
    css_path.write_text(css, encoding='utf-8')

root_index = ROOT / 'index.html'
text = root_index.read_text(encoding='utf-8')
if 'website/updates.html' not in text:
    text = text.replace('<table>', '<p><a href="website/updates.html">Updates &amp; TV Playlists — Pluto UK setup, source links and release history</a></p><table>', 1)
    root_index.write_text(text, encoding='utf-8')
print(json.dumps({'video_releases': len(video_history), 'component_releases': {title: len(histories[identity]) for identity, title in identities}, 'live_playlist_cards': len(live_cards), 'new_page': 'website/updates.html'}))
