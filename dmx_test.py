#!/usr/bin/env python3
"""
DMX test using libftdi1 directly via ctypes.
Mirrors QLC+'s libFTDI interface exactly:
  - ftdi_set_line_property2() with BREAK_ON/BREAK_OFF for the break signal
  - 110 µs break, 16 µs MAB, 30 Hz frame rate
  - Talks directly to the FTDI chip via USB (bypasses /dev/ttyUSB0 entirely)

Run with sudo if you get a "unable to open" error.
"""
import ctypes
import time

lib = ctypes.CDLL("libftdi1.so.2")

_P = ctypes.c_void_p

lib.ftdi_new.restype                 = _P
lib.ftdi_usb_open.restype            = ctypes.c_int
lib.ftdi_usb_open.argtypes           = [_P, ctypes.c_int, ctypes.c_int]
lib.ftdi_set_baudrate.restype        = ctypes.c_int
lib.ftdi_set_baudrate.argtypes       = [_P, ctypes.c_int]
lib.ftdi_set_line_property2.restype  = ctypes.c_int
lib.ftdi_set_line_property2.argtypes = [_P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
lib.ftdi_write_data.restype          = ctypes.c_int
lib.ftdi_write_data.argtypes         = [_P, ctypes.c_void_p, ctypes.c_int]
lib.ftdi_usb_close.restype           = ctypes.c_int
lib.ftdi_usb_close.argtypes          = [_P]
lib.ftdi_get_error_string.restype  = ctypes.c_char_p

# enum values from libftdi.h
BITS_8      = 8
STOP_BIT_2  = 2
NONE        = 0   # parity
BREAK_OFF   = 0
BREAK_ON    = 1

VENDOR  = 0x0403
PRODUCT = 0x6001


def send_frame(ctx, frame: bytearray):
    lib.ftdi_set_line_property2(ctx, BITS_8, STOP_BIT_2, NONE, BREAK_ON)
    time.sleep(0.000110)   # 110 µs break
    lib.ftdi_set_line_property2(ctx, BITS_8, STOP_BIT_2, NONE, BREAK_OFF)
    time.sleep(0.000016)   # 16 µs MAB
    lib.ftdi_write_data(ctx, bytes(frame), len(frame))


def main():
    ctx = lib.ftdi_new()
    if not ctx:
        print("ERROR: ftdi_new() failed")
        return

    print(f"Opening FTDI device {VENDOR:#06x}:{PRODUCT:#06x}...")
    ret = lib.ftdi_usb_open(ctx, VENDOR, PRODUCT)
    if ret < 0:
        err = lib.ftdi_get_error_string(ctx)
        print(f"ERROR: ftdi_usb_open() returned {ret}: {err.decode()}")
        print("Try running with: sudo python3 dmx_test.py")
        lib.ftdi_free(ctx)
        return

    lib.ftdi_set_baudrate(ctx, 250000)
    lib.ftdi_set_line_property2(ctx, BITS_8, STOP_BIT_2, NONE, BREAK_OFF)
    print("Device open. Streaming full brightness for 5 seconds...")

    # All channels to 255 — ch1=R, ch2=G, ch3=B, ch4=White, ch5=Dimmer
    frame = bytearray(513)
    for i in range(1, 513):
        frame[i] = 255

    deadline = time.monotonic() + 5.0
    frames = 0
    while time.monotonic() < deadline:
        send_frame(ctx, frame)
        frames += 1
        time.sleep(1 / 30)

    print(f"Sent {frames} frames. Sending blackout...")
    frame = bytearray(513)
    for _ in range(30):
        send_frame(ctx, frame)
        time.sleep(1 / 30)

    lib.ftdi_usb_close(ctx)
    lib.ftdi_free(ctx)
    print("Done.")


if __name__ == "__main__":
    main()
