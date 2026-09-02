import time
import input
from PIL import Image, ImageDraw

_selected = 0

def show_confirm(gr, translator, title, body="", buttons=None, version="", draw_callback=None):
    global _selected
    if buttons is None:
        buttons = [{"key": "yes", "label": "A:Yes", "key_trigger": "A"}, {"key": "no", "label": "B:No", "key_trigger": "B"}]

    input.reset_input()
    backup = gr.active_image.copy()

    while True:
        input.check()

        if input.key("B"):
            _selected = 0
            input.reset_input()
            return None

        if input.key("DY") and input.value != 0:
            _selected = max(0, min(len(buttons) - 1, _selected + input.value))

        if input.key("A"):
            k = buttons[_selected]["key"]
            _selected = 0
            input.reset_input()
            return k

        for btn in buttons:
            if input.key(btn["key_trigger"]):
                _selected = 0
                input.reset_input()
                return btn["key"]

        gr.active_image.paste(backup, (0, 0))
        overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 180))
        gr.active_image.paste(overlay, (0, 0), overlay)

        box_w = 400
        line_h = 30
        body_lines = body.split("\n") if body else []
        body_h = len(body_lines) * 20
        hint_h = 40 if buttons else 0
        box_h = 60 + 24 + body_h + hint_h
        bx = (gr.screen_width - box_w) // 2
        by = (gr.screen_height - box_h) // 2

        gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)
        gr.draw_text((gr.screen_width // 2, by + 28), title, font=20, color=gr.colorAccent, anchor="mm")

        y = by + 55
        for line in body_lines:
            gr.draw_text((gr.screen_width // 2, y), line, font=15, color=gr.colorText, anchor="mm")
            y += 20

        if buttons:
            hint_parts = [b["label"] for b in buttons]
            hint_text = "  |  ".join(hint_parts)
            gr.draw_text((gr.screen_width // 2, by + box_h - 18), hint_text, font=14, color=gr.colorAccent, anchor="mm")

        gr.draw_paint()
        time.sleep(0.01)
