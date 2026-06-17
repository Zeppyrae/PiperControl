# Piper_Control Code Walkthrough

This document explains what the repository actually does, file by file and flow by flow.
It is written for someone learning Python, so it focuses on "what happens" and "why this code exists"
rather than only describing features.

## Big Picture

This project is a browser-based control panel for Piper TTS.
Piper is an offline text-to-speech system. This repo does not implement speech synthesis itself.
Instead, it:

1. Starts a small local Python web server.
2. Serves a single HTML page with JavaScript UI.
3. Accepts HTTP requests from the UI.
4. Calls external command-line tools like `piper-tts`, `pw-play`, `paplay`, and `pactl`.
5. Stores user preferences and history in local JSON files.

The code is intentionally compact and uses only the Python standard library on the backend.
That makes it a good learning project because you can study:

- HTTP servers
- JSON persistence
- subprocess management
- threading
- simple state management
- browser-to-Python communication

## Repository Map

Main files:

- `Piper_Control.desktop` - icon-based launcher that starts `main.py` and points at `assets/icon.png`
- `main.py` - command-line entry point
- `browser_ui.py` - main app, HTTP API, and generated HTML/JS UI
- `engine.py` - launches Piper TTS and audio playback
- `settings.py` - loads and saves config values
- `utils.py` - helper functions for voices and audio sinks

Legacy note:

- The older `web_control.py` mini web UI has been retired and is no longer part of the current repository.

Data files created at runtime:

- `config.json`
- `history.json`
- `favorites.json`
- `presets.json`
- `recents.json`

Voice models live in:

- `voices/`

## How To Read The Project

If you want to study the code in a useful order, follow this path:

1. `main.py`
2. `browser_ui.py` - top-to-bottom, because this is where the whole app lives
3. `engine.py`
4. `settings.py`
5. `utils.py`
6. Historical note: older versions of this repo included `web_control.py`, but it is no longer present

## Execution Flow

When you run:

```bash
python3 -u main.py
```

the flow is:

1. `main.py` parses `--port=...` if provided.
2. It imports `BrowserApp` from `browser_ui.py`.
3. `BrowserApp(port=...)` loads saved settings and local state.
4. `BrowserApp.run()` starts the threaded HTTP server.
5. The app opens your browser to the local UI.
6. The browser page makes API requests back to Python.
7. When you press "Speak", the backend starts a thread that runs Piper and playback commands.

So the Python program is both:

- a local server
- a state manager
- a process launcher for TTS

## `main.py`

This file is the smallest and easiest place to start.

### What it does

`main.py` does only a few things:

- checks for `--help` or `-h`
- parses `--port=...`
- imports `BrowserApp`
- constructs it
- runs it

### Why it matters

This file shows the basic entry-point pattern for Python programs:

- define a `main()` function
- call it from `if __name__ == "__main__":`

That `if` check means:

- if the file is run directly, `main()` runs
- if the file is imported by another module, `main()` does not run automatically

### Learning note

This is a very common Python pattern. It keeps import side effects under control.

## `browser_ui.py`

This is the heart of the project.

It contains:

- the HTTP request handler
- the application class
- history/favorites/preset persistence
- port startup logic
- the generated HTML, CSS, and JavaScript UI

## Part 1: Helper Function

### `get_local_ip()`

This function tries to discover the computer's LAN IP address by:

1. creating a UDP socket
2. connecting to `8.8.8.8` on port `80`
3. reading the socket's own local address

It does not actually send traffic to Google DNS in a normal way.
It uses that address as a trick so the OS chooses the outbound interface.

If anything fails, it falls back to `127.0.0.1`.

### Why it exists

The app prints both:

- a local URL for the same machine
- a LAN URL for accessing from a phone or another device

## Part 2: `BrowserRequestHandler`

This class subclasses `http.server.BaseHTTPRequestHandler`.
That means each browser request gets routed into methods like:

- `do_GET()`
- `do_POST()`

The handler is initialized with `app=self`, so it can access the shared `BrowserApp` instance.

### Important idea

The handler itself does not own the real state.
It just receives HTTP requests and forwards them into the app object.
This is a common pattern in Python web code.

### GET routes

#### `/`

Returns the full HTML page from `self.app.html_page()`.

#### `/api/status`

Returns JSON containing:

- current settings
- available voices from `voices/`
- available audio sinks
- local IP
- current port

This is how the frontend learns what to display.

#### `/api/history`

Returns the history list.

#### `/api/favorites`

Returns saved favorites.

#### `/api/presets`

Returns saved presets.

#### `/api/recents`

Returns the recent voice and device selections.

### POST routes

#### `/api/speak`

Reads request data, updates settings, and starts speech.

The request can be JSON or form-style data.

#### `/api/stop`

Stops current speech playback and synthesis.

#### `/api/settings`

Updates settings and saves them to `config.json`.

#### `/api/favorite/add`

Adds a named favorite phrase.

#### `/api/favorite/remove`

Removes a favorite by name.

#### `/api/history/clear`

Clears all history.

#### `/api/preset/save`

Saves the current voice/settings under a preset name.

#### `/api/preset/load`

Loads a preset and applies it to current settings.

#### `/api/preset/delete`

Deletes a preset.

#### `/api/shutdown`

Starts shutdown in a background thread.

### Response helpers

The methods `_set_json_headers()` and `_set_html_headers()` only set:

- status code
- content type
- end headers

That is a small but useful pattern to avoid repeating header code.

### `log_message()`

This suppresses the default noisy HTTP log messages.

## Part 3: `BrowserApp`

This is the real application state object.

### Constructor: `__init__`

On startup, the app loads:

- settings from `config.json`
- voice engine object
- history from `history.json`
- favorites from `favorites.json`
- presets from `presets.json`
- recent selections from `recents.json`

This means most user state survives program restarts.

### Why use a class here

The class groups all app-related state together:

- configuration
- runtime process handles
- history lists
- saved data

Instead of using many global variables, the state lives inside one object.

That is a clean Python design for a small application.

## Persistence Methods

### `load_history()` / `save_history()`

History is loaded from `history.json`.

Only valid items are kept:

- the file must contain a list
- each item must be a dict
- each item must have `"text"`

The list is sorted by timestamp descending and trimmed to 10 entries.

### `add_to_history(text)`

When new text is spoken:

1. the text is stripped
2. duplicates are removed
3. the new item is inserted at the top
4. the list is trimmed to 10
5. the file is saved

This gives you a "last 10 unique texts" history.

### `load_favorites()` / `save_favorites()`

Favorites are stored as a dictionary:

```json
{
  "My Name": "Hello there"
}
```

So the key is the favorite name and the value is the spoken text.

### `load_presets()` / `save_presets()`

Presets are also stored as a dictionary.

Each preset contains selected settings such as:

- voice
- speed
- noise
- noise_w
- sentence_silence

### `load_recents()` / `save_recents()`

Recents are stored as:

```json
{
  "voices": [],
  "devices": []
}
```

The app keeps only the last 3 voices and last 3 devices.

### Why recents exist

They make the UI faster to use by exposing recently chosen options as buttons.

## Settings Updates

### `update_settings(data)`

This method is called when the frontend submits settings changes.

It updates fields like:

- `voice`
- `speed`
- `noise`
- `noise_w`
- `sentence_silence`
- `output_device`
- `mute`

Then it saves settings to `config.json`.

### Important detail

`update_settings()` also tells the engine to mute or unmute:

```python
self.engine.set_mute(self.settings["mute"])
```

That means the mute checkbox is not just visual state.
It directly affects playback behavior.

## Speech Flow

### `speak(text)`

This is one of the most important methods in the project.

It does the following:

1. returns immediately if muted or if text is empty
2. returns if a TTS thread is already running
3. adds the text to history
4. starts a background thread that calls `self.engine._run(text, self.settings)`

### Why use a thread

The TTS process and audio playback can take time.
If the app ran them on the main thread, the server could freeze or become unresponsive.

Using a thread lets the UI stay responsive while speech is generated.

### `stop()`

Calls `self.engine.stop()`.

### `shutdown()`

Stops speech and shuts down the server.

## Server Startup

### `start()`

This method starts the HTTP server.

It does something nice for the user:

- tries the requested port
- if busy, keeps trying the next 9 ports
- prints a warning if it had to fall back

It uses `socketserver.ThreadingTCPServer`, which means each request can be handled in parallel threads.

That matters because the browser may fetch several endpoints quickly.

### `stop_server()`

Shuts the server down and clears the server/thread references.

### `run()`

This is the high-level startup sequence:

1. print progress message
2. call `start()`
3. print local and LAN URLs
4. try to open the browser
5. wait for the server thread
6. shut down cleanly on Ctrl+C

This method is the bridge between the command-line program and the browser experience.

## `html_page()`

This method returns one giant HTML string.

That HTML string includes:

- CSS styling
- the visible UI
- all client-side JavaScript

This is an important design choice:

- instead of loading separate `.html`, `.css`, and `.js` files
- the app embeds everything into one Python string

That makes the repo smaller, but harder to maintain.

## Frontend Structure

The page has:

- a sidebar for presets, recents, history, favorites
- a main card with text input and controls
- modals for help and phone access
- a mobile action bar

### Why the frontend matters

The browser is not just "a display".
It is an active client that calls the backend API.

The page fetches data from `/api/...` routes and sends user actions back to the server.

## Frontend JavaScript Flow

The JavaScript is worth studying because it mirrors the backend state.

### `q(id)`

Short helper for `document.getElementById(id)`.

This is a nice example of making code shorter without changing behavior.

### `setStatus(msg)`

Updates the status text at the bottom of the card.

### `createItemRow(...)`

Builds a UI row for history, favorites, or presets.

This avoids repeating the same DOM creation code many times.

## UI Behavior

### Theme toggling

The app stores theme choice in `localStorage`.

That means the browser remembers light/dark mode even though the backend does not care.

### Batch mode

If batch mode is enabled:

- the text area is treated as multiple lines
- each non-empty line is spoken separately
- a 500 ms pause is inserted between lines

This is a useful feature for reading lists or scripts line by line.

### Text cleanup

The "Clean text" checkbox normalizes text by:

- compressing repeated whitespace
- adding spacing after sentence punctuation in one specific pattern

### Counter

The page updates:

- character count
- word count
- estimated read time

That is all client-side; no server call is needed.

### Drag and drop

Dropping a text file into the text box loads the file contents.

That is a nice example of using the browser File API.

## Frontend Fetch Flow

### `loadState()`

This runs on page load.

It:

1. reads theme and enter-to-speak state from localStorage
2. fetches `/api/status`
3. fills dropdowns and sliders
4. stores the remote access URL
5. loads history, favorites, presets, and recents

This is the main synchronization step between backend and frontend.

### `loadHistory()`

Fetches `/api/history` and renders it.

The user can filter history using the search box.

### `loadFavorites()`

Fetches `/api/favorites`.

Each favorite can be used or deleted.

### `loadPresets()`

Fetches `/api/presets`.

Each preset can be loaded or deleted.

### `loadRecents()`

Fetches `/api/recents`.

This renders buttons for recent voices and recent output devices.

## Actions That Call The Backend

### `onSpeak()`

This is the frontend button handler for speech.

It:

1. gets the text
2. optionally cleans it
3. checks batch mode
4. POSTs to `/api/speak`
5. refreshes history
6. clears the box if auto-clear is enabled

In batch mode, it sends one request per line.

### `onStop()`

POSTs to `/api/stop`.

### `saveFavorite()`

Prompts for a name, then sends `/api/favorite/add`.

### `removeFavorite(name)`

Sends `/api/favorite/remove`.

### `savePreset()`

Saves current settings to `/api/preset/save`.

### `loadPreset(name)`

Loads a preset from `/api/preset/load`, then applies returned values to the form.

### `deletePreset(name)`

Sends `/api/preset/delete`.

### `clearHistory()`

Sends `/api/history/clear`.

### `saveSettings()`

POSTs the current control values to `/api/settings`.

### `onShutdown()`

POSTs to `/api/shutdown`.

## Keyboard Shortcuts

The UI supports:

- `Ctrl+Enter` -> speak
- `Escape` -> stop
- `Ctrl+L` -> clear text
- `Ctrl+B` -> toggle batch mode

This is a good example of event handling in browser JavaScript.

## `engine.py`

This file is the bridge between the app and the external Piper tools.

It does not synthesize speech itself.
It builds shell commands and runs them.

## `PiperEngine.__init__`

The engine stores:

- `voice_dir` - where voice models are located
- `current_process` - the Piper synthesis process
- `play_process` - the playback process
- `mute` - whether speech is blocked
- `lock` - a thread lock for safe stopping
- `pipewire` - whether PipeWire is available

### Why the lock exists

The app may call stop while a process is starting or running.
The lock helps prevent race conditions around process handles.

## PipeWire Detection

### `_is_pipewire()`

This runs:

```python
pw-cli info
```

If it succeeds, the app assumes PipeWire is available.
If it fails, it falls back to `paplay`.

## `stop()`

This method tries to terminate any running synthesis/playback processes.

It:

- terminates `current_process`
- terminates `play_process`
- force-kills them if they do not exit fast enough
- runs `pkill` for `piper-tts` and `pw-play` as a cleanup fallback

### Learning note

This is a real-world example of defensive process cleanup.
External audio tools do not always exit cleanly, so the code uses more than one layer of stopping.

## `set_mute(state)`

Sets the mute flag.

If muting is turned on, it immediately stops current audio.

## `_run(text, settings)`

This is the main synthesis/playback path.

### Step 1: early exits

It returns immediately if:

- muted
- text is empty after stripping

### Step 2: read settings

It reads:

- `voice`
- `speed`
- `noise`
- `output_device`

### Step 3: locate the model

The model path is:

```python
voices/<voice>.onnx
```

If the file does not exist, it prints an error and stops.

### Step 4: prepare output file

The code uses a fixed temp file:

```python
/tmp/piper_output.wav
```

### Step 5: build the Piper command

It builds a command like:

```python
piper-tts --model <model> --length_scale <speed> --noise_scale <noise> --noise_w <noise> --output_file /tmp/piper_output.wav
```

### Step 6: run Piper

It launches Piper with `subprocess.Popen(...)`, sends the text on stdin, and waits for completion.

### Step 7: play the audio

The audio playback command is:

- `pw-play` if PipeWire is detected
- `paplay` otherwise

If a non-default output device is selected, the code adds device arguments.

### Step 8: cleanup

Finally it:

- clears the process references
- deletes the temp WAV file if possible

## `settings.py`

This module handles user preferences.

## `CONFIG_PATH`

The config file is `config.json` in the project directory.

## `DEFAULTS`

Default settings include:

- `voice`
- `speed`
- `noise`
- `volume`
- `mute`
- `output_device`

### Important observation

Some settings in the frontend are not fully used by the backend.
For example:

- `volume` is stored in the browser's localStorage, but not used by the engine
- `noise_w` and `sentence_silence` are saved, but the engine does not pass them to Piper

That means the UI is a little ahead of the backend in some places.

## `load_settings()`

This does:

1. load `config.json` if it exists
2. detect available voices
3. choose a default voice
4. merge defaults with saved data
5. ensure the selected voice exists

### Why this matters

This prevents broken settings from crashing startup if the chosen voice model is missing.

## `save_settings(settings)`

Writes the settings dictionary to `config.json` using pretty JSON formatting.

## `utils.py`

This file contains helper functions.

### `get_voice_dir()`

Returns the absolute `voices/` directory path next to the script.

### `list_voices(voice_dir=None)`

Scans the voice directory and returns all files ending in `.onnx`, with the suffix removed.

So a file named:

```text
en_GB-cori-high.onnx
```

becomes:

```text
en_GB-cori-high
```

### `list_audio_sinks()`

Runs:

```python
pactl list short sinks
```

Then parses sink names from the output.

It always includes `"default"` first.

## Historical Note

Older versions of this repository included a separate `web_control.py` experiment.
That file has been removed, and the current app now lives entirely in `main.py`,
`browser_ui.py`, `engine.py`, `settings.py`, `utils.py`, and `static/`.

The important lesson from that older code path is the same:

- serve a local webpage
- accept `/speak` and `/stop`
- trigger callbacks

The current app does all of that with a richer UI, persistent state, presets,
history, favorites, recents, port fallback, and browser auto-open.

## What The README Says vs What The Code Does

The README is helpful, but parts of it are stale or aspirational.

### Examples

- The README mentions GTK4 in one place, but the active app is browser-based.
- The README says volume control is done via `sox`, but the current backend code does not actually apply volume changes.
- The README mentions `sentence_silence`, but the engine does not pass it to `piper-tts`.

### What this means for study

Trust the code more than the README when the two disagree.

## Important Python Concepts In This Repo

### 1. Modules

Each `.py` file is a module you can import.

Example:

```python
from engine import PiperEngine
```

### 2. Classes

`BrowserApp` and `PiperEngine` are classes.

They bundle data and behavior together.

### 3. Methods

Functions defined inside a class are methods.

They usually operate on `self`, which refers to the current object.

### 4. Threads

The app uses threads so speech generation does not block the server.

### 5. Subprocesses

The code launches external programs with `subprocess.Popen` and `subprocess.run`.

### 6. JSON

User data is stored in JSON files.

### 7. HTTP

The browser and backend communicate using GET and POST requests.

### 8. File paths

The code uses `Path(__file__).parent` and `os.path.dirname(...)` to find files relative to the script.

That is how the project stays portable.

## State Flow Summary

Here is the simplest way to understand the data flow:

1. The browser loads the page.
2. The page calls `/api/status`.
3. Python replies with settings and available options.
4. The user changes settings in the page.
5. The page POSTs the changes to `/api/settings`.
6. Python saves them to `config.json`.
7. When the user clicks Speak, the page POSTs text to `/api/speak`.
8. Python records history and launches Piper.
9. The engine writes a WAV file and plays it.
10. The browser refreshes its lists from the API as needed.

## Things That Are Good For A Beginner To Notice

- The backend is built from standard library pieces instead of a big framework.
- The app separates concerns reasonably well:
  - UI generation in `browser_ui.py`
  - synthesis in `engine.py`
  - config in `settings.py`
  - small helpers in `utils.py`
- The code is mostly straightforward imperative Python.
- There are many opportunities to practice reading real code:
  - conditionals
  - loops
  - dictionaries
  - file IO
  - exception handling
  - threading

## Things That Look Incomplete Or Legacy

These are not necessarily "bad", but they are important to know while learning:

- some UI controls are not fully implemented in the backend
- the browser page used to live inside one giant Python string, which was harder to maintain
- some settings are stored but not actually used by synthesis

## Suggested Study Path

If you want to learn from this repo, I suggest studying it in this order:

1. `main.py`
2. `settings.py`
3. `utils.py`
4. `engine.py`
5. `browser_ui.py` top section
6. `browser_ui.py` request handler
7. `browser_ui.py` `BrowserApp` state methods
8. `static/index.html`
9. `static/styles.css`
10. `static/app.js`

## Mental Model To Keep In Mind

Think of the app as three layers:

### 1. Browser layer

The HTML and JavaScript the user sees.

### 2. Python server layer

The HTTP API and local state management.

### 3. External tool layer

The Piper executable and audio playback utilities.

Most of the code is about moving information cleanly between those layers.

## Final Takeaway

This repo is a small but real example of a Python application that:

- serves a browser UI
- stores local state
- launches command-line tools
- uses threads to keep the server responsive

If you study the file order above and trace one action end to end, especially "click Speak", you will learn a lot about practical Python application structure.
