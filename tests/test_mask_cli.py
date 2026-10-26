import io

from ws.cli import main


def test_mask_reads_stdin_and_writes_stdout(ws_config, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("Acme Capital and acme\n"))
    assert main(["mask"]) == 0
    assert capsys.readouterr().out == "Summit Partners and apex\n"


def test_mask_dash_means_stdin(ws_config, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("ACME"))
    assert main(["mask", "-"]) == 0
    assert capsys.readouterr().out == "APEX"


def test_mask_file_goes_to_stdout_and_leaves_the_file(ws_config, tmp_path, capsys):
    note = tmp_path / "note.md"
    note.write_text("Acme\n", encoding="utf-8")
    assert main(["mask", str(note)]) == 0
    assert capsys.readouterr().out == "Apex\n"
    assert note.read_text(encoding="utf-8") == "Acme\n"


def test_mask_in_place_rewrites_the_file(ws_config, tmp_path, capsys):
    note = tmp_path / "note.md"
    note.write_bytes("Acme\r\nMéridia\r\n".encode())
    assert main(["mask", "--in-place", str(note)]) == 0
    assert note.read_bytes() == b"Apex\r\nMeridiana\r\n"
    assert capsys.readouterr().out == ""


def test_mask_in_place_needs_a_file(ws_config, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("Acme"))
    assert main(["mask", "--in-place"]) == 2
    assert "--in-place needs a file" in capsys.readouterr().err


def test_mask_check_exits_1_and_names_each_hit(ws_config, tmp_path, capsys):
    note = tmp_path / "note.md"
    note.write_text("Acme and Méridia and brilliant\n", encoding="utf-8")
    assert main(["mask", "--check", str(note)]) == 1
    assert capsys.readouterr().out == f"{note}: Acme\n{note}: Méridia\n"


def test_mask_check_exits_0_when_clean(ws_config, tmp_path, capsys):
    note = tmp_path / "note.md"
    note.write_text("Apex and Meridiana\n", encoding="utf-8")
    assert main(["mask", "--check", str(note)]) == 0
    assert capsys.readouterr().out == ""


def test_mask_check_reads_stdin(ws_config, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("Acme"))
    assert main(["mask", "--check"]) == 1
    assert capsys.readouterr().out == "-: Acme\n"


def test_mask_missing_table_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "empty"))
    monkeypatch.setattr("sys.stdin", io.StringIO("Acme"))
    assert main(["mask"]) == 2
    expected = f"names table not found at {tmp_path / 'empty' / 'names.toml'}"
    assert expected in capsys.readouterr().err


def test_mask_unreadable_file_exits_2(ws_config, tmp_path, capsys):
    assert main(["mask", str(tmp_path / "absent.md")]) == 2
    assert "cannot read" in capsys.readouterr().err
