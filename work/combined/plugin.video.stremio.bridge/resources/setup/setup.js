'use strict';
const $ = id => document.getElementById(id);
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
  $('editor-title').textContent = 'Add a source'; $('save').textContent = 'Add source'; $('cancel').hidden = true;
}
function edit(source) {
  $('source-key').value = source.key; $('label').value = source.label; $('url').value = source.url;
  $('group').value = source.group; $('enabled').checked = source.enabled;
  $('guide-country').value = source.guide_country || '';
  $('editor-title').textContent = 'Edit source'; $('save').textContent = 'Save changes'; $('cancel').hidden = false;
  $('source-form').scrollIntoView({behavior: 'smooth'}); $('url').focus();
}
async function loadSources() {
  const result = await api('/api/sources');
  $('pair-panel').hidden = true; $('workspace').hidden = false; $('sources').replaceChildren();
  for (const source of result.sources) {
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
    buttons.append(change, remove); card.append(title, info, address, buttons); $('sources').append(card);
  }
  if (!result.sources.length) $('sources').textContent = 'No sources saved yet. Add your first source below.';
}
$('pair-form').addEventListener('submit', async event => {
  event.preventDefault();
  try { await api('/api/pair', {code: $('code').value.trim()}); await loadSources(); await loadProgrammes(); await loadPvr(); message('Connected. You can now add or edit your TV’s sources.'); }
  catch (error) { message(error.message, true); }
});
$('source-form').addEventListener('submit', async event => {
  event.preventDefault(); $('save').disabled = true; message('Checking the source and saving…');
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
let pvrPage = 0;
let pvrDisplayed = [];
const pvrEdits = new Map();
async function loadPvr() {
  pvrData = await api('/api/pvr');
  pvrData.channels.sort((a, b) => a.number - b.number);
  const status = pvrData.status;
  $('pvr-status').textContent = `${status.state || 'Not configured'} · ${status.channels || 0} channels · ${status.guide_channels || 0} with guide data` + (status.message ? ` · ${status.message}` : '');
  $('pvr-sources').replaceChildren();
  const groupSelect = $('pvr-group'), currentGroup = groupSelect.value;
  groupSelect.replaceChildren(new Option('All groups', ''));
  for (const group of pvrData.groups) groupSelect.add(new Option(group, group));
  groupSelect.value = currentGroup;
  const otherCountries = document.createElement('details');
  const countrySummary = document.createElement('summary'); countrySummary.textContent = 'Other M3U playlist countries'; otherCountries.append(countrySummary);
  let otherCount = 0;
  for (const source of pvrData.sources) {
    const label = document.createElement('label'); label.className = 'check';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.value = source.key;
    checkbox.checked = pvrData.config.selected === null ? source.default : pvrData.config.selected.includes(source.key);
    label.append(checkbox, document.createTextNode(source.label));
    if (source.playlist && !source.default) { otherCountries.append(label); otherCount++; }
    else $('pvr-sources').append(label);
  }
  if (otherCount) $('pvr-sources').append(otherCountries);
  renderPvrChannels();
}
function renderPvrChannels() {
  if (!pvrData) return;
  const query = $('pvr-filter').value.toLowerCase().trim();
  const group = $('pvr-group').value, view = $('pvr-view').value;
  const filtered = pvrData.channels.filter(original => {
    const row = pvrEdits.get(original.id) || original;
    return row.name.toLowerCase().includes(query) && (!group || row.groups.includes(group)) &&
      (view !== 'missing' || !original.has_programmes) && (view !== 'hidden' || !row.visible) &&
      (view !== 'alternatives' || original.alternatives > 1);
  });
  pvrPage = Math.min(pvrPage, Math.max(0, Math.ceil(filtered.length / 40) - 1));
  const rows = filtered.slice(pvrPage * 40, (pvrPage + 1) * 40);
  pvrDisplayed = rows;
  $('pvr-count').textContent = `${filtered.length} matching channels · page ${pvrPage + 1} of ${Math.max(1, Math.ceil(filtered.length / 40))} · ${pvrEdits.size} unsaved edits`;
  $('pvr-prev').disabled = pvrPage === 0;
  $('pvr-next').disabled = (pvrPage + 1) * 40 >= filtered.length;
  $('pvr-channels').replaceChildren();
  for (const original of rows) {
    const row = pvrEdits.get(original.id) || {...original, groups: [...original.groups]};
    const card = document.createElement('article'); card.className = 'source';
    const title = document.createElement('h3'); title.textContent = original.name;
    const number = document.createElement('input'); number.type = 'number'; number.min = 1; number.max = 9999; number.value = row.number; number.setAttribute('aria-label', `${original.name} channel number`);
    const name = document.createElement('input'); name.value = row.name; name.maxLength = 100; name.setAttribute('aria-label', `${original.name} channel name`);
    const visible = document.createElement('input'); visible.type = 'checkbox'; visible.checked = row.visible;
    const show = document.createElement('label'); show.className = 'check'; show.append(visible, document.createTextNode('Show channel'));
    const groups = document.createElement('div'); groups.className = 'group-options';
    const save = () => {
      row.name = name.value; row.number = Number(number.value); row.visible = visible.checked; pvrEdits.set(row.id, row);
      $('pvr-count').textContent = $('pvr-count').textContent.replace(/\d+ unsaved edits/, `${pvrEdits.size} unsaved edits`);
    };
    number.onchange = save; name.onchange = save; visible.onchange = save;
    for (const group of pvrData.groups) {
      const label = document.createElement('label'); label.className = 'check';
      const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = row.groups.includes(group);
      checkbox.onchange = () => { row.groups = checkbox.checked ? [...new Set([...row.groups, group])] : row.groups.filter(g => g !== group); save(); };
      label.append(checkbox, document.createTextNode(group)); groups.append(label);
    }
    const info = document.createElement('p'); info.className = 'muted';
    info.textContent = `${original.alternatives} channel alternative(s) · ` + (original.guide ?
      `Guide: ${original.guide.name}${original.has_programmes ? '' : ' (no upcoming programmes)'}` : 'No programme match') +
      (original.manual_guide ? ' · Manual match' : ' · Automatic match');
    const details = document.createElement('details');
    const summary = document.createElement('summary'); summary.textContent = 'Choose programme guide match'; details.append(summary);
    let loaded = false;
    details.ontoggle = () => {
      if (!details.open || loaded) return;
      loaded = true;
      const select = document.createElement('select'); select.setAttribute('aria-label', `${original.name} programme guide`);
      select.add(new Option('Automatic matching', ''));
      for (const option of pvrData.guide_options) select.add(new Option(`${option.name} — ${option.label}`, JSON.stringify({feed: option.feed, channel: option.channel})));
      select.value = original.manual_guide ? JSON.stringify(original.manual_guide) : '';
      const apply = document.createElement('button'); apply.type = 'button'; apply.textContent = 'Apply programme match';
      apply.onclick = async () => {
        apply.disabled = true;
        try {
          const result = await api('/api/pvr/guide', {id: original.id, mapping: select.value ? JSON.parse(select.value) : null});
          await loadPvr(); message(result.message);
        } catch (error) { message(error.message, true); apply.disabled = false; }
      };
      details.append(select, apply);
    };
    card.append(title, info, number, name, show, groups, details); $('pvr-channels').append(card);
  }
  if (!rows.length) $('pvr-channels').textContent = 'Build TV channels first, or try another channel name.';
}
function filterPvr() { pvrPage = 0; renderPvrChannels(); }
$('pvr-filter').oninput = filterPvr;
$('pvr-group').onchange = filterPvr;
$('pvr-view').onchange = filterPvr;
$('pvr-prev').onclick = () => { pvrPage--; renderPvrChannels(); };
$('pvr-next').onclick = () => { pvrPage++; renderPvrChannels(); };
function showPvrPage(visible) {
  for (const original of pvrDisplayed) {
    const row = pvrEdits.get(original.id) || {...original, groups: [...original.groups]};
    row.visible = visible; pvrEdits.set(row.id, row);
  }
  renderPvrChannels();
}
$('pvr-hide').onclick = () => showPvrPage(false);
$('pvr-show').onclick = () => showPvrPage(true);
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
  if (pvrEdits.size > 100) { message('Save up to 100 channel edits at a time. Reload the page to discard unsaved changes.', true); return; }
  try { const result = await api('/api/pvr/channels', {channels: [...pvrEdits.values()]}); pvrEdits.clear(); await loadPvr(); message(result.message); }
  catch (error) { message(error.message, true); }
};
loadSources().then(loadProgrammes).then(loadPvr).catch(() => {});
