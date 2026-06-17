const q = id => document.getElementById(id);
const setStatus = msg => q('status').textContent = msg;
let allHistory = [];
let remoteUrl = '';

const createItemRow = (label, title, actions) => {
  const item = document.createElement('div');
  item.className = 'item';

  const text = document.createElement('span');
  text.className = 'item-text';
  text.textContent = label;
  text.title = title || label;
  item.appendChild(text);

  const actionWrap = document.createElement('div');
  actionWrap.className = 'item-actions';
  actions.forEach(action => {
    const button = document.createElement('button');
    button.className = 'item-btn';
    button.type = 'button';
    button.textContent = action.label;
    button.title = action.title;
    button.addEventListener('click', action.onClick);
    actionWrap.appendChild(button);
  });
  item.appendChild(actionWrap);

  return item;
};

const createEmptyState = (text) => {
  const empty = document.createElement('div');
  empty.className = 'item';
  empty.textContent = text;
  return empty;
};

const toggleSection = (id) => q(id).classList.toggle('open');
const toggleSidebar = () => {
  q('sidebar').classList.toggle('open');
  q('sidebar-overlay').classList.toggle('open');
  document.body.classList.toggle('sidebar-open');
};
const closeSidebar = () => {
  q('sidebar').classList.remove('open');
  q('sidebar-overlay').classList.remove('open');
  document.body.classList.remove('sidebar-open');
};
const toggleTheme = () => {
  document.body.classList.toggle('light-mode');
  localStorage.setItem('theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
};
const toggleBatchMode = () => {
  q('text').classList.toggle('batch-mode');
  q('text').placeholder = q('text').classList.contains('batch-mode')
    ? 'Enter multiple lines to speak sequentially...'
    : 'Type your text here...';
};
const showHelp = () => q('help-modal').classList.add('open');
const closeHelp = () => q('help-modal').classList.remove('open');
const showRemoteAccess = () => {
  if (!remoteUrl) {
    setStatus('Remote URL not ready yet');
    return;
  }
  q('remote-modal').classList.add('open');
};
const closeRemoteAccess = () => q('remote-modal').classList.remove('open');
const copyRemoteUrl = async () => {
  if (!remoteUrl) {
    setStatus('Remote URL not ready yet');
    return;
  }
  try {
    await navigator.clipboard.writeText(remoteUrl);
    setStatus('Phone access URL copied');
  } catch (error) {
    setStatus(error.message || 'Failed to copy URL');
  }
};

const handleDrop = (e) => {
  e.preventDefault();
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    const reader = new FileReader();
    reader.onload = (event) => q('text').value = event.target.result;
    reader.readAsText(files[0]);
    setStatus('File loaded');
  }
};

const updateCounter = () => {
  const text = q('text').value;
  const chars = text.length;
  const words = text.trim().split(/\s+/).filter(w => w.length > 0).length;
  const readTime = Math.ceil(words / 150 * 60);
  q('char-count').textContent = chars;
  q('word-count').textContent = words;
  q('read-time').textContent = '~' + readTime + ' sec';
};

const cleanupText = (text) => {
  return text
    .replace(/\s+/g, ' ')
    .replace(/([.!?])\s+([A-Z])/g, '$1 $2')
    .trim();
};

const updateLabel = id => {
  const el = q(`${id}_val`);
  if (!el) return;
  el.textContent = id === 'volume' ? `${q(id).value}%` : q(id).value;
};

const loadHistory = async () => {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    allHistory = Array.isArray(data.history) ? data.history : [];
    renderHistory(allHistory);
  } catch (e) {
    console.error('Failed to load history', e);
  }
};

const renderHistory = (items) => {
  const list = q('history-list');
  list.replaceChildren();
  if (!items.length) {
    list.appendChild(createEmptyState('No history yet'));
    return;
  }

  items.forEach(item => {
    list.appendChild(createItemRow(item.text, item.text, [{
      label: '↗',
      title: 'Use',
      onClick: () => insertHistoryText(item.text),
    }]));
  });
};

q('history-search').addEventListener('input', (e) => {
  const query = e.target.value.toLowerCase();
  const filtered = allHistory.filter(item => item.text.toLowerCase().includes(query));
  renderHistory(filtered);
});

const loadFavorites = async () => {
  try {
    const res = await fetch('/api/favorites');
    const data = await res.json();
    const list = q('favorites-list');
    list.replaceChildren();
    const favorites = Object.entries(data.favorites || {});
    if (!favorites.length) {
      list.appendChild(createEmptyState('No favorites yet'));
      return;
    }
    favorites.forEach(([name, text]) => {
      list.appendChild(createItemRow(name, `${name}: ${text}`, [
        {
          label: '↗',
          title: 'Use',
          onClick: () => insertHistoryText(text),
        },
        {
          label: '✕',
          title: 'Delete',
          onClick: () => removeFavorite(name),
        },
      ]));
    });
  } catch (e) {
    console.error('Failed to load favorites', e);
  }
};

const loadPresets = async () => {
  try {
    const res = await fetch('/api/presets');
    const data = await res.json();
    const list = q('presets-list');
    list.replaceChildren();
    const presets = Object.entries(data.presets || {});
    if (!presets.length) {
      list.appendChild(createEmptyState('No presets saved yet'));
      return;
    }
    presets.forEach(([name]) => {
      list.appendChild(createItemRow(name, name, [
        {
          label: '↗',
          title: 'Load',
          onClick: () => loadPreset(name),
        },
        {
          label: '✕',
          title: 'Delete',
          onClick: () => deletePreset(name),
        },
      ]));
    });
  } catch (e) {
    console.error('Failed to load presets', e);
  }
};

const loadRecents = async () => {
  try {
    const res = await fetch('/api/recents');
    const data = await res.json();

    const recentVoices = q('recent-voices');
    recentVoices.replaceChildren();
    (data.voices || []).forEach(voice => {
      const button = document.createElement('button');
      button.className = 'recent-btn';
      button.type = 'button';
      button.textContent = voice;
      button.addEventListener('click', () => setVoice(voice));
      recentVoices.appendChild(button);
    });

    const recentDevices = q('recent-devices');
    recentDevices.replaceChildren();
    (data.devices || []).forEach(device => {
      const button = document.createElement('button');
      button.className = 'recent-btn';
      button.type = 'button';
      button.textContent = device;
      button.addEventListener('click', () => setDevice(device));
      recentDevices.appendChild(button);
    });
  } catch (e) {
    console.error('Failed to load recents', e);
  }
};

const readSettings = () => ({
  voice: q('voice').value,
  output_device: q('output_device').value,
  speed: q('speed').value,
  noise: q('noise').value,
  noise_w: q('noise_w').value,
  sentence_silence: q('sentence_silence').value,
  volume: Number(q('volume').value) / 100,
  mute: q('mute').checked,
});

const insertText = (text) => {
  q('text').value = text;
  q('text').focus();
  updateCounter();
  if (window.innerWidth <= 768) closeSidebar();
};

const insertHistoryText = (text) => insertText(text);

const setVoice = (voice) => {
  q('voice').value = voice;
  updateSettings();
  if (window.innerWidth <= 768) closeSidebar();
};

const setDevice = (device) => {
  q('output_device').value = device;
  updateSettings();
  if (window.innerWidth <= 768) closeSidebar();
};

const loadState = async () => {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') document.body.classList.add('light-mode');
  q('enterToSpeak').checked = localStorage.getItem('enterToSpeak') === 'true';

  try {
    const res = await fetch('/api/status');
    const body = await res.json();
    const settings = body.settings;
    const voices = body.voices;
    const sinks = body.sinks;

    q('voice').innerHTML = voices.map(v => `<option value="${v}">${v}</option>`).join('');
    if (settings.voice) q('voice').value = settings.voice;

    q('output_device').innerHTML = sinks.map(s => `<option value="${s}">${s}</option>`).join('');
    if (settings.output_device) q('output_device').value = settings.output_device;

    q('speed').value = settings.speed ?? 1.0;
    q('noise').value = settings.noise ?? 0.5;
    q('noise_w').value = settings.noise_w ?? 0.5;
    q('sentence_silence').value = settings.sentence_silence ?? 0.0;
    q('mute').checked = settings.mute ?? false;
    q('volume').value = Math.round((settings.volume ?? 1.0) * 100);

    ['speed', 'noise', 'noise_w', 'sentence_silence', 'volume'].forEach(id => updateLabel(id));
    remoteUrl = `http://${body.local_ip}:${body.port}`;
    q('remote_info').textContent = remoteUrl;
    q('remote_open').href = remoteUrl;

    await loadHistory();
    await loadFavorites();
    await loadPresets();
    await loadRecents();
    setStatus('Ready');
  } catch (e) {
    setStatus('Error loading state');
  }
};

['speed', 'noise', 'noise_w', 'sentence_silence', 'volume'].forEach(id => {
  q(id).addEventListener('input', () => {
    updateLabel(id);
  });
});

q('text').addEventListener('input', updateCounter);
q('enterToSpeak').addEventListener('change', () => {
  localStorage.setItem('enterToSpeak', q('enterToSpeak').checked ? 'true' : 'false');
});

const onSpeak = async () => {
  try {
    let text = q('text').value.trim();
    if (!text) {
      setStatus('Enter text before speaking');
      return;
    }

    if (q('cleanup').checked) text = cleanupText(text);

    const isBatch = q('text').classList.contains('batch-mode');
    if (isBatch) {
      const lines = text.split('\n').filter(line => line.trim());
      for (const line of lines) {
        const body = { ...readSettings(), text: line };
        const res = await fetch('/api/speak', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error('Failed to speak batch line');
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      setStatus('Batch complete');
      await loadHistory();
    } else {
      const body = { ...readSettings(), text };
      const res = await fetch('/api/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to speak text');
      setStatus('Speaking...');
      await loadHistory();
    }

    if (q('autoClear').checked) {
      setTimeout(() => {
        q('text').value = '';
        updateCounter();
      }, 100);
    }
  } catch (error) {
    setStatus(error.message || 'Failed to speak');
  }
};

const onStop = async () => {
  await fetch('/api/stop', { method: 'POST' });
  setStatus('Stopped');
};

const onClear = () => {
  q('text').value = '';
  q('text').focus();
  updateCounter();
  setStatus('Text cleared');
};

const saveFavorite = async () => {
  const text = q('text').value.trim();
  if (!text) {
    setStatus('Enter text to save');
    return;
  }
  const name = prompt('Favorite name:', '');
  if (!name) return;
  const res = await fetch('/api/favorite/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, text }),
  });
  if (res.ok) {
    setStatus('Favorite saved');
    loadFavorites();
  } else {
    setStatus('Failed to save favorite');
  }
};

const removeFavorite = async (name) => {
  if (!confirm('Remove this favorite?')) return;
  const res = await fetch('/api/favorite/remove', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    setStatus('Favorite removed');
    loadFavorites();
  }
};

const savePreset = async () => {
  const name = prompt('Preset name:', '');
  if (!name) return;
  const res = await fetch('/api/preset/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, ...readSettings() }),
  });
  if (res.ok) {
    setStatus('Preset saved');
    loadPresets();
  }
};

const loadPreset = async (name) => {
  const res = await fetch('/api/preset/load', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    const data = await res.json();
    q('voice').value = data.preset.voice;
    q('speed').value = data.preset.speed;
    q('noise').value = data.preset.noise;
    q('noise_w').value = data.preset.noise_w;
    q('sentence_silence').value = data.preset.sentence_silence;
    q('volume').value = Math.round((data.preset.volume ?? 1.0) * 100);
    ['speed', 'noise', 'noise_w', 'sentence_silence', 'volume'].forEach(updateLabel);
    setStatus('Preset loaded');
  }
};

const deletePreset = async (name) => {
  if (!confirm('Delete this preset?')) return;
  const res = await fetch('/api/preset/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    setStatus('Preset deleted');
    loadPresets();
  }
};

const clearHistory = async () => {
  if (!confirm('Clear all history?')) return;
  const res = await fetch('/api/history/clear', { method: 'POST' });
  if (res.ok) {
    setStatus('History cleared');
    loadHistory();
  }
};

const saveSettings = async () => {
  const res = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(readSettings()),
  });
  setStatus(res.ok ? 'Settings saved' : 'Failed to save');
};

const updateSettings = async () => {
  await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(readSettings()),
  });
};

const onShutdown = async () => {
  if (!confirm('Shutdown server?')) return;
  await fetch('/api/shutdown', { method: 'POST' });
  setStatus('Server shutting down...');
};

const bindUiEvents = () => {
  q('sidebar-overlay').addEventListener('click', closeSidebar);
  q('sidebar-toggle-btn').addEventListener('click', toggleSidebar);
  q('theme-toggle-sidebar').addEventListener('click', toggleTheme);
  q('theme-toggle-mobile').addEventListener('click', toggleTheme);
  q('batch-toggle-btn').addEventListener('click', toggleBatchMode);
  q('help-btn').addEventListener('click', showHelp);
  q('remote-btn').addEventListener('click', showRemoteAccess);
  q('speak-btn').addEventListener('click', onSpeak);
  q('speak-btn-mobile').addEventListener('click', onSpeak);
  q('stop-btn').addEventListener('click', onStop);
  q('stop-btn-mobile').addEventListener('click', onStop);
  q('clear-btn').addEventListener('click', onClear);
  q('save-btn').addEventListener('click', saveSettings);
  q('shutdown-btn').addEventListener('click', onShutdown);
  q('save-favorite-btn').addEventListener('click', saveFavorite);
  q('save-preset-btn').addEventListener('click', savePreset);
  q('clear-history-btn').addEventListener('click', clearHistory);
  q('help-close-btn').addEventListener('click', closeHelp);
  q('remote-close-btn').addEventListener('click', closeRemoteAccess);
  q('remote-copy-btn').addEventListener('click', copyRemoteUrl);
  q('text').addEventListener('drop', handleDrop);
  q('text').addEventListener('dragover', event => event.preventDefault());
  q('text').addEventListener('dragenter', event => event.preventDefault());
  q('remote-modal').addEventListener('click', event => {
    if (event.target === event.currentTarget) closeRemoteAccess();
  });

  document.querySelectorAll('.sidebar-title[data-section]').forEach(el => {
    el.addEventListener('click', () => toggleSection(el.dataset.section));
  });
};

window.addEventListener('DOMContentLoaded', () => {
  bindUiEvents();
  loadState();
  updateCounter();

  q('text').addEventListener('keydown', event => {
    if (
      event.key === 'Enter' &&
      q('enterToSpeak').checked &&
      !event.shiftKey &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey
    ) {
      event.preventDefault();
      onSpeak();
      return;
    }

    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      onSpeak();
    }
  });

  window.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onStop();
    }
    if ((event.ctrlKey || event.metaKey) && event.key === 'l') {
      event.preventDefault();
      onClear();
    }
    if ((event.ctrlKey || event.metaKey) && event.key === 'b') {
      event.preventDefault();
      toggleBatchMode();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) closeSidebar();
  });
});
