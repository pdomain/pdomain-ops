import pytest

from pdomain_ops.suite.storage import LocalFsStorage, StorageAdapter


def test_protocol_methods_present():
    assert hasattr(StorageAdapter, "read")
    assert hasattr(StorageAdapter, "write")
    assert hasattr(StorageAdapter, "exists")
    assert hasattr(StorageAdapter, "delete")
    assert hasattr(StorageAdapter, "list_prefix")


def test_protocol_runtime_checkable():
    storage = LocalFsStorage(root="/tmp")
    assert isinstance(storage, StorageAdapter)


def test_local_fs_storage_round_trip(tmp_path):
    storage = LocalFsStorage(root=tmp_path)
    storage.write("test.json", b'{"key": "value"}')
    assert storage.exists("test.json")
    data = storage.read("test.json")
    assert data == b'{"key": "value"}'
    storage.delete("test.json")
    assert not storage.exists("test.json")
    files = storage.list_prefix("")
    assert "test.json" not in files


def test_local_fs_storage_rejects_absolute_paths(tmp_path):
    storage = LocalFsStorage(root=tmp_path)
    with pytest.raises(ValueError):
        storage.write("/etc/passwd", b"x")


def test_local_fs_storage_rejects_traversal(tmp_path):
    storage = LocalFsStorage(root=tmp_path)
    with pytest.raises(ValueError):
        storage.write("../outside", b"x")


def test_local_fs_storage_creates_intermediate_dirs(tmp_path):
    storage = LocalFsStorage(root=tmp_path)
    storage.write("a/b/c.json", b"data")
    assert (tmp_path / "a" / "b" / "c.json").exists()


def test_local_fs_storage_rejects_sibling_with_shared_prefix(tmp_path):
    """`root/../storex` shares the prefix "store" with `root`; a plain
    string-prefix check let it through."""
    root = tmp_path / "store"
    (tmp_path / "storex").mkdir()
    s = LocalFsStorage(root=root)
    with pytest.raises(ValueError, match="traversal"):
        s.write("../storex/escaped.txt", b"x")
    assert not (tmp_path / "storex" / "escaped.txt").exists()


@pytest.mark.parametrize("key", [r"C:\Windows\x.txt", "C:/Windows/x.txt", r"\\server\share\x.txt"])
def test_local_fs_storage_rejects_windows_absolute_keys(tmp_path, key):
    s = LocalFsStorage(root=tmp_path)
    with pytest.raises(ValueError, match="relative"):
        s.write(key, b"x")


def test_local_fs_storage_list_prefix_returns_posix_keys(tmp_path):
    """Keys are portable: list_prefix must return "a/b.txt", not "a\\b.txt"
    on Windows."""
    s = LocalFsStorage(root=tmp_path)
    s.write("a/b.txt", b"x")
    assert s.list_prefix("a") == ["a/b.txt"]
