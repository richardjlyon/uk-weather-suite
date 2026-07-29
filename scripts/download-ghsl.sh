#!/usr/bin/env bash
# Download GHSL GHS-BUILT-S and GHS-SMOD UK tiles for all epochs
# (add-station-classifier task 1.1). Resumable: re-running skips complete
# files and resumes partial ones. Checksums recorded in checksums.sha256;
# JRC publishes no per-file checksums, so these are recorded at download
# time and re-verified with `--verify`.
set -euo pipefail

BASE="https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
DEST="$(dirname "$0")/../data/ghsl"
# R3/R4 C18-C19 cover all stations; R2_C18 is needed for the one 10 km
# ring (North Rona) that crosses the R3 rasters' northern edge — the
# schema polygons are 41 km wider than the actual rasters, so coverage
# was verified against raster bounds, not the schema.
TILES="R2_C18 R3_C18 R3_C19 R4_C18 R4_C19"
EPOCHS="1975 1980 1985 1990 1995 2000 2005 2010 2015 2020 2025"

mkdir -p "$DEST/built-s" "$DEST/smod" "$DEST/land"
cd "$DEST"

url_for() { # product epoch tile -> url and local path
  local product=$1 epoch=$2 tile=$3
  case $product in
    built-s)
      name="GHS_BUILT_S_E${epoch}_GLOBE_R2023A_54009_100"
      echo "$BASE/GHS_BUILT_S_GLOBE_R2023A/$name/V1-0/tiles/${name}_V1_0_${tile}.zip" ;;
    smod)
      name="GHS_SMOD_E${epoch}_GLOBE_R2023A_54009_1000"
      echo "$BASE/GHS_SMOD_GLOBE_R2023A/$name/V2-0/tiles/${name}_V2_0_${tile}.zip" ;;
    land)
      # GHS-LAND (permanent land fraction, single 2018 epoch) is the land
      # mask: BUILT-S codes sea as 0, not NoData, so land/water must come
      # from this sibling GHSL product on the same 100 m grid.
      name="GHS_LAND_E2018_GLOBE_R2022A_54009_100"
      echo "$BASE/GHS_LAND_GLOBE_R2022A/$name/V1-0/tiles/${name}_V1_0_${tile}.zip" ;;
  esac
}

if [[ "${1:-}" == "--verify" ]]; then
  sha256sum -c checksums.sha256
  for f in built-s/*.zip smod/*.zip land/*.zip; do unzip -tq "$f" >/dev/null || echo "CORRUPT: $f"; done
  echo "verify done"
  exit 0
fi

for product in built-s smod land; do
  case $product in land) epochs="2018" ;; *) epochs="$EPOCHS" ;; esac
  for epoch in $epochs; do
    for tile in $TILES; do
      url=$(url_for $product $epoch $tile)
      out="$product/$(basename "$url")"
      if [[ -f "$out" && ! -f "$out.part" ]]; then
        echo "skip $out"
        continue
      fi
      echo "get  $out"
      touch "$out.part"
      curl -fL --retry 5 --retry-delay 10 -C - -o "$out" "$url"
      rm "$out.part"
    done
  done
done

sha256sum built-s/*.zip smod/*.zip land/*.zip > checksums.sha256
echo "downloaded $(ls built-s/*.zip smod/*.zip land/*.zip | wc -l) files; checksums.sha256 written"
