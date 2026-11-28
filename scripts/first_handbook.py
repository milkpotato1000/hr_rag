"""Build a committed dev checkout and run the first installed handbook search."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
QUESTION = "생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?"
QUOTE = "생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다."


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", SOURCE, *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="새로 만들 실습 폴더")
    parser.add_argument("--wheelhouse", type=Path, help="잠금 파일과 일치하는 의존성 wheel 폴더")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("이 빌드 lock으로 첫 실습을 실행하려면 Python 3.11 이상이 필요합니다.")
    dest = args.out.expanduser().absolute()
    if os.path.lexists(dest) or not dest.parent.is_dir():
        parser.error("기존 작업을 보존하려면 존재하는 부모 폴더 아래의 새 이름을 지정하세요.")
    wheelhouse = args.wheelhouse.resolve() if args.wheelhouse else None
    if wheelhouse and not wheelhouse.is_dir():
        parser.error("wheelhouse 폴더가 없습니다.")
    revision = git("rev-parse", "HEAD").decode().strip()
    print(f"소스 {revision}\n실습 {dest}\nPython {sys.version.split()[0]} · hash lock 빌드 도구 및 pypdf", flush=True)
    dest.mkdir()
    state = {"source_sha": revision, "python": sys.version.split()[0], "install": "pending", "search": "pending"}
    stage = "source"
    log = dest/"commands.log"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PIP_REQUIRE_VIRTUALENV"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    def run(*cmd, cwd=dest):
        with log.open("a") as f:
            print(json.dumps([str(v) for v in cmd], ensure_ascii=False), file=f, flush=True)
            subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
    try:
        # Copy only the release inputs from this commit. Build tools write into this copy.
        def blob(path):
            return git("show", f"{revision}:{path}")
        allow = json.loads(blob("packaging/allowlist.json"))
        src = dest/"build-source"
        for name in allow["modules"] + allow["resources"] + allow["sdist_extra"]:
            path = src/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob(name))
        lock = dest/"requirements-build.lock"
        lock.write_bytes(blob("packaging/requirements-build.lock"))
        offline = ["--no-index", "--find-links", str(wheelhouse)] if wheelhouse else []
        stage = "build_dependencies"
        buildpy = dest/"build-env/bin/python"
        run(sys.executable, "-m", "venv", dest/"build-env")
        run(buildpy, "-m", "pip", "install", *offline, "--require-hashes", "-r", lock)
        stage = "wheel_build"
        run(buildpy, "-m", "build", "--no-isolation", "--outdir", dest/"dist", src)
        wheel, = (dest/"dist").glob("*.whl")
        stage = "wheel_install"
        py = dest/"env/bin/python"
        cli = py.with_name("rag-lab")
        run(sys.executable, "-m", "venv", dest/"env")
        run(py, "-m", "pip", "install", "--no-index", "--no-deps", wheel)
        installed = Path(subprocess.check_output([py, "-I", "-c",
            "from pathlib import Path; import rag_package; print(Path(rag_package.__file__).parent)"],
            cwd=dest, env=env, text=True).strip())
        state.update(wheel=wheel.name, wheel_sha256=sha(wheel), installed_package=str(installed))
        stage = "pdf_reader"
        run(py, "-m", "pip", "install", *offline, "--require-hashes", "-r", installed/"requirements-pdf.lock")
        run(py, "-m", "pip", "check")
        state["install"] = "complete"
        stage = "init"
        ws = dest/"practice"
        run(cli, "init", "--out", ws)
        pdf = ws/"documents/handbook.pdf"
        if sha(pdf) != sha(src/"rag_package/resources/sample/documents/handbook.pdf"):
            raise ValueError("설치된 규정집이 소스 PDF와 다릅니다.")
        state.update(pdf_sha256=sha(pdf), question=QUESTION)
        stage = "snapshot"
        run(cli, "snapshot", "--sources", "handbook-sources.json", "--out", "snapshot", cwd=ws)
        stage = "bm25"
        run(cli, "build", "--snapshot", "snapshot", "--config", "fixed.json", "--out", "bm25", cwd=ws)
        stage = "search"
        run(cli, "ask", "--run", "bm25", "--config", "fixed.json", "--question", QUESTION, "--out", "evidence", cwd=ws)
        result = json.loads((ws/"evidence/result.json").read_text())
        canonical = (ws/"snapshot/handbook/canonical.txt").read_text()
        matches = []
        for rank, chunk in enumerate(result["contexts"], 1):
            if canonical[chunk["start"]:chunk["end"]] != chunk["text"]:
                raise ValueError("전달 청크의 원문 위치가 다릅니다.")
            if "BD-03" in chunk["text"] and QUOTE in chunk["text"]:
                offset = chunk["start"] + chunk["text"].index(QUOTE)
                for page in chunk["pages"]:
                    if page["page"]==1 and page["canonical_start"]<=offset and offset+len(QUOTE)<=page["canonical_end"]:
                        matches.append({"rank": rank, "page": 1, "clause": "BD-03", "quote": QUOTE})
        if result["status"] != "preview" or not matches:
            raise ValueError("검색 결과에서 PDF 1쪽 BD-03의 신청 기한을 확인할 수 없습니다.")
        state.update(search="complete", evidence="practice/evidence/result.json", contexts=len(result["contexts"]),
                     matches=matches, generation_calls=0)
        print(f"검색 근거 · PDF 1쪽 BD-03 (검색 {matches[0]['rank']}위)\n{QUOTE}")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        state.update(failed_stage=stage, error=str(exc))
        print(f"{stage} 단계에서 중단했습니다. {log}에서 마지막 명령을 확인하세요. "
              "의존성·경로 문제를 수정한 뒤 --out에 새 이름을 주어 다시 시작하세요.", file=sys.stderr)
        return 1
    finally:
        (dest/"first-run.json").write_text(json.dumps(state, ensure_ascii=False, indent=2)+"\n")
        print(f"설치·검색 결과 {dest/'first-run.json'}")


if __name__ == "__main__":
    raise SystemExit(main())
