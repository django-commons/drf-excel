"""Opt-in RSS comparison for the regular and streaming XLSX exporters.

Run with:
    DRF_EXCEL_RUN_MEMORY_BENCHMARK=1 pytest -s tests/test_streaming_benchmark.py

The benchmark is intentionally excluded from the normal test suite because RSS
measurements are environment-dependent and should not make CI flaky.
"""

import gc
import os
import threading
from statistics import median

import psutil
import pytest
from rest_framework.test import APIClient

from tests.testapp.models import ExampleModel

pytestmark = pytest.mark.django_db

RUN_BENCHMARK = os.getenv("DRF_EXCEL_RUN_MEMORY_BENCHMARK") == "1"
RECORD_COUNT = int(os.getenv("DRF_EXCEL_BENCHMARK_ROWS", "20000"))
REPETITIONS = int(os.getenv("DRF_EXCEL_BENCHMARK_REPETITIONS", "3"))
SAMPLE_INTERVAL = 0.001


def _consume_response(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if response.streaming:
        byte_count = 0
        try:
            for chunk in response.streaming_content:
                byte_count += len(chunk)
        finally:
            response.close()
    else:
        byte_count = len(response.content)

    assert byte_count > 0
    return byte_count


def _measure_peak_rss(client, path):
    """Return the sampled RSS increase while requesting and consuming an XLSX."""
    process = psutil.Process(os.getpid())
    gc.collect()
    baseline = process.memory_info().rss
    peak = baseline
    finished = threading.Event()

    def sample_rss():
        nonlocal peak
        while not finished.is_set():
            try:
                peak = max(peak, process.memory_info().rss)
            except psutil.Error:
                return
            finished.wait(SAMPLE_INTERVAL)

    sampler = threading.Thread(target=sample_rss, daemon=True)
    sampler.start()

    try:
        byte_count = _consume_response(client, path)
    finally:
        finished.set()
        sampler.join()

    peak = max(peak, process.memory_info().rss)
    return max(0, peak - baseline), byte_count


@pytest.mark.skipif(
    not RUN_BENCHMARK,
    reason="Set DRF_EXCEL_RUN_MEMORY_BENCHMARK=1 to run the opt-in RSS benchmark.",
)
def test_compare_regular_and_streaming_export_peak_rss():
    """Compare both endpoints against the same persisted queryset."""
    if RECORD_COUNT < 1 or REPETITIONS < 1:
        pytest.fail("Benchmark rows and repetitions must both be positive.")

    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index} " * 8,
            )
            for index in range(RECORD_COUNT)
        ],
        batch_size=1000,
    )

    api_client = APIClient()
    endpoints = {
        "regular": "/examples/?format=xlsx",
        "streaming": "/examples/export-xlsx/",
    }

    # Warm up imports, serializers, database connections, and OpenPyXL.
    for path in endpoints.values():
        _consume_response(api_client, path)

    results = {name: [] for name in endpoints}

    for repetition in range(REPETITIONS):
        # Alternate order to reduce systematic bias from always running one
        # implementation first and retaining its allocations in the process.
        order = (
            ("regular", "streaming")
            if repetition % 2 == 0
            else ("streaming", "regular")
        )
        for name in order:
            gc.collect()
            peak_delta, byte_count = _measure_peak_rss(
                api_client,
                endpoints[name],
            )
            results[name].append((peak_delta, byte_count))

    regular_median = median(value[0] for value in results["regular"])
    streaming_median = median(value[0] for value in results["streaming"])

    print("\nPeak RSS comparison (sampled process RSS increase)")
    print(f"Records: {RECORD_COUNT:,}; repetitions: {REPETITIONS}")
    print(f"Regular renderer:  {regular_median / (1024 * 1024):.2f} MiB")
    print(f"Streaming exporter: {streaming_median / (1024 * 1024):.2f} MiB")

    if regular_median > 0:
        reduction = (regular_median - streaming_median) / regular_median * 100
        print(f"Sampled RSS reduction: {reduction:.1f}%")

    for name in endpoints:
        sizes = [value[1] for value in results[name]]
        print(
            f"{name} XLSX output size: "
            f"{median(sizes) / (1024 * 1024):.2f} MiB"
        )

    # Deliberately no memory-ratio assertion: RSS depends on allocator,
    # operating system, Python/OpenPyXL versions, and sampling timing.
