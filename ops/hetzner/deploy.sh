#!/usr/bin/env bash
# Deploy a git commit of mc-wichita to Hetzner (wichitawire.com).
#
#   ops/hetzner/deploy.sh            # deploy origin/main
#   ops/hetzner/deploy.sh <sha>      # deploy a specific commit
#   ops/hetzner/deploy.sh --rollback # point app back at the previous release
#
# Layout on the server:
#   /opt/wichita/repo.git        bare mirror of github.com/mattcarp/mc-wichita (public)
#   /opt/wichita/releases/<sha>  one directory per deployed commit, REVISION file inside
#   /opt/wichita/app ->          symlink to the live release (systemd WorkingDirectory)
#   /opt/wichita/data            state; never inside a release
#
# Each deploy: export the commit, import-check api_server with the live venv, switch the
# symlink atomically, restart, health-check, and switch back automatically on failure.
# Python dependencies are NOT installed automatically: if requirements.txt changed, the
# import check is the gate, and missing packages are installed deliberately.
set -euo pipefail

HOST="${WICHITA_HOST:-matt@91.99.2.222}"
REF="${1:-origin/main}"

if [[ "$REF" == "--rollback" ]]; then
  ssh -o BatchMode=yes "$HOST" 'bash -s' <<'EOF'
set -euo pipefail
cd /opt/wichita
cur=$(readlink app); prev=$(cat releases/.previous 2>/dev/null || true)
[[ -n "$prev" && -d "$prev" ]] || { echo "no previous release recorded"; exit 1; }
ln -sfn "$prev" app.new && mv -T app.new app && echo "$cur" > releases/.previous
sudo systemctl restart wichita-dashboard
for i in $(seq 1 20); do sleep 1; curl -fs -m 3 -o /dev/null http://127.0.0.1:3140/health && { echo "rolled back to $prev"; exit 0; }; done
echo "health check failed after rollback"; exit 1
EOF
  exit $?
fi

SHA=$(git rev-parse --verify "$REF^{commit}")
REMOTE_SHA=$(gh api repos/mattcarp/mc-wichita/commits/"$SHA" -q .sha 2>/dev/null || true)
[[ "$REMOTE_SHA" == "$SHA" ]] || { echo "commit $SHA is not on GitHub; push first"; exit 1; }
echo "deploying ${SHA:0:7}"

ssh -o BatchMode=yes "$HOST" "SHA=$SHA bash -s" <<'EOF'
set -euo pipefail
cd /opt/wichita
mkdir -p releases
[[ -d repo.git ]] || git clone -q --bare https://github.com/mattcarp/mc-wichita repo.git
git --git-dir=repo.git fetch -q origin '+refs/heads/*:refs/heads/*'

rel="/opt/wichita/releases/${SHA:0:12}"
if [[ ! -d "$rel" ]]; then
  mkdir "$rel.tmp"
  git --git-dir=repo.git archive "$SHA" | tar -x -C "$rel.tmp"
  echo "$SHA" > "$rel.tmp/REVISION"
  mv "$rel.tmp" "$rel"
fi

# Gate: the live venv must import the app from the new release.
(cd "$rel" && /opt/wichita/venv/bin/python -c "import api_server" >/dev/null 2>"$rel.importcheck") || {
  echo "import check failed, live site untouched:"; tail -5 "$rel.importcheck"; exit 1; }
rm -f "$rel.importcheck"

cur=$(readlink app || true)
if [[ "$cur" == "$rel" ]]; then echo "already live"; exit 0; fi
[[ -n "$cur" ]] && echo "$cur" > releases/.previous
ln -sfn "$rel" app.new && mv -T app.new app
sudo systemctl restart wichita-dashboard

ok=0
for i in $(seq 1 20); do
  sleep 1
  if curl -fs -m 3 -o /dev/null http://127.0.0.1:3140/health \
     && curl -fs -m 3 -o /dev/null http://127.0.0.1:3140/dashboard/clerk-env.json; then ok=1; break; fi
done
if [[ $ok != 1 ]]; then
  echo "health check failed; restoring $cur"
  ln -sfn "$cur" app.new && mv -T app.new app
  sudo systemctl restart wichita-dashboard
  exit 1
fi

# Keep the five newest releases plus whatever is live or previous.
keep="$(readlink app) $(cat releases/.previous 2>/dev/null || true)"
ls -1dt releases/*/ | sed 's:/$::' | tail -n +6 | while read -r d; do
  case " $keep " in *" /opt/wichita/$d "*|*" $d "*) ;; *) rm -rf "$d" ;; esac
done
echo "live: $(cat app/REVISION)"
EOF
