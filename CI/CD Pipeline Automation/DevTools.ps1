[CmdletBinding()]
param([ValidateSet('Test','Build','Sync')][string]$Action='Test',[switch]$Offline)
$previousBash=[Environment]::GetEnvironmentVariable('BASH_EXECUTABLE','Process')
$previousMake=[Environment]::GetEnvironmentVariable('MAKE_EXECUTABLE','Process')
try {
    if($Action -eq 'Test') {
        $env:BASH_EXECUTABLE='G:\DevTools\Git\2.56.0\bin\bash.exe'
        $env:MAKE_EXECUTABLE='G:\DevTools\BuildTools\Make\4.4.1-msys2-ucrt64\bin\mingw32-make.exe'
        foreach($tool in @($env:BASH_EXECUTABLE,$env:MAKE_EXECUTABLE)) {
            if(-not (Test-Path -LiteralPath $tool -PathType Leaf)){throw "Required test tool missing: $tool"}
        }
    }
    & 'G:\DevTools\Invoke-NodeProject.ps1' -Project 'CICD' -Action $Action -Offline:$Offline
} finally {
    [Environment]::SetEnvironmentVariable('BASH_EXECUTABLE',$previousBash,'Process')
    [Environment]::SetEnvironmentVariable('MAKE_EXECUTABLE',$previousMake,'Process')
}
