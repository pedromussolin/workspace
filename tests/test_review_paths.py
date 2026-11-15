import pytest

from ws.reviewpaths import CATEGORIES, DEFAULT_RULES, category_for


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("app/alembic/versions/0003_lote.py", "migration"),
        ("tests/test_lote.py", "test"),
        ("src/app/lote/lote.component.spec.ts", "test"),
        ("app/api/routes/lote.py", "contract"),
        ("app/schemas/lote.py", "contract"),
        ("app/models/lote.py", "model"),
        ("Dockerfile", "config"),
        (".github/workflows/ci.yml", "config"),
        ("app/core/settings.py", "config"),
        ("src/app/lote/lote.component.ts", "front"),
        ("app/services/lote.py", "other"),
        ("README.md", "other"),
    ],
)
def test_category_defaults(path, expected):
    assert category_for(path) == expected


def test_category_test_wins_over_migration():
    assert category_for("tests/alembic/versions/test_x.py") == "test"


def test_category_override_wins_over_defaults():
    overrides = {"front": ("src/app/models/**",)}

    assert category_for("src/app/models/lote.ts", overrides) == "front"
    assert category_for("src/app/models/lote.ts") == "model"


def test_default_rules_follow_the_categories():
    assert tuple(name for name, _ in DEFAULT_RULES) == CATEGORIES[:-1]
