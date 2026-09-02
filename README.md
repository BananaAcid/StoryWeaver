# StoryWeaver

An AI-powered interactive storybook player. It reads the story aloud, illustrates the plot, and lets you choose where the adventure goes next — every playthrough generates a unique story, and your choices shape the narrative.

<p align="center">
  <picture>
    <source srcset="docs/screens/screens.webp" type="image/webp">
    <img src="docs/screens/screens.gif" alt="StoryWeaver screenshots slideshow">
  </picture>
</p>

<p align="center">
  <a href="docs/screens/edit-infocode.png"><img src="docs/screens/edit-infocode.png" width="320" alt="Edit info code online"></a>
  <a href="docs/screens/edit-config.png"><img src="docs/screens/edit-config.png" width="320" alt="Edit config online"></a>
</p>

## Features

- **Dynamic storytelling** — AI generates branching stories with meaningful choices
- **Scene images** — generated artwork for each location change
- **Voice narration** — text-to-speech with multiple voices and speed control
- **Background music** — ambient loops that set the mood
- **Theme browser** — pick from AI-generated story themes or write your own prompt
- **Favorites & profiles** — save stories, switch between settings profiles
- **Custom prompts** — tune story tone, detail level, and complexity per profile
- **Built-in updater** — check for new versions from the app
- **Multi-language** — English (US, GB) and German currently (extensible via JSON lang files)
- **Edit config online** — change API, settings, language, and prompts from any browser

## Requirements

- **Device:** Anbernic RG40XXV (or compatible Linux handheld with SDL2), or any Linux device
- **Internet connection:** for AI API calls and app updates
- **AI Key:** An AI API key is needed
   - tested with [Pollinations](https://enter.pollinations.ai/keys) — free tokens; any OpenAI-compatible endpoint should work for text/image, possibly audio as well

> **Other Linux devices:** besides the above, make sure `python3` (with `pysdl2` and Pillow) is installed and that `/dev/input/event*` is readable.

## Installation

**Download the latest build from the [releases](https://storyweaver.zeugs.me/releases/) (or possibly unstable but latest [debug build](https://storyweaver.zeugs.me/debugs/)).**


**Anbernic / handheld devices (e.g. RG40XXV):**

- Download a build and extract it on your SD card under `/Roms/APPS/` so that `StoryWeaver.sh` sits directly inside `/Roms/APPS/` — no extra subfolder.
- Alternatively, copy the extracted contents over via SFTP to `/mnt/mmc/Roms/APPS/`.
- Copy once, then launch from the device's app menu. Configure as you like — on the device by hand, or much more comfortably via the built-in **online config editor** (see below). No need to touch files on the device after first install.

**Any other Linux device:**

- Simply extract the archive wherever you like, make `StoryWeaver.sh` executable, then run it:

  ```bash
  cd /path/to/StoryWeaver
  ./StoryWeaver.sh
  ```

### AI provider

StoryWeaver is tested with **Pollinations AI** as the model provider. You can create a free API token there at https://enter.pollinations.ai/keys and enter it under the **AI Settings** (or in `config.ai.json`).

Other OpenAI-compatible providers generally work for the text and image models, but **audio (text-to-speech) is not tested with other providers**. If audio causes errors, you can turn it off in the in-game **Settings** (`useTTS`) or in `config.json`.

## Configuration

| File | Purpose |
|------|---------|
| `config.json` | General settings — story style, TTS, music, font size, theme prompts, language |
| `config.ai.json` | API key, base URL, model names |

Defaults ship as `config.json.default` and `config.ai.json.default`. These will be replaced on update.

### Editing config online

Instead of hand-editing JSON on the device, you can edit everything in a web browser:

1. Open the in-app menu (**MENU Button** short press) → **Edit Config Online**.
2. The app uploads your current `config.json`, `config.ai.json` (and `.default` variants), profiles, the event log, and any screenshots, then shows a short URL.
3. Open that URL on any device to edit:
   - **API key & endpoint** (OpenAI-compatible `base_url`)
   - **Model names** and token limits per feature
   - **Any app configuration** — story style, image style, font size, TTS, music, theme prompts, etc.
   - **Prompt customization** — free-text additions to steering story tone, detail level, and complexity
   - **Multi-language** — change the language
   - **Download screenshots** captured on the device
4. Press **Save** in the browser; the app detects the change, downloads the edits, and applies them — restarting with the new config automatically.

The config is fully **multi-language** (`lang/en_US.json`, `lang/de_DE.json`, etc.) and the active language follows the device system language — editable online too.

### AI Models

Configure any OpenAI-compatible API. StoryWeaver is tested with [Pollinations AI](https://enter.pollinations.ai/keys) (free tokens):

| Model | Purpose |
|-------|---------|
| `story` | Text generation for story continuation |
| `image` | Scene image generation |
| `speech` | Text-to-speech narration |

## Controls

| Button | Action |
|--------|--------|
| **D-Pad** | Navigate menus, scroll text |
| **A** | Confirm / select |
| **B** | Back / cancel |
| **MENU Button short press** | Open in-app menu |
| **MENU Button long press** (1s) | Take screenshot |
| **START** | Pause / resume TTS |


## Update server & self-update

StoryWeaver checks its central update server for new versions on startup:

- **Web site:** https://storyweaver.zeugs.me
- **Releases:** hosted under the `releases/` folder; debug builds under `debugs/`
- **Naming:** `StoryWeaver v<version>.zip`
- The app periodically pings the server (**Menu → Check for updates** also triggers it) and compares the latest build number against its own. When a newer release is available it offers to download and install it in place.

The update server also powers the online config editor (see **Editing config online**) and the extras.

## Screenshots

Hold the **MENU Button** for 1 second. Screenshots save to `cache/screenshots/` and are included when editing the configs online.

## Profiles

Profiles let you save different setups and custom prompts, perfect for different stories, moods, or desired detail/complexity levels:

- **Custom story prompt** (`promptCustomStoryAddition`) — free-text instructions appended to every story generation. Control tone, pacing, level of detail, complexity, world-building depth, or any other aspect of the narrative.
- **Custom theme prompt** (`promptCustomThemeAddition`) — steer the generated story **themes** (settings, genres, restrictions like "no horror"), plus per-profile model overrides.
- **Model overrides** — each profile can use different AI models and token limits (e.g. a "higher quality, more tokens" profile vs. a lighter one).
- Profiles are stored in `cache/profiles/` and can be selected from **Menu → Profiles**, or created/edited online via **Edit Config Online** (profiles are uploaded alongside the config).

## Project Structure

```
StoryWeaver/
├── main.py              # Entry point, SDL2 bootstrap
├── app.py               # Core game loop and state
├── api.py               # AI API client (text, image, TTS)
├── graphic.py           # SDL2 rendering, UI
├── input.py             # Joystick & button input
├── language.py          # i18n translation
├── os_abstraction.py    # Hardware detection, OS layer
├── components/
│   ├── audio.py         # Music & sound effects
│   ├── config_dialog.py # Settings UI
│   ├── menu.py          # In-app menu
│   ├── updater.py       # Version check & self-update
│   ├── vkeyboard.py     # Virtual keyboard
│   └── online_config.py # Cloud config sync
├── lang/                # Language files (en_US, de_DE)
├── res/                 # Fonts, images, music, sounds
├── cache/               # Story cache & screenshots
└── config.json          # User settings
```

## Development: Creating a release (packup)

Newest install packages are always at: https://storyweaver.zeugs.me (is also the update server)

To package the app for distribution/update, use the provided **`packup.ps1`** script (PowerShell 5.1 and 7):

1. Bump the **3rd** version part (e.g. `v0.0.12.x` → `v0.0.13.x`). The 4th/last part is the continuous build counter.
2. Update the `ver` variable in `app.py`.
3. Verify the code (e.g. `python -c "import ast; ast.parse(open('APP/StoryWeaver/app.py').read()); print('OK')"`).
4. Run:

   ```powershell
   .\packup.ps1
   ```

   This reads the version automatically from `app.py` and creates `_packup/StoryWeaver v<version>.zip` with:
   - The `APP/StoryWeaver/` folder, `APP/Imgs/StoryWeaver.png`, and `APP/StoryWeaver.sh`
   - `config.json` duplicated as `config.json.default` and `config.ai.json` as `config.ai.json.default`
   - `res/source/` excluded, empty folders preserved, `.gitkeep` placeholders skipped
5. Deploy changed files to the device and upload the release online.

You can also deploy directly during packing:

```powershell
.\packup.ps1 -Deploy release   # upload to the release branch (subfolder)
.\packup.ps1 -Deploy debug     # upload to the debug branch (subfolder)
```

The upload destination is taken from `-DSN` or a `PACKUP_DSN` entry in the repository `.env` file. (Example DSN: `sftp://username:password@server.com/appdir`)

> **Note:** The `.default` config files only exist in the installed package. Edit `config.json` / `config.ai.json` in `APP/StoryWeaver/` — they are duplicated to `.default` on packup.

## Support

- Report issues and follow development on [GitHub](https://github.com/BananaAcid/StoryWeaver).
- The project is open source and MIT licensed — see [LICENSE](LICENSE).
- See individual license files in `res/` for audio, images, and fonts.
