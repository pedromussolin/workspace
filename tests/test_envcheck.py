import json
import os
import sys
import textwrap
import traceback
from pathlib import Path

import pytest

from ws import envcheck
from ws.envcheck import (
    EnvCheckSettings,
    RepoProfile,
    SetupError,
    StoreUnreachable,
    argocd_env_names,
    deployed_sha,
    files_at,
    is_valid_name,
    normalize_store_name,
    scan_python,
    scan_shell,
    store_names,
)


def profile(**overrides) -> RepoProfile:
    values = {
        "name": "api",
        "path": Path("/nowhere/api"),
        "argocd": Path("/nowhere/api-argocd"),
        "kind": "python",
        "prefix": {"prod": "/realm/env/app"},
        "values": {"prod": ["apps/app/values.yaml"]},
        "profile": {"prod": "some-profile"},
        "helpers": (),
        "migration_globs": (),
        "always_required": (),
        "shell_files": (),
        "dynamic": {},
    }
    values.update(overrides)
    return RepoProfile(**values)


def src(**modules: str) -> dict[str, bytes]:
    """Python sources by path, dedented: `src(**{"src/config.py": "..."})`."""
    return {path: textwrap.dedent(text).encode() for path, text in modules.items()}


def names(result) -> dict[str, bool]:
    return {name: item.required for name, item in result.names.items()}


SETTINGS = {
    "src/config.py": """
        from pydantic_settings import BaseSettings, SettingsConfigDict


        class LogSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="CFG_LOG_", case_sensitive=False)

            level: str = "INFO"
            sink: str
    """
}


def test_settings_class_prefix_and_fields():
    result = scan_python(src(**SETTINGS), profile())
    assert names(result) == {"CFG_LOG_LEVEL": False, "CFG_LOG_SINK": True}
    item = result.names["CFG_LOG_SINK"]
    assert item.kind == "settings"
    assert item.where == ("src/config.py:9",)
    assert item.count == 1


def test_validation_alias_ignores_prefix():
    files = src(
        **{
            "src/config.py": """
                from pydantic import AliasChoices, Field
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class DbSettings(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_DB_")

                    url: str = Field(validation_alias="database_url")
                    region: str = Field("x", alias="Api_Region")
                    host: str = Field("h", validation_alias=AliasChoices("db_host", "host"))
            """
        }
    )
    assert names(scan_python(files, profile())) == {
        "DATABASE_URL": True,
        "API_REGION": False,
        "DB_HOST": False,
    }


def test_required_means_no_default():
    files = src(
        **{
            "src/config.py": """
                from typing import Annotated, ClassVar, Optional
                from pydantic import Field
                from pydantic_settings import BaseSettings


                class S(BaseSettings):
                    a: str
                    b: str = ...
                    c: str = Field(...)
                    d: str = Field()
                    e: str = Field(default="x")
                    f: str = Field(default_factory=list)
                    g: Optional[str]
                    h: Optional[str] = None
                    i: Annotated[str, Field(description="d")]
                    j: Annotated[str, Field(default="d")]
                    k: ClassVar[str] = "not a field"
                    _private: str = "x"
            """
        }
    )
    assert names(scan_python(files, profile())) == {
        "A": True,
        "B": True,
        "C": True,
        "D": True,
        "E": False,
        "F": False,
        "G": True,
        "H": False,
        "I": True,
        "J": False,
    }


def test_inherited_base_settings_class():
    files = src(
        **{
            "src/base.py": """
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class Base(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_BASE_")
            """,
            "src/config.py": """
                from src.base import Base
                from src.mixins import Strip


                class Child(Strip, Base):
                    name: str


                class Other(Child):
                    model_config = {"env_prefix": "CFG_OTHER_"}

                    extra: int = 1


                class NotSettings(Strip):
                    ignored: str
            """,
        }
    )
    assert names(scan_python(files, profile())) == {
        "CFG_BASE_NAME": True,
        "CFG_OTHER_NAME": True,
        "CFG_OTHER_EXTRA": False,
    }


def test_nested_settings_field_is_not_a_name():
    files = src(
        **{
            "src/config.py": """
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class LogSettings(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_LOG_")

                    level: str = "INFO"


                class Settings(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_")

                    log: LogSettings = LogSettings()
                    maybe: "LogSettings | None" = None
                    debug: bool = False
            """
        }
    )
    assert set(names(scan_python(files, profile()))) == {"CFG_LOG_LEVEL", "CFG_DEBUG"}


def test_attribute_name_is_not_the_prefix():
    files = src(
        **{
            "src/config.py": """
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class AWSSettings(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_AWS_")

                    region: str = "x"


                class Settings(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_")

                    aws: AWSSettings = AWSSettings()
            """
        }
    )
    assert set(names(scan_python(files, profile()))) == {"CFG_AWS_REGION"}


def test_property_and_computed_field_skipped():
    files = src(
        **{
            "src/config.py": """
                from pydantic import computed_field
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class S(BaseSettings):
                    model_config = SettingsConfigDict(env_prefix="CFG_S_")

                    host: str = "h"

                    @property
                    def url(self) -> str:
                        return self.host

                    @computed_field
                    @property
                    def dsn(self) -> str:
                        return self.host
            """
        }
    )
    assert set(names(scan_python(files, profile()))) == {"CFG_S_HOST"}


def test_docstring_and_error_string_names_ignored():
    files = src(
        **{
            "src/config.py": """
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class S(BaseSettings):
                    '''Reads CFG_DOC_ONLY and CFG_S_HOST.'''

                    model_config = SettingsConfigDict(env_prefix="CFG_S_")

                    host: str = "h"


                def fail():
                    raise RuntimeError("set CFG_ERROR_ONLY first")
            """
        }
    )
    assert set(names(scan_python(files, profile()))) == {"CFG_S_HOST"}


def test_multiline_field_call():
    files = src(
        **{
            "src/config.py": """
                from pydantic import Field
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class S(BaseSettings):
                    model_config = SettingsConfigDict(
                        env_prefix="CFG_S_",
                        case_sensitive=False,
                    )

                    dsn: str = Field(
                        description="a long description",
                        min_length=3,
                    )
                    port: int = Field(
                        8000,
                        description="port",
                    )
            """
        }
    )
    assert names(scan_python(files, profile())) == {"CFG_S_DSN": True, "CFG_S_PORT": False}


def test_tests_folder_skipped():
    files = src(**SETTINGS)
    files.update(
        src(
            **{
                "tests/test_config.py": """
                    import os

                    os.environ.setdefault("CFG_TEST_ONLY", "x")
                    value = os.getenv("CFG_TEST_READ")
                """,
                "src/tests/helpers.py": """
                    import os

                    os.getenv("CFG_NESTED_TEST")
                """,
            }
        )
    )
    assert set(names(scan_python(files, profile()))) == {"CFG_LOG_LEVEL", "CFG_LOG_SINK"}


def test_syntax_error_file_is_a_warning():
    files = src(**SETTINGS)
    files["src/broken.py"] = b"def broken(:\n"
    result = scan_python(files, profile())
    assert set(names(result)) == {"CFG_LOG_LEVEL", "CFG_LOG_SINK"}
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("src/broken.py:1")


def test_non_python_files_are_ignored():
    files = src(**SETTINGS)
    files["README.md"] = b"CFG_README_ONLY"
    assert set(names(scan_python(files, profile()))) == {"CFG_LOG_LEVEL", "CFG_LOG_SINK"}


@pytest.mark.parametrize("bad", ["env_prefix=PREFIX_CONST", "env_prefix=f'CFG_{X}_'"])
def test_non_literal_prefix_is_a_warning(bad):
    files = src(
        **{
            "src/config.py": f"""
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class S(BaseSettings):
                    model_config = SettingsConfigDict({bad})

                    host: str = "h"
            """
        }
    )
    result = scan_python(files, profile())
    assert any("env_prefix" in w and "src/config.py:6" in w for w in result.warnings)


def test_getenv_and_environ_reads():
    files = src(
        **{
            "src/app.py": """
                import os
                from os import getenv

                A = os.getenv("CFG_ENVIRONMENT")
                B = os.getenv("CFG_B", "x")
                C = os.environ.get("CFG_C")
                D = os.environ["CFG_D"]
                E = getenv("CFG_E", default="x")
                os.environ["CFG_WRITTEN"] = "not a read"
                os.environ.setdefault("CFG_SET", "not a read")
                F = os.environ.get("CFG_F", "x")
            """
        }
    )
    result = scan_python(files, profile())
    assert names(result) == {
        "CFG_ENVIRONMENT": False,
        "CFG_B": False,
        "CFG_C": False,
        "CFG_D": True,
        "CFG_E": False,
        "CFG_F": False,
    }
    assert result.names["CFG_D"].kind == "helper"
    assert result.names["CFG_D"].where == ("src/app.py:8",)


def test_configured_helper_with_literal():
    files = src(
        **{
            "src/job.py": """
                from src.util import env, env_list


                def load():
                    a = env("CFG_JOB_A")
                    b = env("CFG_JOB_B", "x")
                    c = env_list("CFG_JOB_C", default=[])
                    d = settings.env("CFG_JOB_D")
                    e = other("CFG_NOT_A_HELPER")
            """,
            "src/util.py": """
                import os


                def env(name, default=None):
                    return os.environ.get(name, default)
            """,
        }
    )
    result = scan_python(files, profile(helpers=("env", "env_list")))
    assert names(result) == {
        "CFG_JOB_A": True,
        "CFG_JOB_B": False,
        "CFG_JOB_C": False,
        "CFG_JOB_D": True,
    }
    assert result.unresolved == []


def test_fstring_helper_is_unresolved_with_line():
    files = src(
        **{
            "src/job.py": """
                import os


                def load(partner, key):
                    a = env(f"CFG_{partner}_URL")
                    b = os.getenv(key)
                    c = env("CFG_JOB_C")
            """
        }
    )
    result = scan_python(files, profile(helpers=("env",)))
    assert names(result) == {"CFG_JOB_C": True}
    assert [(u.where, u.call) for u in result.unresolved] == [
        ("src/job.py:6", "env"),
        ("src/job.py:7", "os.getenv"),
    ]


def test_migration_glob_goes_to_migration_only():
    files = src(
        **{
            "src/app.py": """
                import os

                A = os.getenv("CFG_SHARED")
            """,
            "migrations/versions/0001_seed.py": """
                import os

                A = os.getenv("CFG_SHARED")
                B = env("CFG_MIGRATION_ONLY")
                C = env(f"CFG_{x}_URL")
            """,
        }
    )
    result = scan_python(files, profile(helpers=("env",), migration_globs=("migrations/**",)))
    assert names(result) == {"CFG_SHARED": False}
    assert {n: i.required for n, i in result.migration_only.items()} == {"CFG_MIGRATION_ONLY": True}
    assert result.migration_only["CFG_MIGRATION_ONLY"].kind == "migration"
    assert [u.where for u in result.unresolved] == ["migrations/versions/0001_seed.py:6"]


def test_dynamic_class_expanded_with_configured_prefixes():
    files = src(
        **{
            "src/storage.py": """
                from pydantic_settings import BaseSettings


                class StorageSettings(BaseSettings):
                    bucket: str
                    region: str = "x"
            """
        }
    )
    result = scan_python(
        files,
        profile(dynamic={"StorageSettings": ("CFG_ONE_", "CFG_TWO_")}),
    )
    assert names(result) == {
        "CFG_ONE_BUCKET": True,
        "CFG_ONE_REGION": False,
        "CFG_TWO_BUCKET": True,
        "CFG_TWO_REGION": False,
    }
    assert {i.kind for i in result.names.values()} == {"dynamic"}


def test_always_required_overrides_default():
    files = src(
        **{
            "src/app.py": """
                import os

                A = os.getenv("CFG_ENVIRONMENT", "local")
                B = os.getenv("CFG_OTHER", "x")
            """
        }
    )
    result = scan_python(files, profile(always_required=("CFG_ENVIRONMENT", "CFG_NOT_READ")))
    assert names(result) == {"CFG_ENVIRONMENT": True, "CFG_OTHER": False}


def test_a_name_read_in_two_places_keeps_every_place_and_the_strictest_rule():
    files = src(
        **{
            "src/a.py": """
                import os

                A = os.getenv("CFG_X", "d")
            """,
            "src/b.py": """
                import os

                B = os.environ["CFG_X"]
            """,
        }
    )
    item = scan_python(files, profile()).names["CFG_X"]
    assert item.required is True
    assert item.where == ("src/a.py:4", "src/b.py:4")
    assert item.count == 2


def sh(**files: str) -> dict[str, bytes]:
    return {path: textwrap.dedent(text).encode() for path, text in files.items()}


def test_shell_expansions_three_forms():
    files = sh(
        **{
            "entrypoint.sh": """\
                #!/bin/sh
                cat > /usr/share/config.js <<EOT
                window.__CONFIG__ = {
                  api: "${APP_API_URL}",
                  mode: "${APP_MODE-prod}",
                  auth: "${APP_AUTH:-none}",
                  nested: "${APP_OUTER:-${APP_INNER}}"
                }
                EOT
                echo "${1} ${#APP_LEN} $HOME"
                # "${APP_IN_A_COMMENT}"
            """,
            "src/app.js": 'const x = "${NOT_A_SHELL_FILE}";',
        }
    )
    result = scan_shell(files, ["entrypoint.sh"])
    assert {n: i.required for n, i in result.names.items()} == {
        "APP_API_URL": True,
        "APP_MODE": False,
        "APP_AUTH": False,
        "APP_OUTER": False,
        "APP_INNER": True,
    }
    assert result.names["APP_API_URL"].kind == "shell"
    assert result.names["APP_API_URL"].where == ("entrypoint.sh:4",)
    assert result.warnings == []


def test_shell_names_assigned_in_script_skipped():
    files = sh(
        **{
            "entrypoint.sh": """\
                #!/bin/sh
                DEST=/usr/share/nginx
                export CONF=${DEST}/conf.d
                for ITEM in a b; do echo "${ITEM}"; done
                while read LINE; do echo "${LINE}"; done
                BASE_URL="${BASE_URL:-http://local}"
                echo "${DEST} ${CONF} ${APP_REAL}"
            """
        }
    )
    result = scan_shell(files, ["entrypoint.sh"])
    assert {n: i.required for n, i in result.names.items()} == {
        "APP_REAL": True,
        "BASE_URL": False,
    }


def test_shell_file_missing_at_the_ref_is_a_warning():
    result = scan_shell(sh(**{"entrypoint.sh": "echo ${A_B}"}), ["entrypoint.sh", "other.sh"])
    assert set(result.names) == {"A_B"}
    assert result.warnings == ["other.sh: shell file not found at that commit"]


def commit_all(git, repo: Path, files: dict[str, str], message: str = "c") -> str:
    for path, text in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(text), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def test_files_at_ref_ignores_dirty_working_tree(repo, git):
    sha = commit_all(git, repo, {"src/a.py": "A = 1\n", "docs/readme.md": "x\n"})
    (repo / "src" / "a.py").write_text("A = 2  # dirty\n", encoding="utf-8")
    (repo / "src" / "untracked.py").write_text("B = 1\n", encoding="utf-8")
    (repo / "docs" / "readme.md").unlink()
    git(repo, "checkout", "-q", "-b", "other")
    commit_all(git, repo, {"src/a.py": "A = 3\n"}, "other branch")
    git(repo, "checkout", "-q", "-")
    assert files_at(repo, sha) == {"src/a.py": b"A = 1\n", "docs/readme.md": b"x\n"}
    assert files_at(repo, sha, only=lambda p: p.endswith(".py")) == {"src/a.py": b"A = 1\n"}


def test_files_at_reads_binary_and_empty_files_and_skips_symlinks(repo, git):
    (repo / "blob.bin").write_bytes(b"\x00\xff\n\x00")
    (repo / "empty.txt").write_bytes(b"")
    (repo / "link").symlink_to("blob.bin")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c")
    assert files_at(repo, "HEAD") == {"blob.bin": b"\x00\xff\n\x00", "empty.txt": b""}


def test_missing_commit_exits_2_without_fetch(repo, git, tmp_path):
    commit_all(git, repo, {"a.py": "A = 1\n"})
    with pytest.raises(SetupError) as error:
        files_at(repo, "origin/not-fetched-yet")
    assert "git fetch first" in str(error.value)
    with pytest.raises(SetupError, match="git fetch first"):
        files_at(repo, "0123456789abcdef0123456789abcdef01234567")
    with pytest.raises(SetupError, match="not a directory"):
        files_at(tmp_path / "nowhere", "HEAD")
    assert not (repo / ".git" / "FETCH_HEAD").exists()


VALUES = """\
    standard-service-chart:
      image:
        # repository: "" # not this one
        tag: sand-0123abc
      env: {}
"""


def test_deployed_sha_from_image_tag(tmp_path):
    (tmp_path / "apps" / "app").mkdir(parents=True)
    (tmp_path / "apps" / "app" / "values.yaml").write_text(textwrap.dedent(VALUES))
    assert deployed_sha(tmp_path, ["apps/app/values.yaml"]) == "0123abc"
    quoted = textwrap.dedent(VALUES).replace("sand-0123abc", '"prod-' + "a" * 40 + '" # comment')
    (tmp_path / "apps" / "app" / "values.yaml").write_text(quoted)
    assert deployed_sha(tmp_path, ["apps/app/values.yaml"]) == "a" * 40


def test_deployed_sha_errors_are_setup_errors(tmp_path):
    (tmp_path / "v.yaml").write_text("standard-service-chart:\n  image:\n    tag: latest\n")
    (tmp_path / "w.yaml").write_text("other:\n  image:\n    tag: sand-0123abc\n")
    (tmp_path / "x.yaml").write_text(textwrap.dedent(VALUES).replace("0123abc", "9999999"))
    (tmp_path / "ok.yaml").write_text(textwrap.dedent(VALUES))
    with pytest.raises(SetupError, match=r"v\.yaml.*not <env>-<sha>"):
        deployed_sha(tmp_path, ["v.yaml"])
    with pytest.raises(SetupError, match=r"w\.yaml.*no image tag"):
        deployed_sha(tmp_path, ["w.yaml"])
    with pytest.raises(SetupError, match="gone.yaml"):
        deployed_sha(tmp_path, ["gone.yaml"])
    with pytest.raises(SetupError, match="differ"):
        deployed_sha(tmp_path, ["ok.yaml", "x.yaml"])
    with pytest.raises(SetupError, match="no values file"):
        deployed_sha(tmp_path, [])


def test_argocd_env_list_and_map_layouts():
    listed = textwrap.dedent(
        """\
        standard-service-chart:
          # env: [{name: IN_COMMENT}]
          env:
            - name: FOO
              value: "x"
            - name: "BAR" # trailing comment

              valueFrom:
                secretKeyRef:
                  name: not-an-env-name
                  key: k
            - {name: FLOW, value: y}
          extraEnv: []
          worker:
            env: {}
        """
    )
    mapped = textwrap.dedent(
        """\
        standard-service-chart:
          env:
            FOO: x

            BAR: "y"  # note
            baz_qux:
              nested: ignored
          other: z
          envFrom:
            - name: NOT_AN_ENV_BLOCK
        """
    )
    assert argocd_env_names("v.yaml", listed) == ({"FOO", "BAR", "FLOW"}, [])
    assert argocd_env_names("v.yaml", mapped) == ({"FOO", "BAR", "BAZ_QUX"}, [])


def test_argocd_list_at_the_key_indent():
    text = "env:\n- name: FOO\n- name: BAR\nafter: 1\n"
    assert argocd_env_names("v.yaml", text) == ({"FOO", "BAR"}, [])


def test_argocd_extra_env_and_one_file_per_brand():
    brand_a = "chart:\n  env:\n    - name: SHARED\n  extraEnv:\n    - name: ONLY_A\n"
    brand_b = "chart:\n  extraEnv:\n    - name: SHARED\n    - name: ONLY_B\n"
    names_a, _ = argocd_env_names("a.yaml", brand_a)
    names_b, _ = argocd_env_names("b.yaml", brand_b)
    assert names_a | names_b == {"SHARED", "ONLY_A", "ONLY_B"}


def test_argocd_unreadable_block_is_a_warning_with_line():
    text = textwrap.dedent(
        """\
        chart:
          env: {FOO: x}
          extraEnv:
            - value: orphan
            - name: GOOD
          worker:
            env: *shared
          other:
            env:
              - just text
        """
    )
    names, warnings = argocd_env_names("apps/v.yaml", text)
    assert names == {"GOOD"}
    assert [w.split(":")[0:2] for w in warnings] == [
        ["apps/v.yaml", "2"],
        ["apps/v.yaml", "4"],
        ["apps/v.yaml", "7"],
        ["apps/v.yaml", "10"],
    ]


CANARY = "leak-canary-7f3a"

FAKE_AWS = """\
#!{python}
import json, os, sys

with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
mode = os.environ.get("FAKE_AWS_MODE", "ok")
errors = {{
    "missing": "The config profile (some-profile) could not be found",
    "expired": "The SSO session associated with this profile (some-profile) has expired",
    "denied": "An error occurred (AccessDeniedException) when calling DescribeParameters",
    "network": "Could not connect to the endpoint URL",
}}
if mode in errors:
    print(errors[mode] + " {canary}", file=sys.stderr)
    sys.exit(255)
if mode == "garbage":
    print("not json {canary}")
    sys.exit(0)
print(json.dumps(json.loads(os.environ["FAKE_AWS_NAMES"])))
"""

FAKE_SCRIPT = """\
#!{python}
import json, os, sys

with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
print("\\x1b[32m[SecureString]\\x1b[0m /realm/env/app/CFG_ONE={canary}")
print("[String] /realm/env/app/CFG/TWO/PART=a=b value with = signs {canary}")
print("[StringList] /realm/env/app-bff/CFG_LONGER=other app {canary}")
print("[String] /realm/env/app/cfg-three=x")
print("Total: 4 parameters")
print("stderr noise {canary}", file=sys.stderr)
sys.exit(int(os.environ.get("FAKE_SCRIPT_EXIT", "0")))
"""


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    """Installs a fake program first on PATH; its calls are logged as JSON lines in FAKE_LOG."""
    folder = tmp_path / "fake-bin"
    folder.mkdir()
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")

    def install(name: str, template: str) -> Path:
        path = folder / name
        path.write_text(template.format(python=sys.executable, canary=CANARY), encoding="utf-8")
        path.chmod(0o755)
        return path

    install.calls = lambda: (
        [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    )
    return install


def aws_settings() -> EnvCheckSettings:
    return EnvCheckSettings(source="aws", script=None, role_vars=(), repos={})


def script_settings(script: Path) -> EnvCheckSettings:
    return EnvCheckSettings(source="script", script=script, role_vars=(), repos={})


def test_aws_describe_parameters_names_paginated(fake_bin, monkeypatch):
    fake_bin("aws", FAKE_AWS)
    many = [f"/realm/env/app/CFG_N{i}" for i in range(120)]
    monkeypatch.setenv("FAKE_AWS_NAMES", json.dumps(many))
    found = store_names(aws_settings(), profile(), "prod")
    assert found == {f"CFG_N{i}" for i in range(120)}
    (call,) = fake_bin.calls()
    assert call[:2] == ["ssm", "describe-parameters"]
    assert call[call.index("--profile") + 1] == "some-profile"
    assert (
        call[call.index("--parameter-filters") + 1]
        == "Key=Path,Option=Recursive,Values=/realm/env/app"
    )
    assert call[call.index("--query") + 1] == "Parameters[].Name"
    assert "--no-paginate" not in call and "--max-items" not in call
    assert "--with-decryption" not in call


def test_aws_profile_error_exits_2_access_error_exits_3(fake_bin, monkeypatch):
    fake_bin("aws", FAKE_AWS)
    monkeypatch.setenv("FAKE_AWS_NAMES", "[]")
    for mode in ("missing", "expired"):
        monkeypatch.setenv("FAKE_AWS_MODE", mode)
        with pytest.raises(SetupError, match="some-profile") as error:
            store_names(aws_settings(), profile(), "prod")
        assert CANARY not in str(error.value)
    for mode in ("denied", "network", "garbage"):
        monkeypatch.setenv("FAKE_AWS_MODE", mode)
        with pytest.raises(StoreUnreachable) as error:
            store_names(aws_settings(), profile(), "prod")
        assert CANARY not in str(error.value)


def test_aws_setup_problems_are_setup_errors(fake_bin, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path / "no-bin"))
    with pytest.raises(SetupError, match="aws CLI not found"):
        store_names(aws_settings(), profile(), "prod")
    with pytest.raises(SetupError, match=r"profile\.prod"):
        store_names(aws_settings(), profile(profile={}), "prod")
    with pytest.raises(SetupError, match=r"prefix\.staging"):
        store_names(aws_settings(), profile(), "staging")


def test_prefix_filter_excludes_longer_app_name(fake_bin, monkeypatch):
    fake_bin("aws", FAKE_AWS)
    listed = [
        "/realm/env/app/CFG_A",
        "/realm/env/app-bff/CFG_B",
        "/realm/env/app2/CFG_C",
        "/realm/env/app",
        "/other/CFG_D",
    ]
    monkeypatch.setenv("FAKE_AWS_NAMES", json.dumps(listed))
    assert store_names(aws_settings(), profile(), "prod") == {"CFG_A"}


def test_normalize_strips_prefix_slashes_dashes_uppercases():
    prefix = "/realm/env/app"
    assert normalize_store_name("/realm/env/app/CFG/FASTAPI/TITLE", prefix) == "CFG_FASTAPI_TITLE"
    assert normalize_store_name("/realm/env/app/CFG_FASTAPI_TITLE", prefix) == "CFG_FASTAPI_TITLE"
    assert normalize_store_name("/realm/env/app/cfg-log/level", prefix) == "CFG_LOG_LEVEL"
    assert normalize_store_name("realm/env/app/CFG_X", "/realm/env/app/") == "CFG_X"
    assert normalize_store_name("/realm/env/app-bff/CFG_X", prefix) is None
    assert normalize_store_name("/realm/env/app", prefix) is None
    assert normalize_store_name("/realm/env/app/", prefix) is None


def test_invalid_normalized_name_reported(fake_bin, monkeypatch):
    fake_bin("aws", FAKE_AWS)
    listed = ["/realm/env/app/CFG_OK", "/realm/env/app/CFG.DOTTED", "/realm/env/app/1ST"]
    monkeypatch.setenv("FAKE_AWS_NAMES", json.dumps(listed))
    found = store_names(aws_settings(), profile(), "prod")
    assert found == {"CFG_OK", "CFG.DOTTED", "1ST"}
    assert {name for name in found if not is_valid_name(name)} == {"CFG.DOTTED", "1ST"}


def export_aws_variables(monkeypatch) -> None:
    for variable in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(variable, "fake")


def test_script_names_parsed_and_values_dropped(fake_bin, monkeypatch, capsys):
    script = fake_bin("list-store", FAKE_SCRIPT)
    export_aws_variables(monkeypatch)
    found = store_names(script_settings(script), profile(), "prod")
    assert found == {"CFG_ONE", "CFG_TWO_PART", "CFG_THREE"}
    assert fake_bin.calls() == [["/realm/env/app"]]
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err + repr(found)


def test_script_without_aws_variables_exits_2(fake_bin, monkeypatch):
    script = fake_bin("list-store", FAKE_SCRIPT)
    for variable in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake")
    with pytest.raises(SetupError, match="AWS_ACCESS_KEY_ID.*terminal"):
        store_names(script_settings(script), profile(), "prod")
    assert fake_bin.calls() == []


def test_script_missing_or_unconfigured_is_a_setup_error(monkeypatch, tmp_path):
    export_aws_variables(monkeypatch)
    with pytest.raises(SetupError, match="not found"):
        store_names(script_settings(tmp_path / "gone"), profile(), "prod")
    with pytest.raises(SetupError, match="script"):
        store_names(script_settings(None), profile(), "prod")


def all_text(error: BaseException) -> str:
    """The message, the repr and the whole traceback of an exception and its chain."""
    parts = []
    seen = error
    while seen is not None:
        parts.append(f"{seen!r} {seen} " + "".join(traceback.format_exception(seen)))
        seen = seen.__cause__ or seen.__context__
    return " ".join(parts)


def test_no_value_reaches_any_output(fake_bin, monkeypatch, capsys):
    script = fake_bin("list-store", FAKE_SCRIPT)
    export_aws_variables(monkeypatch)
    found = store_names(script_settings(script), profile(), "prod")
    monkeypatch.setenv("FAKE_SCRIPT_EXIT", "1")
    with pytest.raises(StoreUnreachable) as error:
        store_names(script_settings(script), profile(), "prod")
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err + all_text(error.value) + repr(found)
    assert "1" in str(error.value)


def test_script_timeout_keeps_no_output_in_the_exception(monkeypatch, tmp_path):
    export_aws_variables(monkeypatch)
    script = tmp_path / "slow"
    script.write_text(
        f"#!{sys.executable}\nimport time\nprint('{CANARY}', flush=True)\ntime.sleep(5)\n"
    )
    script.chmod(0o755)
    monkeypatch.setattr(envcheck, "STORE_TIMEOUT_SECONDS", 0.5)
    with pytest.raises(StoreUnreachable) as error:
        store_names(script_settings(script), profile(), "prod")
    assert CANARY not in all_text(error.value)
    assert error.value.__context__ is None
