import ctypes
import os
import threading
import sdl2
import sdl2.sdlmixer as mx

_MIX_MAX_VOLUME = 128
_LOWER_VOLUME = 32

_music = None
_music_path = None
_music_loop = False
_music_volume_before_tts = _MIX_MAX_VOLUME

_tts_chunk = None
_tts_channel = -1
_tts_active = False
_tts_paused = False
_tts_done = False
_tts_music_mode = False
_tts_finished_callback = None
_tts_music_was_playing = False
_tts_channel_finished = None
_tts_lock = threading.RLock()

_TTS_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)
_tts_callback_func = None


def init():
    sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO)
    mx.Mix_OpenAudio(44100, 0x8010, 2, 4096)
    global _tts_callback_func
    _tts_callback_func = _TTS_CALLBACK(_on_channel_finished)
    mx.Mix_ChannelFinished(_tts_callback_func)


def close():
    stop_tts()
    stop_music()
    mx.Mix_CloseAudio()


def _on_channel_finished(channel):
    global _tts_active, _tts_paused, _tts_done, _tts_chunk, _tts_channel
    if channel == _tts_channel:
        _tts_active = False
        _tts_paused = False
        _tts_done = True
        if _tts_chunk:
            mx.Mix_FreeChunk(_tts_chunk)
            _tts_chunk = None
        _tts_channel = -1
        _handle_tts_finished_music()
        if _tts_finished_callback:
            _tts_finished_callback()


def _handle_tts_started_music(save_volume=True):
    global _music_volume_before_tts, _tts_music_was_playing
    _tts_music_was_playing = bool(mx.Mix_PlayingMusic())
    if _tts_music_mode is False and _tts_music_was_playing:
        mx.Mix_PauseMusic()
    elif _tts_music_mode == "lower" and _tts_music_was_playing:
        if save_volume:
            _music_volume_before_tts = mx.Mix_VolumeMusic(-1)
        mx.Mix_VolumeMusic(_LOWER_VOLUME)


def _handle_tts_finished_music():
    if _tts_music_mode is False and _tts_music_was_playing:
        mx.Mix_ResumeMusic()
    elif _tts_music_mode == "lower":
        mx.Mix_VolumeMusic(_music_volume_before_tts)


def set_tts_music_mode(mode):
    global _tts_music_mode
    _tts_music_mode = mode


def get_tts_music_mode():
    return _tts_music_mode


def set_tts_finished_callback(cb):
    global _tts_finished_callback
    _tts_finished_callback = cb


def play_music(path, loop=False):
    global _music, _music_path, _music_loop
    stop_music()
    if not os.path.exists(path):
        return False
    mus = mx.Mix_LoadMUS(path.encode())
    if not mus:
        return False
    _music = mus
    _music_path = path
    _music_loop = loop
    mx.Mix_PlayMusic(mus, -1 if loop else 1)
    if _tts_active and not _tts_paused:
        _handle_tts_started_music(save_volume=True)
    return True


def stop_music():
    global _music, _music_path
    if _music:
        _music_path = None
        if mx.Mix_PlayingMusic():
            mx.Mix_HaltMusic()
        mx.Mix_FreeMusic(_music)
        _music = None


def pause_music():
    if mx.Mix_PlayingMusic() and not mx.Mix_PausedMusic():
        mx.Mix_PauseMusic()


def resume_music():
    if mx.Mix_PausedMusic():
        mx.Mix_ResumeMusic()


def is_music_playing():
    return bool(mx.Mix_PlayingMusic())


def is_music_paused():
    return bool(mx.Mix_PausedMusic())


def toggle_music(tracks):
    if is_music_playing():
        stop_music()
    else:
        import random
        play_music(random.choice(tracks), loop=True)


def set_music_volume(vol):
    mx.Mix_VolumeMusic(max(0, min(_MIX_MAX_VOLUME, vol)))


def get_music_volume():
    return mx.Mix_VolumeMusic(-1)


def play_tts(wav_path):
    global _tts_chunk, _tts_channel, _tts_active, _tts_paused, _tts_done
    with _tts_lock:
        stop_tts()
        if not os.path.exists(wav_path):
            return False
        chunk = mx.Mix_LoadWAV(wav_path.encode())
        if not chunk or not chunk.contents:
            return False
        ch = mx.Mix_PlayChannel(-1, chunk, 0)
        if ch < 0:
            mx.Mix_FreeChunk(chunk)
            return False
        _tts_chunk = chunk
        _tts_channel = ch
        _tts_active = True
        _tts_paused = False
        _tts_done = False
        _handle_tts_started_music()
    return True


def stop_tts():
    global _tts_chunk, _tts_channel, _tts_active, _tts_paused, _tts_done
    with _tts_lock:
        was_active = _tts_active or _tts_paused
        ch = _tts_channel
        _tts_channel = -1
        _tts_active = False
        _tts_paused = False
        _tts_done = False
        if ch >= 0:
            mx.Mix_HaltChannel(ch)
        if _tts_chunk:
            mx.Mix_FreeChunk(_tts_chunk)
            _tts_chunk = None
        if was_active:
            _handle_tts_finished_music()


def pause_tts():
    global _tts_paused
    with _tts_lock:
        if _tts_active and not _tts_paused and _tts_channel >= 0:
            mx.Mix_Pause(_tts_channel)
            _tts_paused = True
            _handle_tts_finished_music()


def resume_tts():
    global _tts_paused
    with _tts_lock:
        if _tts_paused and _tts_channel >= 0:
            mx.Mix_Resume(_tts_channel)
            _tts_paused = False
            _handle_tts_started_music(save_volume=False)


def is_tts_playing():
    return _tts_active and not _tts_paused


def is_tts_paused():
    return _tts_paused


def is_tts_done():
    return _tts_done


def toggle_tts():
    if is_tts_paused():
        resume_tts()
    elif is_tts_playing():
        pause_tts()
    else:
        return False
    return True
