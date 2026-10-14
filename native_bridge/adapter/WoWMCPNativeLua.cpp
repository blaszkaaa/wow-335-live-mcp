// Optional offline-only adapter for WrathClassicAPI 3.3.5a.
// Copyright (c) WoW MCP contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Compile this source into WrathClassicAPI's Win32 target (NOT as a standalone
// add-on DLL). WrathClassicAPI registers Lua C closures after FrameScript
// initializes. No offsets, anti-cheat bypasses, or loader hooks are implemented
// in this module. The host project's existing licensing applies to the build.

#include "Game.h"
#include <windows.h>
#include <cstdint>
#include <cstring>

namespace {
constexpr wchar_t kPipe[] = LR"(\\.\pipe\wow335-mcp-v1)";
constexpr unsigned int kMaxBytes = 60000;
constexpr DWORD kMaxDurationMs = 100;

// Return false when no collector is running. One JSON object is one pipe message.
// The host runs the Lua callback on WoW's main thread, so keep this path small
// and avoid retries: a failed send should never stop the game.
bool PublishLocalFrame(const char* utf8, unsigned int length) {
    if (!utf8 || length == 0 || length > kMaxBytes || utf8[0] != '{')
        return false;

    HANDLE handle = CreateFileW(
        kPipe, GENERIC_WRITE, 0, nullptr, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OVERLAPPED, nullptr);
    if (handle == INVALID_HANDLE_VALUE)
        return false;

    OVERLAPPED overlapped = {};
    overlapped.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    if (!overlapped.hEvent) {
        CloseHandle(handle);
        return false;
    }

    DWORD written = 0;
    BOOL sent = WriteFile(handle, utf8, length, &written, &overlapped);
    if (!sent && GetLastError() == ERROR_IO_PENDING) {
        DWORD wait = WaitForSingleObject(overlapped.hEvent, kMaxDurationMs);
        if (wait == WAIT_OBJECT_0) {
            sent = GetOverlappedResult(handle, &overlapped, &written, FALSE);
        } else {
            CancelIo(handle);
            // Wait for cancellation to complete before releasing the memory
            // referenced by the async operation. Bound here is best effort.
            GetOverlappedResult(handle, &overlapped, &written, TRUE);
            sent = FALSE;
        }
    }
    CloseHandle(overlapped.hEvent);
    CloseHandle(handle);
    return sent && written == length;
}

int __cdecl Script_Publish(void* lua) {
    if (Game::Lua::Type(lua, 1) != Game::Lua::TYPE_STRING) {
        Game::Lua::PushBool(lua, false);
        return 1;
    }
    unsigned int length = 0;
    const char* value = Game::Lua::ToLString(lua, 1, &length);
    const bool result = PublishLocalFrame(value, length);
    Game::Lua::PushBool(lua, result);
    return 1;
}

int __cdecl Script_Available(void* lua) {
    // This function exists only when the native adapter was loaded.
    Game::Lua::PushBool(lua, true);
    return 1;
}

void RegisterLuaFunctions() {
    Game::Lua::RegisterTableFunction("WoWMCP", "Publish", &Script_Publish);
    Game::Lua::RegisterTableFunction("WoWMCP", "Available", &Script_Available);
}

const Game::ModuleAutoRegister kRegister{&RegisterLuaFunctions};
}  // namespace
