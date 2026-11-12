"""Device probe helper - lists available compute targets with VRAM info."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)
_PROC_NVIDIA_GPUS = Path("/proc/driver/nvidia/gpus")
_NVIDIA_UNUSABLE_REASON = "NVIDIA GPU detected, but CUDA is not usable by PyTorch."
_LSPCI_CONTROLLER_RE = re.compile(
    r"(?:VGA compatible controller|3D controller)(?:\s+\[[0-9a-fA-F]{4}\])?:\s*(.+)"
)
_PCI_ID_RE = re.compile(r"\s+\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]")
_REV_RE = re.compile(r"\s+\(rev [^)]+\)$")


@dataclass(frozen=True)
class DeviceInfoEntry:
    """A single compute target or detected-but-unusable hardware device."""

    id: str
    label: str
    vram_total_mb: int | None = None
    vram_free_mb: int | None = None
    available: bool = True
    kind: str = "cpu"
    reason: str | None = None


class _HardwareScan:
    """Runs the NVIDIA hardware scan at most once, on first use."""

    def __init__(self) -> None:
        self._names: list[str] | None = None

    def names(self) -> list[str]:
        if self._names is None:
            self._names = _detect_unusable_nvidia_hardware()
        return self._names


def _cuda_device_label(
    torch_module: Any, index: int, device_count: int, hardware: _HardwareScan
) -> str:
    try:
        return str(torch_module.cuda.get_device_name(index))
    except RuntimeError:
        # A name from the hardware scan keeps list_devices from adding this card
        # a second time as an unusable NVIDIA device. Scan order only lines up
        # with CUDA indices when both see the same set of cards.
        hardware_names = hardware.names()
        if len(hardware_names) == device_count:
            return hardware_names[index]
        return f"CUDA device {index}"


def _probe_cuda_device(
    torch_module: Any, index: int, device_count: int, hardware: _HardwareScan
) -> DeviceInfoEntry:
    try:
        free, total = torch_module.cuda.mem_get_info(index)
    except RuntimeError as exc:
        first_line = str(exc).partition("\n")[0]
        return DeviceInfoEntry(
            id=f"cuda:{index}",
            label=_cuda_device_label(torch_module, index, device_count, hardware),
            available=False,
            kind="cuda",
            reason=f"CUDA memory query failed: {first_line}",
        )
    free_mb = free // (1024 * 1024)
    has_free_memory = free_mb > 0
    return DeviceInfoEntry(
        id=f"cuda:{index}",
        label=_cuda_device_label(torch_module, index, device_count, hardware),
        vram_total_mb=total // (1024 * 1024),
        vram_free_mb=free_mb,
        available=has_free_memory,
        kind="cuda",
        reason=None if has_free_memory else "No free GPU memory.",
    )


def _probe_cuda(hardware: _HardwareScan | None = None) -> list[DeviceInfoEntry]:
    try:
        import torch
    except ImportError:
        return []
    try:
        if not torch.cuda.is_available():
            return []
        device_count = torch.cuda.device_count()
    except RuntimeError:
        _log.warning("CUDA availability check failed", exc_info=True)
        return []
    scan = hardware if hardware is not None else _HardwareScan()
    return [_probe_cuda_device(torch, index, device_count, scan) for index in range(device_count)]


def _probe_mps() -> list[DeviceInfoEntry]:
    try:
        import torch
    except ImportError:
        return []
    if not torch.backends.mps.is_available():
        return []
    return [DeviceInfoEntry(id="mps", label="Apple MPS", available=True, kind="mps")]


def _nvidia_smi_names() -> list[str]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return []
    try:
        result = subprocess.run(  # noqa: S603  # argv uses the resolved trusted nvidia-smi executable
            [executable, "--query-gpu=name", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _proc_nvidia_names() -> list[str]:
    if not _PROC_NVIDIA_GPUS.is_dir():
        return []
    names: list[str] = []
    for info_file in sorted(_PROC_NVIDIA_GPUS.glob("*/information")):
        try:
            lines = info_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if line.startswith("Model:"):
                name = line.split(":", 1)[1].strip()
                if name:
                    names.append(name)
    return names


def _lspci_nvidia_names() -> list[str]:
    executable = shutil.which("lspci")
    if executable is None:
        return []
    try:
        result = subprocess.run(  # noqa: S603  # argv uses the resolved trusted lspci executable
            [executable, "-nn"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        lowered = line.lower()
        if "nvidia" not in lowered or ("vga" not in lowered and "3d controller" not in lowered):
            continue
        match = _LSPCI_CONTROLLER_RE.search(line)
        if match is None:
            names.append("NVIDIA GPU")
            continue
        name = _REV_RE.sub("", _PCI_ID_RE.sub("", match.group(1))).strip()
        names.append(name or "NVIDIA GPU")
    return names


def _unique_names(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        key = " ".join(name.lower().split())
        if key and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _detect_unusable_nvidia_hardware() -> list[str]:
    return _unique_names([*_nvidia_smi_names(), *_proc_nvidia_names(), *_lspci_nvidia_names()])


def _name_match_key(name: str) -> str:
    product_match = re.search(
        r"\[([^\]]*(?:geforce|rtx|quadro|tesla|a\d+)[^\]]*)\]",
        name,
        re.IGNORECASE,
    )
    if product_match is not None:
        name = product_match.group(1)
    return re.sub(
        r"[^a-z0-9]+",
        "",
        name.lower().replace("nvidia corporation", "").replace("nvidia", ""),
    )


def _matches_cuda_device(name: str, cuda_devices: list[DeviceInfoEntry]) -> bool:
    name_key = _name_match_key(name)
    for device in cuda_devices:
        label_key = _name_match_key(device.label)
        if name_key and label_key and (name_key in label_key or label_key in name_key):
            return True
    return False


def list_devices() -> list[DeviceInfoEntry]:
    """Return available compute targets and detected unavailable hardware."""
    hardware = _HardwareScan()
    cuda_devices = _probe_cuda(hardware)
    mps_devices = _probe_mps()
    unavailable_nvidia = [
        DeviceInfoEntry(
            id=f"nvidia:{idx}",
            label=name,
            available=False,
            kind="nvidia",
            reason=_NVIDIA_UNUSABLE_REASON,
        )
        for idx, name in enumerate(hardware.names())
        if not _matches_cuda_device(name, cuda_devices)
    ]
    return [
        *cuda_devices,
        *mps_devices,
        *unavailable_nvidia,
        DeviceInfoEntry(id="cpu", label="CPU", available=True, kind="cpu"),
    ]
