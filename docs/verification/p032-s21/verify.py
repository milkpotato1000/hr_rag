"""Anonymous public installation; writes a portable observation, never uses a wheelhouse."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlparse

URL = "https://github.com/milkpotato1000/hr_rag.git"
INDEX = "https://pypi.org/simple"
E = Path(__file__).resolve().parent
def sha(data):
    return hashlib.sha256(data).hexdigest()
def read(path):
    return json.loads(path.read_text())

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("select a new evidence path")
    root = Path(tempfile.mkdtemp(prefix="s21-public-")).resolve()
    home, cache, source = root/"home", root/"cache", root/"source"
    home.mkdir(); cache.mkdir()
    env = dict(PATH=os.pathsep.join([str(Path(sys.executable).parent),"/usr/bin","/bin","/usr/sbin","/sbin"]),
               HOME=str(home), LANG="en_US.UTF-8", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="https", PIP_CONFIG_FILE=os.devnull,
               PIP_INDEX_URL=INDEX, PIP_CACHE_DIR=str(cache), PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONNOUSERSITE="1")
    def cmd(*argv,cwd=root):
        return subprocess.check_output(argv,cwd=cwd,env=env,stderr=subprocess.STDOUT)
    report = dict(python=sys.version.split()[0],remote=URL,index=INDEX,initial_cache_entries=len(list(cache.iterdir())))
    stage = "public_checkout"
    try:
        cmd("git","-c","credential.helper=","clone","--quiet","--depth","1","--branch","dev",URL,source)
        ref = cmd("git","rev-parse","HEAD",cwd=source).decode().strip()
        tip = cmd("git","-c","credential.helper=","ls-remote",URL,"refs/heads/dev").decode().split()[0]
        assert ref==tip
        report["source_sha"]=ref
        allow=read(source/"packaging/allowlist.json")
        paths=set(allow["modules"]+allow["resources"]+allow["sdist_extra"]+["README.md","scripts/first_handbook.py","packaging/requirements-build.lock","packaging/allowlist.json"])
        for path in paths:
            assert (source/path).read_bytes()==cmd("git","show",ref+":"+path,cwd=source)
        report["verified_checkout_blobs"]=len(paths)
        stage="first_handbook"
        dest=root/"first"
        cmd(sys.executable,"scripts/first_handbook.py","--out",dest,cwd=source)
        result=read(dest/"first-run.json")
        log=(dest/"commands.log").read_text()
        versions={}
        for lock in ["packaging/requirements-build.lock","rag_package/requirements-pdf.lock"]:
            for name,version in re.findall(r"^([\w-]+)==([^\s]+)",(source/lock).read_text(),re.M):
                versions[name]=version
        wheels=re.findall(r"Downloading ([\w.\-]+\.whl)\s",log)
        assert all(any(f.startswith(name.replace("-","_")+"-"+v+"-") for f in wheels) for name,v in versions.items())
        report.update(downloaded_wheels=sorted(set(wheels)),locked_versions=versions)
        assert "--require-hashes" in log and "--find-links" not in log
        for venv in ("build-env","env"):
            assert "include-system-site-packages = false" in (dest/venv/"pyvenv.cfg").read_text()
        stage="source_and_retrieval_comparison"
        direct=read(next((dest/"env").glob("lib/python*/site-packages/milkpotato_rag_lab-*.dist-info/direct_url.json")))
        wheel=dest/"dist"/result["wheel"]
        assert Path(unquote(urlparse(direct["url"]).path)).resolve()==wheel.resolve()
        assert sha(wheel.read_bytes())==direct["archive_info"]["hashes"]["sha256"]==result["wheel_sha256"]
        ws=dest/"practice"
        prior=read(E.parent/"p032-s20/verified.json")
        contexts=read(ws/"evidence/result.json")["contexts"]
        assert contexts==prior["contexts"] and result["question"]==prior["first"]["question"]
        assert result["pdf_sha256"]==prior["first"]["pdf_sha256"]==sha((ws/"documents/handbook.pdf").read_bytes())
        assert (ws/"fixed.json").read_bytes()==(source/"rag_package/resources/sample/fixed.json").read_bytes()
        assert result["matches"]==prior["first"]["matches"] and result["generation_calls"]==0
        page=(ws/"snapshot/handbook/page-1.txt").read_text()
        for match in result["matches"]:
            assert match["quote"] in page and match["quote"] in contexts[match["rank"]-1]["text"]
        report.update(status="complete",stages={s:"complete" for s in ["download","build","wheel_install","pdf_reader","init","search"]},
                      wheel_sha256=result["wheel_sha256"],pdf_sha256=result["pdf_sha256"],matches=result["matches"],
                      question=result["question"],contexts_identical_to_s20=len(contexts),generation_calls=result["generation_calls"])
    except (subprocess.CalledProcessError,OSError,ValueError,AssertionError) as error:
        detail=getattr(error,"output",b"").decode(errors="replace")[-2000:]
        state=root/"first/first-run.json"
        if state.is_file():
            stage=read(state).get("failed_stage",stage)
            detail=(root/"first/commands.log").read_text()[-2500:]
        report.update(status="failed",stage=stage,error_type=type(error).__name__,detail=detail.replace(str(root),"<run>"))
        raise
    finally:
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":
    main()
