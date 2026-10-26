# Uso: python3 merge-branch.py <repo> <branch-wip> <branch-final>
# Cria a branch final a partir da 04 (--no-track), aplica os commits da wip
# com cherry-pick, troca os assuntos mapeados em R e confere os 72 caracteres.
import subprocess
import sys

repo, src, branch = sys.argv[1:4]
base = "feature/TS-5361-componentes-overlay-tabela"
# Assuntos longos demais -> versão com até 72 caracteres. Preencher por leva.
R = {}


def g(*args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


g("switch", "-c", branch, "--no-track", base)
for line in g("log", "--reverse", "--format=%H %s", f"{base}..{src}").splitlines():
    sha, subject = line.split(" ", 1)
    g("cherry-pick", sha)
    if subject in R:
        g("commit", "--amend", "-m", R[subject])
for subject in g("log", "--format=%s", f"{base}..HEAD").splitlines():
    assert len(subject) <= 72, subject
print(g("log", "--oneline", f"{base}..HEAD"))
