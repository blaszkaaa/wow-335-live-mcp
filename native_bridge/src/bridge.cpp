// MIT-licensed standalone transport prototype. No game hooks or injection.
// Export only a narrow JSON -> local named-pipe publisher.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>

namespace {
constexpr wchar_t kPipe[] = LR"(\\.\pipe\wow335-mcp-v1)";
constexpr unsigned int kMaxBytes = 65536;
}

// Synchronous, for diagnostics and small event-driven payloads.
// Do NOT invoke on the game rendering thread until an async queue is implemented.
extern "C" __declspec(dllexport) int __cdecl WowMcpPublish(const char* utf8, unsigned int length) {
    if (utf8 == nullptr || length == 0 || length > kMaxBytes) return 1;
    HANDLE pipe = CreateFileW(kPipe, GENERIC_WRITE, 0, nullptr,
                              OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) return 2; // Receiver not running.
    DWORD written = 0;
    const BOOL ok = WriteFile(pipe, utf8, length, &written, nullptr);
    CloseHandle(pipe);
    return ok && written == length ? 0 : 3;
}
