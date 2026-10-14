"""Windows named-pipe listener for opt-in telemetry; never injects into WoW."""

import ctypes
import os
import threading

from .state import MAX_MESSAGE_BYTES, NativeState

PIPE_NAME = r"\\.\pipe\wow335-mcp-v1"
PIPE_ACCESS_INBOUND = 0x00000001
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
ERROR_PIPE_CONNECTED = 535


class NativePipeReceiver:
    def __init__(self):
        self.state = NativeState()
        self._thread = None
        self._error = None

    def start(self):
        if os.name != "nt":
            self._error = "Windows named pipes are only supported on Windows."
            return False
        if self._thread is not None:
            return True
        self._thread = threading.Thread(target=self._serve, name="wow-native-pipe", daemon=True)
        self._thread.start()
        return True

    def status(self):
        status = self.state.status()
        return {**status, "enabled": True, "pipe": PIPE_NAME, "error": self._error}

    def snapshot(self):
        return {**self.state.snapshot(), "pipe": PIPE_NAME, "error": self._error}

    def _serve(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateNamedPipeW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
            ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
        ]
        kernel.CreateNamedPipeW.restype = ctypes.c_void_p
        kernel.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel.ConnectNamedPipe.restype = ctypes.c_int
        kernel.ReadFile.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
        ]
        kernel.ReadFile.restype = ctypes.c_int
        kernel.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
        kernel.DisconnectNamedPipe.restype = ctypes.c_int
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.restype = ctypes.c_int
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        while True:
            pipe = kernel.CreateNamedPipeW(
                PIPE_NAME, PIPE_ACCESS_INBOUND,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
                1, MAX_MESSAGE_BYTES, MAX_MESSAGE_BYTES, 0, None,
            )
            if pipe == INVALID_HANDLE_VALUE or not pipe:
                self._error = "CreateNamedPipeW failed: " + str(ctypes.get_last_error())
                return
            try:
                connected = kernel.ConnectNamedPipe(pipe, None)
                if not connected and ctypes.get_last_error() != ERROR_PIPE_CONNECTED:
                    self._error = "ConnectNamedPipe failed: " + str(ctypes.get_last_error())
                    continue
                buf = ctypes.create_string_buffer(MAX_MESSAGE_BYTES)
                size = ctypes.c_ulong()
                if kernel.ReadFile(pipe, buf, MAX_MESSAGE_BYTES, ctypes.byref(size), None):
                    self.state.ingest(buf.raw[:size.value])
                else:
                    self._error = "ReadFile failed: " + str(ctypes.get_last_error())
                    continue
                self._error = None
            finally:
                kernel.DisconnectNamedPipe(pipe)
                kernel.CloseHandle(pipe)
