import json
import os
import platform
import ssl
import time
import threading
import urllib.request
import urllib.parse
import input
from PIL import Image

_SERVER_URL = "https://storyweaver.zeugs.me/config"

# Disable SSL certificate verification, because the AMBERNIC devices do not update their date/time correctly on start
# Having the device turned off 3 months, and the it might not be able to connect to the servers anymore
_insecure_ssl_ctx = ssl.create_default_context()
_insecure_ssl_ctx.check_hostname = False
_insecure_ssl_ctx.verify_mode = ssl.CERT_NONE


def _user_agent():
    return "Mozilla/5.0 ({sys} {arch}) StoryWeaver/online_config".format(
        sys=platform.system(), arch=platform.machine()
    )


def _multipart_encode(fields, files):
    boundary = "----WebKitFormBoundary" + str(time.time()).replace(".", "")
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    for field_name, (file_name, content) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{file_name}"\r\n'.encode())
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return body, boundary


def _http_post(url, data=None, headers=None, binary=False):
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", _user_agent())
    if data is not None and not binary:
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_insecure_ssl_ctx) as resp:
            return resp.read().decode("utf-8"), None
    except Exception as e:
        return None, str(e)


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_insecure_ssl_ctx) as resp:
            return resp.read().decode("utf-8"), None
    except Exception as e:
        return None, str(e)


def _http_delete(url):
    req = urllib.request.Request(url, method="DELETE", headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_insecure_ssl_ctx) as resp:
            return resp.read().decode("utf-8"), None
    except Exception as e:
        return None, str(e)


def upload_config(config_path, ai_path, profile_dir, log_path="", screenshot_dir="", existing_id=""):
    fields = {}
    files = {}

    if existing_id:
        fields["id"] = existing_id

    if os.path.exists(config_path):
        with open(config_path, "rb") as f:
            files["config.json"] = ("config.json", f.read())
    default_path = config_path + ".default"
    if os.path.exists(default_path):
        with open(default_path, "rb") as f:
            files["config.json.default"] = ("config.json.default", f.read())
    if os.path.exists(ai_path):
        with open(ai_path, "rb") as f:
            files["config.ai.json"] = ("config.ai.json", f.read())
    ai_default = ai_path + ".default"
    if os.path.exists(ai_default):
        with open(ai_default, "rb") as f:
            files["config.ai.json.default"] = ("config.ai.json.default", f.read())
    if os.path.isdir(profile_dir):
        for fn in os.listdir(profile_dir):
            if fn.endswith(".json"):
                fp = os.path.join(profile_dir, fn)
                if os.path.isfile(fp):
                    with open(fp, "rb") as fh:
                        data = fh.read()
                    files[f"profiles/{fn}"] = (f"profiles/{fn}", data)
    if log_path and os.path.exists(log_path):
        with open(log_path, "rb") as f:
            files["log.txt"] = ("log.txt", f.read())
    if screenshot_dir and os.path.isdir(screenshot_dir):
        screenshot_files = []
        for fn in sorted(os.listdir(screenshot_dir)):
            if fn.endswith(".png"):
                fp = os.path.join(screenshot_dir, fn)
                if os.path.isfile(fp):
                    with open(fp, "rb") as fh:
                        files[fn] = (fn, fh.read())
                        screenshot_files.append(fn)
        if screenshot_files:
            fields["screenshots"] = "|".join(screenshot_files)

    body, boundary = _multipart_encode(fields, files)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    raw, err = _http_post(_SERVER_URL, data=bytes(body), headers=headers, binary=True)
    if err:
        return None, err
    try:
        data = json.loads(raw)
        sid = data.get("id")
        return sid, "https://sw.zeugs.me/c/" + sid if sid else None
    except Exception as e:
        return None, str(e)


def poll_status(session_id):
    url = f"{_SERVER_URL}/{session_id}"
    raw, err = _http_get(url)
    if err:
        return None, err
    try:
        data = json.loads(raw)
        return data, None
    except Exception as e:
        return None, str(e)


def download_edited(session_id):
    url = f"{_SERVER_URL}/{session_id}?download=1"
    raw, err = _http_get(url)
    if err:
        return None, err
    try:
        return json.loads(raw), None
    except Exception as e:
        return None, str(e)


def cancel_edit(session_id):
    url = f"{_SERVER_URL}/{session_id}"
    raw, err = _http_delete(url)
    return err is None, err


def show_dialog(gr, translator, session_id, short_url, version="", on_music_toggle=None, on_tts_toggle=None):
    """Blocking loop showing waiting dialog. Returns 'done', 'cancelled', 'preserved', or None."""
    dots = 0
    _backup = gr.active_image.copy()
    while True:
        input.check()
        if input.key("B"):
            cancel_edit(session_id)
            return None

        if input.key("X"):
            return "preserved"

        if input.key("Y") and on_music_toggle:
            on_music_toggle()
        if input.key("JOYSTICK") and on_tts_toggle:
            on_tts_toggle()

        gr.active_image.paste(_backup, (0, 0))
        overlay = Image.new("RGBA", (gr.screen_width, gr.screen_height), (0, 0, 0, 180))
        gr.active_image.paste(overlay, (0, 0), overlay)

        box_w = 420
        box_h = 180
        bx = (gr.screen_width - box_w) // 2
        by = (gr.screen_height - box_h) // 2

        gr.draw_rectangle_r([bx, by, bx + box_w, by + box_h], 10, fill=gr.colorPanel, outline=gr.colorBlueD1)

        wait_text = translator.translate("Waiting for saving the file")
        label_text = "\u00d6ffne URL im Browser zum Bearbeiten:"
        short = short_url.replace("https://", "")
        d = "." * (dots % 6)
        gr.draw_text((gr.screen_width // 2, by + 32), wait_text + d, font=18, color=gr.colorAccent, anchor="mm")
        gr.draw_text((gr.screen_width // 2, by + 62), label_text, font=14, color=gr.colorTextMuted, anchor="mm")
        gr.draw_text((gr.screen_width // 2, by + 96), short, font=28, color=gr.colorBlueD1, anchor="mm")
        gr.draw_text((bx + 14, by + box_h - 14), "X:Vorr\u00fcbergehend schlie\u00dfen", font=14, color=gr.colorAccent, anchor="lm")
        gr.draw_text((bx + box_w - 14, by + box_h - 14), "B:" + translator.translate("Cancel"), font=14, color=gr.colorAccent, anchor="rm")
        if version:
            gr.draw_text((5, gr.screen_height - 5), version, font=11, color=gr.colorTextMuted, anchor="lb")
        gr.draw_paint()

        data, err = poll_status(session_id)
        if data:
            st = data.get("status")
            if st == "done":
                return ("done", data.get("preserved", False))
            if st == "cancelled":
                return "cancelled"

        dots += 1
        time.sleep(2)
