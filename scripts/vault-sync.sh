#!/bin/sh
# Daily vault backup for when Obsidian is closed (obsidian-git syncs while the app is open).
# Scheduled by ~/Library/LaunchAgents/com.akash.vault-sync.plist; log: ~/Library/Logs/vault-sync.log
cd "${1:?usage: vault-sync.sh <vault-path>}" || exit 1
now() { date '+%F %T'; }
if pgrep -xq Obsidian; then echo "$(now) Obsidian open, plugin handles sync"; exit 0; fi
git add -A
git diff --cached --quiet || git commit -qm "vault backup: $(date '+%Y-%m-%d %H:%M:%S')"
git pull --no-rebase --no-edit -q || { git merge --abort 2>/dev/null; echo "$(now) pull failed, left for obsidian-git"; exit 1; }
git push -q && echo "$(now) synced"
