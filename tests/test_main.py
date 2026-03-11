import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"


@pytest.fixture
def app():
    spec = importlib.util.spec_from_file_location("ip_addresses_main", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_menu_table_has_expected_rows(app):
    table = app.build_menu_table()

    assert str(table.title) == "IP Lookup Menu"
    assert len(table.rows) == 3


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "Да"),
        (False, "Нет"),
        (None, "Нет"),
    ],
)
def test_bool_to_ru(app, value, expected):
    assert app.bool_to_ru(value) == expected


def test_handle_choice_dispatches_manual(app, monkeypatch):
    called = []
    monkeypatch.setattr(app, "check_manual_ips", lambda: called.append("manual"))

    should_continue = app.handle_choice("1")

    assert should_continue is True
    assert called == ["manual"]


def test_handle_choice_exit_returns_false(app, monkeypatch):
    messages = []
    monkeypatch.setattr(
        app, "print_status", lambda message, level="info": messages.append((message, level))
    )

    should_continue = app.handle_choice("0")

    assert should_continue is False
    assert ("Выход из программы.", "info") in messages


def test_check_manual_ips_validates_and_processes(app, monkeypatch):
    monkeypatch.setattr(
        app.Prompt, "ask", lambda *args, **kwargs: "8.8.8.8, bad-ip, 1.1.1.1"
    )
    warnings = []
    monkeypatch.setattr(
        app, "print_status", lambda message, level="info": warnings.append((message, level))
    )

    fetched = []
    monkeypatch.setattr(
        app, "fetch_ip_data", lambda ip: fetched.append(ip) or {"status": "success", "query": ip}
    )

    processed_titles = []
    monkeypatch.setattr(
        app, "process_result", lambda data, title: processed_titles.append((data["query"], title))
    )

    app.check_manual_ips()

    assert fetched == ["8.8.8.8", "1.1.1.1"]
    assert processed_titles == [
        ("8.8.8.8", " 8.8.8.8 "),
        ("1.1.1.1", " 1.1.1.1 "),
    ]
    assert any("некорректный ip-адрес" in msg.lower() for msg, _ in warnings)


def test_process_result_success_calls_save_and_print(app, monkeypatch, tmp_path):
    data = {"status": "success", "query": "8.8.8.8"}
    fake_map = tmp_path / "map.png"

    monkeypatch.setattr(app, "save_map_image", lambda payload: fake_map)
    captured = {}
    monkeypatch.setattr(
        app,
        "print_result",
        lambda payload, title, map_path=None: captured.update(
            {"payload": payload, "title": title, "map_path": map_path}
        ),
    )
    statuses = []
    monkeypatch.setattr(
        app, "print_status", lambda message, level="info": statuses.append((message, level))
    )

    app.process_result(data, title=" 8.8.8.8 ")

    assert captured["payload"] == data
    assert captured["title"] == " 8.8.8.8 "
    assert captured["map_path"] == fake_map
    assert any(level == "success" for _, level in statuses)


def test_save_map_image_writes_png(app, monkeypatch, tmp_path):
    class FakeResponse:
        headers = {"Content-Type": "image/png"}
        content = b"png-bytes"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(app.requests, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(app, "MAPS_DIR", tmp_path)

    map_path = app.save_map_image({"lat": 55.75, "lon": 37.61, "query": "8.8.8.8"})

    assert map_path is not None
    assert map_path.exists()
    assert map_path.read_bytes() == b"png-bytes"
