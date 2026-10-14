# Experimental native DLL bridge (prototype)

## Desktop application: WoW MCP Control Center

**Windows GUI** (Polish interface, no third-party GUI dependencies):

    py -3 desktop_app.py

The interface includes Dashboard, Character, Quests, Diagnostics and Settings.
It starts the native named-pipe receiver and an authenticated read-only HTTP
status/snapshot hub bound to 127.0.0.1 with a fresh random token. Token discovery
is stored at %LOCALAPPDATA%\WoWMCP\control-center.json, normally accessible only
through the current Windows profile; the file is deleted when the GUI exits.
Do not expose that token or HTTP endpoint to other machines.

Build a Windows GUI executable:

    py -3 -m pip install pyinstaller
    pyinstaller --onefile --windowed --name WoW-MCP-Control-Center desktop_app.py

GitHub Actions also produces a **WoW-MCP-Control-Center-Windows** artifact with
the GUI .exe, compiled DLL and standalone demo executable. Extract the ZIP
before running. The GUI itself does NOT require a working game hook.

**Start GUI first**, then configure your existing MCP client with:

    WOW_GAME_DIR=C:\path\to\World of Warcraft 3.3.5a
    WOW_MCP_NATIVE_BRIDGE=1
    WOW_MCP_NATIVE_HUB=1

Restart the MCP connection. The MCP tools "wow_native_status" and
"read_wow_native_data" will connect to the GUI. In this mode the MCP server
will not create a competing native telemetry pipe. With the GUI closed, the
tools report unavailable. If WOW_MCP_NATIVE_HUB is unset, the legacy
standalone pipe listener can still run without the GUI.

Use "Wyślij dane testowe" in the GUI to invoke the bundled
native_bridge_demo.exe and see sample data appear in both GUI and MCP.
The name "Demo" identifies these as **synthetic** values, not character data.
Optional **native Lua registration source has been implemented** in adapter/WoWMCPNativeLua.cpp. It builds with WrathClassicAPI for isolated testing; it is **not yet verified inside a running client or Warmane**. See adapter/README.md.


This directory is an **opt-in** transport experiment for WoW 3.3.5a. It is
separate from the production-ready read-only visual addon. It does NOT hook
or inject into the game by default. An optional source-level Lua registration module is provided
in adapter/, but no in-game validation or anti-cheat compatibility is claimed. Its purpose is to validate the fast path first:

    Native Win32 DLL -> Windows Named Pipe -> Python receiver -> MCP tool

The experimental native receiver runs only if WOW_MCP_NATIVE_BRIDGE=1. The
existing visual tools keep working as before. No tunnel or network socket is
opened by this transport. The pipe is local-only (PIPE_REJECT_REMOTE_CLIENTS).
Only run code and MCP clients you trust, as this prototype does not authenticate
individual applications under the same Windows user.

## Build (Windows 10/11, Visual Studio with x86 C++ tools)

From repository root in PowerShell:

    cmake -S native_bridge -B build/native-bridge -A Win32
    cmake --build build/native-bridge --config Release

This produces WoWMCPNativeBridge.dll and native_bridge_demo.exe in
build/native-bridge/Release. x64 DLLs cannot be loaded by WoW 3.3.5a.

## Smoke test WITHOUT starting WoW

Terminal 1, from the repository root:

    py -3 -c "import time; from native_bridge.pipe import NativePipeReceiver; r=NativePipeReceiver(); r.start(); print('Listening'); time.sleep(20); print(r.snapshot())"

Terminal 2, during those 20 seconds:

    .\build\native-bridge\Release\native_bridge_demo.exe

The listener should report available=true and a demo character. This validates
the Windows transport, not integration with game Lua. You can adjust the
sleep duration for manual testing.

## Enable the receiver in the existing MCP server

Set environment variable WOW_MCP_NATIVE_BRIDGE=1 in the MCP client's
configuration alongside WOW_GAME_DIR. Then restart the MCP server and call:

- wow_native_status
- read_wow_native_data

Both tools report when no frame has arrived. Stale data (older than 30 seconds
since reception) is **not** presented as live.

## Wire format

Each pipe client opens \\.\pipe\wow335-mcp-v1, sends **exactly one** UTF-8 JSON
message with one WriteFile call, then closes the handle. Max 65536 bytes.

    {
      "version": 1,
      "session": "client-session-id",
      "sequence": 1,
      "kind": "snapshot",
      "captured_at": 1791975600,
      "data": {
        "character": {"name": "Example", "level": 1}
      }
    }

A subsequent "delta" may update top-level keys of "data"; null deletes a key.
Sequence numbers must increase within a session. A new session must start with
a full "snapshot". Out-of-order, malformed and oversized frames are rejected.
The receiver stores the latest validated state only in RAM.

## DLL ABI

The prototype exports a C ABI function:

    int __cdecl WowMcpPublish(const char* utf8, unsigned int length);

Return values: 0=delivered; 1=invalid input; 2=receiver unavailable;
3=write failed. This export is **synchronous** and may block. Do not call it on
a rendering/game thread or on every frame. An asynchronous bounded queue is
required before actual in-game integration.

## Next step: optional WoW Lua binding

The public WrathClassicAPI project demonstrates registering C functions with
the 3.3.5a Lua engine, but requires engine hooks and loader integration:
https://github.com/brues-code/WrathClassicAPI

That project reports tests on ChromieCraft, **not Warmane**. Its source is
GPL-3.0; no part of its engine-hooking code has been copied into this
MIT-licensed prototype. Game-specific hooking would need a separately reviewed,
licensed implementation and testing on the exact client, without attempting
to bypass anti-cheat. Injection or client modifications can violate private
server rules and risk account penalties. Do not load this prototype DLL into
the game or treat it as a ready-to-use Warmane plugin.

Until the Lua binding has been independently validated, the existing visual
addon remains the recommended game-data source.
