$ErrorActionPreference = "Stop"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$profile = "C:\Users\User\Desktop\Project\ticketplus-script\.chrome-profile"
$url = "https://ticketplus.com.tw/order/e5baf60463fccb6391ae4dcb2e314978/0e5b6ce0e4a3c1b0f4571189c11b726e"
New-Item -ItemType Directory -Force -Path $profile | Out-Null
$listening = Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Start-Process -FilePath $chrome -ArgumentList @(
        "--remote-debugging-port=9222",
        "--user-data-dir=$profile",
        "--no-first-run",
        "--no-default-browser-check",
        $url
    )
    Start-Sleep -Seconds 3
}
Get-NetTCPConnection -LocalPort 9222 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, State, OwningProcess |
    Format-List
