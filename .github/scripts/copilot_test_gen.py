import subprocess, sys, json, re, os, inspect, importlib, ast, shutil
from pathlib import Path
import coverage

BASE = Path(".").resolve()
SRC = BASE / "src"
TESTS = BASE / "tests"
TESTS.mkdir(exist_ok=True)

def sh(cmd, capture=False, check=True):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, capture_output=capture)
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout if capture else ""

def module_import_path(file_path: Path) -> str:
    abs_fp = file_path.resolve()
    rel_to_base = abs_fp.relative_to(BASE)
    mod = rel_to_base.with_suffix('').as_posix().replace('/', '.')
    if not mod.startswith("src."):
        mod = f"src.{mod}"
    return mod

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

def extract_function_names(file_path: Path):
    try:
        tree = ast.parse(file_path.read_text())
        return [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    except Exception:
        return []

def get_test_file_for_module(stem: str) -> Path:
    return TESTS / f"test_{stem}.py"

def detect_copilot_cli():
    """Detect installed Copilot CLI flavor."""
    for cmd in ["github-copilot-cli", "gh copilot"]:
        try:
            result = subprocess.run(cmd.split() + ["--help"], capture_output=True, text=True)
            if "generate" in result.stdout:
                print(f"✅ Detected '{cmd}' with 'generate' support.")
                return cmd, "generate"
            elif "suggest" in result.stdout:
                print(f"✅ Detected '{cmd}' with 'suggest' support.")
                return cmd, "suggest"
        except FileNotFoundError:
            continue
    print("❌ No Copilot CLI detected.")
    return None, None

def generate_tests_with_copilot(file_path: Path, specific_function: str = None):
    functions = extract_function_names(file_path)
    func_list = ", ".join(functions) if functions else "No functions found"

    if specific_function:
        prompt = (
            f"Write detailed pytest tests for '{specific_function}' in {file_path.name}. "
            f"Include success, edge, and invalid cases. Output valid Python code only."
        )
    else:
        prompt = (
            f"The file {file_path.name} contains: {func_list}. "
            f"Write runnable pytest tests for ALL functions (success, failure, edge). "
            f"No explanations or markdown — Python code only."
        )

    cli_cmd, mode = detect_copilot_cli()
    if not cli_cmd:
        print("❌ No Copilot CLI found. Skipping generation.")
        return None

    if mode == "generate":
        cmd = f'{cli_cmd} generate -p {json.dumps(prompt)}'
    else:
        cmd = f'{cli_cmd} suggest -p {json.dumps(prompt)}'

    print(f"🧠 Asking Copilot for tests for: {file_path.name}")
    try:
        result = sh(cmd, capture=True)
    except SystemExit:
        print(f"⚠️ Copilot CLI command failed: {cmd}")
        return None

    lines = []
    for line in result.splitlines():
        l = line.strip()
        if not l or "copilot" in l.lower() or "visit" in l.lower():
            continue
        if re.match(r"^(import |from |def |class |@|assert|if |for |while |try|except|with |return|#)", l):
            lines.append(line)
        elif l.startswith(("    ", '"""', "'''")):
            lines.append(line)
    cleaned = "\n".join(lines).replace("```python", "").replace("```", "").strip()

    mod_path = module_import_path(file_path)
    test_file = get_test_file_for_module(file_path.stem)

    if not cleaned or "def test_" not in cleaned:
        print(f"⚠️ Copilot returned no usable tests for {file_path.name}.")
        return None

    if "import pytest" not in cleaned:
        cleaned = f"import pytest\nfrom {mod_path} import *\n\n{cleaned}"

    test_file.write_text(cleaned.strip() + "\n")
    print(f"✅ Generated test file: {test_file}")
    return test_file

def run_pytest():
    print("🧪 Running pytest validation with coverage...")
    res = subprocess.run(
        ["pytest", "-q", "--disable-warnings", "--maxfail=1", "--cov=src", "--cov-report=term", "--cov-report=xml"],
        text=True, capture_output=True
    )
    print(res.stdout)
    return res.returncode == 0

def git_commit_and_push(files):
    sh('git config user.name "ci-bot"')
    sh('git config user.email "ci-bot@users.noreply.github.com"')
    for f in files:
        if f and Path(f).exists():
            sh(f"git add {f}")
    sh('git commit -m "auto: add pytest files generated by Copilot" || true', check=False)
    sh('git push', check=False)
    print("🚀 Committed and pushed generated tests.")

def rollback(files):
    for f in files:
        if f and Path(f).exists():
            Path(f).unlink()
            print(f"🧹 Removed {f}")
    print("🧹 Rollback done.")

if __name__ == "__main__":
    changed = get_changed_files()
    if not changed:
        print("⚠️ No changed Python files found — scanning all src/ files.")
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
        print("✅ Initial tests passed — committing generated tests.")
        git_commit_and_push(generated)
    else:
        print("❌ Tests failed — cleaning up generated files.")
        rollback(generated)
        sys.exit(1)
