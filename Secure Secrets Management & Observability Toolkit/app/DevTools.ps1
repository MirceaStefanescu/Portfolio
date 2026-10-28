[CmdletBinding()]
param([ValidateSet('Test','Build','Sync')][string]$Action='Test',[switch]$Offline)
& 'G:\DevTools\Invoke-NodeProject.ps1' -Project 'SecretsToolkit' -Action $Action -Offline:$Offline