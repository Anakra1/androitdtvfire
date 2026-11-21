"""Categorised setup overlay, based on the immutable 0.12.2/0.12.3 assets."""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / 'reference'
OVERLAY = HERE / 'overlay'


def write(name, value):
    path = OVERLAY / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


html = (REFERENCE / 'resources/setup/index.html').read_text(encoding='utf-8')
before, rest = html.split('<div id="workspace" hidden>', 1)
sections = re.findall(r'<section>.*?</section>', rest, re.S)
assert len(sections) == 6
diagnostics, backup, pvr, sources, editor, programmes = sections
live_config, listings = pvr.split('<h3>Channel names, numbers, favourites and groups</h3>', 1)
live_config += '</section>'
live_config = live_config.replace('<h2>Kodi TV and guide</h2>', '<h2>Choose sources for the Kodi TV guide</h2>')
listings = '<section><h2>Channel listings</h2><p class="muted">Choose where each channel appears: UK TV, sports, internet TV or another guide group. Rename, number, hide or favourite channels here.</p>' + listings
listings = listings.replace('<div id="pvr-channels">', '<label for="pvr-group-filter">Show a guide group</label><select id="pvr-group-filter"><option value="">All groups</option></select><p id="pvr-result-count" class="muted"></p><div id="pvr-channels">')
sources = sources.replace('<section>', '<section id="source-list-section">', 1)
sources = sources.replace('<h2>Your sources</h2>', '<h2 id="sources-title">Live TV sources</h2>')
sources = sources.replace('<div id="sources"></div>', '<button id="add-source" type="button">Add a Live TV source</button><div id="sources"></div>')
editor = editor.replace('<section>', '<section id="source-editor" hidden>', 1)
editor = editor.replace('<label for="group">Live TV category</label>', '<div id="live-source-options"><label for="group">Live TV category</label>')
editor = editor.replace('<label class="check"><input id="enabled"', '</div><label class="check"><input id="enabled"')
editor = editor.replace('Automatic / movies and series', 'Automatic from this source')
editor = editor.replace('id="cancel" type="button" class="secondary" hidden', 'id="cancel" type="button" class="secondary"')
tabs = [('live', 'Live TV'), ('movies', 'Movies'), ('series', 'TV Series'),
        ('listings', 'Channel Listings'), ('programmes', 'Programmes'), ('tools', 'Tools')]
nav = '<nav id="setup-tabs" role="tablist" aria-label="Setup categories">' + ''.join(
    '<button id="tab-{0}" type="button" role="tab" aria-controls="panel-{0}" aria-selected="{2}" tabindex="{3}" data-setup-tab="{0}">{1}</button>'.format(key, label, 'true' if key == 'live' else 'false', '0' if key == 'live' else '-1')
    for key, label in tabs) + '</nav>'
panels = {
    'live': '<p class="category-intro">Add or update live channel playlists and manifests. Choose which sources feed the Kodi TV guide below.</p><div id="mount-live">' + sources + editor + '</div>' + live_config,
    'movies': '<p class="category-intro">Update the providers used for film catalogues and playback links. Sources supporting both films and series appear in both categories.</p><div id="mount-movies"></div>',
    'series': '<p class="category-intro">Update providers used for TV series and episode links. A shared provider has one saved configuration across Movies and TV Series.</p><div id="mount-series"></div>',
    'listings': listings,
    'programmes': programmes,
    'tools': diagnostics + backup,
}
body = ''.join('<div id="panel-{0}" role="tabpanel" aria-labelledby="tab-{0}"{1}>{2}</div>'.format(key, '' if key == 'live' else ' hidden', panels[key]) for key, _ in tabs)
html = before + '<div id="workspace" hidden>' + nav + body + '<p class="muted">Changes are saved on this Kodi device. Reopen the catalogue in CBR after updating sources.</p></div></main></body></html>\n'
write('resources/setup/index.html', html)

script = (REFERENCE / 'resources/setup/setup.js').read_text(encoding='utf-8')
insert = '''
let setupCategory = 'live';
let savedSources = [];
const categoryNames = {live: 'Live TV', movies: 'Movies', series: 'TV Series'};
function sourceSections(source) {
  return source.sections && source.sections.length ? source.sections : (source.group ? ['live'] : ['movies', 'series']);
}
function selectCategory(category, focus = false) {
  if (!$('panel-' + category)) return;
  setupCategory = category;
  for (const tab of document.querySelectorAll('[data-setup-tab]')) {
    const active = tab.dataset.setupTab === category;
    tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
    $('panel-' + tab.dataset.setupTab).hidden = !active;
    if (active && focus) tab.focus();
  }
  if (categoryNames[category]) {
    $('mount-' + category).append($('source-list-section'), $('source-editor'));
    $('sources-title').textContent = categoryNames[category] + ' sources';
    $('add-source').textContent = 'Add a ' + categoryNames[category] + ' source';
    $('live-source-options').hidden = category !== 'live';
    renderSources();
  }
}
const setupTabs = [...document.querySelectorAll('[data-setup-tab]')];
for (const [index, tab] of setupTabs.entries()) {
  tab.onclick = () => selectCategory(tab.dataset.setupTab);
  tab.onkeydown = event => {
    let next = null;
    if (event.key === 'ArrowRight') next = (index + 1) % setupTabs.length;
    if (event.key === 'ArrowLeft') next = (index + setupTabs.length - 1) % setupTabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = setupTabs.length - 1;
    if (next !== null) { event.preventDefault(); selectCategory(setupTabs[next].dataset.setupTab, true); }
  };
}
$('add-source').onclick = () => {
  resetEditor(); $('source-editor').hidden = false;
  $('group').value = setupCategory === 'live' ? 'tv' : '';
  $('editor-title').textContent = 'Add a ' + categoryNames[setupCategory] + ' source';
  $('label').focus();
};
'''
script = script.replace("const $ = id => document.getElementById(id);", "const $ = id => document.getElementById(id);\n" + insert)
script = script.replace("$('cancel').hidden = true;", "$('cancel').hidden = false; $('source-editor').hidden = true;")
script = script.replace('function edit(source) {', "function edit(source) {\n  $('source-editor').hidden = false;")
old = "  $('pair-panel').hidden = true; $('workspace').hidden = false; $('sources').replaceChildren();\n  for (const source of result.sources) {"
new = "  $('pair-panel').hidden = true; $('workspace').hidden = false;\n  savedSources = result.sources; renderSources();\n}\nfunction renderSources() {\n  $('sources').replaceChildren();\n  const visible = savedSources.filter(source => sourceSections(source).includes(setupCategory));\n  for (const source of visible) {"
assert old in script
script = script.replace(old, new)
script = script.replace("if (!result.sources.length) $('sources').textContent = 'No sources saved yet. Add your first source below.';", "if (!visible.length) $('sources').textContent = 'No sources in this category yet. Choose Add a source to get started.';")
script = script.replace("  renderPvrChannels();\n}\nfunction renderPvrChannels()", "  const groupFilter = $('pvr-group-filter'), selectedGroup = groupFilter.value;\n  groupFilter.replaceChildren(new Option('All groups', ''));\n  for (const group of pvrData.groups) groupFilter.add(new Option(group, group));\n  groupFilter.value = pvrData.groups.includes(selectedGroup) ? selectedGroup : '';\n  renderPvrChannels();\n}\nfunction renderPvrChannels()")
script = script.replace("  const rows = pvrData.channels.filter(row => row.name.toLowerCase().includes(query)).slice(0, pvrLimit);", "  const selectedGroup = $('pvr-group-filter').value;\n  const matches = pvrData.channels.map(row => pvrEdits.get(row.id) || row).filter(row => row.name.toLowerCase().includes(query) && (!selectedGroup || row.groups.includes(selectedGroup)));\n  const rows = matches.slice(0, pvrLimit);\n  $('pvr-result-count').textContent = `${rows.length} shown of ${matches.length} matching channels`;\n  $('pvr-more').hidden = rows.length >= matches.length;")
script = script.replace("$('pvr-filter').oninput =", "$('pvr-group-filter').onchange = () => { pvrLimit = 40; renderPvrChannels(); };\n$('pvr-filter').oninput =")
write('resources/setup/setup.js', script)
css = (REFERENCE / 'resources/setup/style.css').read_text(encoding='utf-8')
css += '''
#setup-tabs{position:sticky;top:0;z-index:10;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:12px 0;background:#10090d;border-bottom:1px solid #48232f}
#setup-tabs button{background:#21141c;border-color:#6b4352;padding:12px 8px;font-size:15px}
#setup-tabs [aria-selected="true"]{background:#ae173c;border-color:#ef7895;box-shadow:inset 0 -3px #ffb3c4}
.category-intro{line-height:1.6;color:#dcc5ce;padding:4px 0}
[role="tabpanel"]{scroll-margin-top:125px}
#source-editor{border-color:#dc5272;scroll-margin-top:135px}
#pvr-channels .source{padding:14px 0}
@media(min-width:1000px){main{max-width:1100px}#setup-tabs{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(max-width:500px){#setup-tabs button{font-size:13px;padding:10px 4px}}
'''
write('resources/setup/style.css', css)

server = (REFERENCE / 'resources/lib/setup_web.py').read_text(encoding='utf-8')
helper = '''
def source_sections(entry):
    """Display categories only; never change a provider's playback scope."""
    manifest = entry.get('manifest', {})
    types = set(entry.get('scope_types') or manifest.get('types', []))
    types.update(c.get('type', '') for c in manifest.get('catalogs', []) if isinstance(c, dict))
    if entry.get('live_group') or entry.get('kind') in ('m3u', 'daddylive') or types.intersection(('tv', 'sport', 'sports', 'channel', 'live')):
        return ['live']
    sections = []
    if 'movie' in types:
        sections.append('movies')
    if 'series' in types:
        sections.append('series')
    return sections or ['movies', 'series']

'''
server = server.replace('class SetupServer:', helper + '\nclass SetupServer:', 1)
server = server.replace("'health': health.get(entry['key'], {})}", "'health': health.get(entry['key'], {}), 'sections': source_sections(entry)}")
write('resources/lib/setup_web.py', server)

# Match the in-Kodi menu to the paired setup page. No provider configuration is migrated.
from zipfile import ZipFile
ROOT = HERE.parents[1]
with ZipFile(ROOT / 'windows/packages/plugin.video.stremio.bridge/plugin.video.stremio.bridge-0.12.2.zip') as archive:
    addon = archive.read('plugin.video.stremio.bridge/addon.py').decode('utf-8-sig').replace('\r\n', '\n')
start = addon.index('def manage():')
end = addon.index('\ndef add_provider(', start)
addon = addon[:start] + '''def manage(category=None):
    from resources.lib.setup_web import source_sections
    labels = {'live': 'Live TV', 'movies': 'Movies', 'series': 'TV Series', 'tools': 'Tools'}
    if category not in labels:
        xbmcplugin.setPluginCategory(HANDLE, 'CBR Setup')
        for key, title in [('live', 'Live TV sources'), ('movies', 'Movie sources'), ('series', 'TV Series sources')]:
            item(title, 'manage', category=key, artwork='settings')
        item('Channel Listings / numbers and groups', 'pvr', artwork='live')
        item('Programmes / guide feeds', 'programme_settings', artwork='live')
        item('Tools / updates, backup and repair', 'manage', category='tools', artwork='settings')
        item('Connect phone or PC / edit manifest links', 'web_setup', artwork='settings')
        item('Setup status', 'command_setup_status', artwork='settings')
        item('Exit CBR → Kodi add-ons', 'command_exit', artwork='settings')
        item('Quit Kodi', 'command_quit', artwork='settings')
        finish()
        return
    xbmcplugin.setPluginCategory(HANDLE, 'CBR Setup · ' + labels[category])
    if category == 'tools':
        item('Check, repair and back up CBR', 'maintenance', artwork='settings')
        item('Refresh provider catalogues', 'command_sources_refresh', artwork='settings')
        item('Check CBR component updates', 'maintenance_updates', artwork='settings')
        item('Import manifest URLs from a text file', 'import', category=category, artwork='settings')
        item('Restore missing default providers', 'defaults', artwork='settings')
        item('Player settings', 'configure', artwork='settings')
        finish()
        return
    item('Add a ' + labels[category] + ' source / manifest URL', 'add', category=category, group='tv' if category == 'live' else '', artwork='settings')
    item('Edit manifest links on phone or PC', 'web_setup', artwork='settings')
    if category in ('movies', 'series'):
        item('Add Cinemeta movie and series catalogue', 'cinemeta', category=category, artwork='settings')
    matches = [entry for entry in STORE.providers() if category in source_sections(entry)]
    for entry in matches:
        item(('ON  ' if entry.get('enabled', True) else 'OFF  ') + entry['label'],
             'provider', key=entry['key'], category=category, artwork='settings')
    if not matches:
        item('No sources in this category yet', 'manage', category=category, artwork='settings')
    finish()

''' + addon[end:]
addon = addon.replace("elif action == 'manage':\n            manage()", "elif action == 'manage':\n            manage(params.get('category'))")
addon = addon.replace("            else:\n                manage()\n        elif action == 'catalogues':", "            else:\n                manage(params.get('category'))\n        elif action == 'catalogues':")
addon = addon.replace("if action == 'add' and params.get('group') in GROUP_NAMES:", "if action == 'add' and params.get('group') in GROUP_NAMES and not params.get('category'):")
assert "elif action == 'manage':\n            manage(params.get('category'))" in addon
start = addon.index('def command_setup():')
end = addon.index('\ndef command_setup_status():', start)
addon = addon[:start] + 'def command_setup():\n    manage()\n\n' + addon[end:]
write('addon.py', addon)
print('Prepared categorised source setup overlay.')
