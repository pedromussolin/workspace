import textwrap
from pathlib import Path

import pytest

from ws.envcheck import RepoProfile, scan_python


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
