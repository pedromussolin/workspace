import textwrap
from pathlib import Path

import pytest

from ws.envcheck import (
    RepoProfile,
    SetupError,
    argocd_env_names,
    deployed_sha,
    files_at,
    scan_python,
    scan_shell,
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
