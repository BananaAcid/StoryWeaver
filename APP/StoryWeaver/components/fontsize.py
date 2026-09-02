_FONT_SIZES = [15, 17, 20, 22, 25]
_selected = 2


def sync_selected(app_config):
    global _selected
    cur = app_config.get("fontSizeText", 15)
    _selected = min(range(len(_FONT_SIZES)), key=lambda i: abs(_FONT_SIZES[i] - cur))


def cycle(app_config, gr):
    global _selected
    _selected = (_selected + 1) % len(_FONT_SIZES)
    app_config["fontSizeText"] = _FONT_SIZES[_selected]
    gr.font_size_text = _FONT_SIZES[_selected]


def draw_row(gr, card_x, card_y, card_w, card_h):
    area_left = card_x + 160
    area_w = card_x + card_w - area_left - 10
    spacing = area_w / 4 - 3
    current = _FONT_SIZES[_selected]
    for i, sz in enumerate(_FONT_SIZES):
        cx = area_left + i * spacing
        if sz == current:
            color = gr.colorBlueL1
        else:
            color = gr.colorTextMuted
        gr.draw_text((cx, card_y + card_h // 2), "A", font=sz, color=color, anchor="mm")
