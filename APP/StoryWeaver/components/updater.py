import json
import os
import platform
import shutil
import ssl
import urllib.request
import zipfile
import time
import threading


_new_release_version = None

UPDATES_URL = "https://storyweaver.zeugs.me/updates"
DEFAULT_VERSION = "1.0.0.0"

# Disable SSL certificate verification, because the AMBERNIC devices do not update their date/time correctly on start
# Having the device turned off 3 months, and the it might not be able to connect to the servers anymore
_insecure_ssl_ctx = ssl.create_default_context()
_insecure_ssl_ctx.check_hostname = False
_insecure_ssl_ctx.verify_mode = ssl.CERT_NONE


def _user_agent(version=None):
    return "Mozilla/5.0 ({sys} {arch}) StoryWeaver/{ver}".format(
        sys=platform.system(), arch=platform.machine(), ver=version or DEFAULT_VERSION
    )


def _fetch_updates(timeout=10, version=None):
    req = urllib.request.Request(
        UPDATES_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": _user_agent(version),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_insecure_ssl_ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def new_release_version():
    return _new_release_version


def check_version(current_build, version=None):
    try:
        data = _fetch_updates(version=version)
        rel = data.get("releases", {})
        deb = data.get("debugs", {})
        rel_latest = rel.get("latest") or {}
        deb_latest = deb.get("latest") or {}
        result = {}
        if rel_latest.get("build"):
            result["release_ver"] = rel_latest["version"]
            result["release_build"] = rel_latest["build"]
            result["release_url"] = rel_latest["url"]
            result["newer_release"] = rel_latest["build"] > current_build
        else:
            result["release_ver"] = None
            result["release_build"] = 0
            result["newer_release"] = False
        if deb_latest.get("build"):
            result["debug_ver"] = deb_latest["version"]
            result["debug_build"] = deb_latest["build"]
            result["debug_url"] = deb_latest["url"]
            result["newer_debug"] = deb_latest["build"] > current_build
        else:
            result["debug_ver"] = None
            result["debug_build"] = 0
            result["newer_debug"] = False
        return result
    except Exception as e:
        return None


def start_background_check(current_build, set_label_func, log_func, done_callback=None, version=None):
    """Start async version check. set_label_func(str) updates the menu label."""
    t = threading.Thread(target=_run_check, args=(current_build, set_label_func, log_func, done_callback, version), daemon=True)
    t.start()


def _run_check(current_build, set_label, log, done_callback=None, version=None):
    global _new_release_version
    try:
        log("Update check started...")
        data = _fetch_updates(version=version)
        rel = data.get("releases", {})
        deb = data.get("debugs", {})
        rel_latest = rel.get("latest") or {}
        deb_latest = deb.get("latest") or {}

        rel_build = rel_latest.get("build", 0)
        deb_build = deb_latest.get("build", 0)

        newer_release = rel_latest.get("build") and rel_latest["build"] > current_build
        newer_debug = deb_latest.get("build") and deb_latest["build"] > current_build

        if newer_release or newer_debug:
            ver = rel_latest.get("version", "") if newer_release else deb_latest.get("version", "")
            set_label(f"Update (-> v{ver})")
            log(f"Update: newer version {ver} available (current build {current_build})")
            _new_release_version = rel_latest.get("version", "") if newer_release else None
        else:
            set_label("Update (up to date)")
            log(f"Update: up to date (build {current_build})")
            _new_release_version = None
    except Exception as e:
        log(f"Update check failed: {e}")
    finally:
        if done_callback:
            done_callback()


def do_update(url, script_dir, version=None):
    tmp_zip = os.path.join(script_dir, "cache", "_update.zip")
    config_path = os.path.join(script_dir, "config.json")
    bak_path = os.path.join(script_dir, "config.json.bak")
    ai_config_path = os.path.join(script_dir, "config.ai.json")
    ai_bak_path = os.path.join(script_dir, "config.ai.json.bak")
    install_root = os.path.dirname(script_dir)
    try:
        if os.path.exists(config_path):
            shutil.copy2(config_path, bak_path)
        if os.path.exists(ai_config_path):
            shutil.copy2(ai_config_path, ai_bak_path)
        os.makedirs(os.path.dirname(tmp_zip), exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": _user_agent(version)})
        with urllib.request.urlopen(req, context=_insecure_ssl_ctx) as resp:
            with open(tmp_zip, "wb") as out:
                shutil.copyfileobj(resp, out)
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(install_root)
        if os.path.exists(ai_bak_path):
            shutil.copy2(ai_bak_path, ai_config_path)
            os.remove(ai_bak_path)
        if os.path.exists(bak_path):
            try:
                with open(config_path) as f:
                    new_cfg = json.load(f)
                with open(bak_path) as f:
                    old_cfg = json.load(f)
                for k, v in old_cfg.items():
                    if k in new_cfg and not isinstance(v, dict):
                        new_cfg[k] = v
                with open(config_path, "w") as f:
                    json.dump(new_cfg, f, indent=4)
            except Exception:
                pass
            os.remove(bak_path)
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)
        return True
    except Exception as e:
        if os.path.exists(tmp_zip):
            try:
                os.remove(tmp_zip)
            except Exception:
                pass
        return False
