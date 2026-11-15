"""File categories for the card review: config overrides first, then the defaults."""

from ws.envcheck import glob_regex

CATEGORIES = ("test", "migration", "contract", "model", "config", "front", "other")

DEFAULT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "test",
        (
            "**/tests/**",
            "**/test_*.py",
            "**/*_test.py",
            "**/conftest.py",
            "**/*.spec.ts",
            "**/__tests__/**",
        ),
    ),
    ("migration", ("**/alembic/versions/*.py", "**/migrations/versions/*.py")),
    (
        "contract",
        (
            "**/api/**",
            "**/routes/**",
            "**/routers/**",
            "**/endpoints/**",
            "**/controllers/**",
            "**/schemas/**",
            "**/serializers/**",
            "**/openapi*.json",
            "**/openapi*.yaml",
            "**/openapi*.yml",
        ),
    ),
    ("model", ("**/models/**", "**/models.py", "**/entities/**")),
    (
        "config",
        (
            "**/Dockerfile*",
            "**/*.toml",
            "**/*.ini",
            "**/*.cfg",
            "**/*.y*ml",
            "**/.env*",
            "**/requirements*.txt",
            "**/package*.json",
            "**/settings.py",
            "**/config.py",
            "**/environment*.ts",
            ".github/**",
        ),
    ),
    ("front", ("**/*.ts", "**/*.tsx", "**/*.js", "**/*.html", "**/*.scss", "**/*.css")),
)


def category_for(path: str, overrides: dict[str, tuple[str, ...]] | None = None) -> str:
    rules = [*(overrides or {}).items(), *DEFAULT_RULES]
    for category, globs in rules:
        if any(glob_regex(glob).fullmatch(path) for glob in globs):
            return category
    return "other"
