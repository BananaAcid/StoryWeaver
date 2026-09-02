import input
import os
import time

MARGIN = 16
TITLE_H = 30
INPUT_H = 40
ROW_H = 68
ROW_GAP = 6
COL_W = 60

SHIFT_LABEL = "^"
BKSP_LABEL = "<"
OK_LABEL = "OK"
SPACE_LABEL = "     "

ROWS = [
    [("1",1), ("2",1), ("3",1), ("4",1), ("5",1), ("6",1), ("7",1), ("8",1), ("9",1), ("0",1)],
    [("Q",1), ("W",1), ("E",1), ("R",1), ("T",1), ("Z",1), ("U",1), ("I",1), ("O",1), ("P",1)],
    [("A",1), ("S",1), ("D",1), ("F",1), ("G",1), ("H",1), ("J",1), ("K",1), ("L",1)],
    [(SHIFT_LABEL,1), ("Y",1), ("X",1), ("C",1), ("V",1), ("B",1), ("N",1), ("M",1), (BKSP_LABEL,1)],
    [(".",1), (",",1), (SPACE_LABEL,4), ("-",1), ("_",1), (OK_LABEL,2)],
]

ROWS_SHIFTED = [
    [("!",1), ("@",1), ("#",1), ("$",1), ("%",1), ("^",1), ("&",1), ("*",1), ("(",1), (")",1)],
    [("Q",1), ("W",1), ("E",1), ("R",1), ("T",1), ("Z",1), ("U",1), ("I",1), ("O",1), ("P",1)],
    [("A",1), ("S",1), ("D",1), ("F",1), ("G",1), ("H",1), ("J",1), ("K",1), ("L",1)],
    [(SHIFT_LABEL,1), ("Y",1), ("X",1), ("C",1), ("V",1), ("B",1), ("N",1), ("M",1), (BKSP_LABEL,1)],
    [(".",1), (",",1), (SPACE_LABEL,4), ("-",1), ("_",1), (OK_LABEL,2)],
]


def _build_key_map(rows):
    key_map = []
    for row in rows:
        total_cols = sum(r for _, r in row)
        row_keys = []
        col_acc = 0
        for label, ratio in row:
            row_keys.append({"label": label, "ratio": ratio, "col": col_acc})
            col_acc += ratio
        key_map.append((total_cols, row_keys))
    return key_map


def _get_action(label, text, cursor, shift):
    if label == OK_LABEL:
        return "ok", text
    if label == BKSP_LABEL:
        if cursor > 0:
            return "backspace", (text[:cursor-1] + text[cursor:], cursor-1)
        return None, None
    if label == SHIFT_LABEL:
        return "shift", None
    if label == SPACE_LABEL:
        return "char", (text[:cursor] + " " + text[cursor:], cursor+1)
    return "char", (text[:cursor] + label + text[cursor:], cursor+1)


def _draw_keyboard(gr, title, text, cursor, shift, sel_row, sel_key_idx, key_map):
    gr.draw_clear()

    gr.draw_rectangle_r([5, 5, gr.screen_width-5, TITLE_H], 5, fill=gr.colorPanel)
    gr.draw_text((gr.screen_width//2, TITLE_H//2), title, font=18, color=gr.colorText, anchor="mm")

    iy = TITLE_H + 4
    gr.draw_rectangle_r([MARGIN, iy, gr.screen_width-MARGIN, iy+INPUT_H], 5, fill=gr.colorBg2, outline=gr.colorAccent)
    display_text = text + ("|" if (int(time.time()*2) % 2) else " ")
    gr.draw_text((MARGIN+8, iy+INPUT_H//2), display_text, font=18, color=gr.colorText, anchor="lm")

    ky = TITLE_H + INPUT_H + 6
    for ri in range(len(key_map)):
        total_cols, keys_list = key_map[ri]
        row_w = total_cols * COL_W
        left = MARGIN + (gr.screen_width - 2*MARGIN - row_w)//2

        for ki, kdata in enumerate(keys_list):
            kw = kdata["ratio"] * COL_W
            kx = left + kdata["col"] * COL_W
            ry = ky + ri * (ROW_H + ROW_GAP)

            label = kdata["label"]
            selected = (ri == sel_row and ki == sel_key_idx)
            is_shift = (label == SHIFT_LABEL)
            is_ok = (label == OK_LABEL)

            if selected:
                fill = gr.colorAccent
                tc = gr.colorBg
            elif is_ok:
                fill = gr.colorBlue
                tc = gr.colorText
            elif is_shift and shift:
                fill = gr.colorYellow
                tc = gr.colorBg
            else:
                fill = gr.colorPanelL
                tc = gr.colorText

            gr.draw_rectangle_r([kx+2, ry+2, kx+kw-2, ry+ROW_H-2], 5, fill=fill)

            if label == SPACE_LABEL:
                disp = "SPACE"
            elif label == BKSP_LABEL:
                disp = "\u232b"
            elif label == SHIFT_LABEL:
                disp = "\u21e7"
            elif label == OK_LABEL:
                disp = "OK"
            else:
                disp = label

            gr.draw_text((kx+kw//2, ry+ROW_H//2), disp, font=16, color=tc, anchor="mm")

    gr.draw_text((MARGIN, gr.screen_height-MARGIN), "A:Press  |  B:Cancel  |  DX/DY:Move", font=13, color=gr.colorTextMuted, anchor="lm")


def show_keyboard(gr, title="Enter text", initial_text="", max_length=50):
    text = initial_text[:max_length]
    cursor = len(text)
    shift = False
    sel_row = 0
    sel_key_idx = 0
    key_map = _build_key_map(ROWS)

    backup = gr.active_image.copy()

    try:
        while True:
            _draw_keyboard(gr, title, text, cursor, shift, sel_row, sel_key_idx, key_map)
            gr.draw_paint()

            input.reset_input()
            input.check()

            if input.key("B"):
                return None

            if input.key("DX"):
                total_cols, keys_list = key_map[sel_row]
                new_idx = sel_key_idx + (1 if input.value > 0 else -1)
                if 0 <= new_idx < len(keys_list):
                    sel_key_idx = new_idx

            elif input.key("DY"):
                new_row = sel_row + (1 if input.value > 0 else -1)
                if 0 <= new_row < len(key_map):
                    _, tgt_keys = key_map[new_row]
                    cur_col = key_map[sel_row][1][sel_key_idx]["col"]
                    best = 0
                    for ki, k in enumerate(tgt_keys):
                        if k["col"] <= cur_col < k["col"] + k["ratio"]:
                            best = ki
                            break
                        if k["col"] + k["ratio"]//2 <= cur_col:
                            best = ki
                    sel_row = new_row
                    sel_key_idx = best

            elif input.key("A"):
                _, keys_list = key_map[sel_row]
                kdata = keys_list[sel_key_idx]
                action, result = _get_action(kdata["label"], text, cursor, shift)
                if action == "ok":
                    return result
                elif action == "backspace":
                    text, cursor = result
                elif action == "shift":
                    shift = not shift
                    key_map = _build_key_map(ROWS_SHIFTED if shift else ROWS)
                elif action == "char":
                    if len(text) < max_length:
                        text, cursor = result

            time.sleep(0.05)
    finally:
        gr.active_image.paste(backup, (0, 0))
        gr.draw_paint()
