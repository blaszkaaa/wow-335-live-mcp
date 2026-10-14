// A standalone smoke test. No WoW installation, hooks or loader needed.
#include <ctime>
#include <iostream>
#include <string>

extern "C" __declspec(dllimport) int __cdecl WowMcpPublish(const char* utf8, unsigned int length);

int main() {
    const std::string json =
        std::string(R"({"version":1,"session":"native-demo","sequence":1,"kind":"snapshot","captured_at":)") +
        std::to_string(static_cast<long long>(std::time(nullptr))) +
        R"(,"data":{"character":{"name":"Demo","level":1},"location":{"zone":"Test zone"}}})";
    const int result = WowMcpPublish(json.data(), static_cast<unsigned int>(json.size()));
    if (result != 0) {
        std::cerr << "Native pipe send failed: " << result
                  << " (start MCP with WOW_MCP_NATIVE_BRIDGE=1 first)\n";
    } else {
        std::cout << "Sample character data delivered to MCP pipe.\n";
    }
    return result;
}
