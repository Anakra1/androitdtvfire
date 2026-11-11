param(
    [Parameter(Mandatory=$true)][string]$GoRoot,
    [Parameter(Mandatory=$true)][string]$NdkRoot,
    [string[]]$Architectures = @('arm64', 'arm7')
)
$ErrorActionPreference = 'Stop'
$taskProject = Split-Path (Split-Path $PSScriptRoot)
if (!(Test-Path (Join-Path $taskProject 'source/TorrServer-MatriX.150-source.zip'))) {
    $taskProject = $PSScriptRoot
}
$taskNative = Join-Path $taskProject 'work/native-engine'
$taskServer = Join-Path $taskNative 'TorrServer-MatriX.150/server'
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (!(Test-Path $taskServer)) {
    New-Item $taskNative -ItemType Directory -Force | Out-Null
    [IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $taskProject 'source/TorrServer-MatriX.150-source.zip'), $taskNative, $true)
}
New-Item "$taskServer/cbrshared" -ItemType Directory -Force | Out-Null
Copy-Item "$PSScriptRoot/script.module.cbr.engine/native/main.go" "$taskServer/cbrshared/main.go" -Force
$env:GOPATH = Join-Path $taskProject 'work/toolchains/go-cache'
$env:GOCACHE = Join-Path $taskProject 'work/toolchains/go-build-cache'
$env:CGO_ENABLED = '1'
$env:GOOS = 'android'
$taskTargets = @{
    arm64 = @('arm64', 'aarch64-linux-android23-clang.cmd')
    arm7 = @('arm', 'armv7a-linux-androideabi23-clang.cmd')
    amd64 = @('amd64', 'x86_64-linux-android23-clang.cmd')
    '386' = @('386', 'i686-linux-android23-clang.cmd')
}
Push-Location $taskServer
try {
    foreach ($taskArch in $Architectures) {
        if (!$taskTargets.ContainsKey($taskArch)) { throw "Unsupported build architecture: $taskArch" }
        $env:GOARCH = $taskTargets[$taskArch][0]
        $env:GOARM = '7'
        $env:CC = Join-Path $NdkRoot "toolchains/llvm/prebuilt/windows-x86_64/bin/$($taskTargets[$taskArch][1])"
        $taskOutput = Join-Path $PSScriptRoot "script.module.cbr.engine/resources/lib/android-$taskArch/libcbrengine.so"
        New-Item (Split-Path $taskOutput) -ItemType Directory -Force | Out-Null
        & "$GoRoot/bin/go.exe" build -trimpath -tags=nosqlite -buildmode=c-shared -ldflags '-s -w -checklinkname=0 -X server/version.Version=MatriX.150' -o $taskOutput ./cbrshared
        if ($LASTEXITCODE -ne 0) { throw "Shared engine build failed: $taskArch" }
        Write-Output "Built $taskArch : $((Get-FileHash $taskOutput).Hash)"
    }
} finally {
    Pop-Location
}
$taskChecksums = @{}
Get-ChildItem "$PSScriptRoot/script.module.cbr.engine/resources/lib" -Directory | ForEach-Object {
    $taskChecksums[$_.Name] = (Get-FileHash (Join-Path $_.FullName 'libcbrengine.so')).Hash.ToLowerInvariant()
}
[IO.File]::WriteAllText("$PSScriptRoot/script.module.cbr.engine/resources/checksums.json", ($taskChecksums | ConvertTo-Json))
