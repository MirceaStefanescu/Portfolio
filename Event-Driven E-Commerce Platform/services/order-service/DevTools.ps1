[CmdletBinding()]
param([ValidateSet('Compile','Test')][string]$Action='Compile',[switch]$Offline)
$ErrorActionPreference='Stop'
$env:JAVA_HOME='H:\DevTools\Java\Temurin\jdk-25.0.4.1+1'
$env:PATH=$env:JAVA_HOME+'\bin;'+$env:PATH
$env:MAVEN_USER_HOME='H:\DevTools\_Cache\maven\user'
$env:TEMP='H:\DevTools\_Downloads\_Temp';$env:TMP=$env:TEMP
$env:MAVEN_OPTS='-Djava.io.tmpdir=H:\DevTools\_Downloads\_Temp'
$arguments=@('-B','-ntp','-C','-Dmaven.repo.local=H:\DevTools\_Cache\maven\repository','-f',(Join-Path $PSScriptRoot 'pom.xml'))
if($Offline){$arguments+='--offline'}
$arguments+=if($Action -eq 'Test'){'test'}else{'test-compile'}
& 'H:\DevTools\BuildTools\Maven\apache-maven-3.10.0\bin\mvn.cmd' @arguments
if($LASTEXITCODE){throw "Maven failed: $LASTEXITCODE"}