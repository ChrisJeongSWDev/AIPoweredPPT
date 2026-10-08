#!/bin/bash
wt="C:/Users/2021670/.ma-stg/stg.jefKC919"
cd "$wt"
changed=()
while IFS= read -r -d '' p; do
  changed+=("$p")
done < <(git diff HEAD --name-status -z | awk -v RS='\0' -v ORS='\0' '
  NR%2==1 { st=$0 }
  NR%2==0 { if (st ~ /^[^D]/) print $0 }
')

echo "--- Phase D ---"
declare -p changed
for p in "${changed[@]}"; do
  echo "path length: ${#p}"
  printf '%q\n' "$p"
  echo -n "$p" | od -An -tx1 -v
done

echo "--- Phase E ---"
manifest="C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/approved_write_manifest.txt"
command -v grep
grep --version | head -n 1
echo "LC_ALL=$LC_ALL"
echo "LANG=$LANG"
echo "manifest realpath: $manifest"
sha256sum "$manifest" | awk '{print $1}'

overreach=()
for p in "${changed[@]}"; do
  grep -Fxq "$p" "$manifest" 2>/dev/null || overreach+=("$p")
done
declare -p overreach