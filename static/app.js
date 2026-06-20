const q = id => document.getElementById(id);
const setStatus = msg => q('status').textContent = msg;
const ACCESS_TOKEN_KEY = 'piper_access_token';
let allHistory = [];
let allAudioClips = [];
let remoteUrl = '';
let networkEnabled = false;
let authRequired = false;
let authToken = '';
let clipCompletionState = {
  prefix: '',
  matches: [],
  index: -1,
  start: -1,
  cursor: -1,
};

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

const apiFetch = (url, options = {}) => {
  const headers = new Headers(options.headers || {});
  if (authToken) {
    headers.set('X-Access-Token', authToken);
  }
  return fetch(url, {
    ...options,
    headers,
  });
};

const setSelectOptions = (select, values, emptyLabel) => {
  select.replaceChildren();
  if (!values.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = emptyLabel;
    select.appendChild(option);
    select.disabled = true;
    return;
  }

  select.disabled = false;
  values.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
};

const normalizeClipToken = (value) => value.trim().replace(/^!+/, '').toLowerCase();

const formatClipCommand = (clip) => (clip.startsWith('!') ? clip : `!${clip}`);

const resetClipCompletion = () => {
  clipCompletionState = {
    prefix: '',
    matches: [],
    index: -1,
    start: -1,
    cursor: -1,
  };
  q('text')._clipCompletionDirection = 1;
};

const readAuthTokenFromLocation = () => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (token) {
    authToken = token.trim();
    localStorage.setItem(ACCESS_TOKEN_KEY, authToken);
    params.delete('token');
    const cleanQuery = params.toString();
    const nextUrl = `${window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ''}${window.location.hash}`;
    window.history.replaceState({}, document.title, nextUrl);
    return;
  }

  authToken = localStorage.getItem(ACCESS_TOKEN_KEY) || '';
};

const getClipMatches = (prefix) => {
  const needle = normalizeClipToken(prefix);
  if (!needle) return [];

  return allAudioClips.filter(clip => normalizeClipToken(clip).startsWith(needle));
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
  if (!networkEnabled) {
    enablePhoneAccess();
    return;
  }
  if (authRequired && !authToken) {
    showLogin('Enter the access code to open network control.');
    return;
  }
  q('remote-modal').classList.add('open');
};
const closeRemoteAccess = () => q('remote-modal').classList.remove('open');
const enablePhoneAccess = async () => {
  try {
    const res = await apiFetch('/api/network/enable', { method: 'POST' });
    if (!res.ok) {
      throw new Error('Failed to enable phone access');
    }
    const data = await res.json();
    authToken = data.access_token || authToken;
    localStorage.setItem(ACCESS_TOKEN_KEY, authToken);
    networkEnabled = true;
    authRequired = true;
    updateRemoteButton();
    remoteUrl = `http://${data.local_ip}:${data.port}`;
    q('remote_info').textContent = remoteUrl;
    q('remote_open').href = remoteUrl;
    q('access_code_display').textContent = authToken;
    q('access_code_display').title = authToken;
    setStatus('Phone access enabled');
    q('remote-modal').classList.add('open');
  } catch (error) {
    setStatus(error.message || 'Failed to enable phone access');
  }
};
const disablePhoneAccess = async () => {
  try {
    const res = await apiFetch('/api/network/disable', { method: 'POST' });
    if (!res.ok) {
      throw new Error('Failed to disable phone access');
    }
    const data = await res.json();
    networkEnabled = false;
    authRequired = false;
    authToken = '';
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    updateRemoteButton();
    q('access_code_display').textContent = 'Not required';
    q('access_code_display').title = 'Not required';
    remoteUrl = `http://${data.local_ip}:${data.port}`;
    q('remote_info').textContent = remoteUrl;
    q('remote_open').href = remoteUrl;
    closeRemoteAccess();
    setStatus('Phone access disabled');
  } catch (error) {
    setStatus(error.message || 'Failed to disable phone access');
  }
};
const showLogin = (message = 'Enter the access code to unlock network control') => {
  q('login-message').textContent = message;
  q('access_code').value = authToken;
  q('login-error').style.display = 'none';
  q('login-error').textContent = '';
  q('login-modal').classList.add('open');
  setTimeout(() => q('access_code').focus(), 0);
};
const closeLogin = () => q('login-modal').classList.remove('open');
const connectWithToken = async () => {
  const token = q('access_code').value.trim();
  if (!token) {
    setStatus('Enter an access code first');
    return;
  }

  try {
    const res = await fetch('/api/status', {
      headers: { 'X-Access-Token': token },
    });
    if (!res.ok) {
      throw new Error('Access code not accepted');
    }

    authToken = token;
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
    closeLogin();
    setStatus('Access granted');
    await loadState();
  } catch (error) {
    q('login-error').textContent = error.message || 'Failed to verify access code';
    q('login-error').style.display = 'block';
  }
};
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

const updateRemoteButton = () => {
  q('remote-btn').textContent = networkEnabled ? 'Phone Access' : 'Enable Phone Access';
  q('remote-disable-row').style.display = networkEnabled ? 'flex' : 'none';
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
    const res = await apiFetch('/api/history');
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
    const res = await apiFetch('/api/favorites');
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
    const res = await apiFetch('/api/presets');
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
    const res = await apiFetch('/api/recents');
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
    const res = await apiFetch('/api/status');
    if (res.status === 401) {
      authRequired = true;
      showLogin('This network session needs the access code from the host machine.');
      setStatus('Access code required');
      return;
    }
    const body = await res.json();
    const settings = body.settings;
    const voices = body.voices;
    const sinks = body.sinks;
    const clips = body.clips || [];
    allAudioClips = clips;
    networkEnabled = Boolean(body.network_enabled);
    authRequired = Boolean(body.auth_required);
    updateRemoteButton();

    setSelectOptions(q('voice'), voices, 'No voices found');
    if (settings.voice) q('voice').value = settings.voice;

    setSelectOptions(q('output_device'), sinks, 'No devices found');
    if (settings.output_device) q('output_device').value = settings.output_device;

    setSelectOptions(q('audio_clip'), clips, 'No audio clips found');

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
    q('access_code_display').textContent = authRequired ? (authToken || 'Use the terminal code') : 'Not required';
    q('access_code_display').title = authRequired ? (authToken || 'Use the terminal code') : 'Not required';

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
q('text').addEventListener('input', resetClipCompletion);
q('enterToSpeak').addEventListener('change', () => {
  localStorage.setItem('enterToSpeak', q('enterToSpeak').checked ? 'true' : 'false');
});

const insertClip = () => {
  const clip = q('audio_clip').value;
  if (!clip) {
    setStatus('Choose an audio clip first');
    return;
  }

  const command = formatClipCommand(clip);
  insertText(command);
  setStatus(`Inserted ${command}`);
};

q('audio_clip_insert').addEventListener('click', insertClip);

const completeClipCommand = () => {
  const textEl = q('text');
  const value = textEl.value;
  const start = textEl.selectionStart ?? value.length;
  const end = textEl.selectionEnd ?? start;
  if (start !== end) {
    return false;
  }

  const textBefore = value.slice(0, start);
  const match = textBefore.match(/(^|\s)(!\S*)$/);
  if (!match) {
    resetClipCompletion();
    return false;
  }

  const token = match[2];
  const tokenStart = start - token.length;
  const prefix = normalizeClipToken(token);
  const matches = getClipMatches(prefix);
  if (!matches.length) {
    setStatus(`No clip matches ${token}`);
    resetClipCompletion();
    return true;
  }

  const continuing =
    clipCompletionState.prefix === prefix &&
    clipCompletionState.start === tokenStart &&
    clipCompletionState.cursor === start &&
    clipCompletionState.matches.length === matches.length;

  const direction = q('text')._clipCompletionDirection || 1;
  const index = continuing
    ? (clipCompletionState.index + direction + matches.length) % matches.length
    : (direction > 0 ? 0 : matches.length - 1);
  const clip = matches[index];
  const command = formatClipCommand(clip);
  const addSpace = matches.length === 1;
  const replacement = addSpace ? `${command} ` : command;

  textEl.value = value.slice(0, tokenStart) + replacement + value.slice(end);
  const caret = tokenStart + replacement.length;
  textEl.setSelectionRange(caret, caret);
  textEl.focus();
  updateCounter();
  clipCompletionState = {
    prefix,
    matches,
    index,
    start: tokenStart,
    cursor: caret,
  };
  q('text')._clipCompletionDirection = direction;
  setStatus(matches.length === 1
    ? `Completed ${token} → ${command}`
    : `Clip match ${index + 1} of ${matches.length}: ${command}${direction < 0 ? ' (backward)' : ''}`);
  return true;
};

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
        const res = await apiFetch('/api/speak', {
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
      const res = await apiFetch('/api/speak', {
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
  await apiFetch('/api/stop', { method: 'POST' });
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
  const res = await apiFetch('/api/favorite/add', {
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
  const res = await apiFetch('/api/favorite/remove', {
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
  const res = await apiFetch('/api/preset/save', {
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
  const res = await apiFetch('/api/preset/load', {
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
  const res = await apiFetch('/api/preset/delete', {
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
  const res = await apiFetch('/api/history/clear', { method: 'POST' });
  if (res.ok) {
    setStatus('History cleared');
    loadHistory();
  }
};

const saveSettings = async () => {
  const res = await apiFetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(readSettings()),
  });
  setStatus(res.ok ? 'Settings saved' : 'Failed to save');
};

const updateSettings = async () => {
  await apiFetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(readSettings()),
  });
};

const onShutdown = async () => {
  if (!confirm('Shutdown server?')) return;
  await apiFetch('/api/shutdown', { method: 'POST' });
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
  q('remote-copy-code-btn').addEventListener('click', async () => {
    if (!authToken) {
      setStatus('No access code available yet');
      return;
    }
    try {
      await navigator.clipboard.writeText(authToken);
      setStatus('Access code copied');
    } catch (error) {
      setStatus(error.message || 'Failed to copy access code');
    }
  });
  q('login-connect-btn').addEventListener('click', connectWithToken);
  q('login-cancel-btn').addEventListener('click', closeLogin);
  q('remote-disable-btn').addEventListener('click', disablePhoneAccess);
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
  readAuthTokenFromLocation();
  loadState();
  updateCounter();

  // 1. THIS IS YOUR ORIGINAL KEYDOWN LISTENER (Leave this alone)
  q('text').addEventListener('keydown', event => {
    if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
      q('text')._clipCompletionDirection = event.shiftKey ? -1 : 1;
      if (completeClipCommand()) {
        event.preventDefault();
      }
      return;
    }

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


  q('text').addEventListener('input', event => {
    if (event.inputType !== 'insertText' || !event.data) return;

    if (event.data === '!') {
      const textarea = q('text');
      const text = textarea.value;
      const cursor = textarea.selectionStart;

      
      const textBeforeCursor = text.substring(0, cursor - 1);
      const lastExclamation = textBeforeCursor.lastIndexOf('!');

      if (lastExclamation !== -1 && !/\s/.test(textBeforeCursor.substring(lastExclamation))) {
        textarea.value = text.substring(0, cursor - 1) + text.substring(cursor);
        textarea.selectionStart = textarea.selectionEnd = cursor - 1;

        textarea._clipCompletionDirection = 1;

        completeClipCommand();
      }
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
