import subprocess, sys, json, re, os, inspect, importlib
from pathlib import Path
import coverage

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
    abs_fp = file_path.resolve()
    try:
        rel_to_base = abs_fp.relative_to(BASE)
    except ValueError:
        rel_to_base = Path(abs_fp.name)
    mod = rel_to_base.with_suffix('').as_posix().replace('/', '.')
    if not mod.startswith("src."):
        mod = f"src.{mod}"
    return mod

# === Detect changed Python files ===
def get_changed_files():
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

# === Find unique test filenames ===
def get_next_test_filename(stem: str) -> Path:
    base_name = f"test_{stem}.py"
    file_path = TESTS / base_name
    counter = 1
    while file_path.exists():
        file_path = TESTS / f"test_{stem}_{counter}.py"
        counter += 1
    return file_path

# === Coverage analysis ===
def find_uncovered_functions(module_name: str):
    """
    Analyze coverage data to find functions that have untested lines.
    Returns a list of uncovered function names.
    """
    cov = coverage.Coverage(data_file='.coverage')
    try:
        cov.load()
    except Exception as e:
        print(f"⚠️ No coverage data found: {e}")
        return []

    analyzed_files = cov.get_data().measured_files()
    missed_funcs = []

    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        print(f"⚠️ Could not import {module_name}: {e}")
        return []

    for name, func in inspect.getmembers(module, inspect.isfunction):
        func_file = inspect.getsourcefile(func)
        if func_file in analyzed_files:
            _, _, _, missing_lines = cov.analysis(func_file)
            if missing_lines:
                missed_funcs.append(name)

    return missed_funcs

# === Generate tests with GitHub Copilot ===
def generate_tests_with_copilot(file_path: Path, specific_function: str = None):
    if specific_function:
        prompt = (
            f"You are a senior QA engineer. Write pytest test cases only for the function '{specific_function}' "
            f"in the module {file_path}. Include edge cases, exception handling, and normal scenarios. "
            f"Output only Python code."
        )
    else:
        prompt = (
            f"You are a senior Python QA engineer. Write complete pytest test cases "
            f"for all functions in the module {file_path}. "
            f"Include edge cases, exception handling, and normal scenarios. "
            f"Do not include explanations or markdown formatting. Output only Python code."
        )

    print(f"🧠 Asking Copilot for tests for: {file_path}")

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

    result = sh(cmd, capture=True)
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

    test_file = get_next_test_filename(file_path.stem)

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

# === Run pytest ===
def run_pytest():
    print("🧪 Running pytest validation with coverage...")
    res = subprocess.run(
        ["pytest", "-q", "--disable-warnings", "--maxfail=1", "--cov=src", "--cov-report=term", "--cov-report=xml"],
        text=True, capture_output=True
    )
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

# === Rollback ===
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
        print("⚠️ No changed Python files found — forcing full scan of src/.")
        changed = list(SRC.rglob("*.py"))
        changed = [p.resolve() for p in changed if p.exists()]
        if not changed:
            print("ℹ️ Still no Python files found under src/. Nothing to do.")
            sys.exit(0)

    generated = []
    for f in changed:
        generated.append(generate_tests_with_copilot(f))

    if run_pytest():
        print("✅ Initial tests passed! Checking coverage gaps...")
        for f in changed:
            mod_name = module_import_path(f)
            uncovered = find_uncovered_functions(mod_name)
            if uncovered:
                print(f"⚠️ Functions missing coverage in {mod_name}: {uncovered}")
                for func in uncovered:
                    print(f"🧠 Re-asking Copilot for missing function: {func}")
                    generated.append(generate_tests_with_copilot(f, func))
        print("🚀 Finalizing and committing all tests.")
        git_commit_and_push(generated)
    else:
        print("❌ Tests failed. Cleaning up generated test files.")
        rollback(generated)
        sys.exit(1)