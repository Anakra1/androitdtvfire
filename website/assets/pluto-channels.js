'use strict';
const channelRows = [...document.querySelectorAll('[data-channel-name]')];
const channelSearch = document.getElementById('pluto-channel-search');
const channelGroup = document.getElementById('pluto-channel-group');
const channelCount = document.getElementById('pluto-channel-count');
function filterChannels() {
  const query = channelSearch.value.trim().toLocaleLowerCase();
  const group = channelGroup.value;
  let count = 0;
  for (const row of channelRows) {
    const match = row.dataset.channelName.toLocaleLowerCase().includes(query) && (!group || row.dataset.channelGroup === group);
    row.hidden = !match;
    if (match) count++;
  }
  channelCount.textContent = `Showing ${count} of ${channelRows.length} channels.`;
  document.getElementById('pluto-channel-empty').hidden = count !== 0;
}
channelSearch.addEventListener('input', filterChannels);
channelGroup.addEventListener('change', filterChannels);
document.getElementById('pluto-channel-filters').addEventListener('submit', event => event.preventDefault());
document.getElementById('pluto-channel-filters').addEventListener('reset', () => setTimeout(filterChannels, 0));
