import pytest

from ws.cli import main


def test_main_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


@pytest.mark.parametrize(
    "argv",
    [["gate"], ["gate", "catalog", "pass"], ["gate", "catalog", "ask", "server"]],
)
def test_gate_catalog_commands_need_their_arguments(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2


def test_gate_catalog_help_lists_pass_and_ask(capsys):
    with pytest.raises(SystemExit):
        main(["gate", "catalog", "--help"])
    out = capsys.readouterr().out
    assert "pass" in out and "ask" in out and "--json" in out
