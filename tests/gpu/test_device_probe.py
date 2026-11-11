import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import pytest

from pdomain_ops.gpu import device_probe
from pdomain_ops.gpu.device_probe import DeviceInfoEntry, list_devices

_ONE_MIB = 1024 * 1024
_CARD_BYTES = 8192 * _ONE_MIB
_OOM_MESSAGE = "CUDA error: out of memory\nSearch for `cudaErrorMemoryAllocation' ..."


def _raise_oom(*_args: object) -> NoReturn:
    raise RuntimeError(_OOM_MESSAGE)


def _install_fake_torch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    mem_get_info: Callable[[int], tuple[int, int]] = lambda _i: (_CARD_BYTES, _CARD_BYTES),
    get_device_name: Callable[[int], str] = lambda _i: "Fake GPU",
    is_available: Callable[[], bool] = lambda: True,
    device_count: int = 1,
) -> None:
    cuda = SimpleNamespace(
        is_available=is_available,
        device_count=lambda: device_count,
        mem_get_info=mem_get_info,
        get_device_name=get_device_name,
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))


def test_probe_reports_device_when_memory_query_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=_raise_oom)

    [device] = device_probe._probe_cuda()

    assert device.id == "cuda:0"
    assert device.label == "Fake GPU"
    assert device.kind == "cuda"
    assert device.available is False
    assert device.vram_total_mb is None
    assert device.vram_free_mb is None
    assert device.reason == "CUDA memory query failed: CUDA error: out of memory"


def test_probe_reports_device_when_query_error_has_no_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_blank(*_args: object) -> NoReturn:
        raise RuntimeError

    _install_fake_torch(monkeypatch, mem_get_info=_raise_blank)

    [device] = device_probe._probe_cuda()

    assert device.available is False
    assert device.reason == "CUDA memory query failed: "


def test_probe_marks_card_with_no_free_memory_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=lambda _i: (0, _CARD_BYTES))

    [device] = device_probe._probe_cuda()

    assert device.available is False
    assert device.vram_free_mb == 0
    assert device.vram_total_mb == 8192
    assert device.reason == "No free GPU memory."


def test_probe_keeps_card_with_free_memory_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=lambda _i: (_ONE_MIB, _CARD_BYTES))

    [device] = device_probe._probe_cuda()

    assert device.available is True
    assert device.vram_free_mb == 1
    assert device.reason is None


def test_probe_returns_nothing_when_cuda_availability_check_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(monkeypatch, is_available=_raise_oom)

    assert device_probe._probe_cuda() == []


def test_unnamed_busy_card_is_listed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=_raise_oom, get_device_name=_raise_oom)
    monkeypatch.setattr(device_probe, "_probe_mps", list)
    monkeypatch.setattr(
        device_probe,
        "_detect_unusable_nvidia_hardware",
        lambda: ["NVIDIA GeForce RTX 5070 Ti"],
    )

    devices = list_devices()

    assert [d.id for d in devices] == ["cuda:0", "cpu"]
    assert devices[0].label == "NVIDIA GeForce RTX 5070 Ti"
    assert devices[0].available is False


def test_unnamed_busy_card_without_detected_hardware_gets_generic_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=_raise_oom, get_device_name=_raise_oom)
    monkeypatch.setattr(device_probe, "_detect_unusable_nvidia_hardware", list)

    [device] = device_probe._probe_cuda()

    assert device.label == "CUDA device 0"


def test_unnamed_busy_card_ignores_hardware_names_when_counts_differ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=_raise_oom, get_device_name=_raise_oom)
    monkeypatch.setattr(
        device_probe,
        "_detect_unusable_nvidia_hardware",
        lambda: ["NVIDIA GeForce RTX 3070", "NVIDIA GeForce RTX 5070 Ti"],
    )

    [device] = device_probe._probe_cuda()

    assert device.label == "CUDA device 0"


def _counting_hardware_scan(monkeypatch: pytest.MonkeyPatch, names: list[str]) -> list[int]:
    calls: list[int] = []

    def _scan() -> list[str]:
        calls.append(1)
        return list(names)

    monkeypatch.setattr(device_probe, "_detect_unusable_nvidia_hardware", _scan)
    return calls


def test_probe_scans_hardware_once_for_several_unnamed_busy_cards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(
        monkeypatch, mem_get_info=_raise_oom, get_device_name=_raise_oom, device_count=2
    )
    calls = _counting_hardware_scan(monkeypatch, ["NVIDIA RTX A", "NVIDIA RTX B"])

    devices = device_probe._probe_cuda()

    assert [d.label for d in devices] == ["NVIDIA RTX A", "NVIDIA RTX B"]
    assert len(calls) == 1


def test_list_devices_scans_hardware_once_when_name_and_memory_queries_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(
        monkeypatch, mem_get_info=_raise_oom, get_device_name=_raise_oom, device_count=2
    )
    monkeypatch.setattr(device_probe, "_probe_mps", list)
    calls = _counting_hardware_scan(monkeypatch, ["NVIDIA RTX A", "NVIDIA RTX B"])

    devices = list_devices()

    assert [d.id for d in devices] == ["cuda:0", "cuda:1", "cpu"]
    assert len(calls) == 1


def test_list_devices_skips_label_scan_when_names_are_known(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_torch(monkeypatch, mem_get_info=_raise_oom, device_count=2)
    monkeypatch.setattr(device_probe, "_probe_mps", list)
    calls = _counting_hardware_scan(monkeypatch, ["Fake GPU"])

    devices = list_devices()

    assert [d.id for d in devices] == ["cuda:0", "cuda:1", "cpu"]
    assert len(calls) == 1


def test_list_devices_always_includes_cpu():
    devices = list_devices()
    assert any(d.id == "cpu" for d in devices)
    cpu = next(d for d in devices if d.id == "cpu")
    assert cpu.label.lower().startswith("cpu")
    assert cpu.vram_total_mb is None


def test_cuda_entries_have_vram(monkeypatch):
    monkeypatch.setattr(
        "pdomain_ops.gpu.device_probe._probe_cuda",
        lambda _hardware: [
            DeviceInfoEntry(id="cuda:0", label="Fake GPU", vram_total_mb=8192, vram_free_mb=4096)
        ],
    )
    ids = [d.id for d in list_devices()]
    assert "cuda:0" in ids
    assert "cpu" in ids


def test_mps_included_when_available(monkeypatch):
    monkeypatch.setattr(
        "pdomain_ops.gpu.device_probe._probe_mps",
        lambda: [DeviceInfoEntry(id="mps", label="Apple MPS")],
    )
    ids = [d.id for d in list_devices()]
    assert "mps" in ids
    assert "cpu" in ids


def test_mps_not_included_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        "pdomain_ops.gpu.device_probe._probe_mps",
        list,
    )
    ids = [d.id for d in list_devices()]
    assert "mps" not in ids
    assert "cpu" in ids


def test_detect_nvidia_hardware_from_lspci_when_torch_cuda_unavailable(monkeypatch) -> None:
    """NVIDIA hardware presence is separate from CUDA runtime usability."""

    monkeypatch.setattr(device_probe, "_probe_cuda", lambda _hardware: [])
    monkeypatch.setattr(device_probe, "_probe_mps", list)
    monkeypatch.setattr(device_probe, "_nvidia_smi_names", list)
    monkeypatch.setattr(device_probe, "_proc_nvidia_names", list)
    monkeypatch.setattr(
        device_probe,
        "_lspci_nvidia_names",
        lambda: ["NVIDIA Corporation GA104 [GeForce RTX 3070]"],
    )

    devices = device_probe.list_devices()

    assert devices[0].id == "nvidia:0"
    assert devices[0].label == "NVIDIA Corporation GA104 [GeForce RTX 3070]"
    assert devices[0].available is False
    assert devices[0].kind == "nvidia"
    assert devices[0].reason == "NVIDIA GPU detected, but CUDA is not usable by PyTorch."
    assert devices[-1].id == "cpu"
    assert devices[-1].available is True


def test_detect_nvidia_hardware_deduplicates_against_cuda_devices(monkeypatch) -> None:
    """When CUDA is usable, do not show a second unavailable NVIDIA row."""

    monkeypatch.setattr(
        device_probe,
        "_probe_cuda",
        lambda _hardware: [
            device_probe.DeviceInfoEntry(
                id="cuda:0",
                label="NVIDIA GeForce RTX 3070",
                vram_total_mb=8192,
                vram_free_mb=4096,
                available=True,
                kind="cuda",
            )
        ],
    )
    monkeypatch.setattr(device_probe, "_probe_mps", list)
    monkeypatch.setattr(
        device_probe,
        "_detect_unusable_nvidia_hardware",
        lambda: ["NVIDIA GeForce RTX 3070"],
    )

    devices = device_probe.list_devices()

    assert [device.id for device in devices] == ["cuda:0", "cpu"]


def test_proc_nvidia_names_reads_information_files(tmp_path: Path, monkeypatch) -> None:
    gpu_dir = tmp_path / "gpus" / "0000:01:00.0"
    gpu_dir.mkdir(parents=True)
    (gpu_dir / "information").write_text(
        "Model: NVIDIA GeForce RTX 3070\nIRQ: 16\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(device_probe, "_PROC_NVIDIA_GPUS", tmp_path / "gpus")

    assert device_probe._proc_nvidia_names() == ["NVIDIA GeForce RTX 3070"]


def test_lspci_nvidia_names_parses_class_code_before_model(monkeypatch) -> None:
    monkeypatch.setattr(device_probe.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        device_probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "01:00.0 VGA compatible controller [0300]: "
                "NVIDIA Corporation GA104 [GeForce RTX 3070] [10de:2484]\n"
            ),
        ),
    )

    assert device_probe._lspci_nvidia_names() == [
        "NVIDIA Corporation GA104 [GeForce RTX 3070]",
    ]
