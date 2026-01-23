#!/usr/bin/env pwsh

<#
Initialize the Cosmos DB Emulator schema for Ground Truth Curator.

This script mirrors the CD workflow's Cosmos DB creation steps, but targets
the local Cosmos DB Emulator (key auth + SSL verify disabled).

It creates:
- Database:                    $DbName
- Ground truth container:      $GtContainer            (HPK: /datasetName + /bucket, with indexing policy)
- Assignments container:       $AssignmentsContainer   (PK: /pk)
- Tags container:              $TagsContainer          (PK: /pk)
- Tag definitions container:   $TagDefinitionsContainer (PK: /tag_key)

Environment variable shortcuts (override defaults):
  COSMOS_EMULATOR_ENDPOINT, COSMOS_EMULATOR_KEY,
  GTC_COSMOS_DB_NAME, GTC_COSMOS_CONTAINER_GT, GTC_COSMOS_CONTAINER_ASSIGNMENTS, GTC_COSMOS_CONTAINER_TAGS,
  GTC_COSMOS_CONTAINER_TAG_DEFINITIONS, GTC_COSMOS_DB_INDEXING_POLICY
#>

param(
    [Alias('e')]
    [string]$Endpoint,

    [Alias('k')]
    [string]$Key,

    [Alias('d')]
    [string]$DbName,

    [string]$GtContainer,

    [string]$AssignmentsContainer,

    [string]$TagsContainer,

    [string]$TagDefinitionsContainer,

    [Alias('i')]
    [string]$IndexingPolicy,

    [switch]$DryRun,

    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
    $defaultEndpoint = 'http://localhost:8081'
    Write-Host @"
Usage: $(Split-Path -Leaf $PSCommandPath) [options]

Options:
  -Endpoint URL              Emulator endpoint (default: $defaultEndpoint)
  -Key KEY                   Emulator master key (default: well-known emulator key)
  -DbName NAME               Database name (default: env GTC_COSMOS_DB_NAME or 'gt-curator')
  -GtContainer NAME          Ground truth container name (default: env GTC_COSMOS_CONTAINER_GT or 'ground_truth')
  -AssignmentsContainer NAME Assignments container name (default: env GTC_COSMOS_CONTAINER_ASSIGNMENTS or 'assignments')
  -TagsContainer NAME        Tags container name (default: env GTC_COSMOS_CONTAINER_TAGS or 'tags')
  -TagDefinitionsContainer NAME Tag definitions container name (default: env GTC_COSMOS_CONTAINER_TAG_DEFINITIONS or 'tag_definitions')
  -IndexingPolicy PATH       Indexing policy JSON for ground truth container
                             (default: scripts/indexing-policy.json)
  -DryRun                    Print the command without running it
  -Help                      Show this help and exit

Environment variable shortcuts (override defaults):
  COSMOS_EMULATOR_ENDPOINT, COSMOS_EMULATOR_KEY,
  GTC_COSMOS_DB_NAME, GTC_COSMOS_CONTAINER_GT, GTC_COSMOS_CONTAINER_ASSIGNMENTS, GTC_COSMOS_CONTAINER_TAGS,
  GTC_COSMOS_CONTAINER_TAG_DEFINITIONS, GTC_COSMOS_DB_INDEXING_POLICY

Notes:
  - Requires Cosmos Emulator to be running and reachable at the endpoint.
  - Uses key-based auth and passes --no-verify (required for emulator TLS).
"@
}

function Quote-Arg {
    param([Parameter(Mandatory = $true)][string]$Value)

    try {
        return [System.Management.Automation.Language.CodeGeneration]::QuoteArgument($Value)
    } catch {
        if ($Value -match '[\s''"]') {
            return "'" + ($Value -replace "'", "''") + "'"
        }
        return $Value
    }
}

if ($Help.IsPresent) {
    Show-Usage
    exit 0
}

$scriptDir = $PSScriptRoot
$backendDir = (Resolve-Path (Join-Path $scriptDir '..')).Path
$repoRoot = (Resolve-Path (Join-Path $backendDir '../..')).Path

$defaultEndpoint = 'http://localhost:8081'
# Well-known Cosmos Emulator master key
$defaultKey = 'C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=='
$defaultIndexingPolicy = (Join-Path $scriptDir 'indexing-policy.json')

if ([string]::IsNullOrWhiteSpace($Endpoint)) {
    $Endpoint = if ($env:COSMOS_EMULATOR_ENDPOINT) { $env:COSMOS_EMULATOR_ENDPOINT } else { $defaultEndpoint }
}
if ([string]::IsNullOrWhiteSpace($Key)) {
    $Key = if ($env:COSMOS_EMULATOR_KEY) { $env:COSMOS_EMULATOR_KEY } else { $defaultKey }
}
if ([string]::IsNullOrWhiteSpace($DbName)) {
    $DbName = if ($env:GTC_COSMOS_DB_NAME) { $env:GTC_COSMOS_DB_NAME } else { 'gt-curator' }
}
if ([string]::IsNullOrWhiteSpace($GtContainer)) {
    $GtContainer = if ($env:GTC_COSMOS_CONTAINER_GT) { $env:GTC_COSMOS_CONTAINER_GT } else { 'ground_truth' }
}
if ([string]::IsNullOrWhiteSpace($AssignmentsContainer)) {
    $AssignmentsContainer = if ($env:GTC_COSMOS_CONTAINER_ASSIGNMENTS) { $env:GTC_COSMOS_CONTAINER_ASSIGNMENTS } else { 'assignments' }
}
if ([string]::IsNullOrWhiteSpace($TagsContainer)) {
    $TagsContainer = if ($env:GTC_COSMOS_CONTAINER_TAGS) { $env:GTC_COSMOS_CONTAINER_TAGS } else { 'tags' }
}
if ([string]::IsNullOrWhiteSpace($TagDefinitionsContainer)) {
    $TagDefinitionsContainer = if ($env:GTC_COSMOS_CONTAINER_TAG_DEFINITIONS) { $env:GTC_COSMOS_CONTAINER_TAG_DEFINITIONS } else { 'tag_definitions' }
}
if ([string]::IsNullOrWhiteSpace($IndexingPolicy)) {
    $IndexingPolicy = if ($env:GTC_COSMOS_DB_INDEXING_POLICY) { $env:GTC_COSMOS_DB_INDEXING_POLICY } else { $defaultIndexingPolicy }
}

if ([string]::IsNullOrWhiteSpace($DbName)) {
    Write-Error "Error: database name is required (-DbName or env:GTC_COSMOS_DB_NAME)."
    exit 2
}

if (-not (Test-Path -Path $IndexingPolicy -PathType Leaf)) {
    Write-Error "Error: indexing policy file not found: $IndexingPolicy"
    Write-Host "Tip: expected at $defaultIndexingPolicy"
    exit 1
}

# Prefer uv if available (keeps dependencies aligned with backend/pyproject.toml)
$runner = @()
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $runner = @('uv', 'run', 'python')
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $runner = @('python3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $runner = @('python')
} else {
    Write-Error "Error: couldn't find a Python interpreter (expected 'uv', 'python3', or 'python')."
    exit 1
}

$containerManager = Join-Path $backendDir 'scripts/cosmos_container_manager.py'

$cmd = @()
$cmd += $runner
$cmd += @(
    $containerManager,
    '--endpoint', $Endpoint,
    '--key', $Key,
    '--no-verify',
    '--db', $DbName,
    '--gt-container', $GtContainer,
    '--assignments-container', $AssignmentsContainer,
    '--tags-container', $TagsContainer,
    '--tag-definitions-container', $TagDefinitionsContainer,
    '--indexing-policy', $IndexingPolicy
)

Write-Host "Repo root:   $repoRoot"
Write-Host "Backend dir: $backendDir"
Write-Host "Endpoint:    $Endpoint"
Write-Host "Database:    $DbName"
Write-Host "Containers:  GT=$GtContainer, assignments=$AssignmentsContainer, tags=$TagsContainer, tag_def=$TagDefinitionsContainer"
Write-Host "Indexing:    $IndexingPolicy"
Write-Host ""

Write-Host "Running:"
Write-Host ("  " + (($cmd | ForEach-Object { Quote-Arg -Value $_ }) -join ' '))
Write-Host ""

if ($DryRun.IsPresent) {
    Write-Host 'Dry-run: not executing.'
    exit 0
}

# Run from backend dir so relative imports/config match existing docs.
Push-Location $backendDir
try {
    $exe = $cmd[0]
    $args = @()
    if ($cmd.Count -gt 1) {
        $args = $cmd[1..($cmd.Count - 1)]
    }

    & $exe @args
} finally {
    Pop-Location
}
