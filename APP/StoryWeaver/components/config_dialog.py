import json
import os
import input
from PIL import Image
from components import fontsize

_selected = 0


def handle_config_dialog(app_config, config_path, gr, translator, version="", backup=None, profile_dir="", active_profile=None, from_menu=False):
    global _selected
    fontsize.sync_selected(app_config)

    if input.key("B"):
        _save_config(app_config, config_path, profile_dir=profile_dir, active_profile=active_profile)
        input.reset_input()
        if backup:
            gr.active_image.paste(backup, (0, 0))
        gr.draw_paint()
        return False

    if backup:
        gr.active_image.paste(backup, (0, 0))
    else:
        gr.draw_clear()
    gr._paint_blocked = False

    if input.key("DY"):
        _selected = max(0, min(4, _selected + input.value))

    if input.key("A"):
        if _selected == 0:
            app_config["useTTS"] = not app_config.get("useTTS", True)
        elif _selected == 1:
            app_config["useMusic"] = not app_config.get("useMusic", True)
        elif _selected == 2:
            cur = app_config.get("useTTSwithMusic", "lower")
            if cur is False:
                app_config["useTTSwithMusic"] = True
            elif cur is True:
                app_config["useTTSwithMusic"] = "lower"
            else:
                app_config["useTTSwithMusic"] = False
        elif _selected == 3:
            app_config["useStoryImages"] = not app_config.get("useStoryImages", True)
        else:
            fontsize.cycle(app_config, gr)

    _draw(gr, app_config, translator, version, from_menu)
    gr.draw_paint()
    return True


_PROFILE_KEYS = ("useTTS", "useMusic", "useStoryImages", "useTTSwithMusic", "fontSizeText")
_PROFILE_ONLY_KEYS = ("profileTitle", "promptCustomStoryAddition", "promptCustomThemeAddition")


def _save_config(app_config, config_path, profile_dir="", active_profile=None):
    routed_to_profile = set()
    ai_path = config_path.replace(".json", ".ai.json")

    # Load all disk sources
    profile_file_data = {}
    profile_file = None
    if active_profile and profile_dir:
        profile_file = os.path.join(profile_dir, active_profile)
        try:
            if os.path.exists(profile_file):
                with open(profile_file) as f:
                    profile_file_data = json.load(f)
        except Exception as e:
            from app import write_log
            write_log(f"Failed to read profile for save: {e}")
    try:
        with open(config_path) as f:
            disk_config = json.load(f)
    except:
        disk_config = {}
    try:
        with open(ai_path) as f:
            ai_disk = json.load(f)
    except:
        ai_disk = {}

    # Route _PROFILE_KEYS: if profile has them, save to profile; else config.json
    profile_changed = False
    if profile_file_data:
        for key in _PROFILE_KEYS:
            if key in app_config and key in profile_file_data:
                profile_file_data[key] = app_config[key]
                routed_to_profile.add(key)
                profile_changed = True

    # Route ai{} and models{} sub-keys
    ai_changed = False
    for domain in ('ai', 'models'):
        if domain not in app_config or not isinstance(app_config[domain], dict):
            disk_config.pop(domain, None)
            continue
        in_profile = (profile_file_data
                      and isinstance(profile_file_data.get(domain), dict))
        for sub_key, val in app_config[domain].items():
            if in_profile and sub_key in profile_file_data[domain]:
                profile_file_data.setdefault(domain, {})[sub_key] = val
                profile_changed = True
            else:
                ai_disk.setdefault(domain, {})[sub_key] = val
                ai_changed = True

    # Write changed sources
    if profile_changed and profile_file:
        try:
            os.makedirs(profile_dir, exist_ok=True)
            with open(profile_file, "w") as f:
                json.dump(profile_file_data, f, indent=4)
        except Exception as e:
            from app import write_log
            write_log(f"Failed to save profile: {e}")
    if ai_changed:
        try:
            os.makedirs(os.path.dirname(ai_path), exist_ok=True)
            with open(ai_path, "w") as f:
                json.dump(ai_disk, f, indent=4)
        except Exception as e:
            from app import write_log
            write_log(f"Failed to save config.ai.json: {e}")

    # Save config.json — never contains ai/models or PROFILE_ONLY_KEYS
    disk_config.pop("ai", None)
    disk_config.pop("models", None)
    for k in _PROFILE_ONLY_KEYS:
        disk_config.pop(k, None)
    for k in _PROFILE_KEYS:
        if k in app_config and k not in routed_to_profile:
            disk_config[k] = app_config[k]
    try:
        with open(config_path, "w") as f:
            json.dump(disk_config, f, indent=4)
    except Exception as e:
        from app import write_log
        write_log(f"Failed to save config: {e}")


def _draw(gr, app_config, translator, version="", from_menu=False):
    overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 180))
    gr.active_image.paste(overlay, (0, 0), overlay)

    box_w = 400
    card_h = 52
    box_h = 30 + 30 + card_h * 5 + 20 + 40
    x = (gr.screen_width - box_w) // 2
    y = (gr.screen_height - box_h) // 2
    gr.draw_rectangle_r([x, y, x + box_w, y + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)

    gr.draw_text((gr.screen_width // 2, y + 24), translator.translate("Config - Title"), font=20, color=gr.colorAccent, anchor="mm")

    ttswm = app_config.get("useTTSwithMusic", "lower")
    ttswm_label = "Off"
    if ttswm == "lower":
        ttswm_label = "Lower"
    elif ttswm is True:
        ttswm_label = "Mix"

    items = [
        ("Config - useTTS", app_config.get("useTTS", True)),
        ("Config - useMusic", app_config.get("useMusic", True)),
        ("Config - TTS with Music", ttswm_label),
        ("Config - useStoryImages", app_config.get("useStoryImages", True)),
        ("Config - Font Size Text", app_config.get("fontSizeText", 15)),
    ]

    card_x = x + 20
    card_w = box_w - 40
    start_y = y + 50

    for i, entry in enumerate(items):
        key, val = entry[0], entry[1]
        is_selected = (i == _selected)
        cy = start_y + i * (card_h + 8)

        bg = gr.colorPanelL if is_selected else gr.colorPanel
        border = gr.colorAccent if is_selected else gr.colorBg2
        txt_color = gr.colorText if is_selected else gr.colorTextMuted

        gr.draw_rectangle_r([card_x, cy, card_x + card_w, cy + card_h], 8, fill=bg, outline=border)

        if i == 2:
            label = translator.translate("Config - TTS with Music")
            cb_size = 24
            cb_x = card_x + 22
            cb_y = cy + (card_h - cb_size) // 2
            cb_outline = gr.colorAccent if is_selected else gr.colorTextMuted
            if val == "Lower":
                inner = cb_size // 2
                off = (cb_size - inner) // 2
                gr.draw_rectangle_r([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], 3, fill=None, outline=cb_outline)
                gr.draw_rectangle_r([cb_x + off, cb_y + off, cb_x + off + inner, cb_y + off + inner], 3, fill=gr.colorBlueL1, outline=cb_outline)
            elif val == "Mix":
                gr.draw_rectangle_r([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], 3, fill=gr.colorBlueL1, outline=cb_outline)
            else:
                gr.draw_rectangle_r([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], 3, fill=None, outline=cb_outline)
            gr.draw_text((card_x + 55, cy + card_h // 2), label, font=15, color=txt_color, anchor="lm")
            gr.draw_text((card_x + card_w - 14, cy + card_h // 2), val, font=15, color=gr.colorAccent, anchor="rm")
        elif i < 2 or i == 3:
            label = translator.translate(key)
            cb_size = 24
            cb_x = card_x + 22
            cb_y = cy + (card_h - cb_size) // 2
            cb_fill = gr.colorBlueL1 if val else None
            cb_outline = gr.colorAccent if is_selected else gr.colorTextMuted
            gr.draw_rectangle_r([cb_x, cb_y, cb_x + cb_size, cb_y + cb_size], 3, fill=cb_fill, outline=cb_outline)
            gr.draw_text((card_x + 55, cy + card_h // 2), label, font=15, color=txt_color, anchor="lm")
        else:
            label = translator.translate(key)
            gr.draw_text((card_x + 12, cy + card_h // 2), label, font=15, color=txt_color, anchor="lm")
            fontsize.draw_row(gr, card_x, cy, card_w, card_h)

    hint_key = "Config Hint - Close (Menu)" if from_menu else "Config Hint - Close"
    hint_parts = translator.translate(hint_key).split("  ")
    if len(hint_parts) == 2:
        gr.draw_text((x + 30, y + box_h - 12), hint_parts[0], font=14, color=gr.colorTextMuted, anchor="lm")
        gr.draw_text((x + box_w - 30, y + box_h - 12), hint_parts[1], font=14, color=gr.colorAccent, anchor="rm")
    else:
        gr.draw_text((gr.screen_width // 2, y + box_h - 12), translator.translate("Config Hint - Close"), font=14, color=gr.colorTextMuted, anchor="mm")
    if version:
        gr.draw_text((5, gr.screen_height - 5), version, font=11, color=gr.colorTextMuted, anchor="lb")
