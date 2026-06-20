# Piper_Control
Piper TTS Control – Portable Edition

A simple, self-contained, portable graphical interface for Piper TTS
(offline neural text-to-speech system by rhasspy)

https://github.com/rhasspy/piper

If you want to study how the code works in depth, see:

- [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md)

That file explains the app flow, backend, frontend, and data files in detail.

Project structure
-----------------
- `Piper_Control.desktop` - icon-based desktop launcher using `assets/icon.png`
- `main.py` - command-line entry point
- `browser_ui.py` - HTTP server and API
- `static/index.html` - browser UI markup
- `static/styles.css` - UI styling
- `static/app.js` - UI behavior and API calls
- `audio/` - optional audio clips played with `!clipname`
- `engine.py` - Piper synthesis and playback
- `settings.py` - config loading and saving
- `utils.py` - voice and sink helpers

This application is intentionally designed to be fully portable:
- Just copy the entire folder anywhere
- Place your voice models (*.onnx + *.onnx.json) in the voices/ subfolder
- Place optional audio clips in the audio/ subfolder
- Supported clip formats are intentionally limited so the app does not create
  conversion files or extra work on every play
- Audio clips are local-only and ignored by git, like voice model files
- Run: python3 -u main.py
- Use `--host=0.0.0.0` or `--network` only if you want phone/LAN access
  and be ready to use the generated access code, or just press the Phone Access button to toggle it
- Or open `Piper_Control.desktop` for the icon-based launcher
- The desktop launcher uses a relative icon path, so keep the repo folder together if you move it
- All settings are saved in config.json inside the same folder
- History, favorites, presets and recents are saved in separate JSON files in the same folder

No installation, no system-wide GUI toolkit dependencies are required — just a modern browser and audio tools.

Features
--------
• Browser-based control panel
• Voice selection (auto-detected from voices/ folder)
• Audio output device selection (PulseAudio / PipeWire sinks)
• Audio clips folder for one-shot sound playback
• Clip picker with keyboard type-ahead, `Tab`/`Shift+Tab` cycling for clip commands, and a green insert button for `!clipname`
• Adjustable parameters:
  - Speech speed (length_scale)
  - Noise scale / noise_w (character / expressiveness)
  - Volume multiplier (via sox when ≠ 1.0)
• Mute button (stops current speech and blocks new playback)
• History: last 10 unique spoken texts (newest first)
• Favorites: persistent starred phrases (add from history, delete individually)
• Stop button (kills ongoing synthesis + playback)

Requirements
------------
Software you need (usually already present on most Linux distributions):

• Linux with PipeWire or PulseAudio
• Python 3.8 or newer

• piper-tts binary in your $PATH
  (download from https://github.com/rhasspy/piper/releases)

• pactl (comes with pulseaudio-utils or pipewire-pulse)

• pw-play (PipeWire) or paplay (PulseAudio fallback)

• sox (strongly recommended for volume control when slider ≠ 1.0)
  sudo apt install sox   /   sudo dnf install sox   /   sudo pacman -S sox

• Any modern browser for the web UI

Voice models
------------
Place .onnx and .onnx.json files into the voices/ folder.

https://rhasspy.github.io/piper-samples/

Basic usage
-----------
1. Write or paste text in the large text area
2. (Optional) Open "Audio Settings" expander
   • Choose a voice
   • Choose output device (if you have several)
   • Choose an audio clip or type `!clipname`
   • Adjust speed / noise / clarity / silence / volume sliders
3. Click "Speak"
4. (Optional) After speaking, open "History & Favorites" expander
   • Click ★ on a recent entry to add it to favorites
   • Click "Use" on any entry to reload text
   • In favorites: click "Delete" to remove entries
5. Click "Mute" to silence everything immediately
6. Click "Stop" if the speech is taking too long or is incorrect
7. If you want to open the UI from another device, press the `Phone Access`
   button to enable it, or use `Disable Phone Access` to turn it back off
   • The app prints a random access code in the terminal
   • The Phone Access button shows the code and enables the LAN server
   • Enter that code on the network login screen before using the UI

Controls explained
------------------
Text area              →  Type or paste what you want to speak
Voice dropdown         →  Selects which model to use (saved)
Output dropdown        →  Selects audio sink (friendly names, saved)
Audio Clip dropdown    →  Picks an audio file; type letters to jump, `Tab`/`Shift+Tab` cycle matches in the text box, button inserts `!clipname`
Speed slider           →  0.7 = slower, 1.5 = faster (saved)
Noise slider           →  0.0 = clean, 1.0 = very expressive/noisy (saved)
Clarity slider         →  Separate `noise_w` control for voice texture (saved)
Silence slider         →  Adds pauses between sentences via `sentence_silence`
Volume slider          →  0.0 = silent, 2.0 = very loud (saved, requires sox)
`!clipname`            →  Plays an audio clip from `audio/` through the same output device
Mute button            →  Red + "Unmute" when active, stops all sound (saved)
Speak                  →  Generate and play the current text
Stop                   →  Immediately kill synthesis + playback
Clear                  →  Empty the text area
Phone Access           →  Turns on LAN mode, shows the code, and prefers the
                         local/private network IP over VPN-style addresses
Disable Phone Access   →  Turns LAN mode back off

History & Favorites panel
-------------------------
Located in the bottom expander.

Recent messages:
• Shows up to 10 most recent unique texts (newest at top)
• "Use" → loads text back into main input area
• "★"   → adds the text to Favorites

Favorites:
• Persistent list (no automatic limit)
• "Use"   → loads text
• "Delete" → removes from favorites

All changes are saved instantly to the local JSON files.

Troubleshooting quick list
--------------------------
No voices shown           → No .onnx files in voices/ folder

No sound                  → Check selected device, mute status, pw-play/paplay working?

Volume slider ineffective → Install sox package or check your playback device

Clip not found            → Check the file is in `audio/` and the name after `!` matches
Login required            → Enter the random access code shown by Phone Access
Phone Access shows a VPN/WARP IP → The app now prefers the LAN/private interface IP

Long device names ugly    → Should be ellipsized (GTK theme issue?)

History/Favorites gone    → history.json, favorites.json, or config.json deleted or corrupted

UI changes not showing    → Hard refresh the browser or restart the app
Static files missing      → Check that `static/index.html`, `static/styles.css`, and `static/app.js` are present

Enjoy your portable TTS control!
Zeppyrae 2026
