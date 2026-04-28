param(
    [string]$ImageName = "ndlocr-cli-cpu-test",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Repo = Join-Path $Root "external\ndlocr_cli"
$SplitDir = Join-Path $Root "ocr_output\manshu_full_pipeline_211_215_resplit\split_halves"
$OutDir = Join-Path $Root "ocr_output\ndlocr_full_page211"
$Config = Join-Path $Repo "config_cpu_page211.yml"

if (-not (Test-Path $Repo)) {
    throw "NDLOCR full repository is missing: $Repo"
}
if (-not (Test-Path $Config)) {
    throw "CPU test config is missing: $Config"
}
if (-not (Test-Path (Join-Path $SplitDir "page_0211_right.png"))) {
    throw "Page 211 right-half image is missing in: $SplitDir"
}
if (-not (Test-Path (Join-Path $SplitDir "page_0211_left.png"))) {
    throw "Page 211 left-half image is missing in: $SplitDir"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (-not $SkipBuild) {
    docker build -t $ImageName -f (Join-Path $Repo "docker\Dockerfile") $Repo
}

$mountSplit = "${SplitDir}:/data/input:ro"
$mountOut = "${OutDir}:/data/output"
$mountConfig = "${Config}:/root/ocr_cli/config_cpu_page211.yml:ro"

docker run --rm `
    -v $mountSplit `
    -v $mountOut `
    -v $mountConfig `
    $ImageName `
    python main.py infer /data/input/page_0211_right.png /data/output/right -s f -p 1..3 -x -c config_cpu_page211.yml

docker run --rm `
    -v $mountSplit `
    -v $mountOut `
    -v $mountConfig `
    $ImageName `
    python main.py infer /data/input/page_0211_left.png /data/output/left -s f -p 1..3 -x -c config_cpu_page211.yml

python (Join-Path $Root "scripts\compare_ndlocr_models_page211.py")
