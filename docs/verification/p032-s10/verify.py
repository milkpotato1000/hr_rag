"""Build a wheel from sdist, then run the installed handbook in a fresh directory."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

here = Path(__file__).resolve().parent
root = here.parents[2]
base = Path(tempfile.mkdtemp(prefix="p032-s10-")).resolve()
build_python = root / ".rag-runs/p028-build/.venv/bin/python"
env = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "PIP_NO_INDEX": "1",
       "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PYTHONDONTWRITEBYTECODE": "1"}
commands = []


def run(*args, cwd=base, ok=True):
    result = subprocess.run(list(map(str, args)), cwd=cwd, env=env,
                            text=True, capture_output=True)
    commands.append({"args": list(map(str, args)), "cwd": str(cwd), "exit": result.returncode})
    if ok:
        assert result.returncode == 0, result.stderr + result.stdout
    return result


def digest(data):
    return hashlib.sha256(data).hexdigest()


src = base / "build-source"
allow = json.loads((root / "packaging/allowlist.json").read_text())
for name in allow["modules"] + allow["resources"] + allow["sdist_extra"]:
    dest = src / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / name, dest)
run(build_python, "-m", "build", "--no-isolation", "--outdir", base / "dist", src)
wheel, = (base / "dist").glob("*.whl")
original = root / "2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf"
data = original.read_bytes()
with zipfile.ZipFile(wheel) as archive:
    assert archive.read("rag_package/resources/sample/documents/handbook.pdf") == data
run(build_python, "-m", "venv", "env")
env["PATH"] = str(base / "env/bin") + ":" + env["PATH"]
run("python", "-m", "pip", "install", "--no-deps", wheel)
# Reuse the pinned PDF reader from the earlier installed practice, offline.
site = Path(run("python", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))").stdout.strip())
previous = Path(json.loads((here.parent / "p032-s7/installation.json").read_text())["base"])
for name in ("pypdf", "pypdf-6.21.2.dist-info"):
    shutil.copytree(previous / site.relative_to(base) / name, site / name)
run("python", "-m", "pip", "check")
run("python", "-c", "import pypdf; assert pypdf.__version__=='6.21.2'")
run("rag-lab", "init", "--out", "handbook-practice")
ws = base / "handbook-practice"
assert (ws / "documents/handbook.pdf").read_bytes() == data
run("rag-lab", "doctor", cwd=ws)
guide = (ws / "HANDBOOK.md").read_text()
commands_block = guide.split("## 모델 호출 없이 검색 확인")[1].split("```sh\n")[1].split("\n```")[0]
run("/bin/sh", "-ec", commands_block, cwd=ws)
result = json.loads((ws / ".rag-runs/preview/result.json").read_text())
quote = "생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다."
match = next((rank, chunk) for rank, chunk in enumerate(result["contexts"], 1)
             if quote in chunk["text"] and "BD-03" in chunk["text"])
assert 1 in [p["page"] for p in match[1]["pages"]]
assert quote in (ws / ".rag-runs/pdf/handbook/page-1.txt").read_text()
run("rag-lab", "snapshot", "--sources", "sources.json", "--out", ".rag-runs/original-example", cwd=ws)
user_pdf = base / "existing/documents/handbook.pdf"
user_pdf.parent.mkdir(parents=True)
user_pdf.write_bytes(data + b"\n% independently marked user copy\n")
before = digest(user_pdf.read_bytes())
blocked = run("rag-lab", "init", "--out", "existing", ok=False)
assert blocked.returncode and "output_exists" in (blocked.stdout + blocked.stderr)
assert digest(user_pdf.read_bytes()) == before
report = dict(commands=commands, wheel_sha256=digest(wheel.read_bytes()), pdf_sha256=digest(data),
              contexts=len(result["contexts"]), rank=match[0], page=1, clause="BD-03", quote=quote,
              existing_pdf_before_and_after_sha256=before, generation_calls=0)
(here / "verified.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(match[0], quote)
