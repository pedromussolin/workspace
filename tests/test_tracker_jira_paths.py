import ws.adf
import ws.jira
import ws.tracker.jira.adf
import ws.tracker.jira.client
import ws.tracker.jira.discover
import ws.tracker.jira_discover


def test_old_paths_are_the_moved_modules():
    assert ws.jira is ws.tracker.jira.client
    assert ws.adf is ws.tracker.jira.adf
    assert ws.tracker.jira_discover is ws.tracker.jira.discover


def test_patching_through_an_old_path_reaches_the_new_module(monkeypatch):
    monkeypatch.setattr("ws.adf.to_adf", lambda *a, **k: "patched")
    assert ws.tracker.jira.adf.to_adf() == "patched"
