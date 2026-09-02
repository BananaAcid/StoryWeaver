from main import hw_info, system_lang
from graphic import screen_resolutions, UserInterface
from language import Translator
from api import ApiClient
from PIL import Image
import input
import sys
import time
import json
import os
import subprocess
import shutil
import threading
import datetime
import random
import ctypes
import sdl2
import components.menu as menu_mod
from components.updater import start_background_check, new_release_version
from components import online_config
from components import audio

config_path = ""
ver = "v0.0.12.735"

app_config = {}
translator = None
api = None
gr = None
language = system_lang

skip_input_check = True
current_window = "boot"
selected_index = 0
theme_scroll_offset = 0

themes = []
thumbnails = {}
selected_theme = None
current_story = None
last_scene_path = None
story_history = []
story_steps = []
story_step = 0
story_scroll_offset = 0

tts_active = False
tts_paused = False
tts_loading = False
tts_done = False
loading_message = ""

api_thread = None
api_result = None
api_error = None

is_compacting = False

dot_count = 0
_last_auto_check = 0
show_log = False
show_menu = False
menu_backup = None
_menu_was_open = False
_config_from_menu = False

_profile_dir = ""
_active_profile = None
log_scroll_offset = 0
error_scroll_offset = 0
error_raw_response = ""
_error_from_window = ""
_boot_auto_started = False
show_config = False
show_welcome = False
config_dialog_backup = None
log_backup = None
detail_backup = None
detail_painted = False
favorites = {}
favorites_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "favorites.json")
_app_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(_app_dir, "log.txt")
_cachebuster = None
_tts_gen = 0
_tts_ready_path = None
_tts_ready_gen = 0
_tts_step = -1
_fav_toggle_redraw = False
_theme_retries = 0
_theme_select_index = 0
_theme_detail_scroll_offset = 0
_welcome_scroll_offset = 0

_image_thread = None
_image_done = False
_image_callback = None

_screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "screenshots")

def write_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _take_screenshot():
    try:
        os.makedirs(_screenshot_dir, exist_ok=True)
        ss_name = datetime.datetime.now().strftime("ss_%Y%m%d_%H%M%S.png")
        ss_path = os.path.join(_screenshot_dir, ss_name)
        gr.active_image.save(ss_path)
        write_log(f"Screenshot saved: {ss_name}")
        gr.notification_text = translator.translate("Screenshot taken")
        gr.notification_time = time.time()
    except Exception as e:
        write_log(f"Screenshot failed: {e}")


def _save_favorites():
    try:
        os.makedirs(os.path.dirname(favorites_path), exist_ok=True)
        with open(favorites_path, "w") as f:
            json.dump(favorites, f, indent=2)
    except Exception as e:
        write_log(f"Failed to save favorites: {e}")


def _save_cachebuster_to_config(cb):
    try:
        _safe_save_config({"freezeThemes": cb})
        write_log(f"Persisted freezeThemes cachebuster: {cb}")
    except Exception as e:
        write_log(f"Failed to persist freezeThemes: {e}")


def _cache_cleanup():
    cache_base = os.path.join(script_dir, "cache")
    if os.path.exists(cache_base):
        for f in os.listdir(cache_base):
            if f.startswith("themes_current-") and f.endswith(".json"):
                cb_part = f[len("themes_current-"):-len(".json")]
                if cb_part != _cachebuster:
                    try:
                        os.remove(os.path.join(cache_base, f))
                        write_log(f"Removed stale themes_current: {f}")
                    except Exception as e:
                        write_log(f"Failed to remove {f}: {e}")

    current_batch_hashes = set()
    batch_path = os.path.join(cache_base, f"themes_current-{_cachebuster}.json")
    if os.path.exists(batch_path):
        try:
            with open(batch_path) as f:
                data = json.load(f)
                current_batch_hashes = set(data.get("hashes", []))
        except Exception as e:
            write_log(f"Failed to load themes_current: {e}")

    fav_hashes = set(favorites.keys())
    preserve = fav_hashes | current_batch_hashes
    write_log(f"Cache cleanup: {len(fav_hashes)} favorite + {len(current_batch_hashes)} batch = {len(preserve)} hashes to preserve")
    for d, desc in [(cache_dir, "imgs"), (speak_dir, "speak"), (story_dir, "story"), (history_dir, "history")]:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            path = os.path.join(d, f)
            if not os.path.isfile(path):
                continue
            try:
                name, _ = os.path.splitext(f)
                h = name.split("_")[0] if "_" in name else None
                if h is None or h not in preserve:
                    os.remove(path)
                    write_log(f"Cleaned {desc}: {f}")
            except Exception as e:
                write_log(f"Cleanup skip {f}: {e}")


def _play_music(path, loop=False):
    ok = audio.play_music(path, loop=loop)
    if ok:
        write_log(f"Music: {os.path.basename(path)} {'loop' if loop else ''}")


def _stop_music():
    audio.stop_music()
    write_log("Music stopped")


def _toggle_music():
    was = audio.is_music_playing()
    if was:
        audio.stop_music()
        write_log("Music stopped by Y")
    else:
        import random
        audio.play_music(random.choice(theme_music_tracks), loop=True)
        write_log("Music toggled on by Y")


def _toggle_dialog_tts():
    if not audio.toggle_tts():
        _start_tts(force=True)


def _build_image_url(prompt):
    import urllib.parse
    model = app_config.get("models", {}).get("image", "zimage")
    base = app_config.get("ai", {}).get("base_url", "")
    encoded = urllib.parse.quote(prompt)
    return f"{base}/image/{encoded}?model={model}&width=1495&height=256&nologo=true"


script_dir = os.path.dirname(os.path.abspath(__file__))
cache_dir = os.path.join(script_dir, "cache", "imgs")
speak_dir = os.path.join(script_dir, "cache", "speak")
story_dir = os.path.join(script_dir, "cache", "story")
history_dir = os.path.join(script_dir, "cache", "history")
_profile_dir = os.path.join(script_dir, "cache", "profiles")
res_dir = os.path.join(script_dir, "res")
def _restart_app():
    python = sys.executable
    script = os.path.join(script_dir, "main.py")
    cfg = os.path.join(script_dir, "config.json")
    os.execv(python, [python, script, cfg])

intro_music = os.path.join(res_dir, "universfield-solar-system-space-journey-153272.wav")
theme_music_tracks = [
    os.path.join(res_dir, "alexisortizsofield-ominous-bass-arp-and-riff_ab-minor_aos-160137.wav"),
    os.path.join(res_dir, "fronbondi_skegs-amb-intrigued-ambient-background-effect-seamless-loop-523879.wav"),
    os.path.join(res_dir, "freesound_community-mellowloop-93589.wav"),
    os.path.join(res_dir, "freesound_community-the-pattern-loop-64547.wav"),
]

x_size, y_size, max_elem = screen_resolutions.get(hw_info, (640, 480, 11))
button_x = x_size - 120
button_y = y_size - 30
ratio = y_size / x_size


def _deep_merge(defaults, overrides):
    result = defaults.copy()
    for key, val in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _safe_save_config(updates=None):
    if updates is None:
        updates = {}
    try:
        with open(config_path) as f:
            disk = json.load(f)
    except:
        disk = {}
    for k, v in updates.items():
        if k in disk and isinstance(disk[k], dict) and isinstance(v, dict):
            disk[k].update(v)
        else:
            disk[k] = v
    disk.pop("ai", None)
    disk.pop("models", None)
    with open(config_path, "w") as f:
        json.dump(disk, f, indent=4)


def _load_json(filepath, label):
    try:
        with open(filepath) as f:
            return json.load(f), None
    except Exception as e:
        return None, f"Failed to load {label}: {e}"


def _get_profile_list():
    """Return list of dicts with 'filename' and 'title' for each profile."""
    profiles = []
    if not os.path.isdir(_profile_dir):
        return profiles
    for fn in os.listdir(_profile_dir):
        if not fn.endswith(".json"):
            continue
        fp = os.path.join(_profile_dir, fn)
        try:
            with open(fp) as f:
                data = json.load(f)
            title = data.get("profileTitle", fn)
            profiles.append({"filename": fn, "title": title})
        except Exception:
            profiles.append({"filename": fn, "title": f"{fn} (invalid JSON)"})
    profiles.sort(key=lambda p: p["title"].lower())
    return profiles


def _activate_profile(filename_or_none):
    """Set _active_profile and reload config to merge the profile."""
    global _active_profile
    _active_profile = filename_or_none
    _reload_config(allow_quit=False)


def _profile_changes_config(profile_dict, config_dict):
    """Check if profile changes any ai{}, models{} or *prompt* key value vs current config.
    Returns reason string or None."""
    for k, v in profile_dict.items():
        if k in ("ai", "models"):
            cv = config_dict.get(k, {})
            if isinstance(v, dict) and isinstance(cv, dict):
                for sk, sv in v.items():
                    if cv.get(sk) != sv:
                        return f"{k}.{sk}: {cv.get(sk, '<unset>')} → {sv}"
        elif isinstance(v, dict):
            cv = config_dict.get(k, {})
            if isinstance(cv, dict):
                reason = _profile_changes_config(v, cv)
                if reason:
                    return reason
        elif "prompt" in str(k).lower():
            if config_dict.get(k) != v:
                return f"prompt key '{k}' changed"
    return None


def _reload_config(allow_quit=False):
    global app_config, log_file, _active_profile, api
    while True:
        data, err = _load_json(config_path, "config.json")
        if data is not None:
            break
        gr.draw_clear()
        gr.draw_error(
            f"Config error: {err}",
            retry_text="A:Retry", back_text="B:Exit",
            log_text="", version=ver,
        )
        gr.draw_paint()
        while True:
            input.check()
            if input.key("A"):
                break
            if input.key("B"):
                if allow_quit:
                    gr.draw_end()
                    sys.exit()
                return False
            time.sleep(0.05)
    temp = {}
    default_path = config_path + ".default"
    if os.path.exists(default_path):
        d, err = _load_json(default_path, "config.json.default")
        if d is not None:
            temp = _deep_merge(temp, d)
            write_log("Loaded config.json.default as base")
        else:
            write_log(err)
    else:
        write_log("config.json.default not found, skipping")
    temp = _deep_merge(temp, data)
    write_log("Loaded config.json")
    ai_path = config_path.replace(".json", ".ai.json")
    ai_default = ai_path + ".default"
    if os.path.exists(ai_default):
        d, err = _load_json(ai_default, "config.ai.json.default")
        if d is not None:
            temp = _deep_merge(temp, d)
            write_log("Loaded config.ai.json.default as base")
        else:
            write_log(err)
    else:
        write_log("config.ai.json.default not found, skipping")
    if os.path.exists(ai_path):
        d, err = _load_json(ai_path, "config.ai.json")
        if d is not None:
            temp = _deep_merge(temp, d)
            write_log("Loaded config.ai.json")
        else:
            write_log(err)
            set_error(f"Config error: {err}")
    else:
        write_log("config.ai.json not found, skipping")
    temp.setdefault("useTTS", True)
    temp.setdefault("useMusic", True)
    temp.setdefault("useTTSwithMusic", "lower")
    temp.setdefault("useStoryImages", True)
    temp.setdefault("seenWelcomescreen", False)
    temp.setdefault("debug", {}).setdefault("editOnlineId", "")
    temp.setdefault("debug", {}).setdefault("overwriteLangCode", "")
    temp.setdefault("debug", {}).setdefault("sleep", "mem")
    temp.setdefault("debug", {}).setdefault("sleep_possiblestates", [
        ["freeze", "Freeze userspace (light suspend)"],
        ["mem", "Suspend-to-RAM (deep sleep)"],
    ])
    temp.setdefault("fontSizeText", 15)

    if _active_profile:
        profile_path = os.path.join(_profile_dir, _active_profile)
        if os.path.exists(profile_path):
            d, err = _load_json(profile_path, f"profile {_active_profile}")
            if d is not None:
                profile_title = d.get("profileTitle", _active_profile)
                write_log(f"Merged profile: {profile_title}")
                write_log(f"Merged profile file: {_active_profile}")
                temp = _deep_merge(temp, d)
                for k in ("profileTitle", "promptCustomStoryAddition", "promptCustomThemeAddition"):
                    temp.pop(k, None)
            else:
                write_log(err)
                set_error(f"Profilfehler: {err}")
        else:
            write_log(f"Profile file not found: {_active_profile}")
            _active_profile = None

    old_models = app_config.get("models", {}).copy() if isinstance(app_config.get("models"), dict) else {}

    app_config.clear()
    app_config.update(temp)
    audio.set_tts_music_mode(app_config.get("useTTSwithMusic", "lower"))
    gr.font_size_text = app_config["fontSizeText"]
    _log_cfg = str(app_config.get("debug", {}).get("log", "log.txt"))
    log_file = _log_cfg if _log_cfg.startswith("/") else os.path.join(_app_dir, _log_cfg)
    if api:
        api = ApiClient(app_config, version=ver, log_file=log_file)

    new_models = app_config.get("models", {})
    if isinstance(new_models, dict) and isinstance(old_models, dict):
        for k in sorted(set(list(old_models.keys()) + list(new_models.keys()))):
            ov = old_models.get(k, "<unset>")
            nv = new_models.get(k, "<removed>")
            if ov != nv:
                write_log(f"config.models.{k}: {ov} \u2192 {nv}")

    write_log("Config reloaded")
    return True


def _history_path():
    if not selected_theme or not selected_theme.get("hash"):
        return None
    return os.path.join(history_dir, f"{selected_theme['hash']}_history.json")


def _save_history(step=None):
    path = _history_path()
    if not path:
        return
    s = story_step if step is None else step
    data = {
        "theme_hash": selected_theme["hash"],
        "step": s,
        "steps": story_steps,
        "messages": story_history,
    }
    try:
        os.makedirs(history_dir, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        write_log(f"Saved history: step {s}, {len(story_history)} messages")
    except Exception as e:
        write_log(f"Failed to save history: {e}")


def _load_history():
    global story_history, story_step, story_steps
    path = _history_path()
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        story_history = data.get("messages", [])
        story_step = data.get("step", 0)
        story_steps = data.get("steps", [])
        if story_step == 0 and story_steps:
            story_step = 1
        write_log(f"Loaded history: {len(story_history)} messages, step {story_step}")
        return True
    except Exception as e:
        write_log(f"Failed to load history: {e}")
        return False


def _check_compact_history():
    global story_history, is_compacting
    compact_at = app_config.get("story", {}).get("compactAt", 20) if isinstance(app_config.get("story"), dict) else 20
    if len(story_history) >= compact_at:
        write_log(f"History at {len(story_history)} messages, compacting...")
        is_compacting = True
        try:
            initial = story_history[:3]
            last_asst = max(i for i, m in enumerate(story_history) if m["role"] == "assistant")
            tail = story_history[last_asst:]
            compact_input = story_history[:last_asst]
            summary = api.compact_history(compact_input, language)
            story_history = initial + [{"role": "system", "content": summary}] + tail
            api.dump_compact_event({
                "before": len(compact_input) + len(tail),
                "after": len(story_history),
                "initial_count": len(initial),
                "middle_count": len(compact_input) - len(initial),
                "tail_count": len(tail),
            }, summary)
            write_log("History compacted successfully")
        except Exception as e:
            write_log(f"History compaction failed: {e}")
        finally:
            is_compacting = False


def start():
    global skip_input_check, current_window, api, translator, gr, app_config, language, log_file, _last_auto_check

    # open(log_file, "w").close()
    write_log(f"StoryWeaver {ver} started")

    global favorites
    if os.path.exists(favorites_path):
        try:
            with open(favorites_path) as f:
                favorites = json.load(f)
        except Exception:
            favorites = {}
    write_log(f"Loaded {len(favorites)} favorites")

    gr = UserInterface()

    if not _reload_config(True):
        return

    global _cachebuster
    cb = app_config.get("freezeThemes")
    if isinstance(cb, str) and cb:
        _cachebuster = cb
    else:
        old_val = repr(cb)
        _cachebuster = str(int(time.time() * 1000000))
        write_log(f"Generated cachebuster: {old_val} -> {_cachebuster}")
        _save_cachebuster_to_config(_cachebuster)

    lang = app_config.get("debug", {}).get("overwriteLangCode", "") or system_lang
    translator = Translator(lang)
    language = lang

    if app_config.get("debug", {}).get("cacheClearForce", False):
        write_log("cacheClearForce is true, clearing cache")
        cache_base = os.path.join(script_dir, "cache")
        if os.path.exists(cache_base):
            for f in os.listdir(cache_base):
                if f.startswith("themes_current-") and f.endswith(".json"):
                    try:
                        os.remove(os.path.join(cache_base, f))
                        write_log(f"Cleared {f}")
                    except Exception as e:
                        write_log(f"Failed to remove {f}: {e}")
        for cd in [cache_dir, speak_dir, story_dir, history_dir]:
            if os.path.exists(cd):
                shutil.rmtree(cd)
        try:
            _safe_save_config({"debug": {"cacheClearForce": False}})
        except Exception as e:
            write_log(f"Failed to persist cacheClearForce reset: {e}")
        _restart_app()

    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(speak_dir, exist_ok=True)
    os.makedirs(story_dir, exist_ok=True)
    os.makedirs(history_dir, exist_ok=True)
    os.makedirs(os.path.join(script_dir, "res"), exist_ok=True)
    _cache_cleanup()

    res_bg = os.path.join(script_dir, "res", "bg.jpg")
    res_bg_720 = os.path.join(script_dir, "res", "bg_720.jpg")
    if os.path.exists(res_bg) and not os.path.exists(res_bg_720):
        try:
            from PIL import Image
            img = Image.open(res_bg)
            w, h = img.size
            if w > h:
                new_w, new_h = 720, int(h * 720 / w)
            else:
                new_h, new_w = 720, int(w * 720 / h)
            img.resize((new_w, new_h), Image.LANCZOS).save(res_bg_720, quality=85)
            write_log(f"Background resized to {new_w}x{new_h}")
        except Exception as e:
            write_log(f"Background resize failed: {e}")

    audio.init()
    audio.set_tts_music_mode(app_config.get("useTTSwithMusic", "lower"))

    api = ApiClient(app_config, version=ver, log_file=log_file)

    gr.draw_boot_screen(
        title=translator.translate("Story Weaver"),
        subtitle=translator.translate("An AI Adventure Game"),
        prompt=translator.translate("Press START to start"),
        version=ver,
    )
    gr.draw_paint()

    if app_config.get("useMusic", True):
        _play_music(intro_music)
        write_log(f"Starting intro music")

    current_window = "boot"

    start_background_check(
        int(ver.split(".")[-1]),
        lambda lbl: setattr(menu_mod, '_last_update_label',
            translator.translate("Update (new)").format(ver=lbl.replace("Update (-> v", "").rstrip(")"))
            if lbl.startswith("Update (-> v") else
            translator.translate(lbl) if lbl in ("Update (up to date)",) else lbl),
        lambda msg: write_log(msg),
        version=ver,
    )
    _last_auto_check = time.time()
_suspended = False

def update():
    global current_window, skip_input_check, dot_count, _last_auto_check, show_log, log_scroll_offset, log_backup, show_config, show_welcome, config_dialog_backup, show_menu, menu_backup, _menu_was_open, _suspended, _config_from_menu

    if skip_input_check:
        input.reset_input()
        skip_input_check = False
    else:
        input.check()

    # SDL event pump (may not generate events on this platform)
    _sdl_event = sdl2.SDL_Event()
    while sdl2.SDL_PollEvent(ctypes.byref(_sdl_event)):
        if _sdl_event.type == sdl2.SDL_APP_WILLENTERBACKGROUND:
            _music_was_playing = audio.is_music_playing()
            audio.pause_music()
            stop_tts()
            _suspended = True
            write_log("Suspend: entering background")
        elif _sdl_event.type == sdl2.SDL_APP_DIDENTERFOREGROUND:
            if _music_was_playing:
                audio.resume_music()
            _music_was_playing = False
            _suspended = False
            write_log("Resume: entered foreground")

    # POWER key → stop audio, then force kernel suspend.
    if input.key("POWER"):
        if not _suspended:
            audio.pause_music()
            stop_tts()
            _suspended = True
            write_log("Suspend: power button pressed")
            try:
                with open("/sys/power/state", "w") as f:
                    f.write(app_config.get("debug", {}).get("sleep", "mem"))
            except Exception as e:
                write_log(f"Suspend write failed: {e}")
            input.drain()
            input.reset_input()
            _suspended = False
            audio.resume_music()
            write_log("Resume: woken from sleep")

    dot_count += 1

    if time.time() - _last_auto_check >= 300:
        start_background_check(
            int(ver.split(".")[-1]),
            lambda lbl: setattr(menu_mod, '_last_update_label',
                translator.translate("Update (new)").format(ver=lbl.replace("Update (-> v", "").rstrip(")"))
                if lbl.startswith("Update (-> v") else
                translator.translate(lbl) if lbl in ("Update (up to date)",) else lbl),
            lambda msg: write_log(msg),
            version=ver,
        )
        _last_auto_check = time.time()

    if (input.key("SELECT") or input.key("MENUF") or input.key("B")) and show_log:
        show_log = False
        gr._paint_blocked = False
        if log_backup:
            gr.active_image.paste(log_backup, (0, 0))
            log_backup = None
        if not show_menu and current_window == "error":
            gr.draw_error(
                error_message,
                raw_response=error_raw_response,
                scroll_offset=error_scroll_offset,
                retry_text=translator.translate("A:Retry"),
                back_text=translator.translate("B:Back"),
                log_text=translator.translate("SEL:Log"),
                version=ver,
            )
        gr.draw_paint()
        return

    if show_config:
        try:
            from components.config_dialog import handle_config_dialog
            _prev_music = app_config.get("useMusic", True)
            show_config = handle_config_dialog(app_config, config_path, gr, translator, version=ver, backup=config_dialog_backup, profile_dir=_profile_dir, active_profile=_active_profile, from_menu=_config_from_menu)
            audio.set_tts_music_mode(app_config.get("useTTSwithMusic", "lower"))
            if app_config.get("useMusic", True) != _prev_music:
                if app_config.get("useMusic", True):
                    import random
                    audio.play_music(random.choice(theme_music_tracks), loop=True)
                else:
                    audio.stop_music()
        except Exception as e:
            write_log(f"Config dialog error: {e}")
            show_config = False
        if not show_config:
            if _menu_was_open:
                show_menu = True
                _menu_was_open = False
                menu_mod.reset_menu_state()
        return

    if not show_log and not show_config and not show_menu:
        if input.key_held_for("MENUF", 1.0):
            _take_screenshot()
            return
        if input.key_released_short("MENUF", 1.0):
            show_menu = True
            menu_backup = gr.active_image.copy()
            menu_mod.reset_menu_state()
            return

    if show_menu:
        try:
            if show_log:
                pass  # log block handles background via log_backup
            else:
                from components.menu import handle_menu
                from components.updater import check_version, do_update
                from components.confirm_dialog import show_confirm
                profile_title = None
                if _active_profile:
                    plist = _get_profile_list()
                    for p in plist:
                        if p["filename"] == _active_profile:
                            profile_title = p["title"]
                            break
                action = handle_menu(gr, translator, current_window, version=ver, backup=menu_backup, active_profile_title=profile_title)
                if action == "config":
                    show_config = True
                    _config_from_menu = True
                    config_dialog_backup = gr.active_image.copy()
                    show_menu = False
                    _menu_was_open = True
                elif action == "welcome":
                    show_welcome = True
                    show_menu = False
                    menu_backup = None
                elif action == "log":
                    show_log = True
                    log_backup = gr.active_image.copy()
                    log_scroll_offset = 999999
                elif action == "clear_cache":
                    result = show_confirm(gr, translator,
                        translator.translate("Clear Cache"),
                        translator.translate("Really clear cache?"),
                        buttons=[
                            {"key": "yes", "label": translator.translate("Yes"), "key_trigger": "A"},
                            {"key": "no", "label": translator.translate("No"), "key_trigger": "B"},
                        ],
                        version=ver,
                    )
                    if result == "yes":
                        cache_base = os.path.join(script_dir, "cache")
                        for cd in [cache_dir, speak_dir, story_dir, history_dir]:
                            if os.path.exists(cd):
                                shutil.rmtree(cd)
                        for f in os.listdir(cache_base):
                            fp = os.path.join(cache_base, f)
                            if os.path.isfile(fp) and f.startswith("themes_current-"):
                                try:
                                    os.remove(fp)
                                except Exception:
                                    pass
                        try:
                            _safe_save_config({"debug": {"cacheClearForce": False}})
                        except Exception:
                            pass
                        show_confirm(gr, translator,
                            translator.translate("Clear Cache"),
                            translator.translate("Cache cleared"),
                            buttons=[{"key": "ok", "label": translator.translate("Ok"), "key_trigger": "A"}],
                            version=ver,
                        )
                        stop_tts()
                        _stop_music()
                        gr.draw_end()
                        _restart_app()
                    show_menu = False
                    menu_backup = None
                elif action == "update":
                    current_build = int(ver.split(".")[-1])
                    info = check_version(current_build, version=ver)
                    if info and (info.get("release_ver") or info.get("debug_ver")):
                        buttons = []
                        if info.get("release_ver"):
                            buttons.append({"key": "release", "label": translator.translate("Update release hint").format(ver=info["release_ver"]), "key_trigger": "A"})
                        if info.get("debug_ver"):
                            buttons.append({"key": "debug", "label": translator.translate("Update debug hint").format(ver=info["debug_ver"]), "key_trigger": "X"})
                        buttons.append({"key": "back", "label": translator.translate("Update back hint"), "key_trigger": "B"})
                        from components.menu import _last_update_label
                        upd_ver = info.get("release_ver") or info.get("debug_ver") or ""
                        _last_update_label = translator.translate("Update (new)").format(ver=upd_ver)
                        body_parts = []
                        if info.get("release_ver"):
                            body_parts.append(f"Release: {info['release_ver']}")
                        if info.get("debug_ver"):
                            body_parts.append(f"Debug: {info['debug_ver']}")
                        body = f"{ver} -> " + ", ".join(body_parts)
                        result = show_confirm(gr, translator,
                            translator.translate("Update version"),
                            body=body,
                            buttons=buttons,
                            version=ver,
                        )
                        if result in ("release", "debug"):
                            update_type = "Release" if result == "release" else "Debug"
                            url = info["release_url"] if result == "release" else info["debug_url"]
                            ok = do_update(url, script_dir, version=ver)
                            if ok:
                                done_body = f"{translator.translate('Update done restart')}\n{ver} -> {update_type}: v{upd_ver}"
                                show_confirm(gr, translator,
                                    translator.translate("Update"),
                                    done_body,
                                    buttons=[{"key": "restart", "label": "A:" + translator.translate("Restart App"), "key_trigger": "A"}],
                                    version=ver,
                                )
                                stop_tts()
                                _stop_music()
                                gr.draw_end()
                                _restart_app()
                            else:
                                show_confirm(gr, translator,
                                    translator.translate("Update failed"),
                                    buttons=[{"key": "ok", "label": translator.translate("Ok"), "key_trigger": "A"}],
                                    version=ver,
                                )
                        _last_update_label = None
                        if result is not None:
                            show_menu = False
                            menu_backup = None
                            input.reset_input()
                    else:
                        _last_update_label = translator.translate("Update (up to date)")
                        show_confirm(gr, translator,
                            translator.translate("Update"),
                            translator.translate("Update (up to date)"),
                            buttons=[{"key": "ok", "label": translator.translate("Ok"), "key_trigger": "A"}],
                            version=ver,
                        )
                        _last_update_label = None
                        show_menu = False
                        menu_backup = None
                        input.reset_input()
                elif action == "check_update":
                    start_background_check(
                        int(ver.split(".")[-1]),
                        lambda lbl: setattr(menu_mod, '_last_update_label',
                            translator.translate("Update (new)").format(ver=lbl.replace("Update (-> v", "").rstrip(")"))
                            if lbl.startswith("Update (-> v") else
                            translator.translate(lbl) if lbl in ("Update (up to date)",) else lbl),
                        lambda msg: write_log(msg),
                        lambda: time.sleep(0.5) or setattr(menu_mod, '_checking_update', False),
                        version=ver,
                    )
                elif action == "select_profile":
                    from components.menu import handle_profile_select
                    profiles = _get_profile_list()
                    _profile_dlg_backup = gr.active_image.copy()
                    result = handle_profile_select(gr, translator, profiles, _active_profile, version=ver)
                    if result == "__back__":
                        input.reset_input()
                    else:
                        from copy import deepcopy
                        config_before = deepcopy(app_config)
                        _activate_profile(result)
                        show_menu = False
                        menu_backup = None
                        input.reset_input()
                        # Check if profile changes ai{}, models{} or prompt keys
                        needs_new_themes = False
                        if result is not None:
                            pp = os.path.join(_profile_dir, result)
                            if os.path.isfile(pp):
                                try:
                                    with open(pp) as f:
                                        pd = json.load(f)
                                    reason = _profile_changes_config(pd, config_before)
                                    if reason:
                                        needs_new_themes = True
                                        write_log(f"Profile change: {reason} — new themes recommended")
                                except:
                                    pass
                        overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 210))
                        gr.active_image.paste(_profile_dlg_backup, (0, 0))
                        gr.active_image.paste(overlay, (0, 0), overlay)
                        box_w = 380
                        box_h = 100
                        bx = (gr.screen_width - box_w) // 2
                        by = (gr.screen_height - box_h) // 2
                        gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)
                        gr.draw_text((gr.screen_width // 2, by + 32), translator.translate("Profile loaded (new themes)" if needs_new_themes else "Profile loaded"), font=16, color=gr.colorAccent, anchor="mm")
                        if needs_new_themes:
                            gr.draw_text((bx + 14, by + box_h - 14), "B:" + translator.translate("Close"), font=14, color=gr.colorTextMuted, anchor="lm")
                            gr.draw_text((bx + box_w - 14, by + box_h - 14), "A:" + translator.translate("New Themes"), font=14, color=gr.colorAccent, anchor="rm")
                        else:
                            gr.draw_text((bx + box_w - 14, by + box_h - 14), "A:" + translator.translate("Close"), font=14, color=gr.colorAccent, anchor="rm")
                        gr.draw_paint()
                        while True:
                            input.check()
                            if needs_new_themes:
                                if input.key("A"):
                                    start_theme_generation()
                                    break
                                if input.key("B"):
                                    break
                            else:
                                if input.key("A"):
                                    break
                            gr.active_image.paste(_profile_dlg_backup, (0, 0))
                            gr.active_image.paste(overlay, (0, 0), overlay)
                            gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)
                            gr.draw_text((gr.screen_width // 2, by + 32), translator.translate("Profile loaded (new themes)" if needs_new_themes else "Profile loaded"), font=16, color=gr.colorAccent, anchor="mm")
                            if needs_new_themes:
                                gr.draw_text((bx + 14, by + box_h - 14), "B:" + translator.translate("Close"), font=14, color=gr.colorTextMuted, anchor="lm")
                                gr.draw_text((bx + box_w - 14, by + box_h - 14), "A:" + translator.translate("New Themes"), font=14, color=gr.colorAccent, anchor="rm")
                            else:
                                gr.draw_text((bx + box_w - 14, by + box_h - 14), "A:" + translator.translate("Close"), font=14, color=gr.colorAccent, anchor="rm")
                            gr.draw_paint()
                            time.sleep(0.05)
                elif action == "edit_config_online":
                    show_menu = False
                    menu_backup = None
                    input.reset_input()
                    existing_id = app_config.get("debug", {}).get("editOnlineId", "") or ""
                    upload_id, upload_url = None, None
                    upload_id, upload_url = online_config.upload_config(config_path, config_path.replace(".json", ".ai.json"), _profile_dir, log_path=log_file, screenshot_dir=_screenshot_dir, existing_id=existing_id)
                    if upload_id is None:
                        upload_url = upload_url or "Failed"
                        show_confirm(gr, translator,
                            translator.translate("Edit Config Online"),
                            translator.translate("Update failed"),
                            buttons=[{"key": "ok", "label": translator.translate("Ok"), "key_trigger": "A"}],
                            version=ver,
                        )
                    else:
                        app_config.setdefault("debug", {})["editOnlineId"] = upload_id
                        try:
                            _safe_save_config({"debug": {"editOnlineId": upload_id}})
                        except:
                            pass
                        result = online_config.show_dialog(gr, translator, upload_id, upload_url, version=ver, on_music_toggle=_toggle_music, on_tts_toggle=_toggle_dialog_tts)
                        if isinstance(result, tuple) and result[0] == "done":
                            preserved = result[1]
                            changed, _err = online_config.download_edited(upload_id)
                            if changed:
                                for fname, fdata in changed.items():
                                    if fname == "config.json":
                                        try:
                                            fdata.pop("ai", None)
                                            fdata.pop("models", None)
                                            with open(config_path, "w") as f:
                                                json.dump(fdata, f, indent=4)
                                            write_log("Downloaded config.json from online editor")
                                        except Exception as e:
                                            write_log(f"Failed to save {fname}: {e}")
                                    elif fname == "config.json.default":
                                        try:
                                            with open(config_path + ".default", "w") as f:
                                                json.dump(fdata, f, indent=4)
                                        except Exception:
                                            pass
                                    elif fname == "config.ai.json":
                                        try:
                                            with open(config_path.replace(".json", ".ai.json"), "w") as f:
                                                json.dump(fdata, f, indent=4)
                                        except Exception as e:
                                            write_log(f"Failed to save {fname}: {e}")
                                    elif fname == "config.ai.json.default":
                                        try:
                                            with open(config_path.replace(".json", ".ai.json") + ".default", "w") as f:
                                                json.dump(fdata, f, indent=4)
                                        except Exception:
                                            pass
                                if "profiles" in changed:
                                    os.makedirs(_profile_dir, exist_ok=True)
                                    for pfn, pdata in changed["profiles"].items():
                                        try:
                                            with open(os.path.join(_profile_dir, pfn), "w") as f:
                                                json.dump(pdata, f, indent=4)
                                        except Exception as e:
                                            write_log(f"Failed to save profile {pfn}: {e}")
                                if "delete_profiles" in changed:
                                    for dfn in changed["delete_profiles"]:
                                        dp = os.path.join(_profile_dir, dfn)
                                        if os.path.exists(dp):
                                            try:
                                                os.remove(dp)
                                                write_log(f"Deleted profile: {dfn}")
                                            except Exception as e:
                                                write_log(f"Failed to delete profile {dfn}: {e}")
                                if "delete_screenshots" in changed:
                                    for sfn in changed["delete_screenshots"]:
                                        sp = os.path.join(_screenshot_dir, sfn)
                                        if os.path.exists(sp):
                                            try:
                                                os.remove(sp)
                                                write_log(f"Deleted screenshot: {sfn}")
                                            except Exception as e:
                                                write_log(f"Failed to delete screenshot {sfn}: {e}")
                            _reload_config(allow_quit=False)
                            # Restore editOnlineId — _reload_config overwrote it from downloaded config
                            app_config.setdefault("debug", {})["editOnlineId"] = upload_id
                            # Done dialog with X:Preserve ID
                            _backup = gr.active_image.copy()
                            input.reset_input()
                            while True:
                                input.check()
                                if input.key("A") or input.key("B") or (input.key("X") and not preserved):
                                    try:
                                        _safe_save_config({"debug": {"editOnlineId": ""}})
                                    except:
                                        pass
                                    break
                                if input.key("X") and preserved:
                                    try:
                                        _safe_save_config({"debug": {"editOnlineId": upload_id}})
                                    except:
                                        pass
                                    break
                                gr.active_image.paste(_backup, (0, 0))
                                overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 180))
                                gr.active_image.paste(overlay, (0, 0), overlay)
                                box_w = 400
                                box_h = 100
                                bx = (gr.screen_width - box_w) // 2
                                by = (gr.screen_height - box_h) // 2
                                gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)
                                gr.draw_text((gr.screen_width // 2, by + 30), translator.translate("Config and Profiles updated"), font=18, color=gr.colorAccent, anchor="mm")
                                if preserved:
                                    gr.draw_text((bx + 14, by + box_h - 14), "X:" + translator.translate("Preserve ID"), font=14, color=gr.colorAccent, anchor="lm")
                                gr.draw_text((bx + box_w - 14, by + box_h - 14), "A:" + translator.translate("Ok"), font=14, color=gr.colorAccent, anchor="rm")
                                gr.draw_paint()
                                time.sleep(0.05)
                        elif result is None:
                            try:
                                _safe_save_config({"debug": {"editOnlineId": ""}})
                            except:
                                pass
                        elif result == "cancelled":
                            try:
                                _safe_save_config({"debug": {"editOnlineId": ""}})
                            except:
                                pass
                        # "preserved" — keep ID, do nothing
                elif action == "reload_config":
                    _reload_config(allow_quit=False)
                    show_menu = False
                    menu_backup = None
                    input.reset_input()
                elif action == "restart":
                    gr.draw_background()
                    gr.draw_paint()
                    stop_tts()
                    _stop_music()
                    gr.draw_end()
                    _restart_app()
                elif action == "exit":
                    gr.draw_background()
                    gr.draw_paint()
                    stop_tts()
                    _stop_music()
                    gr.draw_end()
                    sys.exit()
                elif action == "__close__":
                    show_menu = False
                    menu_backup = None
                elif action is None:
                    pass  # keep menu open
        except Exception:
            import traceback
            write_log("Menu error:\n" + traceback.format_exc())
            show_menu = False
            menu_backup = None
        if not show_log:
            return

    if show_welcome:
        show_welcome = False
        current_window = "welcome"

    if show_log:
        gr._paint_blocked = True

    if input.key("Y") and not show_log:
        _toggle_music()

    if not show_log and not show_menu:
        if current_window == "welcome":
            handle_welcome()
        elif current_window == "boot":
            handle_boot()
        elif current_window == "theme_gen":
            handle_theme_gen()
        elif current_window == "theme_select":
            handle_theme_select()
        elif current_window == "theme_detail":
            handle_theme_detail()
        elif current_window == "story_gen":
            handle_story_gen()
        elif current_window == "story_show":
            handle_story_show()
        elif current_window == "story_loading":
            handle_story_loading()
        elif current_window == "decision":
            handle_decision()
        elif current_window == "error":
            handle_error()

    if show_log:
        try:
            if input.key("X"):
                open(log_file, "w").close()
                log_backup = None
                input.reset_input()
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
            total = len(lines)
            max_offset = max(0, total - 21)
            if log_scroll_offset > max_offset:
                log_scroll_offset = max_offset
            if input.key("DY") and input.value != 0:
                log_scroll_offset = max(0, log_scroll_offset + input.value)
            elif input.key("DX"):
                log_scroll_offset = max(0, log_scroll_offset + input.value * 10)
            if log_backup:
                gr.active_image.paste(log_backup, (0, 0))
            gr.draw_log_overlay(lines, scroll_offset=log_scroll_offset, close_text="B/SEL:" + translator.translate("Back"), clear_text="X:" + translator.translate("Clear"))
            gr._paint_blocked = False
            gr.draw_paint()
        except Exception:
            gr._paint_blocked = False


def handle_boot():
    global current_window, _boot_auto_started
    auto_start = app_config.get("debug", {}).get("seenIntro", False)
    if auto_start and not _boot_auto_started:
        _boot_auto_started = True
        gr.draw_boot_screen(
            title=translator.translate("Story Weaver"),
            subtitle=translator.translate("An AI Adventure Game"),
            prompt="",
            version=ver,
        )
        gr.draw_paint()
        time.sleep(2)
        if not app_config.get("seenWelcomescreen", False):
            current_window = "welcome"
            input.reset_input()
        else:
            _reload_config()
            start_theme_generation()
        return
    if input.key("START"):
        _boot_auto_started = True
        if not app_config.get("seenWelcomescreen", False):
            current_window = "welcome"
            input.reset_input()
        else:
            _reload_config()
            start_theme_generation()
        return
    gr.draw_boot_screen(
        title=translator.translate("Story Weaver"),
        subtitle=translator.translate("An AI Adventure Game"),
        prompt=translator.translate("Press START to start"),
        version=ver,
    )
    gr.draw_paint()


def handle_welcome():
    global current_window, _welcome_scroll_offset
    if input.key("A") or input.key("START"):
        try:
            _safe_save_config({"seenWelcomescreen": True})
        except Exception as e:
            write_log(f"Failed to save config: {e}")
        start_theme_generation()
        return

    sections = [
        translator.translate("Welcome - 1"),
        translator.translate("Welcome - 2"),
        translator.translate("Welcome - 3"),
        translator.translate("Welcome - 4"),
        translator.translate("Welcome - 5"),
        translator.translate("Welcome - 6"),
        translator.translate("Welcome - 8"),
        translator.translate("Welcome - 7"),
    ]

    # Pre-wrap all text
    all_lines = []
    for sec in sections:
        wrapped = gr._wrap_text(sec, font=gr.font_size_text, max_width=gr.screen_width - 70)
        all_lines.extend(wrapped)
        all_lines.append(None)  # section separator

    line_h = gr.font_size_text + 10
    sec_gap = gr.font_size_text + 3
    total_h = 0
    for i, line in enumerate(all_lines):
        total_h += line_h if line is not None else sec_gap

    y_start = 75
    avail_h = gr.screen_height - 18 - y_start - 10

    if input.key("DY") and input.value != 0:
        max_scroll = max(0, int((total_h - avail_h) // line_h) + 1)
        _welcome_scroll_offset = max(0, min(_welcome_scroll_offset + input.value, max_scroll))

    gr.draw_background()
    overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 210))
    gr.active_image.paste(overlay, (0, 0), overlay)
    gr.draw_text((gr.screen_width // 2, 30), translator.translate("Welcome - Title"), font=24, color=gr.colorAccent, anchor="mm")

    y = y_start
    drawn = 0
    total_lines = len(all_lines)
    start_idx = 0
    # Skip lines that are above scroll offset
    if _welcome_scroll_offset > 0 and total_lines:
        acc = 0
        for idx, line in enumerate(all_lines):
            h = line_h if line is not None else sec_gap
            if acc + h > _welcome_scroll_offset * line_h:
                start_idx = idx
                y = y_start - (acc + h - _welcome_scroll_offset * line_h)
                break
            acc += h
        else:
            start_idx = total_lines

    for i in range(start_idx, total_lines):
        line = all_lines[i]
        if line is None:
            y += sec_gap
        else:
            if y + line_h > gr.screen_height - 28:
                break
            gr.draw_text((35, y), line, font=gr.font_size_text, color=gr.colorText, anchor="la")
            y += line_h

    if total_h > avail_h:
        bar_x = gr.screen_width - 14
        bar_y = y_start
        bar_h = avail_h
        pct = _welcome_scroll_offset * line_h / max(1, total_h - avail_h)
        pct = min(1, pct)
        thumb_h = max(8, int(bar_h * avail_h / total_h))
        thumb_y = bar_y + int((bar_h - thumb_h) * pct)
        gr.draw_rectangle_r([bar_x - 4, bar_y, bar_x, bar_y + bar_h], 2, fill=gr.colorBg2)
        gr.draw_rectangle_r([bar_x - 4, thumb_y, bar_x, thumb_y + thumb_h], 2, fill=gr.colorAccent)

    gr.draw_text((gr.screen_width // 2, gr.screen_height - 18), translator.translate("Welcome - Press START"), font=16, color=gr.colorAccent, anchor="mm")
    gr.draw_paint()


def start_theme_generation():
    global current_window, api_thread, _theme_retries
    _theme_retries = 0
    current_window = "theme_gen"
    gr.draw_loading(translator.translate("Generating themes"), please_wait_text=translator.translate("Please wait"), dots=dot_count, version=ver)
    gr.draw_paint()
    api_thread = threading.Thread(target=_generate_themes_thread)
    api_thread.start()


def _generate_themes_thread():
    global themes, api_error, api_result, _cachebuster
    import socket
    test_servers = [("8.8.8.8", 53), ("1.1.1.1", 53)]
    connected = False
    for host, port in test_servers:
        try:
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            connected = True
            break
        except (socket.timeout, socket.error):
            continue
    if not connected:
        msg = translator.translate("No internet")
        write_log(f"No internet connection detected")
        api_error = msg
        return
    write_log("Internet OK, starting theme generation")
    model_name = app_config.get("models", {}).get("story", "?")
    try:
        if _cachebuster is None:
            _cachebuster = str(int(time.time() * 1000000))
        _save_cachebuster_to_config(_cachebuster)
        write_log(f"Requesting theme generation (model={model_name}, cachebuster={_cachebuster})")
        result = api.generate_themes(language, cachebuster_value=_cachebuster)
        api_result = result
        api_error = None
        write_log(f"Theme generation returned {len(result)} themes (model={model_name})")
    except Exception as e:
        api_error = str(e)
        api_result = None
        write_log(f"Theme generation failed (model={model_name}): {api_error}")


def handle_theme_gen():
    global current_window, themes, api_result, api_error, api_thread

    if input.key("B"):
        stop_tts()
        current_window = "boot"
        skip_input_check = True
        write_log("Theme generation cancelled by user")
        return

    if api_thread and api_thread.is_alive():
        gr.draw_loading(translator.translate("Generating themes"), please_wait_text=translator.translate("Please wait"), dots=dot_count, version=ver)
        gr.draw_paint()
        time.sleep(0.05)
        return

    if api_error:
        write_log(f"Theme generation error: {api_error}")
        set_error(f"{translator.translate('Theme loading failed')}: {api_error}")
        return

    themes = api_result or []
    if not themes:
        global _theme_retries, _cachebuster
        _theme_retries += 1
        if _theme_retries < 3:
            _cachebuster = str(int(time.time() * 1000000))
            _save_cachebuster_to_config(_cachebuster)
            write_log(f"Theme generation empty (retry {_theme_retries}/3), new cachebuster={_cachebuster}")
            api_result = None
            api_error = None
            api_thread = threading.Thread(target=_generate_themes_thread)
            api_thread.start()
            return
        write_log(f"Theme generation empty after {_theme_retries} retries, giving up")
        _theme_retries = 0
        msg = translator.translate("Theme loading failed")
        fr = api._last_finish_reason
        if fr:
            msg += f" (Grund: {fr})"
        if fr == "length" and api.theme_max_tokens is not None:
            tt = api._last_usage.get("total_tokens", 0)
            msg += f"\nTokens {api.theme_max_tokens}/{tt}"
        set_error(msg)
        return

    _theme_retries = 0
    _generate_thumbnails()


def _match_favorites_to_themes():
    global themes
    if not themes or not favorites:
        return
    for theme in themes:
        cap = theme.get("caption", "")
        for fav_hash, fav_data in favorites.items():
            if cap and cap == fav_data.get("caption", ""):
                old_hash = theme.get("hash", "")
                if old_hash != fav_hash:
                    write_log(f"Hash mismatch for '{cap}': theme={old_hash} fav={fav_hash}")
                break

def _generate_thumbnails():
    global thumbnails, current_window, selected_index, theme_scroll_offset, api_thread, api_result
    from concurrent.futures import ThreadPoolExecutor, as_completed
    model_name = app_config.get("models", {}).get("image", "?")
    thumbnails = {}
    current_window = "theme_gen"

    _match_favorites_to_themes()

    existing_hashes = {t["hash"] for t in themes}
    for fav_hash, fav_data in favorites.items():
        if fav_hash not in existing_hashes:
            themes.append({
                "id": "fav_" + fav_hash,
                "caption": fav_data.get("caption", ""),
                "description": fav_data.get("description", ""),
                "image_prompt": fav_data.get("image", {}).get("prompt", ""),
                "hash": fav_hash,
            })
            existing_hashes.add(fav_hash)
            write_log(f"Appended favorite: '{fav_data.get('caption')}' ({fav_hash})")

    cols = 2
    rows = 3
    card_w = (gr.screen_width - 40) // cols
    card_h = (gr.screen_height - 120) // rows
    thumb_w = card_w - 8
    thumb_h = card_h - 70

    def fetch_one(idx, theme):
        try:
            thumb_path = os.path.join(cache_dir, f"{theme['hash']}_theme.png")
            large_path = os.path.join(cache_dir, f"{theme['hash']}_theme_large.png")
            if os.path.exists(thumb_path) and os.path.exists(large_path):
                write_log(f"Theme {idx+1} thumbnail cache hit: {theme['caption']}")
                return idx, theme, "thumb_done", None
            if os.path.exists(large_path):
                write_log(f"Theme {idx+1} _large cache hit: {theme['caption']}")
                return idx, theme, "large", None
            if os.path.exists(thumb_path):
                write_log(f"Theme {idx+1} migrating old _theme.png: {theme['caption']}")
                return idx, theme, "migrate", None
            write_log(f"Theme {idx+1} cache miss, fetching: {theme['caption']}")
            img_data = api.fetch_image(theme["image_prompt"], width=1495, height=256, label="Theme")
            return idx, theme, "api", img_data
        except Exception as e:
            write_log(f"Theme {idx+1} fetch failed: {e}")
            return idx, theme, "failed", None

    total = len(themes)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_one, i, t) for i, t in enumerate(themes)]
        done = 0
        for future in as_completed(futures):
            done += 1
            input.check()
            if input.key("MENUF") or input.key("B"):
                break
            gr.draw_loading(f"{translator.translate('Generating image')} {done}/{total}", please_wait_text=translator.translate("Please wait"), dots=dot_count, version=ver)
            gr.draw_paint()
            idx, theme, status, img_data = future.result()

            if status == "thumb_done":
                thumb_path = os.path.join(cache_dir, f"{theme['hash']}_theme.png")
                thumbnails[idx] = Image.open(thumb_path).convert("RGBA")
                write_log(f"Theme thumbnail {idx+1}/{total} loaded from disk (model={model_name})")
                continue

            if status == "failed" or (img_data is None and status not in ("migrate", "large")):
                write_log(f"Theme {idx+1} image fetch failed for {theme['caption']} (model={model_name})")
                continue

            try:
                if status == "migrate":
                    old_path = os.path.join(cache_dir, f"{theme['hash']}_theme.png")
                    large_path = os.path.join(cache_dir, f"{theme['hash']}_theme_large.png")
                    os.rename(old_path, large_path)
                    source_path = large_path
                    write_log(f"Theme {idx+1} migrated _theme.png to _theme_large.png")
                elif status == "large":
                    source_path = os.path.join(cache_dir, f"{theme['hash']}_theme_large.png")
                else:
                    source_path = api.cache_image(img_data, f"{theme['hash']}_theme_large", cache_dir)

                if not source_path:
                    continue

                img = Image.open(source_path).convert("RGBA")
                img.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
                canvas = Image.new("RGBA", (thumb_w, thumb_h), (0, 0, 0, 0))
                ox = (thumb_w - img.width) // 2
                oy = (thumb_h - img.height) // 2
                canvas.paste(img, (ox, oy), img)
                thumbnails[idx] = canvas

                thumb_path = os.path.join(cache_dir, f"{theme['hash']}_theme.png")
                canvas.save(thumb_path, "PNG")
                write_log(f"Theme thumbnail {idx+1}/{total} {'generated' if status == 'api' else 'regenerated'} (model={model_name})")

                header_cache_path = os.path.join(cache_dir, f"{theme['hash']}_description.png")
                if os.path.exists(header_cache_path):
                    write_log(f"Theme header {idx+1} cache hit")
                else:
                    write_log(f"Theme header {idx+1} cache miss, generating")
                    header_img = Image.open(source_path).convert("RGBA")
                    header_w = 720
                    h_ratio = header_w / header_img.width
                    header_h = int(header_img.height * h_ratio)
                    header_img = header_img.resize((header_w, header_h), Image.LANCZOS)
                    header_img.save(header_cache_path)
                    write_log(f"Theme header {idx+1} cached at {header_w}x{header_h}")
            except Exception as e:
                write_log(f"Theme {idx+1} processing failed: {e}")

    try:
        batch_path = os.path.join(script_dir, "cache", f"themes_current-{_cachebuster}.json")
        with open(batch_path, "w") as f:
            json.dump({"freezeThemes": _cachebuster, "hashes": [t["hash"] for t in themes if t.get("hash")]}, f, indent=2)
    except Exception as e:
        write_log(f"Failed to save themes_current list: {e}")

    selected_index = 0
    theme_scroll_offset = 0
    _stop_music()
    api_thread = None
    api_result = None
    if app_config.get("useMusic", True):
        _play_music(random.choice(theme_music_tracks), loop=True)
    _rumble()
    current_window = "theme_select"
    skip_input_check = True


def handle_theme_select():
    global selected_index, current_window, selected_theme, story_history, story_steps, story_step, theme_scroll_offset, favorites, _fav_toggle_redraw, current_story, api_thread, api_result

    if not themes:
        set_error(translator.translate("Theme loading failed"))
        return

    cols = 2
    max_visible = 6

    if input.key("DX"):
        i = selected_index - theme_scroll_offset
        col = i % cols
        new_col = col + input.value
        if 0 <= new_col < cols:
            row = i // cols
            new_i = row * cols + new_col
            new_idx = theme_scroll_offset + new_i
            if new_idx < len(themes):
                selected_index = new_idx
    elif input.key("DY") and input.value != 0:
        if input.value > 0:
            pos = selected_index - theme_scroll_offset
            col = pos % cols
            row = pos // cols
            new_idx = theme_scroll_offset + (row + 1) * cols + col
            if new_idx >= len(themes):
                new_idx = theme_scroll_offset + (row + 1) * cols
            if new_idx < len(themes):
                selected_index = new_idx
        else:
            new_idx = selected_index - cols
            if new_idx >= 0:
                selected_index = new_idx
    elif input.key("L1"):
        selected_index = 0
    elif input.key("R1"):
        selected_index = len(themes) - 1
    elif input.key("L2"):
        selected_index = max(0, selected_index - 6)
    elif input.key("R2"):
        selected_index = min(len(themes) - 1, selected_index + 6)

    if selected_index < theme_scroll_offset:
        theme_scroll_offset = selected_index
    elif selected_index >= theme_scroll_offset + max_visible:
        theme_scroll_offset = selected_index - max_visible + 1

    theme_scroll_offset = (theme_scroll_offset // cols) * cols
    if selected_index >= theme_scroll_offset + max_visible:
        theme_scroll_offset += cols

    if input.key("X"):
        theme = themes[selected_index]
        h = theme["hash"]
        if h in favorites:
            del favorites[h]
            write_log(f"Removed favorite: {theme['caption']} ({h})")
        else:
            cache_relative = "cache/imgs/" + h + "_theme.png"
            cache_path = os.path.join(cache_dir, f"{h}_theme.png")
            favorites[h] = {
                "caption": theme["caption"],
                "description": theme["description"],
                "image": {
                    "prompt": theme["image_prompt"],
                    "hash": h,
                    "url": _build_image_url(theme["image_prompt"]),

                    "cache": cache_relative if os.path.exists(cache_path) else "",
                },
            }
            write_log(f"Added favorite: {theme['caption']} ({h})")
        _save_favorites()
    if not os.listdir(cache_dir):
        write_log   ("No cache files to clean")
    if _fav_toggle_redraw:
        _fav_toggle_redraw = False
        return

    if input.key("SELECT") and not show_log:
        global _cachebuster
        _cachebuster = str(int(time.time() * 1000000))
        _save_cachebuster_to_config(_cachebuster)
        write_log(f"Manual refresh: cachebuster={_cachebuster}")
        start_theme_generation()
        return

    elif input.key("A"):
        selected_theme = themes[selected_index]
        current_window = "theme_detail"
        skip_input_check = True
        return

    elif input.key("START"):
        global _theme_select_index
        _theme_select_index = selected_index
        selected_theme = themes[selected_index]
        story_history = [
            {"role": "system", "content": api.story_system_prompt},
            {"role": "system", "content": f"The adventure begins in {selected_theme['caption']}: {selected_theme['description']}"},
            {"role": "user", "content": api.format_story_prompt(language)}
        ]
        story_steps = []
        story_step = 0
        api.set_dump_prefix(selected_theme['hash'])
        api_thread = None
        api_result = None
        if _load_history() and story_steps and story_history:
            last_asst_idx = None
            for i in range(len(story_history) - 1, -1, -1):
                if story_history[i]["role"] == "assistant":
                    last_asst_idx = i
                    break
            if last_asst_idx is not None:
                story_history = story_history[:last_asst_idx + 1]
                current_story = api._parse_story_xml(story_history[-1]["content"])
                current_story["raw_content"] = story_history[-1]["content"]
                _save_history()
                if _ensure_story_image(_show_story_from_history):
                    return
                _show_story_from_history()
                return
        current_window = "story_gen"
        skip_input_check = True
        _start_story_generation()
        return


    steps_map = {}
    for theme in themes:
        h = theme.get("hash", "")
        if h:
            hp = os.path.join(history_dir, f"{h}_history.json")
            if os.path.exists(hp):
                try:
                    with open(hp) as f:
                        d = json.load(f)
                    s = d.get("step", 0)
                    steps = d.get("steps", [])
                    if s == 0 and steps:
                        s = 1
                    if s > 0:
                            steps_map[h] = s
                except Exception:
                    pass

    gr.draw_theme_selection(
        themes, selected_index, theme_scroll_offset, thumbnails,
        title_text=translator.translate("Choose Your Adventure"),
        sel_text=translator.translate("SEL:Regenerate"),
        scroll_text=translator.translate("DY:Scroll"),
        exit_text=translator.translate("A:Details"),
        favorites=favorites,
        version=ver,
        steps_map=steps_map,
    )
    _upd = new_release_version()
    if _upd and int(time.time()) % 2 == 0:
        gr.draw_text((13, 13), f"Update -> v{_upd}", font=14, color=gr.colorAccent, anchor="lt")
    gr.draw_paint()


def handle_theme_detail():
    global current_window, selected_theme, story_history, story_steps, story_step, skip_input_check, detail_backup, detail_painted, favorites, tts_active, tts_paused, tts_loading, tts_done, _fav_toggle_redraw, current_story, api_thread, api_result, _theme_detail_scroll_offset, _tts_step

    if input.key("DY") and input.value != 0:
        _theme_detail_scroll_offset = max(0, _theme_detail_scroll_offset + input.value)
        detail_painted = False

    if input.key("JOYSTICK"):
        current_step = story_step
        if _tts_step != current_step:
            stop_tts()
            _start_tts(text=selected_theme["description"], hash_str=selected_theme["hash"], prefix="description", force=True)
        elif tts_paused:
            resume_tts()
        elif tts_active:
            pause_tts()
        elif tts_done:
            stop_tts()
            _start_tts(text=selected_theme["description"], hash_str=selected_theme["hash"], prefix="description", force=True)
        elif tts_loading:
            pass
        else:
            _start_tts(text=selected_theme["description"], hash_str=selected_theme["hash"], prefix="description", force=True)

    if input.key("A") or input.key("START"):
        global _theme_select_index
        _theme_select_index = themes.index(selected_theme)
        stop_tts()
        detail_backup = None
        detail_painted = False
        story_history = [
            {"role": "system", "content": api.story_system_prompt},
            {"role": "system", "content": f"The adventure begins in {selected_theme['caption']}: {selected_theme['description']}"},
            {"role": "user", "content": api.format_story_prompt(language)}
        ]
        story_steps = []
        story_step = 0
        api.set_dump_prefix(selected_theme['hash'])
        api_thread = None
        api_result = None
        if _load_history() and story_steps and story_history:
            last_asst_idx = None
            for i in range(len(story_history) - 1, -1, -1):
                if story_history[i]["role"] == "assistant":
                    last_asst_idx = i
                    break
            if last_asst_idx is not None:
                story_history = story_history[:last_asst_idx + 1]
                current_story = api._parse_story_xml(story_history[-1]["content"])
                current_story["raw_content"] = story_history[-1]["content"]
                _save_history()
                if _ensure_story_image(_show_story_from_history):
                    return
                _show_story_from_history()
                return
        current_window = "story_gen"
        skip_input_check = True
        _start_story_generation()
        return
    elif input.key("B"):
        stop_tts()
        detail_backup = None
        detail_painted = False
        _theme_detail_scroll_offset = 0
        _welcome_scroll_offset = 0
        current_window = "theme_select"
        skip_input_check = True
        return

    if input.key("X"):
        h = selected_theme["hash"]
        if h in favorites:
            del favorites[h]
            write_log(f"Removed favorite: {selected_theme['caption']} ({h})")
        else:
            cache_relative = "cache/imgs/" + h + "_theme.png"
            cache_path = os.path.join(cache_dir, f"{h}_theme.png")
            favorites[h] = {
                "caption": selected_theme["caption"],
                "description": selected_theme["description"],
                "image": {
                    "prompt": selected_theme["image_prompt"],
                    "hash": h,
                    "url": _build_image_url(selected_theme["image_prompt"]),
                    "cache": cache_relative if os.path.exists(cache_path) else "",
                }
            }
            write_log(f"Added favorite: {selected_theme['caption']} ({h})")
        _save_favorites()
        detail_painted = False
        _fav_toggle_redraw = True
        return

    is_fav = selected_theme["hash"] in favorites
    fav_text = translator.translate("X:Unfav") if is_fav else translator.translate("X:Fav")

    step_count = 0
    hpath = os.path.join(history_dir, f"{selected_theme['hash']}_history.json")
    if os.path.exists(hpath):
        try:
            with open(hpath) as f:
                d = json.load(f)
                step_count = d.get("step", 0)
                if step_count == 0 and d.get("steps", []):
                    step_count = 1
        except Exception:
            pass

    if not detail_painted or detail_backup is None:
        if detail_backup is None:
            detail_backup = gr.active_image.copy()
            if not _fav_toggle_redraw:
                _start_tts(text=selected_theme["description"], hash_str=selected_theme["hash"], prefix="description")
        header_path = None
        if selected_theme and selected_theme.get("hash"):
            cache_path = os.path.join(cache_dir, f"{selected_theme['hash']}_description.png")
            if os.path.exists(cache_path):
                header_path = cache_path
        gr.active_image.paste(detail_backup, (0, 0))
        _theme_detail_scroll_offset = gr.draw_theme_detail(
            selected_theme,
            header_path,
            start_text=fav_text,
            back_text=translator.translate("B:Back"),
            direct_hint=translator.translate("SEL:Direct"),
            fav_text=translator.translate("A:Start"),
            is_fav=is_fav,
            desc_scroll_offset=_theme_detail_scroll_offset,
            step_count=step_count,
        )
        gr.draw_text((gr.screen_width - 10, gr.screen_height - 10), f"ID: {selected_theme['hash']}", font=11, color="#555", anchor="rb")
        gr.draw_tts_indicator(loading=tts_loading, active=tts_active, paused=tts_paused, done=tts_done)
        detail_painted = True
        if _fav_toggle_redraw:
            _fav_toggle_redraw = False

    gr.draw_tts_indicator(loading=tts_loading, active=tts_active, paused=tts_paused, done=tts_done)
    gr.draw_paint()


def _start_story_generation():
    global api_thread
    write_log("Starting story generation")
    api_thread = threading.Thread(target=_generate_story_thread)
    api_thread.start()


def _generate_story_thread():
    global current_story, api_error, api_result, error_raw_response
    model_name = app_config.get("models", {}).get("story", "?")
    try:
        _check_compact_history()
        write_log(f"Requesting story generation (model={model_name})")
        result = api.generate_story(story_history)
        api_result = result
        api_error = None
        write_log(f"Story generation completed (model={model_name})")
    except Exception as e:
        api_error = str(e)
        api_result = None
        error_raw_response = getattr(api, '_last_raw_response', '')
        write_log(f"Story generation failed (model={model_name}): {api_error}")


def handle_story_gen():
    global current_window, skip_input_check

    if input.key("B"):
        stop_tts()
        current_window = "boot"
        skip_input_check = True
        write_log("Story generation cancelled by user")
        return

    if _process_story_result():
        return

    if api_thread and api_thread.is_alive():
        gr.draw_loading(translator.translate("Weaving tale"), please_wait_text=translator.translate("Please wait"), dots=dot_count, version=ver)
        gr.draw_paint()
        time.sleep(0.05)
        return


def _show_story():
    global story_scroll_offset, current_window, skip_input_check, story_step
    story_scroll_offset = 0
    current_window = "story_show"
    skip_input_check = True
    story_step += 1
    story_text = current_story.get("text", "")
    if story_text and selected_theme:
        story_path = os.path.join(story_dir, f"{selected_theme['hash']}_story_{story_step}.txt")
        with open(story_path, "w", encoding="utf-8") as sf:
            sf.write(story_text)
        write_log(f"Saved story text to {story_path}")
    _play_cached_tts()



def _process_story_result():
    global current_story, api_result, api_error, story_history, story_steps, api_thread

    if api_thread is None:
        return False

    if api_thread.is_alive():
        return False

    api_thread = None

    if api_error:
        write_log(f"Story generation error: {api_error}")
        set_error(f"{translator.translate('Story loading failed')}: {api_error}", raw_response=error_raw_response)
        api_error = None
        api_result = None
        return True

    current_story = api_result
    api_result = None
    if not current_story or not current_story.get("text"):
        write_log("Story generation returned empty result")
        msg = translator.translate("Story loading failed")
        fr = api._last_finish_reason
        if fr:
            msg += f" (Grund: {fr})"
        if fr == "length" and api.story_max_tokens is not None:
            tt = api._last_usage.get("total_tokens", 0)
            msg += f"\nTokens {api.story_max_tokens}/{tt}"
        set_error(msg)
        return True

    write_log("Story generated successfully")
    write_log(f"Story image_prompt: '{current_story.get('image_prompt', '')}' hash: '{current_story.get('hash', '')}'")

    story_text = current_story.get("text", "")
    raw_content = current_story.get("raw_content", story_text)
    if story_text:
        story_history.append({
            "role": "assistant",
            "content": raw_content,
        })
        story_steps.append({
            "header_image": f"{selected_theme['hash']}_story_{story_step + 1}.png",
            "response": story_text,
        })
        _save_history(step=story_step + 1)

    _start_tts(start_playback=False)

    if app_config.get("useStoryImages", True):
        if current_story.get("image_prompt") and current_story.get("hash"):
            _start_image_generation()
        elif story_step == 0 and selected_theme and selected_theme.get("image_prompt"):
            write_log("First story step has no image_prompt, using theme image_prompt as fallback")
            current_story["image_prompt"] = selected_theme["image_prompt"]
            current_story["hash"] = selected_theme["hash"]
            _start_image_generation()
        else:
            _show_story()
    else:
        write_log("Story images disabled, skipping image generation")
        _show_story()

    return True


def _fetch_image_thread(image_prompt, cache_hash, cache_step):
    global _image_done
    model_name = app_config.get("models", {}).get("image", "?")
    img_data = None
    for attempt in range(5):
        write_log(f"Fetching scene image attempt {attempt+1}/5 (model={model_name})")
        img_data = api.fetch_image(image_prompt, width=1116, height=256, cache_dir=cache_dir, label="Scene")
        if img_data:
            break
        write_log(f"Scene image fetch attempt {attempt+1} failed, retrying in 200ms")
        time.sleep(0.2)
    if img_data:
        api.cache_image(img_data, f"{cache_hash}_story_{cache_step}_large", cache_dir)
        write_log("Full-size scene image cached as _large")
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(img_data))
            img = img.resize((680, 156), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_data = buf.getvalue()
            write_log("Story thumbnail resized to 680x156")
        except Exception as e:
            write_log(f"Story thumbnail resize failed: {e}")
        api.cache_image(img_data, f"{cache_hash}_story_{cache_step}", cache_dir)
        write_log(f"Scene image cached (model={model_name})")
    else:
        write_log(f"Scene image fetch failed after 5 attempts (model={model_name})")
    _image_done = True


def _show_story_from_history():
    global current_window, selected_index, skip_input_check
    current_window = "story_show"
    selected_index = 0
    skip_input_check = True
    _start_tts()


def _ensure_story_image(callback):
    global current_window, _image_thread, _image_done, _image_callback
    if not app_config.get("useStoryImages", True):
        return False
    if not current_story or not current_story.get("image_prompt"):
        return False
    img_path = api.get_cached_path(f"{selected_theme['hash']}_story_{story_step}", cache_dir)
    if img_path:
        return False
    _image_done = False
    _image_callback = callback
    _image_thread = threading.Thread(
        target=_fetch_image_thread,
        args=(current_story["image_prompt"], selected_theme["hash"], story_step)
    )
    _image_thread.start()
    current_window = "story_loading"
    return True


def _start_image_generation():
    global current_window, _image_thread, _image_done, _image_callback
    if not current_story or not current_story.get("image_prompt"):
        _show_story()
        return
    _image_done = False
    _image_callback = _show_story
    _image_thread = threading.Thread(
        target=_fetch_image_thread,
        args=(current_story["image_prompt"], selected_theme["hash"], story_step + 1)
    )
    _image_thread.start()
    current_window = "story_loading"


def handle_story_loading():
    global current_window, _image_thread, _image_done, _image_callback
    skip_hint = translator.translate("B:don't wait")
    if input.key("B"):
        _image_callback = None
        _image_thread = None
        _image_done = False
        _show_story()
        return
    if _image_thread and not _image_done:
        gr.draw_loading(translator.translate("Generating image"), please_wait_text=translator.translate("Please wait"), dots=dot_count, version=ver, hint=skip_hint)
        gr.draw_paint()
        time.sleep(0.05)
        return
    if _image_done:
        cb = _image_callback
        _image_thread = None
        _image_done = False
        _image_callback = None
        if cb:
            cb()
        return
    gr.draw_loading(translator.translate("Generating image"), please_wait_text=translator.translate("Please wait"), dots=dot_count, version=ver, hint=skip_hint)
    gr.draw_paint()
    time.sleep(0.05)


def _start_tts(text=None, hash_str=None, prefix=None, force=False, start_playback=True):
    global tts_active, tts_loading, tts_done, story_step, _tts_gen, _tts_step, _tts_ready_path, _tts_ready_gen
    if not app_config.get("useTTS", True) and not force:
        write_log("TTS disabled by config")
        return
    model_name = app_config.get("models", {}).get("speech", "?")
    stop_tts()

    if text is None:
        text = current_story.get("text", "") if current_story else ""
    if not text:
        return

    if prefix == "description":
        audio_name = f"{hash_str}_description.wav" if hash_str else f"{selected_theme['hash']}_description.wav"
        if hash_str:
            desc_path = os.path.join(story_dir, f"{hash_str}_description.txt")
            with open(desc_path, "w", encoding="utf-8") as sf:
                sf.write(text)
            write_log(f"Saved description text to {desc_path}")
    else:
        step_for_name = len(story_steps) - 1 if story_steps else story_step
        audio_name = f"{selected_theme['hash']}_story_{step_for_name}.wav"
    audio_path = os.path.join(speak_dir, audio_name)

    _tts_step = step_for_name if prefix != "description" else story_step

    _tts_gen += 1
    my_gen = _tts_gen
    _tts_ready_path = None

    def _on_tts_finished():
        global tts_active, tts_done
        if my_gen != _tts_gen:
            return
        tts_active = False
        tts_done = True

    audio.set_tts_finished_callback(_on_tts_finished)

    def play_tts():
        global tts_active, tts_loading, tts_done, _tts_ready_path, _tts_ready_gen
        if my_gen != _tts_gen:
            tts_loading = False
            tts_done = False
            return
        tts_loading = True
        write_log(f"TTS status: loading={tts_loading}")
        try:
            if os.path.exists(audio_path):
                with open(audio_path, "rb") as _f:
                    _hdr = _f.read(4)
                if _hdr != b'RIFF':
                    write_log(f"Corrupt cached speech (not WAV), re-fetching: {audio_path}")
                    os.remove(audio_path)
                else:
                    write_log(f"Speech already cached at {audio_path}, skipping generation")
            else:
                for attempt in range(3):
                    write_log(f"Generating speech (model={model_name}) attempt {attempt+1}/3")
                    try:
                        api.generate_speech(text, audio_path)
                        break
                    except Exception as e:
                        write_log(f"TTS generation attempt {attempt+1} failed: {e}")
                        if attempt == 2:
                            raise
                        time.sleep(0.5)
            if my_gen != _tts_gen:
                write_log("TTS generation stale, skipping playback")
                tts_loading = False
                tts_done = False
                return
            tts_loading = False
            tts_done = False
            write_log(f"TTS status: loading={tts_loading}")
            if os.path.exists(audio_path):
                write_log(f"TTS ready: model={model_name}")
                if start_playback:
                    write_log(f"Playing TTS audio")
                    if my_gen != _tts_gen:
                        write_log("TTS stale before playback, skipping")
                        return
                    if audio.play_tts(audio_path) and my_gen == _tts_gen:
                        tts_active = True
                else:
                    _tts_ready_path = audio_path
                    _tts_ready_gen = my_gen
                    if current_window == "story_show" or current_window == "decision":
                        _play_cached_tts()
        except Exception as e:
            tts_loading = False
            tts_done = False
            write_log(f"TTS error (model={model_name}): {e}")
        finally:
            if my_gen == _tts_gen and not tts_active:
                tts_paused = False

    write_log(f"TTS status: loading={tts_loading}")
    t = threading.Thread(target=play_tts, daemon=True)
    t.start()


def _play_cached_tts():
    global tts_active, _tts_ready_path
    if _tts_ready_path and _tts_ready_gen == _tts_gen and os.path.exists(_tts_ready_path):
        write_log(f"Playing cached TTS audio")
        if _tts_ready_gen != _tts_gen:
            _tts_ready_path = None
            return
        if audio.play_tts(_tts_ready_path) and _tts_ready_gen == _tts_gen:
            tts_active = True
        _tts_ready_path = None


def pause_tts():
    global tts_paused
    audio.pause_tts()
    tts_paused = audio.is_tts_paused()
    write_log("TTS paused")


def resume_tts():
    global tts_paused
    audio.resume_tts()
    tts_paused = audio.is_tts_paused()
    write_log("TTS resumed")


def stop_tts():
    global tts_active, tts_paused, tts_loading, tts_done, _tts_gen, _tts_ready_path
    _tts_gen += 1
    _tts_ready_path = None
    audio.stop_tts()
    tts_active = False
    tts_paused = False
    tts_loading = False
    tts_done = False
    write_log("TTS stopped")


def handle_story_show():
    global current_window, selected_index, tts_paused, tts_loading, tts_done, last_scene_path, story_scroll_offset, show_config, config_dialog_backup, _tts_step, story_steps, _config_from_menu

    if _process_story_result():
        return

    is_generating = api_thread is not None and api_thread.is_alive()

    if is_generating:
        if is_compacting:
            if input.key("DY") and input.value != 0:
                story_scroll_offset = max(0, story_scroll_offset + input.value)

            if input.key("START"):
                stop_tts()
                current_window = "theme_select"
                selected_index = _theme_select_index
                skip_input_check = True
                return

            if input.key("SELECT"):
                config_dialog_backup = gr.active_image.copy()
                show_config = True
                _config_from_menu = False
                skip_input_check = True
                return

            if input.key("B"):
                current_window = "decision"
                selected_index = 0
                skip_input_check = True
                return

            scene_path = None
            if current_story and current_story.get("hash"):
                scene_path = api.get_cached_path(f"{selected_theme['hash']}_story_{story_step}", cache_dir)
                if scene_path:
                    last_scene_path = scene_path
                elif not app_config.get("useStoryImages", True):
                    scene_path = api.get_cached_path(f"{selected_theme['hash']}_description", cache_dir)
                    if not scene_path:
                        scene_path = api.get_cached_path(f"{selected_theme['hash']}_theme", cache_dir)
            elif last_scene_path:
                scene_path = last_scene_path
            elif selected_theme and selected_theme.get("hash"):
                theme_scene = api.get_cached_path(f"{selected_theme['hash']}_theme", cache_dir)
                if theme_scene:
                    scene_path = theme_scene

            story_scroll_offset = gr.draw_story_scene(
                current_story.get("text", ""),
                scene_path,
                title_text=selected_theme.get("caption", "") if selected_theme else "",
                scroll_offset=story_scroll_offset,
                step_count=story_step,
            )
            gr.draw_tts_indicator(loading=tts_loading, active=tts_active, paused=tts_paused, done=tts_done)
            gr.draw_compacting_hint(translator.translate("compacting_wait"))
            gr.draw_paint()
            return
        else:
            current_window = "story_gen"
            return

    if input.key("DY") and input.value != 0:
        story_scroll_offset = max(0, story_scroll_offset + input.value)

    if input.key("JOYSTICK"):
        current_step = len(story_steps) - 1 if story_steps else story_step
        if _tts_step != current_step:
            stop_tts()
            _start_tts(force=True)
        elif tts_paused:
            resume_tts()
        elif tts_active:
            pause_tts()
        elif tts_done:
            stop_tts()
            _start_tts(force=True)
        elif tts_loading:
            pass
        else:
            _start_tts(force=True)

    if input.key("START"):
        stop_tts()
        current_window = "theme_select"
        selected_index = _theme_select_index
        skip_input_check = True
        return

    if input.key("SELECT"):
        config_dialog_backup = gr.active_image.copy()
        show_config = True
        _config_from_menu = False
        skip_input_check = True
        return

    if input.key("A"):
        current_window = "decision"
        selected_index = 0
        skip_input_check = True
        return

    scene_path = None
    if current_story and current_story.get("hash"):
        scene_path = api.get_cached_path(f"{selected_theme['hash']}_story_{story_step}", cache_dir)
        if scene_path:
            last_scene_path = scene_path
        elif not app_config.get("useStoryImages", True):
            scene_path = api.get_cached_path(f"{selected_theme['hash']}_description", cache_dir)
            if not scene_path:
                scene_path = api.get_cached_path(f"{selected_theme['hash']}_theme", cache_dir)
    elif last_scene_path:
        scene_path = last_scene_path
    elif selected_theme and selected_theme.get("hash"):
        theme_scene = api.get_cached_path(f"{selected_theme['hash']}_theme", cache_dir)
        if theme_scene:
            scene_path = theme_scene

    story_scroll_offset = gr.draw_story_scene(
        current_story.get("text", ""),
        scene_path,
        title_text=selected_theme.get("caption", "") if selected_theme else "",
        scroll_offset=story_scroll_offset,
        step_count=story_step,
    )
    gr.draw_tts_indicator(loading=tts_loading, active=tts_active, paused=tts_paused, done=tts_done)

    gr.draw_text((40, y_size - 20), translator.translate("SEL:Config"), font=14, color=gr.colorTextMuted, anchor="lm")
    gr.draw_text((180, y_size - 20), translator.translate("START:Themenauswahl"), font=14, color=gr.colorTextMuted, anchor="lm")
    gr.draw_text((x_size - 40, y_size - 20), translator.translate("A:Continue"), font=14, color=gr.colorAccent, anchor="rm")

    gr.draw_paint()


def handle_decision():
    global selected_index, current_window, story_history, story_scroll_offset, skip_input_check, show_config, config_dialog_backup, _config_from_menu

    if _process_story_result():
        return

    decisions = current_story.get("decisions", [])
    if not decisions:
        decisions = [{"id": "1", "text": translator.translate("Continue...")}]

    is_generating = api_thread is not None and api_thread.is_alive()

    if is_generating:
        if is_compacting:
            if input.key("DY"):
                selected_index = (selected_index + input.value) % len(decisions)
            elif input.key("B"):
                story_scroll_offset = 0
                current_window = "story_show"
                skip_input_check = True
                return
            elif input.key("START"):
                stop_tts()
                current_window = "theme_select"
                selected_index = _theme_select_index
                skip_input_check = True
                return
            elif input.key("SELECT"):
                config_dialog_backup = gr.active_image.copy()
                show_config = True
                _config_from_menu = False
                skip_input_check = True
                return

            gr.draw_decision_view(
                decisions, selected_index, current_story.get("text", ""),
                title_text=translator.translate("What happens next?"),
                sel_text=translator.translate("SEL:Config"),
                scroll_text=translator.translate("DY:Scroll"),
                exit_text=translator.translate("A:Select"),
                sel2_text=translator.translate("START:Themenauswahl"),
            )
            gr.draw_compacting_hint(translator.translate("compacting_wait"))
            gr.draw_tts_indicator(loading=tts_loading, active=tts_active, paused=tts_paused, done=tts_done)
            gr.draw_paint()
            return
        else:
            current_window = "story_gen"
            return

    if input.key("JOYSTICK"):
        current_step = len(story_steps) - 1 if story_steps else story_step
        if _tts_step != current_step:
            stop_tts()
            _start_tts(force=True)
        elif tts_paused:
            resume_tts()
        elif tts_active:
            pause_tts()
        elif tts_done:
            stop_tts()
            _start_tts(force=True)
        elif tts_loading:
            pass
        else:
            _start_tts(force=True)

    if input.key("DY") and input.value != 0:
        selected_index = (selected_index + input.value) % len(decisions)

    elif input.key("A"):
        choice = decisions[selected_index]

        story_history.append({
            "role": "user",
            "content": f"Decision: {choice['text']}"
        })
        _save_history()

        stop_tts()
        skip_input_check = True
        current_window = "story_gen"
        _start_story_generation()
        return

    elif input.key("B"):
        story_scroll_offset = 0
        current_window = "story_show"
        skip_input_check = True
        return

    elif input.key("START"):
        stop_tts()
        current_window = "theme_select"
        selected_index = _theme_select_index
        skip_input_check = True
        return

    elif input.key("SELECT"):
        config_dialog_backup = gr.active_image.copy()
        show_config = True
        _config_from_menu = False
        skip_input_check = True
        return

    gr.draw_decision_view(
        decisions, selected_index, current_story.get("text", ""),
        title_text=translator.translate("What happens next?"),
        sel_text=translator.translate("SEL:Config"),
        scroll_text=translator.translate("DY:Scroll"),
        exit_text=translator.translate("A:Select"),
        sel2_text=translator.translate("START:Themenauswahl"),
    )
    gr.draw_tts_indicator(loading=tts_loading, active=tts_active, paused=tts_paused, done=tts_done)
    gr.draw_paint()


error_message = ""
error_callback = None


def _rumble():
    try:
        subprocess.run("echo 1 > /sys/class/power_supply/axp2202-battery/moto", shell=True)
        time.sleep(0.15)
        subprocess.run("echo 0 > /sys/class/power_supply/axp2202-battery/moto", shell=True)
    except Exception:
        pass


def set_error(msg, raw_response=""):
    global current_window, error_message, error_raw_response, _error_from_window
    stop_tts()
    _stop_music()
    _rumble()
    error_message = msg
    error_raw_response = raw_response
    write_log(f"ERROR: {msg}")
    _error_from_window = current_window
    current_window = "error"
    gr.draw_error(
        msg,
        raw_response=raw_response,
        retry_text=translator.translate("A:Retry"),
        back_text=translator.translate("B:Back"),
        log_text=translator.translate("SEL:Log"),
        version=ver,
    )
    gr.draw_paint()


def handle_error():
    global current_window, show_log, log_backup, log_scroll_offset, error_scroll_offset, error_raw_response, selected_index, skip_input_check
    if input.key("DY") and input.value != 0:
        error_scroll_offset = max(0, error_scroll_offset + input.value)
        gr.draw_error(
            error_message,
            raw_response=error_raw_response,
            scroll_offset=error_scroll_offset,
            retry_text=translator.translate("A:Retry"),
            back_text=translator.translate("B:Back"),
            log_text=translator.translate("SEL:Log"),
            version=ver,
        )
        gr.draw_paint()
        return
    if input.key("A"):
        show_log = False
        api_error = None
        error_raw_response = ""
        error_scroll_offset = 0
        if _error_from_window == "theme_gen":
            start_theme_generation()
            current_window = "theme_gen"
        else:
            _start_story_generation()
            current_window = "story_gen"
        skip_input_check = True
    elif input.key("B"):
        show_log = False
        error_raw_response = ""
        error_scroll_offset = 0
        if _error_from_window == "story_gen":
            current_window = "theme_select"
            if themes:
                selected_index = _theme_select_index
        else:
            current_window = "boot"
        skip_input_check = True
    elif input.key("SELECT") and not show_log:
        show_log = True
        log_scroll_offset = 999999
        log_backup = gr.active_image.copy()



