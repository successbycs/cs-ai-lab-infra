#!/usr/bin/env bash
set -euo pipefail

repository_url='https://github.com/successbycs/openworker.git'
revision='a9b388b0394d106f69b35326ee954edf7a9d0027'
deployment_branch='openworker-t480-docker'
deployment_root='/home/chris/projects/openworker'
state_dir='/home/chris/.local/state/cs-ai-lab'

if [[ -e "$deployment_root" ]]; then
  [[ -d "$deployment_root/.git" ]] || { echo 'OpenWorker target is not a Git checkout.' >&2; exit 4; }
  [[ "$(git -C "$deployment_root" remote get-url origin)" == "$repository_url" ]] || { echo 'OpenWorker origin differs.' >&2; exit 4; }
  git -C "$deployment_root" diff --quiet && git -C "$deployment_root" diff --cached --quiet || { echo 'OpenWorker checkout has local changes.' >&2; exit 4; }
else
  mkdir -p /home/chris/projects
  git clone --no-checkout "$repository_url" "$deployment_root"
fi

cd "$deployment_root"
if [[ "$(git rev-parse HEAD 2>/dev/null || true)" != "$revision" ]]; then
  git fetch --depth 1 origin "refs/heads/$deployment_branch"
  git checkout --detach FETCH_HEAD
fi
test "$(git rev-parse HEAD)" = "$revision"

umask 077
if [[ ! -f .env ]]; then
  cp .env.example .env
  sed -i "s/REPLACE_WITH_A_RANDOM_TOKEN/$(openssl rand -hex 32)/" .env
  chmod 600 .env
fi
mkdir -p projects "$state_dir"
docker compose config --quiet

pid_file="$state_dir/openworker-deploy.pid"
log_file="$state_dir/openworker-deploy.log"
if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
  echo "OpenWorker deployment is already running: $(cat "$pid_file")"
  exit 0
fi

nohup bash -c 'set -euo pipefail; cd /home/chris/projects/openworker; docker compose up -d --build; for attempt in $(seq 1 90); do curl --fail --silent --max-time 5 http://127.0.0.1:8765/v1/health >/dev/null && curl --fail --silent --max-time 5 http://127.0.0.1:8780 >/dev/null && exit 0; sleep 2; done; exit 1' >"$log_file" 2>&1 < /dev/null &
echo $! > "$pid_file"
echo "OpenWorker deployment started: pid=$(cat "$pid_file") log=$log_file"
