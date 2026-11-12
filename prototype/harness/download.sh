#!/bin/zsh
# Segmented, resumable download: N parallel range requests, each retried until complete, then joined.
# Usage: download.sh <url> <out-file> <total-bytes> [segments]
set -u
URL=$1; OUT=$2; TOTAL=$3; N=${4:-8}
SEG=$(( (TOTAL + N - 1) / N ))
fetch() {  # $1 = index
  local i=$1 start=$(( $1 * SEG )) end=$(( ($1 + 1) * SEG - 1 )) f="$OUT.seg$1"
  (( end >= TOTAL )) && end=$(( TOTAL - 1 ))
  local want=$(( end - start + 1 ))
  while true; do
    local have=$(stat -f %z "$f" 2>/dev/null || echo 0)
    (( have >= want )) && break
    curl -sS -L --speed-limit 50000 --speed-time 30 --connect-timeout 20 \
      -r "$(( start + have ))-$end" "$URL" >> "$f" || sleep 3
  done
}
for i in $(seq 0 $(( N - 1 ))); do fetch $i & done
wait
: > "$OUT.joined"
for i in $(seq 0 $(( N - 1 ))); do cat "$OUT.seg$i" >> "$OUT.joined"; done
SIZE=$(stat -f %z "$OUT.joined")
if [[ $SIZE -eq $TOTAL ]]; then
  mv "$OUT.joined" "$OUT"; rm -f "$OUT".seg*; echo "done $OUT $SIZE bytes"
else
  echo "size mismatch: $SIZE vs $TOTAL"; exit 1
fi
