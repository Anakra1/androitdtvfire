'use strict';
const $ = id => document.getElementById(id);

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

const healthLabels = {ready: 'Catalogue available', manifest_ready: 'Provider connected', unavailable: 'Provider could not be reached', disabled: 'Disabled', not_tested: 'Not checked', sample_responded: 'Sample responded; full playback unverified', sample_failed: 'Sample could not be read', no_links: 'No stream links returned', renew_manifest: 'Needs a renewed manifest', configuration_required: 'Needs a configured manifest'};
const healthLabel = state => healthLabels[state] || 'Not checked';

function message(text, error = false) { $('status').textContent = text; $('status').classList.toggle('error', error); }
async function api(path, data) {
  const options = data === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)};
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The request failed.');
  return result;
}
function resetEditor() {
  $('source-form').reset(); $('source-key').value = ''; $('enabled').checked = true;
  $('editor-title').textContent = 'Add a source'; $('save').textContent = 'Add source'; $('cancel').hidden = false; $('source-editor').hidden = true;
}
function edit(source) {
  $('source-editor').hidden = false;
  $('source-key').value = source.key; $('label').value = source.label; $('url').value = source.url;
  $('group').value = source.group; $('enabled').checked = source.enabled;
  $('guide-country').value = source.guide_country || '';
  $('editor-title').textContent = 'Edit source'; $('save').textContent = 'Save changes'; $('cancel').hidden = false;
  $('source-form').scrollIntoView({behavior: 'smooth'}); $('url').focus();
}
async function loadSources() {
  const result = await api('/api/sources');
  $('pair-panel').hidden = true; $('workspace').hidden = false;
  savedSources = result.sources; renderSources();
}
function renderSources() {
  $('sources').replaceChildren();
  const visible = savedSources.filter(source => sourceSections(source).includes(setupCategory));
  for (const source of visible) {
    const card = document.createElement('article'); card.className = 'source';
    const title = document.createElement('h3'); title.textContent = `${source.enabled ? 'ON' : 'OFF'} · ${source.label}`;
    const info = document.createElement('p');
    const categories = {tv: 'TV Channels', internet: 'Internet TV', sports: 'Live Sports'};
    info.textContent = `${source.provider} · ${categories[source.group] || 'Automatic category'}`;
    const address = document.createElement('p');
    try { address.textContent = new URL(source.url).hostname; } catch (_) { address.textContent = 'Manifest source'; }
    const buttons = document.createElement('div'); buttons.className = 'buttons';
    const change = document.createElement('button'); change.type = 'button'; change.textContent = 'Edit'; change.onclick = () => edit(source);
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove'; remove.className = 'secondary';
    remove.onclick = async () => {
      if (!window.confirm(`Remove ${source.label} from CBR?`)) return;
      try { const result = await api('/api/remove', {key: source.key}); await loadSources(); resetEditor(); message(result.message); }
      catch (error) { message(error.message, true); }
    };
    const health = document.createElement('p'); health.textContent = source.health && source.health.checked ? `Catalogue: ${healthLabel(source.health.catalogue)} · ${healthLabel(source.health.stream)}` : 'Not tested';
    buttons.append(change, remove); card.append(title, info, address, health, buttons); $('sources').append(card);
  }
  if (!visible.length) $('sources').textContent = 'No sources in this category yet. Choose Add a source to get started.';
}
$('pair-form').addEventListener('submit', async event => {
  event.preventDefault();
  try { await api('/api/pair', {code: $('code').value.trim()}); await loadSources(); await loadProgrammes(); await loadPvr(); await loadDiagnostics(); message('Connected. You can now add or edit your TV’s sources.'); }
  catch (error) { message(error.message, true); }
});
$('source-form').addEventListener('submit', async event => {
  event.preventDefault(); $('save').disabled = true; message('Checking the manifest and saving…');
  try {
    const result = await api('/api/save', {key: $('source-key').value, label: $('label').value, url: $('url').value,
                                         group: $('group').value, enabled: $('enabled').checked,
                                         guide_country: $('guide-country').value});
    resetEditor(); await loadSources(); message(result.message);
  } catch (error) { message(error.message, true); }
  finally { $('save').disabled = false; }
});
$('cancel').onclick = resetEditor;
$('refresh').onclick = async () => {
  $('refresh').disabled = true; message('Refreshing enabled source catalogues…');
  try { const result = await api('/api/refresh', {}); await loadSources(); message(result.message + (result.failed.length ? ' Needs attention: ' + result.failed.join(', ') : ''), result.failed.length > 0); }
  catch (error) { message(error.message, true); }
  finally { $('refresh').disabled = false; }
};
function clearFeed() {
  $('feed-form').reset(); $('feed-key').value = ''; $('feed-enabled').checked = true;
  $('feed-country').value = 'GB'; $('feed-title').textContent = 'Add a programme feed';
}
async function loadProgrammes() {
  const result = await api('/api/programmes');
  for (const id of ['guide-country', 'feed-country']) {
    const select = $(id), selected = select.value;
    select.replaceChildren();
    if (id === 'guide-country') select.add(new Option('Automatic from channel', ''));
    for (const [code, label] of Object.entries(result.countries)) select.add(new Option(label, code));
    select.value = selected || (id === 'feed-country' ? 'GB' : '');
  }
  $('programme-feeds').replaceChildren();
  for (const feed of result.settings.feeds) {
    const card = document.createElement('article'); card.className = 'source';
    const title = document.createElement('h3'); title.textContent = `${feed.enabled ? 'ON' : 'OFF'} · ${feed.label}`;
    const status = result.status[feed.key] || {};
    const info = document.createElement('p');
    info.textContent = `${result.countries[feed.country] || feed.country} · ${status.state || 'Waiting for first download'} · ${status.channels || 0} channels`;
    const buttons = document.createElement('div'); buttons.className = 'buttons';
    const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Edit';
    edit.onclick = () => {
      $('feed-key').value = feed.key; $('feed-label').value = feed.label; $('feed-url').value = feed.url;
      $('feed-country').value = feed.country; $('feed-enabled').checked = feed.enabled;
      $('feed-title').textContent = 'Edit programme feed'; $('feed-form').scrollIntoView({behavior: 'smooth'});
    };
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'secondary'; remove.textContent = 'Remove';
    remove.onclick = async () => {
      if (!window.confirm(`Remove the ${feed.label} schedule feed? Streaming sources will stay in place.`)) return;
      try { const result = await api('/api/programmes/remove', {key: feed.key}); await loadProgrammes(); clearFeed(); message(result.message); }
      catch (error) { message(error.message, true); }
    };
    buttons.append(edit, remove); card.append(title, info, buttons); $('programme-feeds').append(card);
  }
}
$('feed-form').addEventListener('submit', async event => {
  event.preventDefault(); $('feed-save').disabled = true;
  try {
    const result = await api('/api/programmes/save', {key: $('feed-key').value, label: $('feed-label').value,
      url: $('feed-url').value, country: $('feed-country').value, enabled: $('feed-enabled').checked});
    clearFeed(); await loadProgrammes(); message(result.message);
  } catch (error) { message(error.message, true); }
  finally { $('feed-save').disabled = false; }
});
$('feed-cancel').onclick = clearFeed;
$('programme-refresh').onclick = async () => {
  try { const result = await api('/api/programmes/refresh', {}); await loadProgrammes(); message(result.message); }
  catch (error) { message(error.message, true); }
};
let pvrData = null;
let pvrLimit = 40;
const pvrEdits = new Map();
async function loadPvr() {
  pvrData = await api('/api/pvr');
  $('favourites-first').checked = pvrData.config.favourites_first !== false;
  pvrData.channels.sort((a, b) => (pvrData.config.favourites_first !== false ? Number(!!b.favourite) - Number(!!a.favourite) : 0) || a.number - b.number);
  const status = pvrData.status;
  $('pvr-status').textContent = `${status.state || 'Not configured'} · ${status.channels || 0} channels · ${status.guide_channels || 0} with guide data` + (status.message ? ` · ${status.message}` : '');
  $('pvr-sources').replaceChildren();
  for (const source of pvrData.sources) {
    const label = document.createElement('label'); label.className = 'check';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = source.key;
    checkbox.checked = pvrData.config.selected === null ? source.default : pvrData.config.selected.includes(source.key);
    label.append(checkbox, document.createTextNode(source.label)); $('pvr-sources').append(label);
  }
  const groupFilter = $('pvr-group-filter'), selectedGroup = groupFilter.value;
  groupFilter.replaceChildren(new Option('All groups', ''));
  for (const group of pvrData.groups) groupFilter.add(new Option(group, group));
  groupFilter.value = pvrData.groups.includes(selectedGroup) ? selectedGroup : '';
  renderPvrChannels();
}
function renderPvrChannels() {
  if (!pvrData) return;
  const query = $('pvr-filter').value.toLowerCase().trim();
  const selectedGroup = $('pvr-group-filter').value;
  const matches = pvrData.channels.map(row => pvrEdits.get(row.id) || row).filter(row => row.name.toLowerCase().includes(query) && (!selectedGroup || row.groups.includes(selectedGroup)));
  const rows = matches.slice(0, pvrLimit);
  $('pvr-result-count').textContent = `${rows.length} shown of ${matches.length} matching channels`;
  $('pvr-more').hidden = rows.length >= matches.length;
  $('pvr-channels').replaceChildren();
  for (const original of rows) {
    const row = pvrEdits.get(original.id) || {...original, groups: [...original.groups]};
    const card = document.createElement('article'); card.className = 'source';
    const title = document.createElement('h3'); title.textContent = original.name;
    const number = document.createElement('input'); number.type = 'number'; number.min = 1; number.max = 9999; number.value = row.number; number.setAttribute('aria-label', `${original.name} channel number`);
    const name = document.createElement('input'); name.value = row.name; name.maxLength = 100; name.setAttribute('aria-label', `${original.name} channel name`);
    const visible = document.createElement('input'); visible.type = 'checkbox'; visible.checked = row.visible;
    const show = document.createElement('label'); show.className = 'check'; show.append(visible, document.createTextNode('Show channel'));
    const favourite = document.createElement('input'); favourite.type = 'checkbox'; favourite.checked = !!row.favourite;
    const favLabel = document.createElement('label'); favLabel.className = 'check'; favLabel.append(favourite, document.createTextNode('Favourite channel'));
    const groups = document.createElement('div'); groups.className = 'group-options';
    const save = () => { row.name = name.value; row.number = Number(number.value); row.visible = visible.checked; row.favourite = favourite.checked; pvrEdits.set(row.id, row); };
    number.onchange = save; name.onchange = save; visible.onchange = save; favourite.onchange = save;
    for (const group of pvrData.groups) {
      const label = document.createElement('label'); label.className = 'check';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = row.groups.includes(group);
      checkbox.onchange = () => { row.groups = checkbox.checked ? [...new Set([...row.groups, group])] : row.groups.filter(g => g !== group); save(); };
      label.append(checkbox, document.createTextNode(group)); groups.append(label);
    }
    card.append(title, number, name, show, favLabel, groups); $('pvr-channels').append(card);
  }
  if (!rows.length) $('pvr-channels').textContent = 'Build TV channels first, or try another channel name.';
}
$('pvr-group-filter').onchange = () => { pvrLimit = 40; renderPvrChannels(); };
$('pvr-filter').oninput = () => { pvrLimit = 40; renderPvrChannels(); };
$('pvr-more').onclick = () => { pvrLimit += 40; renderPvrChannels(); };
$('pvr-reload').onclick = () => loadPvr().catch(error => message(error.message, true));
$('pvr-sources-form').onsubmit = async event => {
  event.preventDefault();
  const selected = [...$('pvr-sources').querySelectorAll('input:checked')].map(input => input.value);
  try { const result = await api('/api/pvr/sources', {selected}); message(result.message); await loadPvr(); }
  catch (error) { message(error.message, true); }
};
$('pvr-refresh').onclick = async () => {
  try { const result = await api('/api/pvr/refresh', {}); message(result.message); await loadPvr(); }
  catch (error) { message(error.message, true); }
};
$('pvr-save').onclick = async () => {
  try { const result = await api('/api/pvr/channels', {channels: [...pvrEdits.values()]}); pvrEdits.clear(); await loadPvr(); message(result.message); }
  catch (error) { message(error.message, true); }
};
loadSources().then(loadProgrammes).then(loadPvr).then(loadDiagnostics).catch(() => {});

let diagnosticData = null;
function downloadJson(name, value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function loadDiagnostics() {
  diagnosticData = await api('/api/diagnostics');
  const data = diagnosticData, runtime = data.runtime || {}, components = runtime.components || {};
  const rows = [`CBR ${data.version}`, `Kodi automatic installation: ${runtime.automatic_install === true ? 'enabled' : runtime.automatic_install === false ? 'disabled' : 'unknown'}`, `TV: ${data.channels.visible} visible channels; ${data.tv.guide_channels || 0} with programme data`, `Player: ${data.player.explanation}`, `Repair: ${(data.repair || {}).state || 'not requested'}`];
  const engine = components['script.module.cbr.engine'];
  rows.push(`Playback engine: ${data.player.engine_started ? 'running' : data.player.windows_engine_present || (engine && engine.enabled) ? 'installed; starts when needed' : 'not verified — check the full install'}`);
  for (const [id, state] of Object.entries(components)) rows.push(`${id}: ${state.version}; ${state.enabled ? 'enabled' : 'disabled / missing'}; ${state.repository_linked ? 'repository linked' : 'repository connection needs attention'}`);
  rows.push('To link a manual ZIP installation, select its CBR repository version once in Kodi Information → Versions.');
  $('diagnostics-summary').textContent = rows.join('\n');
  $('diagnostics-sources').replaceChildren();
  for (const source of data.sources) {
    const row = document.createElement('p');
    row.textContent = `${source.label}: ${source.enabled ? 'enabled' : 'disabled'} · catalogue ${healthLabel(source.health.catalogue)} · ${healthLabel(source.health.stream)}`;
    if (source.health.last_playback) row.textContent += ` · Playback started: ${source.health.playback_channel || 'channel'} (${new Date(source.health.last_playback * 1000).toLocaleString()})`;
    $('diagnostics-sources').append(row);
  }
  $('diagnostics-errors').textContent = data.errors.length ? data.errors.map(e => `${new Date(e.time * 1000).toLocaleString()} · ${e.action}: ${e.summary}`).join('\n') : 'No recent CBR action errors recorded.';
}
$('diagnostics-reload').onclick = () => loadDiagnostics().catch(e => message(e.message, true));
$('diagnostics-download').onclick = () => { if (diagnosticData) downloadJson('cbr-diagnostics.json', diagnosticData); };
$('diagnostics-test').onclick = async () => {
  $('diagnostics-test').disabled = true; message('Checking sources. This may take a minute; keep this page open.');
  try { const result = await api('/api/test-sources', {}); await loadSources(); await loadDiagnostics(); message(result.message); }
  catch (e) { message(e.message, true); } finally { $('diagnostics-test').disabled = false; }
};
$('diagnostics-repair').onclick = async () => {
  try { const result = await api('/api/repair', {}); message(result.message); await loadDiagnostics(); }
  catch (e) { message(e.message, true); }
};
$('backup-download').onclick = async () => {
  try { const data = await api('/api/backup', {personal: $('backup-personal').checked}); downloadJson('cbr-settings-backup.json', data); message('Backup downloaded to this device. Keep personal backups private.'); }
  catch (e) { message(e.message, true); }
};
$('backup-restore').onclick = async () => {
  try {
    const file = $('restore-file').files[0]; if (!file) throw new Error('Choose a CBR backup file first.');
    if (file.size > 4 * 1024 * 1024) throw new Error('Backup exceeds 4 MB.');
    const backup = JSON.parse(await file.text());
    if (backup.format !== 'cbr-settings' || backup.schema !== 1) throw new Error('This is not a supported CBR backup.');
    if (!window.confirm(`Replace the CBR settings contained in this backup? Personal links may need renewal. A local copy of the replaced settings will be kept. Files: ${Object.keys(backup.files || {}).join(', ')}`)) return;
    const result = await api('/api/restore', {backup, confirmed: true});
    await loadSources(); await loadProgrammes(); await loadPvr(); await loadDiagnostics(); message(result.message);
  } catch (e) { message(e.message, true); }
};
$('pvr-preferences').onclick = async () => {
  try { const result = await api('/api/pvr/preferences', {favourites_first: $('favourites-first').checked}); await loadPvr(); message(result.message); }
  catch (e) { message(e.message, true); }
};
