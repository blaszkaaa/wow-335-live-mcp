# WoWMCP native Lua adapter (experimental)

This implements the missing Lua-to-native publishing function for WoW 3.3.5a
using the Lua extension registration machinery of WrathClassicAPI:
https://github.com/brues-code/WrathClassicAPI

**Status:** C++ and Lua source implemented; Windows build and unit checks run
in the "Experimental Lua DLL (offline only)" GitHub workflow. Actual loaded
client compatibility has NOT yet been verified, especially NOT on Warmane.
A successful compile does not prove live compatibility or server permission.

## Components

1. WoWMCPNativeLua.cpp: optional C++ module built into WrathClassicAPI,
   registering WoWMCP.Available() and WoWMCP.Publish(json) to the game Lua state.
2. WoWMCPData/WoWMCPData.lua: detects the optional native function and sends
   full JSON snapshots; retains the existing visual strip as a fallback.
3. native_bridge/pipe.py + native_bridge/state.py: validates framed JSON
   including session, sequence and capture timestamp.
4. wow_native_status / read_wow_native_data: existing MCP tools.

The new adapter does not inject into Wow.exe, bypass anti-cheat or automate
gameplay. However, the upstream WrathClassicAPI runtime itself uses engine
hooks, and may not be permitted by online realm operators.

## Data protocol

The addon publishes a message shaped as follows:

    {
      "version": 1,
      "session": "1791975600-123456",
      "sequence": 1,
      "kind": "snapshot",
      "captured_at": 1791975600,
      "data": {
        "captured_at": 1791975600,
        "character": {"name": "Example", "level": 20},
        "quests": []
      }
    }

Snapshoty natywne są odświeżane przez addon mniej więcej co 3 sekundy,
niezależnie od czasu transmisji wszystkich stron paska wizualnego.
Po ustawieniu WOW_MCP_NATIVE_BRIDGE=1 standardowe narzędzie MCP
read_wow_live_data preferuje świeże dane DLL, jeśli są dostępne, i inaczej
korzysta z odczytu wizualnego. Dane demonstracyjne DLL są pomijane w tej ścieżce.

A packet is limited to 60000 bytes. When character snapshots exceed about
58000 bytes, low-priority sections are removed with truncation markers.
Packets are always full snapshots to tolerate lost frames. Sending uses
a local-only Windows Named Pipe, with a best-effort short write timeout.
No receiver => the addon keeps operating over its visual fallback.

## Reproducible isolated Win32 build

Requires Windows, Git, CMake, Visual Studio C++ Win32 build tools.

From the repo root run:

    powershell -ExecutionPolicy Bypass -File native_bridge/adapter/build-offline.ps1

The script pins upstream WrathClassicAPI to commit
0bc6d57dfd5a98be504895668aae44967afab0bf. It does not alter
your WoW directory. Result:

    build/wowmcp-native-lua/build/Release/WrathClassicAPI.dll

GitHub Actions builds the same module and packages its complete source
and GPL license in "WowMCP-Lua-Bridge-OFFLINE-ONLY". The Windows desktop
installer additionally bundles the built adapter with a pinned, hash-verified
LichLoader release, and publishes "WoWMCP-Native-Corresponding-Source"
alongside the installer.

## Authorized in-game compatibility check

Only use a client/environment where loading these native extensions is explicitly
permitted. The WoW Connect desktop app offers opt-in "Przez LichLoader (DLL)" mode:
it prepares the bundled files in the selected game directory and starts
LichLoader. No manual copying or editing is required; no anti-cheat bypass is
implemented. A successful game launch is not proof the adapter is working.

1. Open WoW Connect to start its local receiver. Do not start two simultaneous
   named-pipe receivers.
2. In the test client with WoWMCPData and the adapter loaded, run /reload.
3. Run /wowmcpnative. Verify it reports the last packet sent and its size.
4. Call wow_native_status and read_wow_native_data in ChatGPT. Inspect
   data.character.name, quests, sequence and age_seconds; compare with the
   visual addon read.
5. Close the receiver and verify the existing visual fallback still works.

This does NOT prove Warmane compatibility or compliance with realm rules.

## Licensing

WoWMCPNativeLua.cpp is GPL-3.0-or-later, to be compiled with the GPL-3.0
WrathClassicAPI. The build artifact includes corresponding source and license.
The original standalone transport remains separately licensed in this repo.
