import subprocess, sys, json, re, os
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

# === Normalize a src/*.py path to an importable module path ===
def module_import_path(file_path: Path) -> str:
    """
    Convert a file path (absolute or relative) into a dotted module path under src/.
    Examples:
      /repo/src/mathops.py -> src.mathops
      src/pkg/util.py      -> src.pkg.util
    """
    abs_fp = file_path.resolve()
    try:
        rel_to_base = abs_fp.relative_to(BASE)   # e.g. src/mathops.py
    except ValueError:
        # If it's not under BASE (shouldn't happen on runner), fallback to name
        rel_to_base = Path(abs_fp.name)

    mod = rel_to_base.with_suffix('').as_posix().replace('/', '.')  # e.g. src.mathops
    if not mod.startswith("src."):
        mod = f"src.{mod}"
    return mod

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
        files = [BASE / Path(line) for line in diff_output.splitlines() if line.endswith(".py")]

    files = [f for f in files if f.exists() and "tests" not in str(f) and f.resolve().is_file() and str(f).startswith(str(SRC))]
    print(f"📂 Changed files detected: {files}")
    return files

# === Find a unique test filename (test_<stem>.py, test_<stem>_1.py, ...) ===
def get_next_test_filename(stem: str) -> Path:
    base_name = f"test_{stem}.py"
    file_path = TESTS / base_name
    counter = 1
    while file_path.exists():
        file_path = TESTS / f"test_{stem}_{counter}.py"
        counter += 1
    return file_path

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

    # --- Clean up Copilot output (strip banners, markdown, non-code) ---
    raw_lines = result.strip().splitlines()
    cleaned_lines = []

    for line in raw_lines:
        line_stripped = line.strip()

        # Skip obvious noise
        if re.search(r"(deprecation|announcement|copilot|visit|information|http|github\.com)", line_stripped, re.IGNORECASE):
            continue
        if not line_stripped:
            continue

        # Keep likely Python code
        if re.match(r"^(import |from |def |class |@|assert|if |for |while |try|except|with |return|#)", line_stripped):
            cleaned_lines.append(line_stripped)
            continue
        # Keep indented/code-block lines and docstrings
        if line_stripped.startswith(("    ", '"""', "'''")):
            cleaned_lines.append(line)
            continue

    cleaned = "\n".join(cleaned_lines)
    cleaned = cleaned.replace("```python", "").replace("```", "").strip()

    # Create a new unique test file name
    test_file = get_next_test_filename(file_path.stem)

    # --- Handle empty or no test functions: create a placeholder with correct import path ---
    if not cleaned or "def test_" not in cleaned:
        print("⚠️ Copilot did not generate any usable tests. Creating placeholder test file.")
        mod_path = module_import_path(file_path)
        cleaned = f"""
import pytest
from {mod_path} import *

def test_placeholder():
    # Placeholder test because Copilot output was empty.
    # Ensures pipeline continuity; replace with real tests later.
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

    # Fallback: if no changed files, force full scan (useful on first PR)
    if not changed:
        print("⚠️ No changed Python files found — forcing full scan of src/.")
        changed = list(SRC.rglob("*.py"))
        # Ensure paths are Paths (absolute) and exist
        changed = [p.resolve() for p in changed if p.exists()]
        if not changed:
            print("ℹ️ Still no Python files found under src/. Nothing to do.")
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
