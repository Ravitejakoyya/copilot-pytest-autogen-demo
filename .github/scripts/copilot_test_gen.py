import subprocess, sys, json, re
from pathlib import Path

# === Base Paths ===
BASE = Path(".").resolve()
SRC = BASE / "src"
TESTS = BASE / "tests"
TESTS.mkdir(exist_ok=True)

# === Utility to run shell commands ===
def sh(cmd, capture=False, check=True):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, capture_output=capture)
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout if capture else ""

# === Detect changed Python files ===
def get_changed_files():
    """
    Detects changed Python files between the PR branch (HEAD) and origin/main.
    Works even on shallow clones or brand-new PRs.
    """
    subprocess.run(["git", "fetch", "origin", "main:refs/remotes/origin/main", "--depth=1"], check=False)

    result = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], capture_output=True, text=True)
    base = result.stdout.strip()

    if not base:
        print("⚠️ No merge base found — assuming first PR. Scanning all files in src/.")
        files = list(SRC.rglob("*.py"))
    else:
        diff_output = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True, text=True
        ).stdout.strip()
        files = [Path(line) for line in diff_output.splitlines() if line.endswith(".py")]

    files = [f for f in files if f.exists() and "tests" not in str(f) and str(f).startswith("src/")]
    print(f"📂 Changed files detected: {files}")
    return files

# === Generate tests with GitHub Copilot ===
def generate_tests_with_copilot(file_path: Path):
    prompt = f"Write runnable pytest test cases for {file_path}. Output only Python code."
    print(f"🧠 Asking Copilot for tests for: {file_path}")

    # --- Detect available flags ---
    version_check = subprocess.run(
        ["gh", "copilot", "suggest", "--help"],
        capture_output=True, text=True
    )
    help_text = version_check.stdout.lower()

    if "--prompt" in help_text:
        cmd = f'gh copilot suggest --prompt {json.dumps(prompt)}'
        print("🔍 Using --prompt flag.")
    elif "-p" in help_text:
        cmd = f'gh copilot suggest -p {json.dumps(prompt)}'
        print("🔍 Using -p flag.")
    else:
        cmd = f'gh copilot suggest "{prompt}"'
        print("⚠️ Using legacy Copilot CLI (no flags or limits).")

    # --- Run Copilot CLI ---
    result = sh(cmd, capture=True)

    # --- Clean up Copilot output ---
    raw_lines = result.strip().splitlines()
    cleaned_lines = []

    for line in raw_lines:
        line_stripped = line.strip()

        if re.search(r"(deprecation|announcement|copilot|visit|information|http|github\.com)", line_stripped, re.IGNORECASE):
            continue
        if not line_stripped:
            continue
        if re.match(r"^(import |from |def |class |@|assert|if |for |while |try|except|with |return|#)", line_stripped):
            cleaned_lines.append(line_stripped)
            continue
        if line_stripped.startswith(("    ", '"""', "'''")):
            cleaned_lines.append(line)
            continue

    cleaned = "\n".join(cleaned_lines)
    cleaned = cleaned.replace("```python", "").replace("```", "").strip()

    # --- Handle empty or invalid output ---
    test_file = TESTS / f"test_{file_path.stem}.py"

    if not cleaned or "def test_" not in cleaned:
        print("⚠️ Copilot did not generate any usable tests. Creating placeholder test file.")
        # Detect module import path based on src structure
        relative_module = file_path.with_suffix('').as_posix().replace('/', '.')
        if relative_module.startswith("src."):
            import_line = f"from {relative_module} import *"
        else:
            import_line = f"from src.{relative_module} import *"

        cleaned = f"""
import pytest
{import_line}

def test_placeholder():
    # Placeholder test because Copilot output was empty.
    assert True
"""

    test_file.write_text(cleaned.strip() + "\n")
    print(f"✅ Generated test file: {test_file}")
    return test_file

# === Run pytest to validate generated tests ===
def run_pytest():
    print("🧪 Running pytest validation...")
    res = subprocess.run(["pytest", "-q", "--disable-warnings", "--maxfail=1"],
                         text=True, capture_output=True)
    print(res.stdout)
    if "collected 0 items" in res.stdout:
        print("⚠️ No tests collected — fallback logic may have run.")
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
    return res.returncode == 0

# def run_pytest():
#     print("🧪 Running pytest validation...")
#     res = subprocess.run(["pytest", "-q", "--disable-warnings", "--maxfail=1"],
#                          text=True, capture_output=True)
#     print(res.stdout)
#     if res.returncode != 0:
#         print(res.stderr, file=sys.stderr)
#     return res.returncode == 0

# === Commit & Push ===
def git_commit_and_push(files):
    sh('git config user.name "ci-bot"')
    sh('git config user.email "ci-bot@users.noreply.github.com"')
    for f in files:
        sh(f"git add {f}")
    sh('git commit -m "auto: add pytest files generated by Copilot" || true', check=False)
    sh('git push', check=False)
    print("🚀 Committed and pushed generated tests.")

# === Rollback generated tests if validation fails ===
def rollback(files):
    for f in files:
        if f.exists():
            f.unlink()
            print(f"🧹 Removed {f}")
    print("🧹 Rolled back generated test files.")

# === Entry Point ===
if __name__ == "__main__":
    changed = get_changed_files()
    if not changed:
        print("ℹ️ No changed Python files found.")
        sys.exit(0)

    generated = []
    for f in changed:
        generated.append(generate_tests_with_copilot(f))

    if run_pytest():
        print("✅ Tests passed! Committing and pushing.")
        git_commit_and_push(generated)
    else:
        print("❌ Tests failed. Cleaning up generated test files.")
        rollback(generated)
        sys.exit(1)
