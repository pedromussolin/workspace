# Sandbox spike: our own bubblewrap box (phase 3 feasibility)

- **Date:** 2026-10-28
- **Method:** bubblewrap 0.9.0 (`bwrap`, a Linux tool that builds an isolated view of the system
  with kernel namespaces), socat 1.8, WSL2 kernel 6.6, throwaway scripts and a stdlib proxy under
  `~/.cache/workspace/spike-sandbox/`. No Claude Code session was started. "The brief" below is the
  spike request: `--ro-bind / /`, key folders hidden, `~/repos` and `~/.cache` writable.
- **Not done on purpose:** any container, any external write, any read of the credentials or of the
  GitHub CLI token file (only existence and size).

## Summary

**Go, with four conditions.** A box around the whole agent is feasible and cheap: starting it
costs 2 to 8 ms, and real commands are 0 to 10 ms slower than outside. The network design (a stdlib
CONNECT proxy on a Unix socket, `--unshare-net`) works for curl, git over HTTPS, uv, npm, wget and
Python. What the spike changes in the approved direction:

1. **`--ro-bind / /` is not a safe baseline.** From inside that box: the Docker socket answered
   (`docker version` returned the server version, which is root on the host), and so did the
   D-Bus, gpg-agent and X11 sockets; **WSL interop ran `cmd.exe` on Windows** (a full escape);
   `~/.ssh`, `~/.aws`, `~/.azure`, `~/.gnupg`, `~/.docker`, `~/.pgpass` and the harness login token
   were readable; the environment carried three secret-looking variables, one a GitHub token. The
   box that works is **deny-by-default**: `tmpfs` over `~`, `/run` and `/mnt`, a cleared
   environment, and an explicit list of what is bound back.
2. **The read-write `~/repos` is an execution channel to the outside.** The box planted a git
   hook and a `core.fsmonitor` key; both ran on the host the next time git ran there. `.git/hooks`,
   `.git/config` and `.githooks/` must be read-only inside, and the outside `ws` must not trust
   repo-local git config.
3. **Git over SSH is dead inside** (port 22 is off the allowlist and there is no key) and the
   remotes here are SSH, so `git fetch/pull/push` and every `gh` read of a private repo run outside,
   through `ws`.
4. **Use a dedicated `CLAUDE_CONFIG_DIR` for the boxed harness**, not `~/.claude`: it keeps the
   login token, the history and 3 GB of old transcripts out of the box.

Open: no real interactive session was run (login hosts, terminal resize, MCP servers).
## The command line

Tested as `box2.sh` (hardened). Paths are written with `~`; the script expands `$HOME`.

```
bwrap --ro-bind / /  --tmpfs /run --tmpfs /mnt  --dev /dev --proc /proc --tmpfs /tmp \
  --unshare-pid --die-with-parent --new-session \
  --tmpfs ~                                          # deny-by-default home
  --ro-bind ~/.local/bin ~/.local/bin  --ro-bind ~/.local/share/claude ~/.local/share/claude \
  --ro-bind ~/.local/share/uv ~/.local/share/uv  --ro-bind ~/.nvm ~/.nvm  --ro-bind ~/.gitconfig ~/.gitconfig \
  --bind ~/repos ~/repos  --bind ~/.cache ~/.cache  --bind ~/.claude ~/.claude \
  --bind ~/.claude.json ~/.claude.json  --ro-bind ~/.claude/settings.json ~/.claude/settings.json \
  --ro-bind ~/.config/workspace/names.toml ~/.config/workspace/names.toml \
  --ro-bind ~/.config/workspace/config.toml ~/.config/workspace/config.toml \
  --clearenv --setenv HOME ~ --setenv PATH <short list> --setenv LANG .. --setenv TERM .. \
  --chdir ~/repos  [network mode]  COMMAND
```

Network mode adds `--unshare-net`, a read-only bind of the folder with the proxy socket and
`HTTPS_PROXY=HTTP_PROXY=http://127.0.0.1:3128`; the command starts through `socat
TCP-LISTEN:3128,bind=127.0.0.1,fork UNIX-CONNECT:<socket> &` and then `exec`s. The `credentials`
file is never bound back: only `names.toml` and `config.toml`, which the git hooks need, are.

The brief's own variant (`--ro-bind / /`, `tmpfs` over `~/.config/workspace` and `~/.config/gh`,
`/dev/null` over `/run/docker.sock`) passes every check of point 1 and still has the summary's leaks.

## Measurements

Wall time in ms, median of 20 runs (`time.perf_counter`, output discarded). The machine was shared
with four other agents (load average about 2.5), so single digits are noisy.

| Command | Outside | Bare `bwrap` | Brief's box | Hardened | Hardened + net |
|---|---|---|---|---|---|
| `true` | 0.5 | 2.9 | 5.0 | 5.9 | 14.3 (min 7.6) |
| `git status --short`, main checkout | 2.0 | n/a | 6.3 | 6.6 | 10.6 |
| `uv run pytest -q tests/test_gate_decision.py` | 178 | n/a | 178 | 182 | 219 |

A quieter re-run: `true` bare 2.1, hardened 4.8, hardened + net 7.5; pytest hardened 141, hardened
+ net 149 (the 219 above was load).

- **Box startup alone:** 2 ms bare, about 5 ms hardened, about 8 ms with the network namespace
  and the forwarder (a launcher inside `ws`, with no `bash` wrapper, should be nearer the bare one).
- **If every command had its own box:** +5 to +8 ms each, invisible next to a model turn; one box
  around the whole agent pays it once. Claude Code's own sandbox was not measured (it needs a
  session), so "as fast as it" is an expectation, not a measurement.

## Findings (point 6, performance, is the Measurements section)

### 1. The box

Booleans and sizes only, no content printed (same in the brief's box and the hardened one):

| Check | Result |
|---|---|
| `~/.config/workspace/credentials` | absent (the folder is a `tmpfs`); `test -r` false |
| same file, with `/dev/null` bound over it instead | `test -r` true, size 0, but `open()` fails with "Permission denied" (bwrap mounts binds `nodev`) |
| append to `~/.claude/settings.json` | "Read-only file system"; `rm` and `mv`: "Device or resource busy"; own read-only mount confirmed in `mountinfo`; hash and mtime unchanged on the host |
| `~/.claude/hooks` | does not exist yet (phase 1 not installed); the same `--ro-bind` on a stand-in folder refused write, create and delete |
| `~/repos`, `~/.cache` | writable; `/etc` read-only; `~` read-only (brief's box) or a throwaway `tmpfs` (hardened); 5 pids visible, no capabilities, `NoNewPrivs` 1 |

Prefer the `tmpfs` to the `/dev/null` bind: the file is simply not there. A read-only file in a
read-write folder protects that file but not its neighbors, so settings should come from a folder
the box cannot write. `ws --help`, `ws mask --help` and `ws check-secrets` run inside; a Jira call
cannot authenticate there.

The baseline's leaks (connect tests only, no data sent): Docker, D-Bus, gpg-agent, X11 and snapd
sockets accept a connection, and `cmd.exe /c ver` runs on Windows through WSL interop. `--tmpfs /run`
removes the sockets and breaks interop; `--tmpfs /mnt` removes `C:` and the Windows binaries.

### 2. Network

With `--unshare-net` the box sees only `lo` (`/proc/net/dev`; `/sys/class/net` still lists the host
interfaces, which is information only). `bwrap` brings `lo` up itself, so the forwarder works.

| Test | Result |
|---|---|
| `curl https://api.github.com/zen` | 200 |
| `curl https://example.com` and Python `urllib` to it; `urllib` to `pypi.org` | 403 from the proxy (`DENY` in its log); 200 |
| direct socket to `1.1.1.1:443`; direct DNS | "Network is unreachable"; "Temporary failure in name resolution" |
| `ssh` to a GitHub IP; `git ls-remote git@github.com:...` | "Network is unreachable"; "Could not resolve hostname" |
| `ssh` through the proxy to `github.com:22`, to `ssh.github.com:443` | both `DENY` |
| `git ls-remote https://github.com/<public repo> HEAD`; the same on another host | works; "CONNECT tunnel failed, response 403" |
| `uv run --no-project --with tomli-w ...`, cold cache and default cache | works; proxy log shows `pypi.org` and `files.pythonhosted.org` |
| `npm view left-pad version`; `wget` to `pypi.org`, to `example.com` | `1.3.0`; exit 0; exit 4 |
| `http://pypi.org/` through `HTTP_PROXY` | 405: the proxy only does CONNECT (host name and port 443 only, no TLS inspection, IP literals denied), so plain HTTP never passes |

**Programs that ignore the proxy variables:** `ssh`, `ping`, raw sockets and `dig` (all fail
closed: there is no route); **Node's built-in `fetch`** ignores them unless `NODE_USE_ENV_PROXY=1`
(Node 24): without it `EAI_AGAIN`, with it the allowed host answers 200 and a denied one fails, so
Node-based MCP servers need that variable. Not tested: Chrome headless (it takes its own
`--proxy-server` flag, so it should fail closed), Java, `dotnet`. `gh` honors the proxy but refuses
to run without a login (point 4).

### 3. Docker

`/var/run/docker.sock` exists (`root:docker`, mode 660) and the user is in the `docker` group. In
the brief's baseline it was **reachable**: `docker version` printed the server version. With
`/dev/null` bound over it, `docker` said "Cannot connect to the Docker daemon"; with `--tmpfs /run`,
"no such file". No container was started.

Risk of binding it: whoever can write to the socket can ask the root daemon for a container with
`-v /:/host` or `--privileged`: root on the host, no box left, and the daemon does not filter by
path. The socket stays out of the box in every mode.

### 4. GitHub without the key

`gh auth status` inside: "You are not logged into any GitHub hosts". `gh api` and `gh repo view`
refuse to run without a login, even for a public repo. The cleared environment has no `GH_TOKEN`.

- Works unauthenticated, through the proxy: `git clone --depth 1` and `git ls-remote` of public
  repos over HTTPS, `curl api.github.com/repos/...` (200; limit 60 per hour **per host IP**, shared
  with the whole machine), `codeload.github.com` tarballs (200).
- Does not work: any private repo, anything over SSH (this repo's remote is SSH),
  `raw.githubusercontent.com` (off the allowlist), `gh`. A write was not tried (no external writes).

Meaning: **inside the box GitHub is read-only public data.** Everything touching a private repo or
the user's identity goes through `ws` outside. Since `~/repos` is shared, an outside `ws git
fetch/pull` is seen inside at once.

### 5. A harness inside

`claude --version` inside: `2.1.312 (Claude Code)`; `claude auth status` and `claude mcp list` also
run offline. `opencode` is not installed here.

Minimal read-write set, measured with `~` read-only (a `tmpfs` remounted read-only) and only
`CLAUDE_CONFIG_DIR` and `/tmp` writable: `--version`, `auth status` and `mcp list` ran and created
only `.claude.json` (which `CLAUDE_CONFIG_DIR` moves into the dir), its `.lock`, `backups/` and
`telemetry/` (events queued, the network being closed). A live session on the host touches (names,
from mtimes) `~/.claude/{projects (3 GB of transcripts), file-history, session-env, sessions,
shell-snapshots, jobs, daemon*, plugins, backups, policy-limits*, remote-settings*, history.jsonl}`,
`~/.claude.json`, `~/.cache/claude*`, `~/.local/state/claude` and `/tmp/claude-<uid>`. The binaries
sit in `~/.local/share/claude/versions`: keep that read-only and set `DISABLE_AUTOUPDATER=1`.

Sharing `~/.claude` exposes its login token (`.credentials.json`; it stays inside the box, as the
brief says), every old transcript (any secret ever printed in a session) and the history. A
dedicated `CLAUDE_CONFIG_DIR` (say under `~/.local/share/workspace/agent/claude/`) removes all
three: the boxed harness logs in on its own and `ws` writes its read-only `settings.json` there.
A single-file bind of `~/.claude.json` is a trap (renaming over a bound file fails with EBUSY, seen
with `git config` on a bound `.git/config`); the config-dir route avoids it. A nested `bwrap`
works inside the box, so Claude Code's own sandbox could stay on as a second layer (tested with
plain `bwrap`, not with Claude's). The login probably needs hosts beyond the brief's allowlist
(`claude.ai`, `console.anthropic.com`): to confirm.

### 7. Escapes

| Attempt from inside | Result |
|---|---|
| write `~/.claude/settings.json`; read the credentials | refused; absent (point 1) |
| TCP to a host listener on `127.0.0.1`; host abstract Unix socket (D-Bus and X11 use them) | connected with host network; "Connection refused" with `--unshare-net` |
| `TIOCSTI` (inject keystrokes into a terminal) | refused, **but also outside the box**: this kernel has `legacy_tiocsti=0`. `--new-session` also removes the controlling terminal (`/dev/tty`: ENXIO) |
| open another terminal by path | `/dev/pts` shows only `ptmx` (`--dev /dev` gives a fresh devpts) |
| plant a git hook and a `core.fsmonitor` key | **worked in a plain read-write repo; both ran on the host** (risk 1) |

Descriptors 0, 1 and 2 are still the user's terminal, so the box can write escape sequences to it
(spoofed text, title, clipboard): approval text must never be rendered there, only in the `ws
approvals` pane, a different terminal. A Unix socket bound into the box as the broker channel is
reachable by **any** process inside, MCP servers and model commands included; a stand-in broker saw
the caller with the same uid and a pid from another pid namespace (`/proc/<pid>/ns/pid`). Identity
by uid is useless: everything on that socket is untrusted input, and approvals must come only from
a channel that is not bound in.

## Risks and limits

1. **Read-write repos run code outside** (proven). On a throwaway repo, `--ro-bind` on
   `.git/hooks` and `.git/config` refused the hook (read-only) and the config write (EBUSY), while
   `commit` and `switch -c --no-track` still worked; `git branch --set-upstream-to` printed success
   and stored nothing (silent). Add `.githooks/`, and run git outside with `-c
   core.hooksPath=<protected copy> -c core.fsmonitor=false`. Left over: the user running
   model-written code later (tests, scripts, `.venv`); only review before commit covers that.
2. **An allow list needs upkeep:** each new tool (a runtime, a version manager) needs a bind.
3. **Allowlisted hosts are a name match,** with no TLS inspection (fronting on shared CDNs is
   theoretically possible); `github.com` is also where prompt-injection content arrives. Plain
   HTTP never passes, by design.
4. **Shared terminal and `--new-session`:** escape sequences reach the user's terminal; resize
   (SIGWINCH) and job control probably stop working in a TUI (not tested without a real session).
5. **WSL specifics:** interop and `/mnt` must be masked on every start; a WSL update can change
   what is exposed, so the escape checks above must run as tests.
6. **Not verified:** a real session, login hosts, MCP servers in the box, Claude Code's own
   sandbox timing, Chrome-based tools, `opencode`.

## Recommendation for phase 3

Build it. `ws agent run <harness>` becomes a launcher that assembles the command line above.

**Inside:** the harness, the model's commands, its MCP servers (stdio), local git, `uv`, Python,
Node, key-free `ws` commands (`check-secrets`, `mask`, previews); `~/repos` and `~/.cache`
read-write with `.git/hooks`, `.git/config` and `.githooks/` read-only; a dedicated
`CLAUDE_CONFIG_DIR` with a generated read-only `settings.json`; `names.toml` and `config.toml`.
**Outside:** the key-holding broker (Jira key, GitHub token, SSH key), the `ws approvals` pane, the
proxy and its allowlist, Docker, and every git network operation on private repos.

**Launcher rules:**
- `--ro-bind / /` only to get binaries and libraries; then `tmpfs` over `~`, `/run`, `/mnt` and an
  explicit bind list. `--clearenv` plus a short list: PATH, HOME, LANG, TERM, the proxy variables,
  `NODE_USE_ENV_PROXY=1`, `DISABLE_AUTOUPDATER=1`, `CLAUDE_CONFIG_DIR`.
- The allowlist lives in the config (a `[sandbox]` table); the proxy logs every `DENY`. The in-box
  forwarder can be a short stdlib Python script (the proxy's pipe code), leaving `bwrap` as the
  only host package; not tested, this spike used socat.
- A pytest suite re-runs this document's checks (credentials absent, settings read-only, no Docker
  socket, `cmd.exe` fails, example host and `127.0.0.1` refused, hook planting refused), skipped
  when `bwrap` is missing.

**GitHub flows:** public reads go through the proxy (curl, `git clone`). `gh` is unusable inside,
so `ws gh <read>` runs outside from a catalog of reads, with no approval; private repo sync is `ws
git fetch/pull` outside; every write (push, PR, merge, comment, release) is `ws` outside, behind the
approval pane. The GitHub and Atlassian connectors stay off or read-only in this mode.

**Docker flows:** never bind the socket. `ws docker <verb>` runs outside through an argument
builder: no `--privileged`, no host network, no socket, no mount outside the project folder; the
approval text shows the image and mounts; read verbs (`ps`, `logs`, `images`) go in the catalog.
Compose files are data the model may write, so the builder parses them and applies the same rules.

**Next:** a short second spike with a real interactive session in the box (login hosts, resize,
MCP servers, `/dev/tty`), the main thing this one could not check.
