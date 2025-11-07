import subprocess, sys, json, re, os, inspect, importlib, ast
from pathlib import Path
import coverage

# === Base Paths ===
BASE = Path(".").resolve()
SRC = BASE / "src"
TESTS = BASE / "tests"
TESTS.mkdir(exist_ok=True)

# === Utility: shell runner ===
def sh(cmd, capture=False, check=True):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, capture_output=capture)
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout if capture else ""

# === Convert src path to Python import path ===
def module_import_path(file_path: Path) -> str:
    abs_fp = file_path.resolve()
    rel_to_base = abs_fp.relative_to(BASE)
    mod = rel_to_base.with_suffix('').as_posix().replace('/', '.')
    if not mod.startswith("src."):
        mod = f"src.{mod}"
    return mod

# === Detect changed Python files ===
def get_changed_files():
    subprocess.run(["git", "fetch", "origin", "main:refs/remotes/origin/main", "--depth=1"], check=False)
    base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], capture_output=True, text=True).stdout.strip()

    if not base:
        print("⚠️ No merge base found — scanning all src/ files.")
        files = list(SRC.rglob("*.py"))
    else:
        diff = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                              capture_output=True, text=True).stdout.strip()
        files = [BASE / Path(line) for line in diff.splitlines() if line.endswith(".py")]

    files = [f for f in files if f.exists() and "tests" not in str(f) and f.is_file() and str(f).startswith(str(SRC))]
    print(f"📂 Changed files detected: {files}")
    return files

# === Always one canonical test file per module ===
def get_test_file_for_module(stem: str) -> Path:
    return TESTS / f"test_{stem}.py"

# === Detect uncovered functions from coverage ===
def find_uncovered_functions(module_name: str):
    try:
        cov = coverage.Coverage(data_file='.coverage')
        cov.load()
    except Exception:
        print("⚠️ No coverage data found — skipping coverage gap check.")
        return []

    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        print(f"⚠️ Could not import {module_name}: {e}")
        return []

    missed = []
    analyzed = cov.get_data().measured_files()
    for name, func in inspect.getmembers(module, inspect.isfunction):
        func_file = inspect.getsourcefile(func)
        if func_file in analyzed:
            _, _, _, missing = cov.analysis(func_file)
            if missing:
                missed.append(name)
    return missed

# === Extract all function names from file using AST ===
def extract_function_names(file_path: Path):
    try:
        tree = ast.parse(file_path.read_text())
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        return funcs
    except Exception:
        return []

# === Copilot Test Generation ===
def generate_tests_with_copilot(file_path: Path, specific_function: str = None):
    functions = extract_function_names(file_path)
    func_list = ", ".join(functions) if functions else "No functions found"

    if specific_function:
        prompt = (
            f"You are a Python QA engineer. Write detailed pytest tests for the function '{specific_function}' "
            f"in the file {file_path.name}. Include normal, edge, and invalid cases. Output only valid Python code."
        )
    else:
        prompt = (
            f"You are a senior Python QA engineer. The file {file_path.name} contains these functions: {func_list}. "
            f"Write runnable pytest test cases covering EVERY function. Include success, failure, and edge-case scenarios. "
            f"Do not include explanations or markdown formatting. Output Python code only."
        )

    print(f"🧠 Asking Copilot for tests for: {file_path.name}")

    version_check = subprocess.run(["gh", "copilot", "suggest", "--help"],
                                   capture_output=True, text=True)
    help_text = version_check.stdout.lower()
    if "--prompt" in help_text:
        cmd = f'gh copilot suggest --prompt {json.dumps(prompt)} --limit 1'
    elif "-p" in help_text:
        cmd = f'gh copilot suggest -p {json.dumps(prompt)} --limit 1'
    else:
        cmd = f'gh copilot suggest "{prompt}"'

    result = sh(cmd, capture=True)
    lines = []
    for line in result.splitlines():
        l = line.strip()
        if not l or "copilot" in l.lower() or "visit" in l.lower():
            continue
        if re.match(r"^(import |from |def |class |@|assert|if |for |while |try|except|with |return|#)", l):
            lines.append(line)
            continue
        if l.startswith(("    ", '"""', "'''")):
            lines.append(line)
    cleaned = "\n".join(lines).replace("```python", "").replace("```", "").strip()

    mod_path = module_import_path(file_path)
    test_file = get_test_file_for_module(file_path.stem)

    # Fallback safety: avoid committing empty test
    if not cleaned or "def test_" not in cleaned:
        print(f"⚠️ Copilot returned no usable tests for {file_path.name}.")
        return None

    # Ensure valid imports
    if "import pytest" not in cleaned:
        cleaned = f"import pytest\nfrom {mod_path} import *\n\n{cleaned}"

    test_file.write_text(cleaned.strip() + "\n")
    print(f"✅ Generated test file: {test_file}")
    return test_file

# === Run pytest with coverage ===
def run_pytest():
    print("🧪 Running pytest validation with coverage...")
    res = subprocess.run(
        ["pytest", "-q", "--disable-warnings", "--maxfail=1",
         "--cov=src", "--cov-report=term", "--cov-report=xml"],
        text=True, capture_output=True
    )
    print(res.stdout)
    return res.returncode == 0

# === Git commit and push ===
def git_commit_and_push(files):
    sh('git config user.name "ci-bot"')
    sh('git config user.email "ci-bot@users.noreply.github.com"')
    for f in files:
        if f and Path(f).exists():
            sh(f"git add {f}")
    sh('git commit -m "auto: add pytest files generated by Copilot" || true', check=False)
    sh('git push', check=False)
    print("🚀 Committed and pushed generated tests.")

# === Rollback failed test files ===
def rollback(files):
    for f in files:
        if f and Path(f).exists():
            Path(f).unlink()
            print(f"🧹 Removed {f}")
    print("🧹 Rollback done.")

# === Entry point ===
if __name__ == "__main__":
    changed = get_changed_files()
    if not changed:
        print("⚠️ No changed Python files found — forcing full scan.")
        changed = list(SRC.rglob("*.py"))
        if not changed:
            print("ℹ️ No src files found. Exiting.")
            sys.exit(0)

    generated = []
    for f in changed:
        file = generate_tests_with_copilot(f)
        if file:
            generated.append(file)

    if run_pytest():
        print("✅ Initial tests passed — checking uncovered functions...")
        for f in changed:
            mod = module_import_path(f)
            uncovered = find_uncovered_functions(mod)
            if uncovered:
                print(f"⚠️ Missing coverage in {mod}: {uncovered}")
                for func in uncovered:
                    newfile = generate_tests_with_copilot(f, func)
                    if newfile:
                        generated.append(newfile)
        print("🚀 Committing improved tests.")
        git_commit_and_push(generated)
    else:
        print("❌ Tests failed — cleaning up generated files.")
        rollback(generated)
        sys.exit(1)
