# Builds a local development copy of WrathClassicAPI including WoWMCP.Publish.
# Offline test environments only. No injector, no anti-cheat bypass.
param(
    [string]$WorkingDirectory = "",
    [switch]$SkipClone
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if (-not $WorkingDirectory) { $WorkingDirectory = Join-Path $root "build/wowmcp-native-lua" }
$work = [System.IO.Path]::GetFullPath($WorkingDirectory)
$upstream = Join-Path $work "WrathClassicAPI"
$build = Join-Path $work "build"
$module = Join-Path $root "native_bridge/adapter/WoWMCPNativeLua.cpp"
$commit = "0bc6d57dfd5a98be504895668aae44967afab0bf"

New-Item -ItemType Directory -Path $work -Force | Out-Null
if (-not $SkipClone) {
    if (-not (Test-Path (Join-Path $upstream ".git"))) {
        git clone "https://github.com/brues-code/WrathClassicAPI.git" $upstream
        if ($LASTEXITCODE -ne 0) { throw "Could not clone WrathClassicAPI" }
    }
}
if (-not (Test-Path (Join-Path $upstream ".git"))) { throw "Missing WrathClassicAPI checkout" }
git -C $upstream fetch origin $commit
if ($LASTEXITCODE -ne 0) { throw "Could not fetch pinned upstream commit" }
git -C $upstream checkout --detach $commit
if ($LASTEXITCODE -ne 0) { throw "Could not checkout pinned upstream commit" }
git -C $upstream submodule update --init --recursive
if ($LASTEXITCODE -ne 0) { throw "Could not initialize upstream submodules" }
$target = Join-Path $upstream "src/wowmcp"
New-Item -ItemType Directory -Path $target -Force | Out-Null
Copy-Item $module (Join-Path $target "WoWMCPNativeLua.cpp") -Force

# Upstream's CMake source glob automatically registers src/wowmcp/*.cpp.
cmake -S $upstream -B $build -A Win32
if ($LASTEXITCODE -ne 0) { throw "Win32 CMake configure failed" }
cmake --build $build --config Release --parallel 4
if ($LASTEXITCODE -ne 0) { throw "WrathClassicAPI Win32 build failed" }
$dll = Join-Path $build "Release/WrathClassicAPI.dll"
if (-not (Test-Path $dll)) { throw "Missing compiled WrathClassicAPI.dll" }
Write-Host "Offline Lua adapter compiled: $dll"

# Only compile/prepare an offline test DLL. Never modify Wow.exe or deploy
# the DLL to any game directory automatically.
