[CmdletBinding()]
param([ValidateSet('Test','Build','Sync')][string]$Action='Test',[switch]$Offline)
& 'G:\DevTools\Invoke-NodeProject.ps1' -Project 'EcommerceFrontend' -Action $Action -Offline:$Offline