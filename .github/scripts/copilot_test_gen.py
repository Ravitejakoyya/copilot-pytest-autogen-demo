import subprocess, sys, json, re, os, inspect, importlib, ast
from pathlib import Path
import coverage

# ✅ Optional fallback to OpenAI GPT-4o
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    client = None

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

# === Convert src path to importable module path ===
def module_import_path(file_path: Path) -> str:
    abs_fp = file_path.resolve()
    rel_to_base = abs_fp.relative_to(BASE)
    mod = rel_to_base.with_suffix("").as_posix().replace("/", ".")
    if not mod.startswith("src."):
        mod = f"src.{mod}"
    return mod

# === Detect changed files ===
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

# === One test file per module ===
def get_test_file_for_module(stem: str) -> Path:
    return TESTS / f"test_{stem}.py"

# === Extract all functions from file ===
def extract_function_names(file_path: Path):
    try:
        tree = ast.parse(file_path.read_text())
        return [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    except Exception:
        return []

# === Find uncovered functions via coverage ===
def find_uncovered_functions(module_name: str):
    try:
        cov = coverage.Coverage(data_file=".coverage")
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

# === Detect installed Copilot CLI flavor ===
def detect_copilot_cli():
    for cmd in [["github-copilot-cli", "--help"], ["gh", "copilot", "--help"]]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if "suggest" in result.stdout or "generate" in result.stdout:
                print(f"✅ Detected Copilot CLI: {' '.join(cmd[:-1])}")
                return cmd[0]
        except FileNotFoundError:
            continue
    print("❌ No Copilot CLI detected.")
    return None

# === Generate tests (Copilot CLI or OpenAI fallback) ===
def generate_tests(file_path: Path, specific_function: str = None):
    functions = extract_function_names(file_path)
    func_list = ", ".join(functions) if functions else "No functions found"
    mod_path = module_import_path(file_path)
    test_file = get_test_file_for_module(file_path.stem)

    if specific_function:
        prompt = (
            f"Write detailed pytest tests for the function '{specific_function}' in {file_path.name}. "
            f"Include valid, invalid, and edge-case inputs. Output only Python code."
        )
    else:
        prompt = (
            f"The file {file_path.name} defines functions: {func_list}. "
            f"Write runnable pytest test cases covering all of them with success, error, and boundary tests. "
            f"Do not include explanations or markdown, output valid Python only."
        )

    cli = detect_copilot_cli()
    cleaned = ""

    if cli:
        print(f"🧠 Asking Copilot CLI for tests for: {file_path.name}")
        cmd = f'{cli} suggest -p {json.dumps(prompt)}' if "copilot" in cli else f'{cli} generate -p {json.dumps(prompt)}'
        try:
            result = sh(cmd, capture=True)
            cleaned = re.sub(r"```.*?```", "", result, flags=re.S).strip()
        except Exception as e:
            print(f"⚠️ CLI failed: {e}")
    elif client:
        print(f"🧠 Using GPT-4o fallback for: {file_path.name}")
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            cleaned = response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ GPT fallback failed: {e}")

    if not cleaned or "def test_" not in cleaned:
        print(f"⚠️ No usable tests generated for {file_path.name}")
        return None

    if "import pytest" not in cleaned:
        cleaned = f"import pytest\nfrom {mod_path} import *\n\n{cleaned}"
    test_file.write_text(cleaned.strip() + "\n")
    print(f"✅ Generated test file: {test_file}")
    return test_file

# === Run pytest with coverage ===
def run_pytest():
    print("🧪 Running pytest validation with coverage...")
    res = subprocess.run(
        ["pytest", "-q", "--disable-warnings", "--maxfail=1", "--cov=src", "--cov-report=term", "--cov-report=xml"],
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
    sh('git commit -m "auto: add pytest files generated by Copilot/GPT" || true', check=False)
    sh('git push', check=False)
    print("🚀 Committed and pushed generated tests.")

# === Rollback ===
def rollback(files):
    for f in files:
        if f and Path(f).exists():
            Path(f).unlink()
            print(f"🧹 Removed {f}")
    print("🧹 Rollback done.")

# === Main entry ===
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
        file = generate_tests(f)
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
                    newfile = generate_tests(f, func)
                    if newfile:
                        generated.append(newfile)
        print("🚀 Committing improved tests.")
        git_commit_and_push(generated)
    else:
        print("❌ Tests failed — cleaning up generated files.")
        rollback(generated)
        sys.exit(1)
