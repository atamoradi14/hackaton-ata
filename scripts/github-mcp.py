"""Launch official read-only GitHub MCP using the existing gh keyring."""
import os
import subprocess
import sys

token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
if token.returncode or not token.stdout.strip():
    raise SystemExit("Run gh auth login interactively; no GitHub credential available")
environment = os.environ.copy()
environment["GITHUB_PERSONAL_ACCESS_TOKEN"] = token.stdout.strip()
command = ["docker", "run", "--rm", "-i", "--env", "GITHUB_PERSONAL_ACCESS_TOKEN",
           "ghcr.io/github/github-mcp-server@sha256:ffced0d76e77428532a2ced185516992d77fd146d69eec2f244e6237d1a97796",
           "stdio", "--read-only", "--toolsets", "repos,issues,pull_requests,users,context"]
raise SystemExit(subprocess.call(command, env=environment))
