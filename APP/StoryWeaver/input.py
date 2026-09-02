import struct
import select
import os
import time

code = 0
codeName = ""
value = 0

mapping = {
    304: "A",   305: "B",   306: "Y",   307: "X",
    308: "L1",  309: "R1",  314: "L2",  315: "R2",
    17: "DY",   16: "DX",
    310: "SELECT",  311: "START",  312: "MENUF",
    114: "V+",  115: "V-",
    313: "JOYSTICK",
    116: "POWER",
}

_fds = []
_press_times = {}
_long_pressed_code = None
_held_fired = set()
_short_release_code = None

def _get_fds():
    global _fds
    if not _fds:
        for i in range(8):
            try:
                fd = os.open(f"/dev/input/event{i}", os.O_RDONLY | os.O_NONBLOCK)
                _fds.append(fd)
            except Exception:
                pass
    return _fds

def check():
    global type, code, codeName, codeDown, value, valueDown, _long_pressed_code, _short_release_code
    codeName = ""
    value = 0
    _short_release_code = None
    fds = _get_fds()
    if not fds:
        return
    r, _, _ = select.select(fds, [], [], 0.05)
    for fd in r:
        try:
            while True:
                event = os.read(fd, 24)
                if not event or len(event) != 24:
                    break
                (tv_sec, tv_usec, type, kcode, kvalue) = struct.unpack('llHHi', event)
                if kvalue == 1:
                    _press_times[kcode] = time.time()
                    _held_fired.discard(kcode)
                elif kvalue == 0:
                    if kcode in _press_times:
                        held = time.time() - _press_times.pop(kcode)
                        if held > 0.5:
                            _long_pressed_code = kcode
                        if held < 1.0:
                            _short_release_code = kcode
                if kvalue != 0:
                    if kvalue != 1 and kcode not in (16, 17):
                        continue
                    if kvalue != 1:
                        kvalue = -1 if kvalue < 0 else 1
                    code = kcode
                    codeName = mapping.get(code, str(code))
                    value = kvalue
        except BlockingIOError:
            pass

def key(keyCodeName, keyValue=99):
    global code, codeName, value
    if codeName == keyCodeName:
        if keyValue != 99:
            return value == keyValue
        return value != 0

def key_long(keyCodeName):
    global _long_pressed_code
    if _long_pressed_code is not None:
        name = mapping.get(_long_pressed_code, str(_long_pressed_code))
        if name == keyCodeName:
            _long_pressed_code = None
            return True
    return False

def key_held_for(keyCodeName, seconds=1.0):
    global _press_times, _held_fired
    for kcode, start in list(_press_times.items()):
        name = mapping.get(kcode, str(kcode))
        if name == keyCodeName and time.time() - start >= seconds:
            if kcode not in _held_fired:
                _held_fired.add(kcode)
                return True
    return False

def key_released_short(keyCodeName, threshold=1.0):
    if _short_release_code is not None:
        name = mapping.get(_short_release_code, str(_short_release_code))
        return name == keyCodeName
    return False

def slide_key():
    global codeName
    if codeName:
        return True

def reset_input():
    global codeName, value, _short_release_code, _held_fired
    codeName = ""
    value = 0
    _short_release_code = None
    _held_fired.clear()

def drain():
    """Read and discard all pending input events."""
    fds = _get_fds()
    for fd in fds:
        try:
            while True:
                event = os.read(fd, 24)
                if not event or len(event) != 24:
                    break
        except BlockingIOError:
            pass
