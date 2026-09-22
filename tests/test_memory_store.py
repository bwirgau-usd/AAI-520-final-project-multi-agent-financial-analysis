import json

from src.memory import memory_store


def test_load_memory_returns_empty_list_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
    assert memory_store.load_memory("AAPL") == []


def test_save_memory_persists_entry_to_disk(tmp_path, monkeypatch):
    path = tmp_path / "memory.json"
    monkeypatch.setenv("MEMORY_PATH", str(path))

    memory_store.save_memory("aapl", "Revenue growth was overstated last run.", ["revenue"])

    assert path.exists()
    with path.open() as f:
        data = json.load(f)
    assert data["entries"]["AAPL"][0]["feedback"] == "Revenue growth was overstated last run."


def test_save_memory_appends_multiple_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))

    memory_store.save_memory("AAPL", "First note")
    memory_store.save_memory("AAPL", "Second note")

    entries = memory_store.load_memory("AAPL")
    assert len(entries) == 2
    assert entries[0]["feedback"] == "Second note"


def test_load_memory_is_isolated_per_symbol(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))

    memory_store.save_memory("AAPL", "Apple note")
    memory_store.save_memory("MSFT", "Microsoft note")

    assert len(memory_store.load_memory("AAPL")) == 1
    assert len(memory_store.load_memory("MSFT")) == 1
