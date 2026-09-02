import ctypes
import os
import time
from main import hw_info, hdmi_info
from typing import Optional

import sdl2
from PIL import Image, ImageDraw, ImageFont

script_dir = os.path.dirname(os.path.abspath(__file__))
local_font_list = os.path.join(script_dir, "font/font.ttf")
sys_font_file = os.path.join("/mnt/vendor/bin/default.ttf")
font_file = local_font_list if os.path.exists(local_font_list) else sys_font_file

color_text = "#ffffff"

screen_resolutions = {
    1: (720, 720, 18),
    2: (720, 480, 11),
}

class UserInterface:
    _instance: Optional["UserInterface"] = None
    _initialized: bool = False

    screen_width, screen_height, max_elem = screen_resolutions.get(hw_info, (640, 480, 11))

    _bg_image: Image.Image = None

    colorBg = "#0f111a"
    colorBg2 = "#141624"
    colorPanel = "#1a1d2e"
    colorPanelL = "#222640"
    colorBlue = "#0072bb"
    colorBlueD1 = "#004f7f"
    colorBlueL1 = "#2a8fd4"
    colorGray = "#292929"
    colorGrayL1 = "#383838"
    colorGrayD2 = "#141414"
    colorGreen = "#00ff00"
    colorRed = "#cb0202"
    colorYellow = "#ffd700"
    colorCyan = "#00d7ff"
    colorIndigo = "#3f51b5"
    colorSlate = "#455a64"
    colorText = "#e0e0e0"
    colorTextMuted = "#8899aa"
    colorAccent = "#00bcd4"
    colorOrange = "#ff8c00"

    active_image: Image.Image
    active_draw: ImageDraw.ImageDraw

    def __init__(self):
        if self._initialized:
            return
        self.window = self._create_window()
        self.renderer = self._create_renderer()
        self.draw_start()
        self._tts_blink = False
        self.opt_stretch = True
        self.font_size_text = 15
        self.notification_text = ""
        self.notification_time = 0
        self._initialized = True

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(UserInterface, cls).__new__(cls)
        return cls._instance

    def create_image(self):
        return Image.new("RGBA", (self.screen_width, self.screen_height), color="black")

    def draw_start(self):
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)
        self.active_image = self.create_image()
        self.active_draw = ImageDraw.Draw(self.active_image)

    def _create_window(self):
        sdl2.SDL_SetHint(sdl2.SDL_HINT_VIDEO_ALLOW_SCREENSAVER, b"1")
        window = sdl2.SDL_CreateWindow(
            "Story".encode("utf-8"),
            sdl2.SDL_WINDOWPOS_UNDEFINED,
            sdl2.SDL_WINDOWPOS_UNDEFINED,
            0, 0,
            sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_SHOWN | 0x00002000,
        )
        if not window:
            print(f"Failed to create window: {sdl2.SDL_GetError()}")
            raise RuntimeError("Failed to create window")
        return window

    def _create_renderer(self):
        renderer = sdl2.SDL_CreateRenderer(
            self.window, -1, sdl2.SDL_RENDERER_ACCELERATED
        )
        if not renderer:
            renderer = sdl2.render.SDL_CreateRenderer(
                self.window, -1, sdl2.render.SDL_RENDERER_SOFTWARE
            )
            if not renderer:
                print(f"Failed to create renderer: {sdl2.SDL_GetError()}")
                raise RuntimeError("Failed to create renderer")
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"0")
        return renderer

    def draw_paint(self):
        if getattr(self, '_paint_blocked', False):
            return

        # Notification overlay
        if self.notification_text and time.time() - self.notification_time < 1.5:
            pad = 12
            tw = len(self.notification_text) * 9 + pad * 2
            th = 18 + pad * 2
            self.draw_rectangle_r([10, 10, 10 + tw, 10 + th], 8, fill=(0, 0, 0, 200))
            self.draw_text((10 + pad, 10 + pad), self.notification_text, font=17, color=(255, 255, 0), anchor="la")
        elif self.notification_text:
            self.notification_text = ""
        if hw_info == 3 and hdmi_info != "HDMI=1":
            rotated_image = self.active_image.rotate(90, expand=True)
            rgba_data = rotated_image.tobytes()
            temp_width, temp_height = rotated_image.size
        else:
            rgba_data = self.active_image.tobytes()
            temp_width, temp_height = self.screen_width, self.screen_height

        surface = sdl2.SDL_CreateRGBSurfaceWithFormatFrom(
            rgba_data, temp_width, temp_height, 32, temp_width * 4,
            sdl2.SDL_PIXELFORMAT_RGBA32,
        )
        texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surface)
        sdl2.SDL_FreeSurface(surface)

        window_width = ctypes.c_int()
        window_height = ctypes.c_int()
        sdl2.SDL_GetWindowSize(
            self.window, ctypes.byref(window_width), ctypes.byref(window_height)
        )
        window_width, window_height = window_width.value, window_height.value

        if not self.opt_stretch:
            scale = min(window_width / temp_width, window_height / temp_height)
            dst_width = int(temp_width * scale)
            dst_height = int(temp_height * scale)
            dst_x = (window_width - dst_width) // 2
            dst_y = (window_height - dst_height) // 2
            dst_rect = sdl2.SDL_Rect(dst_x, dst_y, dst_width, dst_height)
        else:
            dst_rect = sdl2.SDL_Rect(0, 0, window_width, window_height)

        sdl2.SDL_RenderCopy(self.renderer, texture, None, dst_rect)
        sdl2.SDL_RenderPresent(self.renderer)
        sdl2.SDL_DestroyTexture(texture)

    def draw_end(self):
        sdl2.SDL_DestroyRenderer(self.renderer)
        sdl2.SDL_DestroyWindow(self.window)
        sdl2.SDL_Quit()

    def draw_background(self):
        self.active_draw.rectangle(
            [0, 0, self.screen_width, self.screen_height], fill=self.colorBg
        )
        if self._bg_image is None:
            bg_path = os.path.join(script_dir, "res", "bg_720.jpg")
            if os.path.exists(bg_path):
                try:
                    bg = Image.open(bg_path).convert("RGBA")
                    self._bg_image = bg
                except Exception:
                    pass
        if self._bg_image is not None:
            bw, bh = self._bg_image.size
            px = (self.screen_width - bw) // 2
            py = (self.screen_height - bh) // 2
            self.active_image.paste(self._bg_image, (px, py), self._bg_image)

    def draw_clear(self):
        self.active_draw.rectangle(
            [0, 0, self.screen_width, self.screen_height], fill=self.colorBg
        )

    def draw_text(self, position, text, font=21, color=color_text, **kwargs):
        self.active_draw.text(
            position, text, font=ImageFont.truetype(font_file, font), fill=color, **kwargs
        )

    def draw_rectangle(self, position, fill=None, outline=None, width=1):
        self.active_draw.rectangle(position, fill=fill, outline=outline, width=width)

    def draw_rectangle_r(self, position, radius, fill=None, outline=None):
        self.active_draw.rounded_rectangle(position, radius, fill=fill, outline=outline)

    def row_list(self, text, pos, width, selected):
        self.draw_rectangle_r(
            [pos[0], pos[1], pos[0] + width, pos[1] + 32],
            5,
            fill=(self.colorBlue if selected else self.colorGrayL1),
        )
        self.draw_text((pos[0] + 5, pos[1] + 5), text)

    def draw_circle(self, position, radius, fill=None, outline=color_text):
        self.active_draw.ellipse(
            [position[0], position[1], position[0] + radius, position[1] + radius],
            fill=fill, outline=outline,
        )

    def draw_log(self, text, fill="Black", outline="black", width=500, font=21):
        x = (self.screen_width - width) / 2
        y = (self.screen_height - 80) / 2
        self.draw_rectangle_r([x, y, x + width, y + 80], 5, fill=fill, outline=outline)
        font_obj = ImageFont.truetype(font_file, font)
        padding = 10
        max_width = width - 2 * padding
        lines = []
        current_line = ""
        for word in text.split():
            test_line = f"{current_line} {word}".strip() if current_line else word
            bbox = font_obj.getbbox(test_line)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                bbox = font_obj.getbbox(word)
                if (bbox[2] - bbox[0]) <= max_width:
                    current_line = word
                else:
                    remaining = word
                    while remaining:
                        substring = ""
                        for char in remaining:
                            temp_sub = substring + char
                            if (font_obj.getbbox(temp_sub)[2] - font_obj.getbbox(temp_sub)[0]) <= max_width:
                                substring = temp_sub
                            else:
                                break
                        if substring:
                            lines.append(substring)
                            remaining = remaining[len(substring):]
                        else:
                            break
        if current_line:
            lines.append(current_line)
        ascent, descent = font_obj.getmetrics()
        line_height = int((ascent + descent) * 1.2)
        total_height = len(lines) * line_height
        start_y = y + (80 - total_height) // 2
        for i, line in enumerate(lines):
            self.draw_text((x + width / 2, start_y + i * line_height + ascent - 5), line, font, anchor="mm")

    def draw_theme_selection(self, themes, selected_idx, start_offset, thumbnails, title_text="Choose Your Adventure", sel_text="A:Select", scroll_text="DY:Scroll", exit_text="SEL:Exit", favorites=None, version="", steps_map=None):
        self.draw_clear()

        self.draw_rectangle_r([5, 5, self.screen_width - 5, 35], 5, fill=self.colorPanel)
        self.draw_text((self.screen_width // 2, 20), title_text, font=22, color=self.colorText, anchor="mm")

        cols = 2
        rows = 3
        card_w = (self.screen_width - 40) // cols
        card_h = (self.screen_height - 120) // rows
        visible_count = cols * rows

        for i in range(visible_count):
            idx = start_offset + i
            if idx >= len(themes):
                break
            theme = themes[idx]
            col = i % cols
            row = i // cols
            x = 15 + col * (card_w + 10)
            y = 50 + row * (card_h + 11)

            is_selected = (idx == selected_idx)
            bg_color = self.colorPanelL if is_selected else self.colorPanel
            border_color = self.colorAccent if is_selected else self.colorBg2

            self.draw_rectangle_r([x, y, x + card_w, y + card_h], 8, fill=bg_color, outline=border_color)

            thumb_img = thumbnails.get(idx)
            if thumb_img:
                try:
                    tw, th = thumb_img.size
                    tx = x + (card_w - tw) // 2
                    ty = y + 5
                    self.active_image.paste(thumb_img, (tx, ty), thumb_img)
                except Exception:
                    self.draw_rectangle([x + 5, y + 5, x + card_w - 5, y + card_h - 65], fill=self.colorGrayD2)

            caption = theme["caption"]
            cap_font = ImageFont.truetype(font_file, 19)
            cap_width = cap_font.getbbox(caption)[2]
            max_cap_w = card_w - 10
            if cap_width > max_cap_w:
                while cap_font.getbbox(caption + "...")[2] > max_cap_w and len(caption) > 1:
                    caption = caption[:-1]
                caption += "..."
            self.draw_text((x + card_w // 2, y + card_h - 51), caption, font=19, color=self.colorAccent, anchor="mm")
            desc_font = self.font_size_text
            desc_lines = self._wrap_text(theme["description"], font=desc_font, max_width=card_w - 10)
            desc_spacing = desc_font + 2
            two_line_bottom = card_h - 31 + desc_spacing + desc_font / 2
            max_desc_lines = 2 if two_line_bottom <= card_h - 2 else 1
            truncated = len(desc_lines) > max_desc_lines
            block_center_y = card_h - 22
            first_y = block_center_y - (max_desc_lines - 1) * desc_spacing / 2
            for li, line in enumerate(desc_lines[:max_desc_lines]):
                txt = line.rstrip()
                if truncated and li == max_desc_lines - 1:
                    txt = txt[:-3].rstrip() + "..." if len(txt) > 3 else "..."
                self.draw_text((x + card_w // 2, y + int(first_y + li * desc_spacing)), txt, font=desc_font, color=self.colorTextMuted, anchor="mm")

            if favorites and theme.get("hash") in favorites:
                star_pos = (x + card_w - 14, y + 14)
                for ox, oy in ((-1,-1),(-1,1),(1,-1),(1,1)):
                    self.draw_text((star_pos[0] + ox, star_pos[1] + oy), "★", font=18, color="#000000", anchor="mm")
                self.draw_text(star_pos, "★", font=18, color=self.colorYellow, anchor="mm")

            if steps_map and theme.get("hash") in steps_map:
                s = steps_map[theme["hash"]]
                if s > 0:
                    badge_x = x + 4
                    badge_y = y + 5
                    bw = 34
                    bh = 24
                    cut = 9
                    overlay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
                    od = ImageDraw.Draw(overlay)
                    od.polygon([(0, 0), (bw, 0), (bw - cut, bh), (0, bh)], fill=(0, 0, 0, 200))
                    self.active_image.paste(overlay, (badge_x, badge_y), overlay)
                    self.draw_text((badge_x + bw // 2 - cut // 2, badge_y + bh // 2), str(s), font=16, color=self.colorAccent, anchor="mm")

        sw = self.screen_width
        self.draw_text((150, self.screen_height - 20), sel_text, font=14, color=self.colorTextMuted, anchor="mm")
        self.draw_text((sw // 2, self.screen_height - 20), scroll_text, font=14, color=self.colorTextMuted, anchor="mm")
        self.draw_text((sw - 150, self.screen_height - 20), exit_text, font=14, color=self.colorAccent, anchor="mm")
        if favorites:
            fave_pos = (sw - 13, 20)
            for ox, oy in ((-1,-1),(-1,1),(1,-1),(1,1)):
                self.draw_text((fave_pos[0] + ox, fave_pos[1] + oy), f"★ {len(favorites)}", font=14, color="#000000", anchor="rm")
            self.draw_text(fave_pos, f"★ {len(favorites)}", font=14, color=self.colorYellow, anchor="rm")

    def draw_story_scene(self, story_text, scene_image_path=None, title_text="Story Weaver", scroll_offset=0, step_count=None):
        self.draw_clear()

        panel_x = 10
        panel_y = 10
        panel_w = self.screen_width - 20
        panel_h = self.screen_height - 20
        self.draw_rectangle_r([panel_x, panel_y, panel_x + panel_w, panel_y + panel_h], 10, fill=self.colorPanel, outline=self.colorBlueD1)

        img_area_y = panel_y + 9
        img_area_h = 160

        if scene_image_path and os.path.exists(scene_image_path):
            try:
                if not hasattr(self, '_scene_cache') or self._scene_cache[0] != scene_image_path:
                    scene_img = Image.open(scene_image_path).convert("RGBA")
                    self._scene_cache = (scene_image_path, scene_img)
                scene_img = self._scene_cache[1]
                target_w = panel_w - 20
                target_h = img_area_h - 4
                scene_img = scene_img.resize((target_w, target_h), Image.LANCZOS)
                paste_x = panel_x + 10
                paste_y = img_area_y + 2
                self.active_image.paste(scene_img, (paste_x, paste_y), scene_img)
                self.draw_rectangle_r([paste_x - 2, paste_y - 2, paste_x + target_w + 2, paste_y + target_h + 2], 6, outline=self.colorBlueD1)
            except Exception:
                self.draw_rectangle_r([panel_x + 10, img_area_y + 2, panel_x + panel_w - 10, img_area_y + img_area_h - 2], 6, fill=self.colorBg2)
        else:
            self.draw_rectangle_r([panel_x + 10, img_area_y + 2, panel_x + panel_w - 10, img_area_y + img_area_h - 2], 6, fill=self.colorBg2)

        if step_count is not None and step_count > 0:
            bx = panel_x + 10
            by = img_area_y + 2
            bw = 44
            bh = 30
            cut = 12
            overlay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.polygon([(0, 0), (bw, 0), (bw - cut, bh), (0, bh)], fill=(0, 0, 0, 200))
            self.active_image.paste(overlay, (bx, by), overlay)
            self.draw_text((bx + bw // 2 - cut // 2, by + bh // 2), str(step_count), font=24, color=self.colorAccent, anchor="mm")

        if title_text:
            title_gap = 4
            title_font = 14
            self.draw_text((self.screen_width // 2, img_area_y + img_area_h + title_gap + title_font // 2), title_text, font=title_font, color=self.colorAccent, anchor="mm")

        text_y = img_area_y + img_area_h + 4 + 14 + 5
        text_h = panel_y + panel_h - text_y - 20
        text_w = panel_w - 20
        line_h = self.font_size_text + 5

        cache_key = (story_text, self.font_size_text)
        if not hasattr(self, '_text_cache') or self._text_cache[0] != cache_key:
            lines = self._wrap_text(story_text, font=self.font_size_text, max_width=text_w - 10)
            total = len(lines)
            max_visible = max(1, text_h // line_h)
            if total > max_visible:
                text_w = panel_w - 20 - 14
                lines = self._wrap_text(story_text, font=self.font_size_text, max_width=text_w - 10)
                total = len(lines)
                max_visible = max(1, text_h // line_h)
            self._text_cache = (cache_key, lines, total, max_visible)
        else:
            _, lines, total, max_visible = self._text_cache
        scroll_offset = max(0, min(scroll_offset, max(0, total - max_visible)))
        visible = lines[scroll_offset:scroll_offset + max_visible]

        for i, line in enumerate(visible):
            self.draw_text((panel_x + 20, text_y + 5 + i * line_h), line, font=self.font_size_text, color=self.colorText)

        if total > max_visible:
            pct = scroll_offset / max(1, total - max_visible)
            bar_x = panel_x + panel_w - 10
            bar_y = text_y + 5
            bar_h = max_visible * line_h
            bar_w = 4
            thumb_h = max(8, int(bar_h / total * max_visible))
            thumb_y = bar_y + int((bar_h - thumb_h) * pct)
            self.draw_rectangle_r([bar_x - bar_w, bar_y, bar_x, bar_y + bar_h], 2, fill=self.colorBg2)
            self.draw_rectangle_r([bar_x - bar_w, thumb_y, bar_x, thumb_y + thumb_h], 2, fill=self.colorAccent)

        return scroll_offset

    def draw_decision_view(self, decisions, selected_idx, story_text, title_text="What happens next?", sel_text="A:Select", scroll_text="DY:Scroll", exit_text="SEL:Exit", sel2_text=""):
        self.draw_clear()

        self.draw_rectangle_r([10, 10, self.screen_width - 10, self.screen_height - 10], 10, fill=self.colorPanel, outline=self.colorBlueD1)
        self.draw_text((self.screen_width // 2, 41), title_text, font=20, color=self.colorAccent, anchor="mm")

        y_start = 66
        btn_w = self.screen_width - 40
        x = 20
        text_w = btn_w - 65
        avail_h = self.screen_height - 20 - y_start - 10

        pre_heights = []
        pre_wrapped = []
        for dec in decisions[:5]:
            wrapped = self._wrap_text(dec["text"], font=self.font_size_text, max_width=text_w)
            actual = len(wrapped)
            num = max(min(actual, 3), 2)
            h = 20 + num * (self.font_size_text + 5)
            pre_heights.append(h)
            pre_wrapped.append((wrapped, actual, num))

        total_h = sum(pre_heights) + 8 * (len(pre_heights) - 1)

        if total_h > avail_h:
            btn_w = self.screen_width - 40 - 14
            text_w = btn_w - 65
            pre_heights = []
            pre_wrapped = []
            for dec in decisions[:5]:
                wrapped = self._wrap_text(dec["text"], font=self.font_size_text, max_width=text_w)
                actual = len(wrapped)
                num = max(min(actual, 3), 2)
                h = 20 + num * (self.font_size_text + 5)
                pre_heights.append(h)
                pre_wrapped.append((wrapped, actual, num))
            total_h = sum(pre_heights) + 8 * (len(pre_heights) - 1)

        # Determine start_idx so selected is visible and as many buttons fit as possible
        num_btns = len(pre_heights)
        start_idx = 0
        if total_h > avail_h:
            # Find the best start_idx: try each possible start, pick the one showing selected + most buttons
            best_count = -1
            best_start = 0
            for s in range(num_btns):
                y = y_start
                count = 0
                has_sel = False
                for i in range(s, num_btns):
                    if y + pre_heights[i] > y_start + avail_h:
                        break
                    if i == selected_idx:
                        has_sel = True
                    count += 1
                    y += pre_heights[i] + 8
                if has_sel and count > best_count:
                    best_count = count
                    best_start = s
            start_idx = best_start

        y = y_start
        for i in range(start_idx, num_btns):
            dec = decisions[i]
            wrapped, actual_lines, num_lines = pre_wrapped[i]
            btn_h = pre_heights[i]
            is_selected = (i == selected_idx)

            if y + btn_h > self.screen_height - 20 - 5:
                break

            bg = self.colorPanelL if is_selected else self.colorPanel
            border = self.colorAccent if is_selected else self.colorBg2
            txt_color = self.colorText if is_selected else self.colorTextMuted

            self.draw_rectangle_r([x, y, x + btn_w, y + btn_h], 8, fill=bg, outline=border)

            self.draw_circle([x + 20, y + btn_h // 2 - 12], 24, fill=border)
            num_color = self.colorBg2 if is_selected else self.colorAccent
            self.draw_text((x + 32, y + btn_h // 2), str(i + 1), font=18, color=num_color, anchor="mm")

            if actual_lines == 1:
                self.draw_text((x + 55, y + btn_h // 2), wrapped[0], font=self.font_size_text, color=txt_color, anchor="lm")
            else:
                for li, line in enumerate(wrapped[:3]):
                    self.draw_text((x + 55, y + 10 + li * (self.font_size_text + 5)), line, font=self.font_size_text, color=txt_color, anchor="la")

            y += btn_h + 8

        if total_h > avail_h and pre_heights:
            bar_x = self.screen_width - 16
            bar_y = y_start
            bar_h = avail_h - 14
            scroll_px = sum(pre_heights[:start_idx]) + 8 * max(0, start_idx)
            pct = min(1, scroll_px / max(1, total_h - avail_h))
            thumb_h = max(8, int(bar_h * avail_h / total_h))
            thumb_y = bar_y + int((bar_h - thumb_h) * pct)
            self.draw_rectangle_r([bar_x - 4, bar_y, bar_x, bar_y + bar_h], 2, fill=self.colorBg2)
            self.draw_rectangle_r([bar_x - 4, thumb_y, bar_x, thumb_y + thumb_h], 2, fill=self.colorAccent)

        self.draw_text((40, self.screen_height - 20), sel_text, font=14, color=self.colorTextMuted, anchor="lm")

        if sel2_text:
            self.draw_text((170, self.screen_height - 20), sel2_text, font=14, color=self.colorTextMuted, anchor="lm")
        self.draw_text((420, self.screen_height - 20), scroll_text, font=14, color=self.colorTextMuted, anchor="mm")
        self.draw_text((self.screen_width - 40, self.screen_height - 20), exit_text, font=14, color=self.colorAccent, anchor="rm")

    def draw_tts_indicator(self, loading=False, active=False, paused=False, done=False):
        if loading:
            self._tts_blink = not self._tts_blink
            if self._tts_blink:
                self.draw_circle([self.screen_width - 18, 8], 10, fill=self.colorOrange)
            else:
                self.draw_circle([self.screen_width - 18, 8], 10, outline=self.colorOrange)
        elif paused:
            self.draw_circle([self.screen_width - 18, 8], 10, fill=self.colorYellow)
        elif active:
            self.draw_circle([self.screen_width - 18, 8], 10, fill=self.colorGreen)
        elif done:
            self.draw_circle([self.screen_width - 18, 8], 10, fill=self.colorRed)
        else:
            self.draw_circle([self.screen_width - 18, 8], 10, fill=(0, 0, 0, 0))

    def draw_loading(self, message, please_wait_text="Please wait", dots=0, version="", hint=""):
        self.draw_background()
        self.draw_rectangle_r([100, self.screen_height // 2 - 40, self.screen_width - 100, self.screen_height // 2 + 40], 10, fill=self.colorPanel, outline=self.colorBlueD1)
        spinner = "." * (dots % 4)
        self.draw_text((self.screen_width // 2, self.screen_height // 2), message + spinner, font=20, color=self.colorText, anchor="mm")
        self.draw_text((self.screen_width // 2, self.screen_height // 2 + 30), please_wait_text, font=14, color=self.colorTextMuted, anchor="mm")
        if hint:
            self.draw_text((self.screen_width - 100 - 12, self.screen_height // 2 + 40 - 10), hint, font=14, color=self.colorTextMuted, anchor="rb")
        if version:
            self.draw_text((5, self.screen_height - 5), version, font=11, color=self.colorTextMuted, anchor="lb")

    def draw_error(self, message, raw_response="", scroll_offset=0, retry_text="A:Retry", back_text="B:Back", log_text="SEL:Log", version=""):
        self.draw_clear()
        if raw_response:
            full_text = message + "\n\n--- Raw Response ---\n" + raw_response
        else:
            full_text = message
        lines = self._wrap_text(full_text, font=14, max_width=self.screen_width - 180)
        total = len(lines)
        line_h = 17
        title_area = 50
        hint_area = 45
        pad = 20
        if raw_response or total > 5:
            box_top = 60
            box_bot = self.screen_height - 60
        else:
            content_h = total * line_h
            needed = title_area + content_h + hint_area + pad * 2
            box_top = max(10, (self.screen_height - needed) // 2)
            box_bot = box_top + needed
        self.draw_rectangle_r([80, box_top, self.screen_width - 80, box_bot], 10, fill="#1a0000", outline=self.colorRed)
        self.draw_text((self.screen_width // 2, box_top + 25), "Error", font=22, color=self.colorRed, anchor="mm")
        text_top = box_top + title_area
        text_bot = box_bot - hint_area
        text_h = text_bot - text_top
        max_visible = max(1, text_h // line_h)
        clamped = max(0, min(scroll_offset, max(0, total - max_visible)))
        visible = lines[clamped:clamped + max_visible]
        for i, line in enumerate(visible):
            self.draw_text((self.screen_width // 2, text_top + i * line_h), line, font=14, color=self.colorText, anchor="mm")
        if total > max_visible:
            pct = clamped / max(1, total - max_visible)
            bar_x = self.screen_width - 95
            bar_h = text_h
            thumb_h = max(8, int(bar_h / total * max_visible))
            thumb_y = text_top + int((bar_h - thumb_h) * pct)
            self.draw_rectangle_r([bar_x, text_top, bar_x + 4, text_top + bar_h], 2, fill=self.colorBg2)
            self.draw_rectangle_r([bar_x, thumb_y, bar_x + 4, thumb_y + thumb_h], 2, fill=self.colorAccent)
        hint_y = box_bot - 22
        self.draw_text((self.screen_width // 2 - 100, hint_y), back_text, font=13, color=self.colorTextMuted, anchor="mm")
        self.draw_text((self.screen_width // 2, hint_y), log_text, font=13, color=self.colorTextMuted, anchor="mm")
        self.draw_text((self.screen_width // 2 + 100, hint_y), retry_text, font=13, color=self.colorAccent, anchor="mm")
        if version:
            self.draw_text((5, self.screen_height - 5), version, font=11, color=self.colorTextMuted, anchor="lb")

    def draw_boot_screen(self, title="Story Weaver", subtitle="An AI Adventure Game", prompt="Press A to start", version=""):
        self.draw_background()
        self.draw_rectangle_r([50, self.screen_height // 2 - 60, self.screen_width - 50, self.screen_height // 2 + 60], 15, fill=self.colorPanel, outline=self.colorAccent)
        self.draw_text((self.screen_width // 2, self.screen_height // 2 - 30), title, font=28, color=self.colorAccent, anchor="mm")
        self.draw_text((self.screen_width // 2, self.screen_height // 2 + 10), subtitle, font=18, color=self.colorTextMuted, anchor="mm")
        if prompt:
            self.draw_text((self.screen_width // 2, self.screen_height // 2 + 45), prompt, font=16, color=self.colorText, anchor="mm")
        if version:
            self.draw_text((5, self.screen_height - 5), version, font=16, color=self.colorTextMuted, anchor="lb")
        self.draw_text((self.screen_width - 5, self.screen_height - 5), "Copyright Nabil Redmann 2026", font=16, color=self.colorTextMuted, anchor="rb")

    def draw_log_overlay(self, log_lines, scroll_offset=0, max_lines=21, close_text="B/SEL:Close", clear_text=""):
        overlay = Image.new("RGBA", (self.screen_width, self.screen_height), (0, 0, 0, 200))
        self.active_image.paste(overlay, (0, 0), overlay)
        self.draw_rectangle_r([20, 20, self.screen_width - 20, self.screen_height - 20], 10, fill="#0a0a1a", outline=self.colorBlueD1)
        self.draw_text((self.screen_width // 2, 35), "Event Log", font=20, color=self.colorAccent, anchor="mm")

        total = len(log_lines)
        if total == 0:
            visible = []
        else:
            max_offset = max(0, total - max_lines)
            scroll_offset = max(0, min(scroll_offset, max_offset))
            visible = log_lines[scroll_offset:scroll_offset + max_lines]

        avail_y = self.screen_height - 50 - 55
        avail_lines = max(1, avail_y // 18)
        entry_vis = []
        trimmed = []
        for raw in visible:
            wrapped = self._wrap_text(raw, font=13, max_width=self.screen_width - 60)
            entry_vis.append(len(wrapped))
        total_vis = 0
        for i, cnt in enumerate(entry_vis):
            if total_vis + cnt <= avail_lines:
                trimmed.append(i)
                total_vis += cnt
        visible = [visible[i] for i in trimmed]

        y = 55
        for raw_line in visible:
            wrapped = self._wrap_text(raw_line, font=13, max_width=self.screen_width - 60)
            for wl in wrapped:
                self.draw_text((30, y), wl, font=13, color=self.colorTextMuted)
                y += 18

        sw = self.screen_width
        if total > max_lines:
            page_end = min(scroll_offset + max_lines, total)
            pct = (scroll_offset / max(1, total - max_lines)) * 100
            info = f"DY:Scroll  {scroll_offset+1}-{page_end}/{total}  DX:Page"
            self.draw_text((sw // 2, self.screen_height - 30), info, font=14, color=self.colorTextMuted, anchor="mm")
        if clear_text:
            self.draw_text((30, self.screen_height - 30), clear_text, font=14, color=self.colorTextMuted, anchor="lm")
        self.draw_text((sw - 35, self.screen_height - 30), close_text, font=14, color=self.colorAccent, anchor="rm")

    def _wrap_text(self, text, font=16, max_width=None):
        if max_width is None:
            max_width = self.screen_width - 40
        font_obj = ImageFont.truetype(font_file, font)
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            bbox = font_obj.getbbox(test_line)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    def _wrap_text_to_height(self, text, font_obj, max_width, max_height):
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            bbox = font_obj.getbbox(test_line)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        result = []
        total_h = 0
        for line in lines:
            bbox = font_obj.getbbox(line)
            lh = bbox[3] - bbox[1] + 4
            if total_h + lh > max_height:
                break
            result.append(line)
            total_h += lh
        return result

    def button_circle(self, pos, button, text, color=None):
        c = color or self.colorBlueD1
        self.draw_circle(pos, 25, fill=c)
        self.draw_text((pos[0] + 12, pos[1] + 12), button, anchor="mm")
        self.draw_text((pos[0] + 30, pos[1] + 12), text, font=19, anchor="lm")

    def button_rectangle(self, pos, button, text):
        self.draw_rectangle_r(
            (pos[0], pos[1], pos[0] + 60, pos[1] + 25), 5, fill=self.colorGrayL1
        )
        self.draw_text((pos[0] + 30, pos[1] + 12), button, anchor="mm")
        self.draw_text((pos[0] + 65, pos[1] + 12), text, font=19, anchor="lm")

    def display_image(self, image_path, target_x=0, target_y=0, target_width=None, target_height=None):
        if target_width is None:
            target_width = self.screen_width
        if target_height is None:
            target_height = self.screen_height
        try:
            img = Image.open(image_path)
            img = img.resize((target_width, target_height), Image.LANCZOS)
            self.active_image.paste(img, (target_x, target_y))
        except Exception:
            pass

    def draw_theme_detail(self, theme, header_path=None, start_text="A:Start", back_text="B:Back", direct_hint="START:Go!", fav_text="X:Fav", is_fav=False, desc_scroll_offset=0, step_count=None):
        overlay = Image.new("RGBA", (self.screen_width, self.screen_height), (0, 0, 0, 200))
        self.active_image.paste(overlay, (0, 0), overlay)

        box_w = 500
        box_h = 360
        bx = (self.screen_width - box_w) // 2
        by = (self.screen_height - box_h) // 2
        self.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=self.colorPanel, outline=self.colorBlueD1)

        img_x = bx + 11
        img_w = box_w - 22
        img_y = by + 15

        if header_path and os.path.exists(header_path):
            try:
                header_img = Image.open(header_path).convert("RGBA")
                h_ratio = img_w / header_img.width
                img_h = int(header_img.height * h_ratio)
                header_img = header_img.resize((img_w, img_h), Image.LANCZOS)
                self.active_image.paste(header_img, (img_x, img_y), header_img)
            except Exception:
                self.draw_rectangle_r([img_x, img_y, img_x + img_w, img_y + 80], 6, fill=self.colorBg2)
                img_h = 80
        else:
            self.draw_rectangle_r([img_x, img_y, img_x + img_w, img_y + 80], 6, fill=self.colorBg2)
            img_h = 80

        if step_count is not None and step_count > 0:
            badge_x = img_x
            badge_y = img_y
            bw = 44
            bh = 30
            cut = 12
            overlay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.polygon([(0, 0), (bw, 0), (bw - cut, bh), (0, bh)], fill=(0, 0, 0, 200))
            self.active_image.paste(overlay, (badge_x, badge_y), overlay)
            self.draw_text((badge_x + bw // 2 - cut // 2, badge_y + bh // 2), str(step_count), font=24, color=self.colorAccent, anchor="mm")

        title_y = img_y + img_h + 40
        title = theme.get("caption", "")
        title_lines = self._wrap_text(title, font=22, max_width=box_w - 40)
        for i, line in enumerate(title_lines):
            self.draw_text((self.screen_width // 2, title_y + i * 26), line, font=22, color=self.colorAccent, anchor="mm")
        title_h = len(title_lines) * 26

        desc = theme.get("description", "")
        desc_lines = self._wrap_text(desc, font=self.font_size_text, max_width=img_w)
        desc_y_start = title_y + title_h + 12
        line_h = self.font_size_text + 4
        desc_area_bot = by + box_h - 20
        max_visible = max(1, (desc_area_bot - desc_y_start) // line_h)
        total = len(desc_lines)
        if total > max_visible:
            scroll_img_w = img_w - 18
            desc_lines = self._wrap_text(desc, font=self.font_size_text, max_width=scroll_img_w)
            total = len(desc_lines)
            max_visible = max(1, (desc_area_bot - desc_y_start) // line_h)
        scroll_offset = max(0, min(desc_scroll_offset, max(0, total - max_visible)))
        visible = desc_lines[scroll_offset:scroll_offset + max_visible]
        for i, line in enumerate(visible):
            self.draw_text((self.screen_width // 2, desc_y_start + i * line_h), line, font=self.font_size_text, color=self.colorText, anchor="mm")

        if total > max_visible:
            bar_x = bx + box_w - 12
            bar_y = desc_y_start - self.font_size_text // 2
            bar_h = (max_visible - 1) * line_h + self.font_size_text
            pct = scroll_offset / max(1, total - max_visible)
            thumb_h = max(8, int(bar_h * max_visible / total))
            thumb_y = bar_y + int((bar_h - thumb_h) * pct)
            self.draw_rectangle_r([bar_x - 4, bar_y, bar_x, bar_y + bar_h], 2, fill=self.colorBg2)
            self.draw_rectangle_r([bar_x - 4, thumb_y, bar_x, thumb_y + thumb_h], 2, fill=self.colorAccent)

        if is_fav:
            star_pos = (bx + box_w - 26, by + 30)
            for ox, oy in ((-1,-1),(-1,1),(1,-1),(1,1)):
                self.draw_text((star_pos[0] + ox, star_pos[1] + oy), "★", font=22, color="#000000", anchor="mm")
            self.draw_text(star_pos, "★", font=22, color=self.colorYellow, anchor="mm")

        hint_y = by + box_h - 10
        self.draw_text((bx + 70, hint_y), start_text, font=14, color=self.colorTextMuted, anchor="mm")
        self.draw_text((self.screen_width // 2, hint_y), back_text, font=14, color=self.colorTextMuted, anchor="mm")
        self.draw_text((bx + box_w - 70, hint_y), fav_text, font=14, color=self.colorAccent, anchor="mm")
        return scroll_offset

    def draw_compacting_hint(self, text="Bitte warten - Komprimiere"):
        bar_h = 28
        bar_y = self.screen_height - bar_h
        self.draw_rectangle([0, bar_y, self.screen_width, self.screen_height], fill="#2a1a00", outline="#cc8800")
        self.draw_text((self.screen_width // 2, bar_y + bar_h // 2), text, font=14, color="#ffaa00", anchor="mm")

    def get_text_width(self, text, font):
        image = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(image)
        font_obj = ImageFont.truetype(font_file, font)
        bbox = draw.textbbox((0, 0), text, font=font_obj)
        return bbox[2] - bbox[0]
