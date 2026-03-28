param(
    [switch]$SyncOnly,
    [switch]$Clean,
    [switch]$RefreshCache
)

$command = if ($SyncOnly) { "sync" } else { "build" }
$args = @("scripts/build_release.py", $command)

if ($Clean) {
    $args += "--clean"
}

if ($RefreshCache) {
    $args += "--refresh-cache"
}

python @args
