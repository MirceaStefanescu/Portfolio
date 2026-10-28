[CmdletBinding()]
param([ValidateSet('Test','Run','Sync')][string]$Action='Test')
$ErrorActionPreference='Stop'
$project=$PSScriptRoot
$python=Join-Path $PSScriptRoot '.devtools\Windows\Python-3.15.0\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PIP_CACHE_DIR='G:\DevTools\_Cache\pip'
$env:TEMP='G:\DevTools\_Downloads\_Temp';$env:TMP=$env:TEMP
$env:PYTHONPATH=Join-Path $project 'src'
if(!(Test-Path -LiteralPath $python)){throw 'Approved project Python environment missing; see G:\DevTools\README.md'}
Push-Location -LiteralPath $project
try {
  switch($Action){
    Test { & $python -B -m pytest -q tests -o 'cache_dir=G:/DevTools/_Cache/pytest/LLMOpsEvaluation' }
    Sync { & $python -B -m pip install --only-binary=:all: --disable-pip-version-check -r (Join-Path $project 'requirements-dev.txt') }
    Run { & $python -B -m eval_harness.cli --task tasks/contextual.json }
  }
  if($LASTEXITCODE){throw "Python operation failed: $LASTEXITCODE"}
} finally { Pop-Location }