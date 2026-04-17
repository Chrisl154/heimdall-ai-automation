"""
Heimdall first-run setup script.
Pure Python stdlib — no pip installs required.
"""
import base64
import getpass
import http.client
import os
import secrets
import sys
from pathlib import Path


def check_python_version():
    version = sys.version_info
    if version >= (3, 11):
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (required: 3.11+)")
        return False


def check_ollama():
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=5)
        conn.request("GET", "/api/tags")
        response = conn.getresponse()
        response.read()
        if response.status == 200:
            print("✓ Ollama reachable at http://127.0.0.1:11434")
            return True
        else:
            print(f"✗ Ollama returned status {response.status}")
            return False
    except Exception:
        print("✗ Ollama not reachable at http://127.0.0.1:11434")
        return False


def check_lmstudio():
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 1234, timeout=5)
        conn.request("GET", "/v1/models")
        response = conn.getresponse()
        response.read()
        if response.status == 200:
            print("✓ LM Studio reachable at http://127.0.0.1:1234")
            return True
        else:
            print(f"✗ LM Studio returned status {response.status}")
            return False
    except Exception:
        print("✗ LM Studio not reachable at http://127.0.0.1:1234")
        return False


def generate_fernet_key():
    """Generate a Fernet-compatible key using stdlib only."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def prompt_vault_key():
    key = getpass.getpass("Enter HEIMDALL_VAULT_KEY (leave blank to auto-generate): ").strip()
    if not key:
        key = generate_fernet_key()
        print(f"  Auto-generated key: {key}")
        print("  Save this somewhere safe — losing it means losing access to your vault.")
    return key


def prompt_anthropic_key():
    key = getpass.getpass("Enter ANTHROPIC_API_KEY (leave blank to skip): ").strip()
    return key if key else None


def prompt_github_token():
    token = getpass.getpass("Enter GITHUB_TOKEN (leave blank to skip): ").strip()
    return token if token else None


def read_env_example():
    example_path = Path(".env.example")
    if not example_path.exists():
        return []
    return example_path.read_text(encoding="utf-8").splitlines()


def write_env(env_vars):
    lines = read_env_example()
    output_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            output_lines.append(line)
            continue
        for key, value in env_vars.items():
            if line.startswith(f"{key}="):
                output_lines.append(f"{key}={value}")
                break
        else:
            output_lines.append(line)
    Path(".env").write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def main():
    print("=" * 60)
    print("Heimdall AI Automation — First-Run Setup")
    print("=" * 60)
    print()

    print("Running checks...")
    print()

    check_python_version()
    check_ollama()
    check_lmstudio()

    print()
    print("Configuring environment variables...")
    print()

    vault_key = prompt_vault_key()
    anthropic_key = prompt_anthropic_key()
    github_token = prompt_github_token()

    env_vars = {
        "HEIMDALL_VAULT_KEY": vault_key,
        "HEIMDALL_SECRET_KEY": secrets.token_hex(32),
    }
    if anthropic_key:
        env_vars["ANTHROPIC_API_KEY"] = anthropic_key
    if github_token:
        env_vars["GITHUB_TOKEN"] = github_token

    if Path(".env").exists():
        overwrite = input("\n.env already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite == "y":
            write_env(env_vars)
            print("✓ .env updated")
        else:
            print("✗ Skipped .env update")
    else:
        write_env(env_vars)
        print("✓ .env created")

    print()
    print("=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print()
    print("To start the backend:")
    print("  bash start_backend.sh        (Linux/macOS/WSL)")
    print("  start_backend.bat            (Windows CMD)")
    print()
    print("To start the frontend:")
    print("  bash start_frontend.sh       (Linux/macOS/WSL)")
    print("  start_frontend.bat           (Windows CMD)")
    print()


if __name__ == "__main__":
    main()
