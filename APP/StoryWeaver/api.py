import hashlib
import json
import os
import re
import base64
import ssl
import struct
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

# Disable SSL certificate verification, because the AMBERNIC devices do not update their date/time correctly on start
# Having the device turned off 3 months, and the it might not be able to connect to the servers anymore
_insecure_ssl_ctx = ssl.create_default_context()
_insecure_ssl_ctx.check_hostname = False
_insecure_ssl_ctx.verify_mode = ssl.CERT_NONE

script_dir = os.path.dirname(os.path.abspath(__file__))

class ApiClient:
    def __init__(self, config, version="", log_file=""):
        self.config = config
        self.version = version
        self.base_url = config.get("ai", {}).get("base_url", "")
        self.text_base_url = config.get("ai", {}).get("text_base_url", "")
        self.api_key = config.get("ai", {}).get("api_key", "")
        self.story_model = config["models"]["story"]
        self.image_model = config["models"]["image"]
        self.bezels_model = config.get("models", {}).get("image_bezels", self.image_model)
        self.speech_model = config["models"]["speech"]
        self.speech_voice = config["speech"]["voice"]
        self.speech_speed = config["speech"]["speed"]
        self.speech_system_prompt_openaiaudio = config.get("speech", {}).get("system_prompt_openaiaudio", "Read the following text aloud verbatim. Speak only the provided text, nothing else.")
        self.story_prompt_style = config["story"]["prompt_style"]
        self.image_prompt_style = config["image"]["prompt_style"]
        self.story_system_prompt = config["story"]["system_prompt"]
        self.story_prompt = config["story"]["prompt"]
        self.prompt_custom_story_addition = config.get("promptCustomStoryAddition", "")
        self.prompt_custom_theme_addition = config.get("promptCustomThemeAddition", "")
        self.compact_at = config.get("story", {}).get("compactAt", 20)
        self.compact_prompt = config.get("story", {}).get("compact_prompt", "")
        _models = config.get("models", {})
        def _mt(raw, default):
            return None if raw is None or raw == "" or raw == 0 else int(raw)
        self.theme_max_tokens = _mt(_models.get("theme_maxTokens", 2000), 2000)
        self.story_max_tokens = _mt(_models.get("story_maxTokens", 1500), 1500)
        self.compact_max_tokens = _mt(_models.get("compact_maxTokens", 1000), 1000)
        self._last_finish_reason = ""
        self._last_usage = {}
        self.theme_system_prompt = config["themes"]["system_prompt"]
        self.theme_prompt = config["themes"]["prompt"]
        self.debug_log = log_file
        self.dump_enabled = config.get("debug", {}).get("dumpStoryCurrentHistoryCalls", False)
        self.dump_prefix = ""

    def _headers(self, content_type=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": f"Mozilla/5.0 (X11; Linux aarch64) StoryWeaver/{self.version}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _log_debug(self, message):
        self._log(message)

    def _mask_key(self, text):
        key = self.api_key
        if key and len(key) > 8:
            return text.replace(key, key[:4] + "..." + key[-4:])
        return text

    def _request(self, url, data=None, method=None):
        req = urllib.request.Request(url, data=data, method=method)
        ctype = "application/json" if data else None
        for k, v in self._headers(content_type=ctype).items():
            req.add_header(k, v)

        safe_headers = {k: self._mask_key(v) for k, v in req.headers.items()}
        self._log_debug(f"--- REQUEST {method} {url} ---")
        self._log_debug(f"Headers: {safe_headers}")
        if data:
            self._log_debug(f"Body: {self._mask_key(data.decode())}")

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60, context=_insecure_ssl_ctx) as resp:
                body = resp.read()
                elapsed = int((time.time() - t0) * 1000)
                resp_headers = dict(resp.headers)
                safe_headers = {k: self._mask_key(str(v)) for k, v in resp_headers.items()}
                self._log_debug(f"--- RESPONSE {resp.status} ({elapsed}ms) ---")
                self._log_debug(f"Headers: {safe_headers}")
                self._log_debug(f"Body: {body.decode(errors='replace')}")
                return body
        except urllib.error.HTTPError as e:
            elapsed = int((time.time() - t0) * 1000)
            error_body = e.read().decode(errors='replace')
            error_headers = dict(e.headers)
            safe_headers = {k: self._mask_key(str(v)) for k, v in error_headers.items()}
            self._log_debug(f"--- ERROR {e.code} ({elapsed}ms) ---")
            self._log_debug(f"Headers: {safe_headers}")
            self._log_debug(f"Body: {error_body}")
            self._log(f"HTTP Error {e.code}: {error_body}")
            raise
        except urllib.error.URLError as e:
            elapsed = int((time.time() - t0) * 1000)
            self._log_debug(f"--- URL ERROR ({elapsed}ms) ---")
            self._log_debug(f"Reason: {e.reason}")
            self._log(f"URL Error: {e.reason}")
            raise

    def generate_themes(self, language="en_US", cachebuster_value=None):
        system_prompt = self.theme_system_prompt
        user_prompt = self.theme_prompt.format(
            story=SimpleNamespace(prompt_style=self.story_prompt_style),
            image=SimpleNamespace(prompt_style=self.image_prompt_style),
            language=language,
            promptCustomThemeAddition=self.prompt_custom_theme_addition,
        )

        body_dict = {
            "model": self.story_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.8,
        }
        if self.theme_max_tokens is not None:
            body_dict["max_tokens"] = self.theme_max_tokens
        body = json.dumps(body_dict).encode()

        url = f"{self.base_url}/v1/chat/completions"
        if cachebuster_value:
            url += f"?cachebuster={cachebuster_value}"
        resp_data = self._request(url, data=body, method="POST")
        resp_json = json.loads(resp_data)
        self._last_finish_reason = resp_json["choices"][0].get("finish_reason", "")
        self._last_usage = resp_json.get("usage", {})
        content = resp_json["choices"][0]["message"]["content"]

        themes = self._parse_themes_xml(content)
        return themes

    def _parse_themes_xml(self, content):
        themes = []
        xml_str = self._extract_xml(content, "themes")
        if not xml_str:
            self._log("No valid <themes> XML found in response")
            return themes

        try:
            root = ET.fromstring(xml_str)
            for theme_elem in root.findall("theme"):
                tid = theme_elem.get("id", "0")
                caption = self._get_elem_text(theme_elem, "caption")
                description = self._get_elem_text(theme_elem, "description")
                ip_elem = theme_elem.find("image-prompt")
                image_prompt = ip_elem.text.strip() if ip_elem is not None and ip_elem.text else ""
                hash_input = (caption + description + image_prompt).encode()
                ip_hash = hashlib.md5(hash_input).hexdigest()[:12]
                if caption:
                    themes.append({
                        "id": tid,
                        "caption": caption,
                        "description": description,
                        "image_prompt": image_prompt,
                        "hash": ip_hash,
                    })
        except ET.ParseError as e:
            self._log(f"XML parse error: {e}")

        return themes

    def set_dump_prefix(self, prefix):
        self.dump_prefix = prefix

    def dump_compact_event(self, stats, summary):
        if not self.dump_enabled:
            return
        import datetime as _dt
        app_dir = os.path.dirname(self.debug_log) if self.debug_log else ""
        if not app_dir:
            return
        prefix = self.dump_prefix + "_" if self.dump_prefix else ""
        dump_path = os.path.join(app_dir, "cache", f"{prefix}dump_current_history.json")
        entry = {
            "ts": _dt.datetime.now().isoformat(),
            "event": "compact",
            "compact_prompt": self.compact_prompt,
            "stats": stats,
            "summary": summary,
        }
        try:
            os.makedirs(os.path.dirname(dump_path), exist_ok=True)
            with open(dump_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
        except Exception:
            pass

    def _dump_story_event(self, event_type, attempt, messages=None, raw_content=None, parsed=None):
        if not self.dump_enabled:
            return
        import datetime as _dt
        app_dir = os.path.dirname(self.debug_log) if self.debug_log else ""
        if not app_dir:
            return
        prefix = self.dump_prefix + "_" if self.dump_prefix else ""
        dump_path = os.path.join(app_dir, "cache", f"{prefix}dump_current_history.json")
        entry = {
            "ts": _dt.datetime.now().isoformat(),
            "event": event_type,
            "attempt": attempt,
        }
        if messages is not None:
            entry["messages"] = messages
        if raw_content is not None:
            entry["raw_content"] = raw_content
        if parsed is not None:
            entry["parsed"] = parsed
        try:
            os.makedirs(os.path.dirname(dump_path), exist_ok=True)
            with open(dump_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
        except Exception:
            pass

    def format_story_prompt(self, language):
        return self.story_prompt.format(
            story=SimpleNamespace(prompt_style=self.story_prompt_style),
            image=SimpleNamespace(prompt_style=self.image_prompt_style),
            language=language,
            promptCustomStoryAddition=self.prompt_custom_story_addition,
        )

    def generate_story(self, messages):
        system_prompt = self.story_system_prompt
        retry_prompt = self.config.get("story", {}).get("retry_prompt", "")

        url = f"{self.base_url}/v1/chat/completions"

        extra_messages = []

        for attempt in range(1, 5):
            if attempt == 2:
                extra_messages = [{"role": "system", "content": retry_prompt}]
            elif attempt == 3:
                extra_messages = [
                    {"role": "system", "content": retry_prompt},
                    {"role": "system", "content": system_prompt},
                ]
            elif attempt == 4:
                extra_messages = [
                    {"role": "system", "content": retry_prompt},
                    {"role": "system", "content": system_prompt},
                    {"role": "system", "content": "Why are you not returning the story XML?"},
                ]

            chat_messages = list(messages) + extra_messages

            self._dump_story_event("story_req", attempt, messages=chat_messages)

            body_dict = {
                "model": self.story_model,
                "messages": chat_messages,
                "temperature": 0.8,
            }
            if self.story_max_tokens is not None:
                body_dict["max_tokens"] = self.story_max_tokens
            body = json.dumps(body_dict).encode()

            resp_data = self._request(url, data=body, method="POST")
            resp_json = json.loads(resp_data)
            self._last_finish_reason = resp_json["choices"][0].get("finish_reason", "")
            self._last_usage = resp_json.get("usage", {})
            content = resp_json["choices"][0]["message"]["content"]

            result = self._parse_story_xml(content)
            result["raw_content"] = content

            self._dump_story_event("story_resp", attempt, raw_content=content, parsed=result)
            self._log(f"Generating Story (attempt {attempt}): text={len(result.get('text',''))} chars, {len(result.get('decisions',[]))} decisions", debug=True)

            if result["text"] and result["decisions"]:
                return result

            if attempt < 4:
                self._log(f"Story generation attempt {attempt} returned no text or no decisions, retrying...")
                time.sleep(1)
            else:
                self._log(f"Story generation failed after 4 attempts")
                if not content or not content.strip():
                    self._last_raw_response = f'The "{self.story_model}" rejected to respond with any text.'
                    raise Exception(f'Story API returned empty response — the "{self.story_model}" rejected to respond')
                else:
                    self._last_raw_response = content
                    trimmed = content[:500] + "..." if len(content) > 500 else content
                    raise Exception(f"Story API returned invalid response (no XML): {trimmed}")

    def compact_history(self, messages, language="en_US"):
        compact_prompt = self.compact_prompt
        user_messages = [m for m in messages if m["role"] != "system"]

        body_dict = {
            "model": self.story_model,
            "messages": [
                {"role": "system", "content": compact_prompt},
                *user_messages,
            ],
            "temperature": 0.5,
        }
        if self.compact_max_tokens is not None:
            body_dict["max_tokens"] = self.compact_max_tokens
        body = json.dumps(body_dict).encode()

        url = f"{self.base_url}/v1/chat/completions"
        resp_data = self._request(url, data=body, method="POST")
        resp_json = json.loads(resp_data)
        content = resp_json["choices"][0]["message"]["content"]
        self._log(f"compact_history: got {len(content)} chars of compacted text")
        return content

    def _log(self, message, debug=False):
        prefix = "[API DEBUG] " if debug else "[API] "
        print(f"{prefix}{message}")
        if self.debug_log:
            try:
                with open(self.debug_log, "a", encoding="utf-8") as f:
                    f.write(f"{prefix}{message}\n")
            except Exception:
                pass

    def _parse_story_xml(self, content):
        result = {
            "text": "",
            "decisions": [],
            "image_prompt": "",
            "hash": "",
        }

        xml_str = self._extract_xml(content, "story")
        if not xml_str:
            self._log("No valid <story> XML found in response")
            return result

        try:
            root = ET.fromstring(xml_str)

            text_elem = root.find("text")
            if text_elem is not None and text_elem.text:
                result["text"] = text_elem.text.strip()

            decisions_elem = root.find("decisions")
            if decisions_elem is not None:
                for dec in decisions_elem.findall("decision"):
                    did = dec.get("id", "0")
                    dtext = dec.text.strip() if dec.text else ""
                    if dtext:
                        result["decisions"].append({"id": did, "text": dtext})

            ip_elem = root.find("image-prompt")
            if ip_elem is not None:
                if ip_elem.text:
                    result["image_prompt"] = ip_elem.text.strip()
                prompt_text = result["image_prompt"]
                result["hash"] = hashlib.md5(prompt_text.encode()).hexdigest()[:12] if prompt_text else ""

        except ET.ParseError as e:
            self._log(f"XML parse error: {e}")

        return result

    def _extract_xml(self, content, tag):
        pattern = f"<{tag}[\\s\\S]*?</{tag}>"
        match = re.search(pattern, content)
        if match:
            return match.group(0)
        return None

    def _get_elem_text(self, parent, tag):
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return ""

    def fetch_image(self, prompt, model=None, width=720, height=480, cache_dir=None, label=""):
        model = model or self.image_model
        encoded = urllib.parse.quote(prompt)
        url = f"{self.base_url}/image/{encoded}?model={model}&width={width}&height={height}&nologo=true"

        req = urllib.request.Request(url)
        for k, v in self._headers().items():
            req.add_header(k, v)

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120, context=_insecure_ssl_ctx) as resp:
                img_data = resp.read()
                elapsed = int((time.time() - t0) * 1000)
                if label:
                    self._log(f"{label} image loaded ({elapsed}ms)", debug=True)
                return img_data
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            self._log(f"{label} image fetch error ({elapsed}ms): {e}" if label else f"Image fetch error ({elapsed}ms): {e}")
            return None

    def fetch_image_with_reference(self, prompt, ref_image_url, model=None, width=720, height=480, label=""):
        model = model or self.bezels_model
        encoded = urllib.parse.quote(prompt)
        url = f"{self.base_url}/image/{encoded}?model={model}&width={width}&height={height}&nologo=true&image={urllib.parse.quote(ref_image_url)}"

        req = urllib.request.Request(url)
        for k, v in self._headers().items():
            req.add_header(k, v)

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120, context=_insecure_ssl_ctx) as resp:
                img_data = resp.read()
                elapsed = int((time.time() - t0) * 1000)
                if label:
                    self._log(f"{label} image loaded ({elapsed}ms)", debug=True)
                return img_data
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            self._log(f"{label} image fetch error ({elapsed}ms): {e}" if label else f"Image fetch error ({elapsed}ms): {e}")
            return None

    def cache_image(self, img_data, hash_str, cache_dir):
        if not img_data or not hash_str or not cache_dir:
            return None
        path = os.path.join(cache_dir, f"{hash_str}.png")
        try:
            with open(path, "wb") as f:
                f.write(img_data)
            return path
        except Exception as e:
            self._log(f"Cache write error: {e}")
            return None

    def get_cached_path(self, hash_str, cache_dir):
        if not hash_str or not cache_dir:
            return None
        path = os.path.join(cache_dir, f"{hash_str}.png")
        return path if os.path.exists(path) else None

    def _generate_speech_audio_api(self, text, cache_path=None):
        body = json.dumps({
            "model": self.speech_model,
            "input": text,
            "voice": self.speech_voice,
            "speed": self.speech_speed,
            "response_format": "wav",
        }).encode()

        url = f"{self.base_url}/v1/audio/speech"
        req = urllib.request.Request(url, data=body, method="POST")
        for k, v in self._headers(content_type="application/json").items():
            req.add_header(k, v)

        safe_headers = {k: self._mask_key(v) for k, v in req.headers.items()}
        self._log_debug(f"--- REQUEST POST {url} ---")
        self._log_debug(f"Headers: {safe_headers}")
        self._log_debug(f"Body: {self._mask_key(body.decode())}")

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120, context=_insecure_ssl_ctx) as resp:
                audio_data = resp.read()
                elapsed = int((time.time() - t0) * 1000)
                safe_resp_headers = {k: self._mask_key(str(v)) for k, v in dict(resp.headers).items()}
                self._log_debug(f"--- RESPONSE {resp.status} ({elapsed}ms) ---")
                self._log_debug(f"Headers: {safe_resp_headers}")
                self._log(f"Audio bytes: {len(audio_data)}", debug=True)
                if cache_path:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    with open(cache_path, "wb") as f:
                        f.write(audio_data)
                return audio_data
        except urllib.error.HTTPError as e:
            elapsed = int((time.time() - t0) * 1000)
            error_body = e.read().decode(errors='replace')
            error_headers = {k: self._mask_key(str(v)) for k, v in dict(e.headers).items()}
            self._log_debug(f"--- ERROR {e.code} ({elapsed}ms) ---")
            self._log_debug(f"Headers: {error_headers}")
            self._log_debug(f"Body: {error_body}")
            self._log(f"HTTP Error {e.code}: {error_body}")
            return None
        except urllib.error.URLError as e:
            elapsed = int((time.time() - t0) * 1000)
            self._log_debug(f"--- URL ERROR ({elapsed}ms) ---")
            self._log_debug(f"Reason: {e.reason}")
            self._log(f"URL Error: {e.reason}")
            return None

    def generate_speech(self, text, cache_path=None):
        if self.speech_model.startswith("openai-audio"):
            messages = [{"role": "user", "content": text}]
            if self.speech_system_prompt_openaiaudio:
                messages.insert(0, {"role": "system", "content": self.speech_system_prompt_openaiaudio})
            body_dict = {
                "model": self.speech_model,
                "messages": messages,
                "modalities": ["text", "audio"],
                "audio": {"format": "wav", "voice": self.speech_voice},
            }
            body = json.dumps(body_dict).encode()
            url = f"{self.base_url}/v1/chat/completions"
            req = urllib.request.Request(url, data=body, method="POST")
            for k, v in self._headers(content_type="application/json").items():
                req.add_header(k, v)
            safe_headers = {k: self._mask_key(v) for k, v in req.headers.items()}
            self._log_debug(f"--- REQUEST POST {url} ---")
            self._log_debug(f"Headers: {safe_headers}")
            self._log_debug(f"Body: {self._mask_key(body.decode())}")
            _chat = True
        else:
            body = json.dumps({
                "model": self.speech_model,
                "input": text,
                "voice": self.speech_voice,
                "speed": self.speech_speed,
                "response_format": "wav",
            }).encode()
            url = f"{self.base_url}/v1/audio/speech"
            req = urllib.request.Request(url, data=body, method="POST")
            for k, v in self._headers(content_type="application/json").items():
                req.add_header(k, v)
            safe_headers = {k: self._mask_key(v) for k, v in req.headers.items()}
            self._log_debug(f"--- REQUEST POST {url} ---")
            self._log_debug(f"Headers: {safe_headers}")
            self._log_debug(f"Body: {self._mask_key(body.decode())}")
            _chat = False

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120, context=_insecure_ssl_ctx) as resp:
                audio_data = resp.read()
                elapsed = int((time.time() - t0) * 1000)
                safe_resp_headers = {k: self._mask_key(str(v)) for k, v in dict(resp.headers).items()}
                self._log_debug(f"--- RESPONSE {resp.status} ({elapsed}ms) ---")
                self._log_debug(f"Headers: {safe_resp_headers}")
                self._log(f"Audio bytes: {len(audio_data)}", debug=True)
                if _chat:
                    resp_json = json.loads(audio_data)
                    audio_b64 = resp_json["choices"][0]["message"]["audio"]["data"]
                    audio_data = base64.b64decode(audio_b64)
                    if audio_data[:4] == b'RIFF':
                        idx = 12
                        while idx < len(audio_data) - 8:
                            ck_size = struct.unpack('<I', audio_data[idx+4:idx+8])[0]
                            if audio_data[idx:idx+4] == b'data':
                                audio_data = audio_data[:idx+4] + struct.pack('<I', len(audio_data) - idx - 8) + audio_data[idx+8:]
                                break
                            idx += 8 + ck_size
                        audio_data = audio_data[:4] + struct.pack('<I', len(audio_data) - 8) + audio_data[8:]
                    self._log(f"Decoded WAV from chat: {len(audio_data)} bytes", debug=True)
                if cache_path:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    if not cache_path.endswith(".wav"):
                        cache_path = cache_path.rsplit(".", 1)[0] + ".wav"
                    with open(cache_path, "wb") as f:
                        f.write(audio_data)
                return audio_data
        except urllib.error.HTTPError as e:
            elapsed = int((time.time() - t0) * 1000)
            error_body = e.read().decode(errors='replace')
            error_headers = {k: self._mask_key(str(v)) for k, v in dict(e.headers).items()}
            self._log_debug(f"--- ERROR {e.code} ({elapsed}ms) ---")
            self._log_debug(f"Headers: {error_headers}")
            self._log_debug(f"Body: {error_body}")
            self._log(f"HTTP Error {e.code}: {error_body}")
            return None
        except urllib.error.URLError as e:
            elapsed = int((time.time() - t0) * 1000)
            self._log_debug(f"--- URL ERROR ({elapsed}ms) ---")
            self._log_debug(f"Reason: {e.reason}")
            self._log(f"URL Error: {e.reason}")
            return None
