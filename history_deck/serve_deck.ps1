# Serves this folder on http://localhost so the YouTube embeds in the deck can play.
# YouTube refuses embeds on pages opened straight from disk (file://) with "Error 153",
# because such pages send no referrer. A localhost page does.
param(
    [int]$Port = 8765,
    [string]$Page = 'why_english_spelling.html',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootPrefix = $root.TrimEnd('\') + '\'

# Bind to localhost only (no admin rights needed, not reachable from other machines).
$listener = $null
for ($p = $Port; $p -lt $Port + 20; $p++) {
    $candidate = New-Object System.Net.HttpListener
    $candidate.Prefixes.Add("http://localhost:$p/")
    try { $candidate.Start(); $listener = $candidate; $Port = $p; break }
    catch { $candidate.Close() }
}
if (-not $listener) { Write-Host 'Could not open a local port between' $Port 'and' ($Port + 19); exit 1 }

$url = "http://localhost:$Port/$Page"
Write-Host ''
Write-Host "  Deck:  $url"
Write-Host '  Stop:  press Ctrl+C or close this window'
Write-Host ''
if (-not $NoBrowser) { Start-Process $url }

$types = @{
    '.html' = 'text/html; charset=utf-8'; '.css' = 'text/css'; '.js' = 'text/javascript'
    '.png' = 'image/png'; '.jpg' = 'image/jpeg'; '.svg' = 'image/svg+xml'; '.json' = 'application/json'
}

try {
    while ($listener.IsListening) {
        # Poll instead of a blocking GetContext() so Ctrl+C can interrupt between requests.
        $pending = $listener.GetContextAsync()
        while (-not $pending.AsyncWaitHandle.WaitOne(500)) { }
        $ctx = $pending.GetAwaiter().GetResult()
        $res = $ctx.Response
        try {
            $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
            if ($rel -eq '') { $rel = $Page }
            $full = [IO.Path]::GetFullPath((Join-Path $root $rel))
            if ($full.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -and
                (Test-Path -LiteralPath $full -PathType Leaf)) {
                $bytes = [IO.File]::ReadAllBytes($full)
                $ext = [IO.Path]::GetExtension($full).ToLower()
                $res.ContentType = if ($types.ContainsKey($ext)) { $types[$ext] } else { 'application/octet-stream' }
                $res.ContentLength64 = $bytes.Length
                $res.OutputStream.Write($bytes, 0, $bytes.Length)
            }
            else { $res.StatusCode = 404 }
        }
        catch { $res.StatusCode = 500 }
        finally { $res.Close() }
    }
}
finally {
    $listener.Stop()
    $listener.Close()
}
