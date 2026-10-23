#!/bin/sh
# BoomHackerWhite one-line installer (Linux / macOS).
#
#   curl -fsSL https://raw.githubusercontent.com/TheOwlOps/BoomHackerWhite/main/install.sh | sh
#
# What it does:
#   1. Installs uv (Python toolchain manager) if missing.
#   2. Installs BoomHackerWhite as an isolated tool: commands `bhw`,
#      `boom-hacker-white` and `strix` land in ~/.local/bin.
#   3. Runs `bhw --doctor`, which checks Docker + LLM configuration and
#      tells you exactly what is still missing instead of failing silently.
set -eu

REPO="git+https://github.com/TheOwlOps/BoomHackerWhite@main"

echo "==> BoomHackerWhite installer"

if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv..."
  curl -fsSL https://astral.sh/uv/install.sh | sh
  # Make uv available in this shell session.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv installation failed. Install Python 3.12+ and pip, then run:"
  echo "  pip install uv && uv tool install \"boom-hacker-white @ $REPO\""
  exit 1
fi

echo "==> Installing BoomHackerWhite (this can take a minute)..."
uv tool install --force "boom-hacker-white @ $REPO"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v bhw >/dev/null 2>&1; then
  echo "ERROR: 'bhw' not on PATH. Add ~/.local/bin to your PATH and re-open the shell."
  exit 1
fi

echo
echo "==> Installed: $(bhw --version 2>/dev/null || echo 'bhw')"
echo "==> Running preflight checks..."
echo
# Doctor exits non-zero when prerequisites are missing; that is guidance,
# not an installer failure, so don't abort the script on it.
bhw --doctor || true

echo
echo "Next steps:"
echo "  1. Set your model + key:   export STRIX_LLM='openai/gpt-5.4' && export LLM_API_KEY='sk-...'"
echo "  2. Make sure Docker is running."
echo "  3. First scan:             bhw -t https://your-app.example"
echo "     Or try the demo:        see demo/README.md in the repo."
