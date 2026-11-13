'use strict';
const repositoryRoot = new URL('../../', document.currentScript.src);
for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    const input = document.getElementById(button.dataset.copy);
    const status = document.getElementById(button.dataset.status);
    let copied = false;
    try { await navigator.clipboard.writeText(input.value); copied = true; }
    catch (_) { input.focus(); input.select(); copied = document.execCommand('copy'); }
    status.textContent = copied ? 'Source URL copied. Name it CBR in Kodi.' : 'Select the address above and copy it using your browser.';
    button.textContent = copied ? 'Copied ✓' : 'Select address';
  });
}
// Read public repository metadata so version labels and Android update links
// stay current when a new add-on release is published.
for (const platform of ['android', 'windows']) {
  fetch(new URL(`${platform}/addons.xml`, repositoryRoot), {cache: 'no-cache'})
    .then(response => { if (!response.ok) throw new Error('Feed unavailable'); return response.text(); })
    .then(raw => {
      const feed = new DOMParser().parseFromString(raw, 'application/xml');
      const addon = [...feed.querySelectorAll('addon')].find(item => item.getAttribute('id') === 'plugin.video.stremio.bridge');
      const version = addon && addon.getAttribute('version');
      if (!version || !/^\d+\.\d+\.\d+$/.test(version)) return;
      for (const node of document.querySelectorAll(`[data-version="${platform}"]`)) node.textContent = version;
      if (platform === 'android') for (const link of document.querySelectorAll('[data-android-update]')) {
        link.href = new URL(`cbr${version.replaceAll('.', '')}.zip`, repositoryRoot).href;
        for (const node of link.querySelectorAll('[data-update-name]')) node.textContent = `cbr${version.replaceAll('.', '')}.zip`;
      }
    }).catch(() => {});
}
