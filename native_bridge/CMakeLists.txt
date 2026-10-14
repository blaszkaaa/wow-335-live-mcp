cmake_minimum_required(VERSION 3.18)
project(WoWMCPNativeBridge LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "Native bridge is Windows-only.")
endif()

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "Build with -A Win32: WoW 3.3.5a is a 32-bit client.")
endif()

add_library(WoWMCPNativeBridge SHARED src/bridge.cpp)
target_compile_features(WoWMCPNativeBridge PRIVATE cxx_std_17)
target_compile_definitions(WoWMCPNativeBridge PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
set_target_properties(WoWMCPNativeBridge PROPERTIES OUTPUT_NAME "WoWMCPNativeBridge")

add_executable(native_bridge_demo src/demo_sender.cpp)
target_compile_features(native_bridge_demo PRIVATE cxx_std_17)
target_link_libraries(native_bridge_demo PRIVATE WoWMCPNativeBridge)
