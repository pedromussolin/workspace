import json
import os
import sys
import textwrap
import traceback
from pathlib import Path

import pytest

from ws import envcheck
from ws.cli import main
from ws.envcheck import (
    EnvCheckSettings,
    RepoProfile,
    SetupError,
    StoreUnreachable,
    argocd_env_names,
    compare,
    deployed_sha,
    files_at,
    is_valid_name,
    normalize_store_name,
    scan_python,
    scan_shell,
    store_names,
)
from ws.userconfig import ConfigInvalid, ConfigMissing


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


def test_in_environ_is_a_read_with_a_default():
    files = src(
        **{
            "src/app.py": """
                import os

                if "CFG_FLAG_ON" in os.environ:
                    pass
                SKIP = "CFG_FLAG_OFF" not in os.environ
                BOTH = "CFG_X" in os.environ and 1 < 2
                key = "CFG_DYN"
                DYN = key in os.environ
                NOT_ENV = "CFG_NOT_ENV" in {"a": 1}
            """
        }
    )
    result = scan_python(files, profile())
    assert names(result) == {"CFG_FLAG_ON": False, "CFG_FLAG_OFF": False, "CFG_X": False}
    assert result.names["CFG_FLAG_ON"].where == ("src/app.py:4",)
    assert [(u.where, u.call) for u in result.unresolved] == [("src/app.py:9", "in os.environ")]


def test_env_prefix_as_a_class_keyword():
    files = src(
        **{
            "src/config.py": """
                from pydantic_settings import BaseSettings, SettingsConfigDict


                class GroupSettings(BaseSettings, env_prefix="CFG_G_"):
                    host: str


                class Both(BaseSettings, env_prefix="CFG_KW_"):
                    model_config = SettingsConfigDict(env_prefix="CFG_BODY_")

                    port: int = 1


                class Child(GroupSettings):
                    user: str


                class Dynamic(BaseSettings, env_prefix=PREFIX):
                    region: str
            """
        }
    )
    result = scan_python(files, profile())
    assert names(result) == {
        "CFG_G_HOST": True,
        "CFG_G_USER": True,
        "CFG_KW_PORT": False,
        "REGION": True,
    }
    assert any("src/config.py:19" in w and "env_prefix" in w for w in result.warnings)


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


def test_shell_name_defaulted_from_itself_is_optional_everywhere():
    files = sh(
        **{
            "entrypoint.sh": """\
                #!/bin/sh
                echo "${APP_EARLY}"
                APP_EARLY="${APP_EARLY:-x}"
                : "${APP_SET:=y}"
                APP_EQ=${APP_EQ=z}
                echo "${APP_EQ} ${APP_EARLY} ${APP_SELF}"
                APP_SELF=${APP_SELF}
                echo "${APP_SELF} ${APP_PLAIN}"
            """
        }
    )
    result = scan_shell(files, ["entrypoint.sh"])
    assert {n: i.required for n, i in result.names.items()} == {
        "APP_EARLY": False,
        "APP_SET": False,
        "APP_EQ": False,
        "APP_SELF": True,
        "APP_PLAIN": True,
    }


@pytest.mark.parametrize(
    "line",
    [
        "a) SVC=one ;;",
        "true; SVC=one",
        "test -n x && SVC=one",
        "test -n x || SVC=one",
        "if true; then SVC=one; fi",
        "for i in a; do SVC=one; done",
        "if false; then :; else SVC=one; fi",
        "! SVC=one",
        "case x in a) SVC=one;; b) OTHER=two;; esac",
    ],
)
def test_shell_assignment_after_a_separator_or_keyword(line):
    files = sh(**{"entrypoint.sh": f"{line}\necho ${{SVC}} ${{APP_REAL}}\n"})
    result = scan_shell(files, ["entrypoint.sh"])
    assert set(result.names) == {"APP_REAL"}


def test_shell_assignment_value_stops_at_the_separator():
    files = sh(**{"entrypoint.sh": "A=1; B=${A}\nC=${D}; D=${C}\necho ${A} ${B} ${E}\n"})
    result = scan_shell(files, ["entrypoint.sh"])
    assert set(result.names) == {"E"}


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


FAKE_SCRIPT_NOT_UTF8 = """\
#!{python}
import sys

out = sys.stdout.buffer
out.write(b"[SecureString] /realm/env/app/CFG_ONE=\\xff\\xfe{canary}\\n")
# \\xc2\\x85 is U+0085, a line break for str.splitlines: the text after it stays in the value.
out.write(b"[String] /realm/env/app/CFG_TWO=\\xc3{canary}\\xc2\\x85")
out.write(b"[String] /realm/env/app/CFG_X=1\\n")
out.write(b"Total: 2 parameters\\n")
"""


class FakeCompleted:
    def __init__(self, stdout: bytes, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def test_script_output_not_utf8_is_read_without_a_crash(fake_bin, monkeypatch, capsys):
    script = fake_bin("list-store", FAKE_SCRIPT_NOT_UTF8)
    export_aws_variables(monkeypatch)
    found = store_names(script_settings(script), profile(), "prod")
    assert found == {"CFG_ONE", "CFG_TWO"}
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err + repr(found)


@pytest.mark.parametrize("where", ["parse", "run"])
def test_any_script_failure_is_a_fixed_error_without_the_output(fake_bin, monkeypatch, where):
    script = fake_bin("list-store", FAKE_SCRIPT)
    export_aws_variables(monkeypatch)
    output = b"[SecureString] /realm/env/app/CFG_ONE=\xff" + CANARY.encode() + b"\n"

    def broken_parse(text: str) -> list[str]:
        raise UnicodeDecodeError("utf-8", output, 0, 1, "invalid start byte")

    def broken_run(*args, **kwargs):
        raise ValueError(output)

    monkeypatch.setattr(envcheck, "_names_from_script_output", broken_parse)
    run = broken_run if where == "run" else (lambda *a, **k: FakeCompleted(output))
    with pytest.raises(StoreUnreachable) as error:
        store_names(script_settings(script), profile(), "prod", run=run)
    assert error.value.__context__ is None
    assert error.value.__cause__ is None
    assert error.value.args == (envcheck.SCRIPT_UNREADABLE_HINT,)
    for text in (
        str(error.value),
        repr(error.value),
        repr(error.value.args),
        all_text(error.value),
    ):
        assert CANARY not in text


CONFIG = """\
[env_check]
source = "aws"
role_vars = ["AWS_*", "POD_ROLE"]

[env_check.repos.api]
path = "{repo}"
argocd = "{argocd}"
prefix = {{ prod = "/realm/env/app", sandbox = "/realm/sbx/app" }}
values = {{ prod = ["apps/app/prod.yaml"], sandbox = ["apps/app/sbx.yaml"] }}
profile = {{ prod = "some-profile", sandbox = "sbx-profile" }}
helpers = ["env"]
migration_globs = ["migrations/**"]
always_required = ["CFG_ENVIRONMENT"]
"""

CODE = {
    "src/config.py": """
        import os
        from pydantic_settings import BaseSettings, SettingsConfigDict


        class LogSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="CFG_LOG_")

            level: str = "INFO"
            sink: str


        class DbSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="CFG_DB_")

            url: str


        ENVIRONMENT = os.getenv("CFG_ENVIRONMENT", "local")
    """,
    "src/jobs.py": """
        def run(partner):
            a = env(f"CFG_{partner}_URL")
            b = env("CFG_JOB_FLAG")
            c = env("CFG_BUSY")
            c = env("CFG_BUSY")
            c = env("CFG_BUSY")
            c = env("CFG_BUSY")
            c = env("CFG_BUSY")
    """,
    "migrations/versions/0001_seed.py": """
        value = env("CFG_MIG_ONLY")
    """,
}

DEFAULT_STORE = [
    "/realm/env/app/CFG_DB_URL",
    "/realm/env/app/CFG/ENVIRONMENT",
    "/realm/env/app/CFG_OLD_THING",
    "/realm/env/app/cfg.bad",
    "/realm/env/app-bff/CFG_LOG_SINK",
    "/realm/env/app/CFG_BUSY",
    "/realm/env/app/CFG_JOB_FLAG",
]
CLEAN_STORE = [
    f"/realm/env/app/{name}"
    for name in (
        "CFG_LOG_SINK",
        "CFG_LOG_LEVEL",
        "CFG_DB_URL",
        "CFG_ENVIRONMENT",
        "CFG_BUSY",
        "CFG_JOB_FLAG",
    )
]

ARGOCD_VALUES = """\
    standard-service-chart:
      image:
        tag: prod-{sha}
      env:
        - name: AWS_REGION
          value: x
        - name: FOO_FLAG
          value: "1"
      extraEnv:
        - name: CFG_DB_URL
          value: y
"""
ARGOCD_CLEAN = """\
    standard-service-chart:
      image:
        tag: prod-{sha}
      env:
        - name: POD_ROLE
          value: x
"""


class Scenario:
    def __init__(self, tmp_path, monkeypatch, git, fake_bin):
        self.repo = tmp_path / "api"
        self.argocd = tmp_path / "api-argocd"
        self.config = tmp_path / "cfg"
        self.monkeypatch = monkeypatch
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        self.sha = commit_all(git, self.repo, CODE)
        self.write_values(ARGOCD_VALUES)
        self.config.mkdir()
        (self.config / "config.toml").write_text(
            CONFIG.format(repo=self.repo, argocd=self.argocd), encoding="utf-8"
        )
        monkeypatch.setenv("WS_CONFIG_DIR", str(self.config))
        fake_bin("aws", FAKE_AWS)
        self.set_store(DEFAULT_STORE)

    def set_store(self, names: list[str]) -> None:
        self.monkeypatch.setenv("FAKE_AWS_NAMES", json.dumps(names))

    def write_values(self, text: str, name: str = "prod.yaml") -> None:
        target = self.argocd / "apps" / "app" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(text).replace("{sha}", self.sha[:7]), encoding="utf-8")

    def check(self, capsys, *args: str, env: str = "prod", ref: str | None = None):
        """Runs `ws env check api`; returns (exit code, stdout, stderr)."""
        flags = ["--ref", ref or self.sha] if "--deployed" not in args else []
        code = main(["env", "check", "api", "--env", env, *flags, *args])
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    def check_json(self, capsys, *args: str, **kwargs):
        code, out, err = self.check(capsys, "--json", *args, **kwargs)
        return code, json.loads(out), err


@pytest.fixture
def scenario(tmp_path, monkeypatch, git, fake_bin):
    return Scenario(tmp_path, monkeypatch, git, fake_bin)


def names_of(entries) -> list[str]:
    return [e["name"] if isinstance(e, dict) else e for e in entries]


def test_bucket_missing_required(scenario, capsys):
    code, result, _ = scenario.check_json(capsys)
    assert code == 1
    assert names_of(result["missing_required"]) == ["CFG_LOG_SINK"]
    entry = result["missing_required"][0]
    assert entry["where"] == ["src/config.py:10"]
    assert entry["count"] == 1
    assert entry["kind"] == "settings"


def test_bucket_missing_with_default(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert names_of(result["missing_with_default"]) == ["CFG_LOG_LEVEL"]


def test_bucket_in_argocd(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert result["in_argocd"] == [
        {"name": "CFG_DB_URL", "in_store": True, "read_by_code": True},
        {"name": "FOO_FLAG", "in_store": False, "read_by_code": False},
    ]


def test_bucket_only_in_store(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert result["only_in_store"] == ["CFG_OLD_THING"]


def test_bucket_invalid_in_store(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert result["invalid_in_store"] == ["CFG.BAD"]
    assert "CFG.BAD" not in result["only_in_store"]


def test_bucket_migration_only(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert result["migration_only"] == [
        {
            "name": "CFG_MIG_ONLY",
            "required": True,
            "kind": "migration",
            "where": ["migrations/versions/0001_seed.py:2"],
            "count": 1,
            "in_store": False,
        }
    ]
    assert "CFG_MIG_ONLY" not in names_of(result["missing_required"])


def test_bucket_unresolved(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert result["unresolved"] == [{"where": "src/jobs.py:3", "call": "env"}]


def test_role_vars_patterns(scenario, capsys):
    scenario.write_values(
        """\
        standard-service-chart:
          env:
            - name: AWS_REGION
            - name: AWS_ANYTHING_ELSE
            - name: pod_role
            - name: POD_ROLE_NOT
            - name: MY_AWS_X
        """
    )
    _, result, _ = scenario.check_json(capsys)
    assert names_of(result["in_argocd"]) == ["MY_AWS_X", "POD_ROLE_NOT"]


def test_where_keeps_three_and_counts(scenario, capsys):
    scenario.set_store([])
    _, result, _ = scenario.check_json(capsys)
    busy = next(e for e in result["missing_required"] if e["name"] == "CFG_BUSY")
    assert busy["where"] == ["src/jobs.py:5", "src/jobs.py:6", "src/jobs.py:7"]
    assert busy["count"] == 5
    assert "src/jobs.py:5; src/jobs.py:6; src/jobs.py:7 (+2)" in scenario.check(capsys)[1]


def test_always_required_makes_a_defaulted_name_required(scenario, capsys):
    scenario.set_store([])
    _, result, _ = scenario.check_json(capsys)
    assert "CFG_ENVIRONMENT" in names_of(result["missing_required"])
    assert "CFG_ENVIRONMENT" not in names_of(result["missing_with_default"])


def test_json_header_and_counts(scenario, capsys):
    _, result, _ = scenario.check_json(capsys)
    assert result["repo"] == "api"
    assert result["env"] == "prod"
    assert result["source"] == "aws"
    assert result["commit"] == {"ref": scenario.sha, "sha": scenario.sha, "deployed": False}
    assert result["ok"] is False
    assert result["counts"]["store"] == 6
    assert result["counts"]["argocd"] == 3
    assert result["counts"]["missing_required"] == 1
    assert result["warnings"] == []


def test_text_is_ptbr_and_omits_empty_buckets(scenario, capsys):
    code, out, _ = scenario.check(capsys)
    assert code == 1
    assert "Código verificado" in out
    assert "Obrigatórias ausentes do Parameter Store (1)" in out
    assert "CFG_LOG_SINK" in out
    assert "REPROVADO" in out
    scenario.set_store(CLEAN_STORE)
    scenario.write_values(ARGOCD_CLEAN)
    code, out, _ = scenario.check(capsys)
    assert code == 0
    assert "APROVADO" in out
    for omitted in ("Obrigatórias ausentes", "No argocd", "Só no Parameter Store", "Inválidos"):
        assert omitted not in out
    assert "Lidas só nas migrações (1)" in out
    assert "Leituras que o scanner não resolve (1)" in out


def test_deployed_takes_the_sha_of_the_image_tag(scenario, git, capsys):
    git(scenario.repo, "commit", "-q", "--allow-empty", "-m", "later")
    code, out, _ = scenario.check_json(capsys, "--deployed")
    assert code == 1
    assert out["commit"] == {"ref": None, "sha": scenario.sha, "deployed": True}
    assert names_of(out["missing_required"]) == ["CFG_LOG_SINK"]


def test_ref_or_deployed_required(scenario, capsys):
    with pytest.raises(SystemExit) as error:
        main(["env", "check", "api", "--env", "prod"])
    assert error.value.code == 2
    with pytest.raises(SystemExit) as error:
        main(["env", "check", "api", "--env", "prod", "--ref", "HEAD", "--deployed"])
    assert error.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


def test_exit_codes(scenario, capsys, monkeypatch, tmp_path):
    scenario.set_store(CLEAN_STORE)
    scenario.write_values(ARGOCD_CLEAN)
    assert scenario.check(capsys)[0] == 0
    scenario.write_values(ARGOCD_VALUES)
    assert scenario.check(capsys)[0] == 1
    scenario.set_store(DEFAULT_STORE)
    assert scenario.check(capsys)[0] == 1

    assert scenario.check(capsys, ref="no-such-ref")[0] == 2
    assert scenario.check(capsys, env="staging")[0] == 2
    code = main(["env", "check", "other-repo", "--env", "prod", "--ref", "HEAD"])
    assert code == 2
    assert "other-repo" in capsys.readouterr().err

    monkeypatch.setenv("FAKE_AWS_MODE", "expired")
    assert scenario.check(capsys)[0] == 2
    monkeypatch.setenv("FAKE_AWS_MODE", "denied")
    code, out, err = scenario.check(capsys)
    assert code == 3
    assert CANARY not in out + err

    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "empty-config"))
    code = main(["env", "check", "api", "--env", "prod", "--ref", "HEAD"])
    assert code == 2
    assert "config.toml" in capsys.readouterr().err


def test_missing_commit_says_to_fetch_first(scenario, capsys):
    code, out, err = scenario.check(capsys, ref="origin/not-fetched")
    assert (code, out) == (2, "")
    assert "git fetch first" in err


def test_scan_warnings_are_reported(scenario, git, capsys):
    commit_all(git, scenario.repo, {"src/broken.py": "def broken(:\n"})
    scenario.write_values("chart:\n  env: {A: 1}\n")
    code, result, _ = scenario.check_json(capsys, ref="HEAD")
    assert result["warnings"] == [
        "src/broken.py:1: syntax error, file skipped",
        "apps/app/prod.yaml:2: cannot read the inline env value; skipped",
    ]
    assert code == 1


def test_no_values_file_for_the_env_is_a_warning(scenario, capsys):
    _, result, _ = scenario.check_json(capsys, env="sandbox")
    assert result["warnings"] == ["apps/app/sbx.yaml: values file not found; argocd not checked"]
    assert result["in_argocd"] == []


def test_no_value_reaches_the_cli_output(scenario, fake_bin, tmp_path, monkeypatch, capsys):
    script = fake_bin("list-store", FAKE_SCRIPT)
    config = (scenario.config / "config.toml").read_text(encoding="utf-8")
    config = config.replace('source = "aws"', f'source = "script"\nscript = "{script}"')
    (scenario.config / "config.toml").write_text(config, encoding="utf-8")
    export_aws_variables(monkeypatch)
    seen = []
    for mode in ("0", "1"):
        monkeypatch.setenv("FAKE_SCRIPT_EXIT", mode)
        for extra in ((), ("--json",)):
            code, out, err = scenario.check(capsys, *extra)
            seen.append(out + err)
            assert code == (1 if mode == "0" else 3)
    assert CANARY not in " ".join(seen)
    assert "código 1" in seen[-1]


def use_script_source(scenario, script: Path) -> None:
    config = (scenario.config / "config.toml").read_text(encoding="utf-8")
    config = config.replace('source = "aws"', f'source = "script"\nscript = "{script}"')
    (scenario.config / "config.toml").write_text(config, encoding="utf-8")


def test_script_output_problems_never_reach_the_cli(scenario, fake_bin, monkeypatch, capsys):
    use_script_source(scenario, fake_bin("list-store", FAKE_SCRIPT_NOT_UTF8))
    export_aws_variables(monkeypatch)
    code, out, err = scenario.check(capsys)
    assert code == 1
    assert CANARY not in out + err

    def broken_parse(text: str) -> list[str]:
        raise UnicodeDecodeError("utf-8", CANARY.encode(), 0, 1, "invalid start byte")

    monkeypatch.setattr(envcheck, "_names_from_script_output", broken_parse)
    for extra in ((), ("--json",)):
        code, out, err = scenario.check(capsys, *extra)
        assert (code, out) == (3, "")
        assert CANARY not in err
        assert "não pôde ser lida" in err


def settings_file(tmp_path, monkeypatch, body: str) -> Path:
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.toml").write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp_path / "config.toml"


def test_load_settings_reads_the_table(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", "/fake-home")
    settings_file(
        tmp_path,
        monkeypatch,
        """\
        [env_check]
        source = "script"
        script = "~/bashes/list"
        role_vars = ["A_*"]

        [env_check.repos.api]
        path = "~/repos/api"
        argocd = "~/repos/api-argocd"
        prefix = { prod = "/p" }
        values = { prod = ["v.yaml"] }
        dynamic = { Cls = ["CFG_X_"] }

        [env_check.repos.front]
        path = "/abs/front"
        argocd = "/abs/front-argocd"
        kind = "shell"
        shell_files = ["entrypoint.sh"]
        prefix = { prod = "/q" }
        """,
    )
    settings = envcheck.load_settings()
    assert settings.source == "script"
    assert settings.script == Path("/fake-home/bashes/list")
    assert settings.role_vars == ("A_*",)
    api = settings.repos["api"]
    assert (api.name, api.kind, api.path) == ("api", "python", Path("/fake-home/repos/api"))
    assert api.prefix == {"prod": "/p"} and api.values == {"prod": ["v.yaml"]}
    assert api.dynamic == {"Cls": ("CFG_X_",)}
    assert settings.repos["front"].shell_files == ("entrypoint.sh",)


def test_load_settings_defaults_to_aws(tmp_path, monkeypatch):
    settings_file(tmp_path, monkeypatch, "[env_check]\n")
    settings = envcheck.load_settings()
    assert (settings.source, settings.script, settings.repos) == ("aws", None, {})


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ('source = "both"', "env_check.source"),
        ("role_vars = 3", "env_check.role_vars"),
        ("colour = 1", "env_check.colour"),
        ("repos = 1", "env_check.repos"),
        ("[env_check.repos.api]\nargocd = 'a'\nprefix = {p = 'x'}", "env_check.repos.api.path"),
        ("[env_check.repos.api]\npath = 'a'\nprefix = {p = 'x'}", "env_check.repos.api.argocd"),
        ("[env_check.repos.api]\npath = 'a'\nargocd = 'a'", "env_check.repos.api.prefix"),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p=1}",
            "env_check.repos.api.prefix.p",
        ),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p='x'}\nkind='go'",
            "env_check.repos.api.kind",
        ),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p='x'}\nkind='shell'",
            "env_check.repos.api.shell_files",
        ),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p='x'}\nhelpers=[1]",
            "env_check.repos.api.helpers",
        ),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p='x'}\nvalues={p='v'}",
            "env_check.repos.api.values.p",
        ),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p='x'}\ncolour=1",
            "env_check.repos.api.colour",
        ),
        (
            "[env_check.repos.api]\npath='a'\nargocd='a'\nprefix={p='x'}\ndynamic={C='x'}",
            "env_check.repos.api.dynamic.C",
        ),
    ],
)
def test_load_settings_names_the_bad_key(tmp_path, monkeypatch, body, key):
    settings_file(tmp_path, monkeypatch, "[env_check]\n" + body + "\n")
    with pytest.raises(ConfigInvalid, match=key.replace(".", r"\.")):
        envcheck.load_settings()


def test_load_settings_without_the_file_is_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "nowhere"))
    with pytest.raises(ConfigMissing):
        envcheck.load_settings()


def test_compare_is_a_pure_function_of_its_inputs():
    scan = scan_python(
        src(**{"src/a.py": "import os\nA = os.environ['CFG_A']\nB = os.getenv('CFG_B', 'x')\n"}),
        profile(),
    )
    result = compare(scan, {"CFG_B", "CFG_Z"}, {"CFG_Z", "POD_ROLE"}, ["POD_*"], [])
    assert names_of(result["missing_required"]) == ["CFG_A"]
    assert result["missing_with_default"] == []
    assert [e["name"] for e in result["in_argocd"]] == ["CFG_Z"]
    assert result["only_in_store"] == ["CFG_Z"]
    assert result["ok"] is False
    clean = compare(scan, {"CFG_A", "CFG_B"}, {"POD_ROLE"}, ["POD_*"], [])
    assert clean["ok"] is True
    forced = compare(scan, {"CFG_A"}, set(), [], ["CFG_B"])
    assert names_of(forced["missing_required"]) == ["CFG_B"]
    assert forced["missing_with_default"] == []
