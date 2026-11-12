"""Concurrent access to the shared DocTR predictor cache."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar
from unittest.mock import MagicMock

import pdomain_book_tools.hf as hf_module
import pdomain_book_tools.ocr.document as document_module
import pytest
from pdomain_book_tools.ocr import doctr_support

import pdomain_ops.gpu.default_stages as ds
from pdomain_ops.gpu import doctr_batch
from pdomain_ops.gpu.local_stage import LocalStageDispatcher
from pdomain_ops.gpu.types import OcrBatchRequest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_T = TypeVar("_T")

_OVERLAP_WAIT_SECONDS = 0.3
_THREAD_TIMEOUT_SECONDS = 10.0


class _OverlapDetectingBuilder:
    """Holds the first build open long enough for a racing second build to start."""

    def __init__(self) -> None:
        self.calls = 0
        self._calls_lock = threading.Lock()
        self._second_build_started = threading.Event()

    def __call__(self, *_args: object, **_kwargs: object) -> object:
        with self._calls_lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            self._second_build_started.wait(timeout=_OVERLAP_WAIT_SECONDS)
        else:
            self._second_build_started.set()
        return object()


def _run_together(*tasks: Callable[[], _T]) -> list[_T]:
    barrier = threading.Barrier(len(tasks))

    def _start_together(task: Callable[[], _T]) -> _T:
        barrier.wait(timeout=_THREAD_TIMEOUT_SECONDS)
        return task()

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = [pool.submit(_start_together, task) for task in tasks]
        return [future.result(timeout=_THREAD_TIMEOUT_SECONDS) for future in futures]


@pytest.fixture(autouse=True)
def _empty_predictor_cache() -> Iterator[None]:
    ds._predictor_cache.clear()
    yield
    ds._predictor_cache.clear()


def _patch_single_page_ocr(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    used_predictors: list[object] = []
    page = MagicMock()
    page.to_dict.return_value = {"words": []}
    document = MagicMock()
    document.pages = [page]

    def _fake_ocr(*_args: object, predictor: object = None, **_kwargs: object) -> object:
        used_predictors.append(predictor)
        return (document, 0)

    monkeypatch.setattr(document_module.Document, "from_image_ocr_via_doctr", _fake_ocr)
    return used_predictors


def _sync_ocr_task(*, det_bs: int = 2) -> Callable[[], object]:
    return ds._make_doctr_finetuned_sync(
        image_path="/fake/image.png",
        page_id="page-1",
        det_path="/fake/det.pt",
        reco_path="/fake/reco.pt",
        det_bs=det_bs,
    )


def test_single_page_stage_builds_one_predictor_for_racing_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = _OverlapDetectingBuilder()
    monkeypatch.setattr(doctr_support, "get_finetuned_torch_doctr_predictor", builder)
    used_predictors = _patch_single_page_ocr(monkeypatch)

    _run_together(_sync_ocr_task(), _sync_ocr_task())

    assert builder.calls == 1
    assert len(used_predictors) == 2
    assert used_predictors[0] is used_predictors[1]


def test_batch_dispatch_builds_one_predictor_for_racing_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = _OverlapDetectingBuilder()
    used_predictors: list[object] = []

    def _fake_batch(*_args: object, predictor: object = None, **_kwargs: object) -> list[object]:
        used_predictors.append(predictor)
        return []

    monkeypatch.setattr(doctr_support, "get_finetuned_torch_doctr_predictor", builder)
    monkeypatch.setattr(
        hf_module,
        "resolve_ocr_models",
        lambda: (Path("/fake/det.pt"), Path("/fake/reco.pt")),
    )
    monkeypatch.setattr(doctr_batch, "run_doctr_batch", _fake_batch)

    def _dispatch() -> list[dict[str, object]]:
        request = OcrBatchRequest(images=[b"page"], source_identifiers=["page-1"], device="cpu")
        return asyncio.run(LocalStageDispatcher().run_ocr_batch(request))

    _run_together(_dispatch, _dispatch)

    assert builder.calls == 1
    assert len(used_predictors) == 2
    assert used_predictors[0] is used_predictors[1]


@pytest.mark.asyncio
async def test_batch_dispatch_builds_predictor_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_threads: list[int] = []

    def _build(*_args: object, **_kwargs: object) -> object:
        build_threads.append(threading.get_ident())
        return object()

    monkeypatch.setattr(doctr_support, "get_finetuned_torch_doctr_predictor", _build)
    monkeypatch.setattr(
        hf_module,
        "resolve_ocr_models",
        lambda: (Path("/fake/det.pt"), Path("/fake/reco.pt")),
    )
    monkeypatch.setattr(doctr_batch, "run_doctr_batch", lambda *_args, **_kwargs: [])

    request = OcrBatchRequest(images=[b"page"], source_identifiers=["page-1"], device="cpu")
    await LocalStageDispatcher().run_ocr_batch(request)

    assert len(build_threads) == 1
    assert build_threads[0] != threading.get_ident()


def test_racing_builds_for_different_keys_are_both_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[object] = []

    def _build(*_args: object, **_kwargs: object) -> object:
        predictor = object()
        built.append(predictor)
        return predictor

    monkeypatch.setattr(doctr_support, "get_finetuned_torch_doctr_predictor", _build)
    _patch_single_page_ocr(monkeypatch)

    _run_together(_sync_ocr_task(det_bs=2), _sync_ocr_task(det_bs=4))

    assert len(ds._predictor_cache) == 2
    assert {id(predictor) for predictor in ds._predictor_cache.values()} == {
        id(predictor) for predictor in built
    }


def test_cache_stays_usable_during_an_ocr_run(monkeypatch: pytest.MonkeyPatch) -> None:
    other_key = ("/other/det.pt", "/other/reco.pt", 1, 128)
    other_predictor = object()
    predictor_built_during_ocr: list[object] = []
    monkeypatch.setattr(
        doctr_support,
        "get_finetuned_torch_doctr_predictor",
        lambda *_args, **_kwargs: object(),
    )
    page = MagicMock()
    page.to_dict.return_value = {"words": []}
    document = MagicMock()
    document.pages = [page]

    def _ocr_that_builds_another_predictor(*_args: object, **_kwargs: object) -> object:
        worker = threading.Thread(
            target=lambda: predictor_built_during_ocr.append(
                ds.get_or_build_predictor(other_key, lambda: other_predictor)
            ),
            daemon=True,
        )
        worker.start()
        worker.join(timeout=_THREAD_TIMEOUT_SECONDS)
        return (document, 0)

    monkeypatch.setattr(
        document_module.Document,
        "from_image_ocr_via_doctr",
        _ocr_that_builds_another_predictor,
    )

    _sync_ocr_task()()

    assert predictor_built_during_ocr == [other_predictor]


def test_failed_build_is_not_cached_and_can_be_retried() -> None:
    key = ("/fake/det.pt", "/fake/reco.pt", 2, 128)
    predictor = object()

    def _failing_build() -> object:
        raise RuntimeError("build failed")

    with pytest.raises(RuntimeError, match="build failed"):
        ds.get_or_build_predictor(key, _failing_build)

    assert ds.get_or_build_predictor(key, lambda: predictor) is predictor
