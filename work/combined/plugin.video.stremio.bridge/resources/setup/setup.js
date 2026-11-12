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
  try { await api('/api/pair', {code: $('code').value.trim()}); await loadSources(); await loadProgrammes(); message('Connected. You can now add or edit your TV’s sources.'); }
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
loadSources().then(loadProgrammes).catch(() => {});
