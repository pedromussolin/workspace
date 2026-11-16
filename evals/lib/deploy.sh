#!/usr/bin/env bash
# Builds the made-up deploy the deploy-check evals run against, inside the run's HOME.
#
# Order shared, bff, front, all in the sandbox. Every values file arrives on 2026-11-09; only the
# BFF moves again, on 2026-11-12 at 14:00 (-03:00), to version b2c3d4e. The real `ws deploy-check`
# reads this local argocd repo; the Datadog tools are the mocks of evals/mocks/datadog.
set -euo pipefail

argocd_commit() {
  local repo=$1 when=$2 subject=$3
  git -C "$repo" add -A
  GIT_AUTHOR_NAME="Dev Example" GIT_AUTHOR_EMAIL=dev@example.com GIT_AUTHOR_DATE="$when" \
    GIT_COMMITTER_NAME="Dev Example" GIT_COMMITTER_EMAIL=dev@example.com GIT_COMMITTER_DATE="$when" \
    git -C "$repo" commit -q -m "$subject"
}

values_file() {
  local service=$1 version=$2
  printf 'image:\n  repository: registry.example/%s\n  tag: "%s"\nenv:\n  - name: DD_ENV\n    value: "sandbox"\n  - name: DD_VERSION\n    value: "%s"\n' \
    "$service" "$version" "$version"
}

build_deploy_fixture() {
  mkdir -p "$HOME/.config/workspace"
  cat > "$HOME/.config/workspace/config.toml" <<'TOML'
[deploy_check]
order = ["shared", "bff", "front"]

[deploy_check.env_tags]
sandbox = "sandbox"

[deploy_check.services.shared]
service = "demo-shared"
kind = "apm"
argocd = "~/repos/demo-argocd"
values = { sandbox = "envs/sandbox/demo-shared.yaml" }

[deploy_check.services.bff]
service = "demo-bff"
kind = "apm"
span_filter = "operation_name:web.request"
argocd = "~/repos/demo-argocd"
values = { sandbox = "envs/sandbox/demo-bff.yaml" }

[deploy_check.services.front]
service = "demo-front"
kind = "rum"
argocd = "~/repos/demo-argocd"
values = { sandbox = "envs/sandbox/demo-front.yaml" }
TOML

  local repo="$HOME/repos/demo-argocd"
  mkdir -p "$repo/envs/sandbox"
  git -C "$repo" init -q -b master
  values_file demo-shared a1b2c3d > "$repo/envs/sandbox/demo-shared.yaml"
  values_file demo-bff 9f8e7d6 > "$repo/envs/sandbox/demo-bff.yaml"
  values_file demo-front 5a6b7c8 > "$repo/envs/sandbox/demo-front.yaml"
  argocd_commit "$repo" 2026-11-09T10:00:00-03:00 "sandbox: versões iniciais"
  values_file demo-bff b2c3d4e > "$repo/envs/sandbox/demo-bff.yaml"
  argocd_commit "$repo" 2026-11-12T14:00:00-03:00 "sandbox: demo-bff b2c3d4e"
}
