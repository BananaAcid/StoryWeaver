import time
import input
from PIL import Image

_selected = 0
_scroll_offset = 0
_last_update_label = None
_checking_update = False


def _build_items(current_window, translator, version, active_profile_title=None):
    before_start = current_window in ("boot", "welcome", "theme_gen")
    items = []

    global _last_update_label
    if before_start:
        items.append({"key": "log", "label": translator.translate("Event Log")})
    else:
        items.append({"key": "config", "label": translator.translate("Settings")})
        profile_title = active_profile_title or translator.translate("No profile")
        items.append({"key": "select_profile", "label": translator.translate("Profiles") + ": " + profile_title})
        items.append({"key": None, "label": ""})
        items.append({"key": "welcome", "label": translator.translate("Welcome Screen")})
        items.append({"key": None, "label": ""})
        items.append({"key": "edit_config_online", "label": translator.translate("Edit Config Online")})
        items.append({"key": "reload_config", "label": translator.translate("Reload Config")})
        items.append({"key": None, "label": ""})
        items.append({"key": "log", "label": translator.translate("Event Log")})
        items.append({"key": "clear_cache", "label": translator.translate("Clear Cache")})
        items.append({"key": None, "label": ""})
    if _last_update_label is not None:
        update_label = _last_update_label
    else:
        update_label = translator.translate("Update (N/A)")
    items.append({"key": "update", "label": update_label})
    check_label = translator.translate("Check for updates")
    if _checking_update:
        check_label += translator.translate(" (checking)")
    items.append({"key": "check_update", "label": check_label})
    items.append({"key": None, "label": ""})
    items.append({"key": "restart", "label": translator.translate("Restart App")})
    items.append({"key": "exit", "label": translator.translate("Exit")})

    return items


def _item_height(it, card_h, spacer_h):
    return spacer_h if it["key"] is None else card_h + 8


def _clamp_scroll(items, card_h, spacer_h, max_body_h):
    global _scroll_offset
    total = sum(_item_height(it, card_h, spacer_h) for it in items)
    if total <= max_body_h:
        _scroll_offset = 0
        return
    # position of selected item
    sel_pos = 0
    for i in range(_selected):
        sel_pos += _item_height(items[i], card_h, spacer_h)
    sel_h = _item_height(items[_selected], card_h, spacer_h)

    if sel_pos < _scroll_offset:
        _scroll_offset = sel_pos
    elif sel_pos + sel_h > _scroll_offset + max_body_h:
        _scroll_offset = sel_pos + sel_h - max_body_h

    _scroll_offset = max(0, min(_scroll_offset, total - max_body_h))


def reset_menu_state():
    global _selected, _scroll_offset
    _selected = 0
    _scroll_offset = 0


def handle_menu(gr, translator, current_window, version, backup=None, active_profile_title=None):
    global _selected, _scroll_offset, _last_update_label, _checking_update

    items = _build_items(current_window, translator, version, active_profile_title=active_profile_title)
    max_idx = len(items) - 1

    if input.key("B") or input.key("MENUF"):
        _selected = 0
        _scroll_offset = 0
        return "__close__"

    if input.key("SEL") or input.key("SELECT"):
        return "log"

    if input.key("START"):
        _selected = 0
        _scroll_offset = 0
        return "config"

    if input.key("X"):
        _selected = 0
        _scroll_offset = 0
        return "exit"

    if input.key("DY") and input.value != 0:
        step = 1 if input.value > 0 else -1
        new_sel = _selected
        for _ in range(len(items)):
            new_sel = max(0, min(max_idx, new_sel + step))
            if items[new_sel]["key"] is not None:
                break
        _selected = new_sel

    if input.key("DX") and input.value != 0:
        if input.value < 0:
            _selected = next(i for i, it in enumerate(items) if it["key"] is not None)
        else:
            _selected = next(i for i in range(max_idx, -1, -1) if items[i]["key"] is not None)
        _scroll_offset = 0

    if input.key("A"):
        selected_item = items[_selected]
        if selected_item["key"] is not None:
            action_key = selected_item["key"]
            if action_key == "check_update":
                _checking_update = True
                return action_key
            else:
                if action_key not in ("log", "select_profile"):
                    _selected = 0
                    _scroll_offset = 0
                return action_key

    if backup:
        gr.active_image.paste(backup, (0, 0))

    box_w = 400
    card_h = 52
    spacer_h = 10
    title_h = 50
    pad = 20
    hint_h = 40
    max_body_h = 5 * (card_h + 8) + 2 * spacer_h

    total_body_h = sum(_item_height(it, card_h, spacer_h) for it in items)
    _clamp_scroll(items, card_h, spacer_h, max_body_h)

    body_h = min(total_body_h, max_body_h)
    box_h = title_h + pad + body_h + hint_h
    bx = (gr.screen_width - box_w) // 2
    by = (gr.screen_height - box_h) // 2

    overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 180))
    gr.active_image.paste(overlay, (0, 0), overlay)

    gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)
    gr.draw_text((gr.screen_width // 2, by + title_h // 2 + 10), translator.translate("Story Weaver"), font=22, color=gr.colorAccent, anchor="mm")

    card_x = bx + 20
    card_w = box_w - 40
    div_w = max(1, (box_w - 80) // 3)
    body_top = by + title_h + pad

    acc = 0
    first_card = False
    for i, it in enumerate(items):
        h = _item_height(it, card_h, spacer_h)
        cy = body_top + acc - _scroll_offset

        if cy + h < body_top:
            acc += h
            continue
        if cy >= body_top + body_h:
            break

        if it["key"] is None:
            if not first_card or cy < body_top:
                acc += h
                continue
            ly = cy + h // 2 - 4
            lx = bx + box_w // 2 - div_w // 2
            gr.draw_rectangle_r([lx, ly, lx + div_w, ly + 1], 1, fill=gr.colorBlueL1)
        else:
            first_card = True
            is_sel = i == _selected
            bg = gr.colorPanelL if is_sel else gr.colorPanel
            border = gr.colorAccent if is_sel else gr.colorBg2
            txt_color = gr.colorText if is_sel else gr.colorTextMuted

            draw_cy = max(cy, body_top)
            gr.draw_rectangle_r([card_x, draw_cy, card_x + card_w, draw_cy + card_h], 8, fill=bg, outline=border)
            tx = card_x + card_w // 2
            ty = draw_cy + card_h // 2
            gr.draw_text((tx, ty), it['label'], font=17, color=txt_color, anchor="mm")

        acc += h

    hint_y = by + box_h - 14
    hints_left = []
    hints_right = []
    if current_window not in ("boot", "welcome", "theme_gen"):
        hints_left.append("SEL:" + translator.translate("Log"))
        hints_left.append("START:" + translator.translate("Settings"))
    else:
        hints_left.append("SEL:" + translator.translate("Log"))
    hints_right.append("X:" + translator.translate("Exit"))
    hints_right.append("B:" + translator.translate("Close"))

    gr.draw_text((bx + 20, hint_y), "  ".join(hints_left), font=13, color=gr.colorTextMuted, anchor="lm")
    gr.draw_text((bx + box_w - 20, hint_y), "  ".join(hints_right), font=13, color=gr.colorAccent, anchor="rm")

    if total_body_h > body_h:
        bar_x = bx + box_w - 12
        bar_y = by + title_h + pad
        bar_h = body_h
        pct = _scroll_offset / max(1, total_body_h - body_h)
        thumb_h = max(8, int(bar_h * body_h / total_body_h))
        thumb_y = bar_y + int((bar_h - thumb_h) * pct)
        gr.draw_rectangle_r([bar_x, bar_y, bar_x + 4, bar_y + bar_h], 2, fill=gr.colorBg2)
        gr.draw_rectangle_r([bar_x, thumb_y, bar_x + 4, thumb_y + thumb_h], 2, fill=gr.colorAccent)

    if version:
        gr.draw_text((5, gr.screen_height - 5), version, font=11, color=gr.colorTextMuted, anchor="lb")

    gr.draw_paint()

    return None


def handle_profile_select(gr, translator, profiles, active_profile, version=""):
    """Profile selection dialog. Returns filename of selected profile, or None for 'No profile', or '__back__'."""
    sel = 0
    scroll_off = 0
    items = [{"key": None, "label": translator.translate("No profile")}]
    for p in profiles:
        items.append({"key": p["filename"], "label": p["title"]})
    # find active index
    if active_profile is None:
        sel = 0
    else:
        for i, p in enumerate(profiles):
            if p["filename"] == active_profile:
                sel = i + 1
                break

    box_w = 400
    card_h = 52
    spacer_h = 8
    title_h = 50
    pad = 20
    hint_h = 40
    max_body_h = 5 * (card_h + 8)
    line_h = 17  # font(15) + 2 spacing per graphic.py pattern
    text_max_w = box_w - 40 - 52 - 4  # card_w minus circle area minus margin
    _backup = gr.active_image.copy()

    while True:
        input.check()
        if input.key("B") or input.key("MENUF"):
            return "__back__"

        if input.key("DY") and input.value != 0:
            step = 1 if input.value > 0 else -1
            new_sel = max(0, min(len(items) - 1, sel + step))
            sel = new_sel

        if input.key("A"):
            return items[sel]["key"]

        gr.active_image.paste(_backup, (0, 0))
        overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 180))
        gr.active_image.paste(overlay, (0, 0), overlay)

        # Compute per-item heights based on wrapped text
        item_heights = []
        for it in items:
            lines = gr._wrap_text(it["label"], font=15, max_width=text_max_w)
            n = max(1, len(lines))
            text_h = n * line_h
            this_card_h = max(card_h, text_h + 8)
            item_heights.append(this_card_h + spacer_h)

        total_body_h = sum(item_heights)
        body_h = min(total_body_h, max_body_h)
        box_h = title_h + pad + body_h + hint_h
        bx = (gr.screen_width - box_w) // 2
        by = (gr.screen_height - box_h) // 2

        # Clamp scroll to keep selected item visible
        if total_body_h > max_body_h:
            sel_pos = sum(item_heights[:sel])
            sel_h = item_heights[sel]
            if sel_pos < scroll_off:
                scroll_off = sel_pos
            elif sel_pos + sel_h > scroll_off + max_body_h:
                scroll_off = sel_pos + sel_h - max_body_h
            scroll_off = max(0, min(scroll_off, total_body_h - max_body_h))
        else:
            scroll_off = 0

        gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)
        gr.draw_text((gr.screen_width // 2, by + title_h // 2 + 10), translator.translate("Select Profile"), font=20, color=gr.colorAccent, anchor="mm")

        card_x = bx + 20
        card_w = box_w - 40
        body_top = by + title_h + pad
        acc = 0
        for i, it in enumerate(items):
            this_item_h = item_heights[i]
            this_card_h = this_item_h - spacer_h
            cy = body_top + acc - scroll_off
            if cy + this_item_h < body_top:
                acc += this_item_h
                continue
            if cy >= body_top + body_h:
                break

            is_sel = i == sel
            is_active = (i == 0 and active_profile is None) or (i > 0 and it["key"] == active_profile)
            bg = gr.colorPanelL if is_sel else gr.colorPanel
            border = gr.colorAccent if is_sel else gr.colorBg2
            txt_color = gr.colorText if is_sel else gr.colorTextMuted

            draw_cy = max(cy, body_top)
            visible_card_h = min(this_card_h, body_top + body_h - draw_cy)
            if visible_card_h > 0:
                gr.draw_rectangle_r([card_x, draw_cy, card_x + card_w, draw_cy + visible_card_h], 8, fill=bg, outline=border)
                rb_size = 24
                rb_x = card_x + 16
                rb_y = draw_cy + (visible_card_h - rb_size) // 2
                rb_fill = gr.colorBlueL1 if is_active else None
                rb_outline = gr.colorAccent if is_sel else gr.colorTextMuted
                gr.draw_circle((rb_x, rb_y), rb_size, fill=rb_fill, outline=rb_outline)
                lines = gr._wrap_text(it["label"], font=15, max_width=text_max_w)
                n = max(1, len(lines))
                card_mid = draw_cy + visible_card_h // 2
                ty = card_mid - (n - 1) * line_h // 2
                for line in lines:
                    gr.draw_text((card_x + 52, ty), line, font=15, color=txt_color, anchor="lm")
                    ty += line_h
            acc += this_item_h

        hint_y = by + box_h - 14
        gr.draw_text((bx + 20, hint_y), "B:" + translator.translate("Back"), font=13, color=gr.colorAccent, anchor="lm")
        gr.draw_text((bx + box_w - 20, hint_y), "A:" + translator.translate("Select"), font=13, color=gr.colorAccent, anchor="rm")

        # Scrollbar
        if total_body_h > body_h:
            bar_x = bx + box_w - 12
            bar_y = body_top
            bar_h = body_h
            pct = scroll_off / max(1, total_body_h - body_h)
            thumb_h = max(8, int(bar_h * body_h / total_body_h))
            thumb_y = bar_y + int((bar_h - thumb_h) * pct)
            gr.draw_rectangle_r([bar_x, bar_y, bar_x + 4, bar_y + bar_h], 2, fill=gr.colorBg2)
            gr.draw_rectangle_r([bar_x, thumb_y, bar_x + 4, thumb_y + thumb_h], 2, fill=gr.colorAccent)

        if version:
            gr.draw_text((5, gr.screen_height - 5), version, font=11, color=gr.colorTextMuted, anchor="lb")

        gr.draw_paint()
        time.sleep(0.05)
