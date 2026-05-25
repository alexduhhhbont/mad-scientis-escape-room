import ctypes
import time

from pc2.config import FTDI_VENDOR, FTDI_PRODUCT, DMX_REFRESH_HZ
from pc2.lighting.controller import controller
from pc2.log import log_queue

_lib = ctypes.CDLL("libftdi1.so.2")

_P = ctypes.c_void_p

_lib.ftdi_new.restype                 = _P
_lib.ftdi_usb_open.restype            = ctypes.c_int
_lib.ftdi_usb_open.argtypes           = [_P, ctypes.c_int, ctypes.c_int]
_lib.ftdi_set_baudrate.restype        = ctypes.c_int
_lib.ftdi_set_baudrate.argtypes       = [_P, ctypes.c_int]
_lib.ftdi_set_line_property2.restype  = ctypes.c_int
_lib.ftdi_set_line_property2.argtypes = [_P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_lib.ftdi_write_data.restype          = ctypes.c_int
_lib.ftdi_write_data.argtypes         = [_P, ctypes.c_void_p, ctypes.c_int]
_lib.ftdi_usb_close.restype           = ctypes.c_int
_lib.ftdi_usb_close.argtypes          = [_P]
_lib.ftdi_free.restype                = None
_lib.ftdi_free.argtypes               = [_P]
_lib.ftdi_get_error_string.restype    = ctypes.c_char_p
_lib.ftdi_get_error_string.argtypes   = [_P]

_BITS_8     = 8
_STOP_BIT_2 = 2
_NONE       = 0
_BREAK_OFF  = 0
_BREAK_ON   = 1


def dmx_streaming_loop():
    """
    Streams DMX frames via libftdi1 (bypasses the ftdi_sio kernel driver,
    mirrors what QLC+ does). Protocol: BREAK 110 µs → MAB 16 µs → 513 bytes.
    """
    period = 1.0 / DMX_REFRESH_HZ
    ctx    = None

    while True:
        tick_start = time.monotonic()

        if ctx is None:
            c = _lib.ftdi_new()
            if not c:
                time.sleep(2)
                continue
            ret = _lib.ftdi_usb_open(c, FTDI_VENDOR, FTDI_PRODUCT)
            if ret < 0:
                err = _lib.ftdi_get_error_string(c).decode()
                log_queue.put(f"DMX open failed: {err} — retrying in 2s")
                _lib.ftdi_free(c)
                controller.dmx_online = False
                time.sleep(2)
                continue
            _lib.ftdi_set_baudrate(c, 250000)
            _lib.ftdi_set_line_property2(c, _BITS_8, _STOP_BIT_2, _NONE, _BREAK_OFF)
            ctx = c
            controller.dmx_online = True
            log_queue.put("DMX device connected")

        frame = controller.get_frame()

        ret = _lib.ftdi_set_line_property2(ctx, _BITS_8, _STOP_BIT_2, _NONE, _BREAK_ON)
        if ret < 0:
            log_queue.put("DMX write error — retrying in 2s")
            _lib.ftdi_usb_close(ctx)
            _lib.ftdi_free(ctx)
            ctx = None
            controller.dmx_online = False
            time.sleep(2)
            continue

        time.sleep(0.000110)   # 110 µs break
        _lib.ftdi_set_line_property2(ctx, _BITS_8, _STOP_BIT_2, _NONE, _BREAK_OFF)
        time.sleep(0.000016)   # 16 µs MAB
        _lib.ftdi_write_data(ctx, bytes(frame), 513)

        elapsed   = time.monotonic() - tick_start
        remaining = period - elapsed
        if remaining > 0:
            time.sleep(remaining)
