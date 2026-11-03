"""Opt-in isolated-process RSS comparison for XLSX exporters.

Run with:
    DRF_EXCEL_RUN_MEMORY_BENCHMARK=1 pytest -s tests/test_streaming_benchmark.py

Each measurement runs in a fresh forked process. This prevents allocations
retained by one exporter from contaminating the next exporter's measurement.
"""

import gc
import multiprocessing
import os
import time
from statistics import median

import psutil
import pytest

from tests.testapp.models import ExampleModel

pytestmark = pytest.mark.django_db(transaction=True)

RUN_BENCHMARK = os.getenv("DRF_EXCEL_RUN_MEMORY_BENCHMARK") == "1"
RECORD_COUNT = int(os.getenv("DRF_EXCEL_BENCHMARK_ROWS", "20000"))
REPETITIONS = int(os.getenv("DRF_EXCEL_BENCHMARK_REPETITIONS", "5"))
SAMPLE_INTERVAL = 0.002


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


def _isolated_export_worker(send_conn, path):
    """Run one export in a child process and report its baseline and output."""
    import psutil
    from django.db import connections
    from rest_framework.test import APIClient

    # A fork inherits the parent's connection state; never reuse it.
    connections.close_all()
    gc.collect()
    process = psutil.Process(os.getpid())
    baseline_rss = process.memory_info().rss
    send_conn.send(("ready", baseline_rss))

    try:
        byte_count = _consume_response(APIClient(), path)
        send_conn.send(("result", byte_count))
    except BaseException as exc:
        send_conn.send(("error", repr(exc)))
        raise
    finally:
        connections.close_all()
        send_conn.close()


def _measure_isolated_peak_rss(path):
    """Return (peak RSS, baseline RSS, output bytes) from a fresh process."""
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("The isolated RSS benchmark currently requires fork support.")

    context = multiprocessing.get_context("fork")
    recv_conn, send_conn = context.Pipe(duplex=False)
    worker = context.Process(target=_isolated_export_worker, args=(send_conn, path))
    worker.start()
    send_conn.close()

    try:
        if not recv_conn.poll(30):
            worker.terminate()
            worker.join()
            pytest.fail(f"Benchmark worker did not initialize for {path}")

        status, baseline_rss = recv_conn.recv()
        if status != "ready":
            pytest.fail(f"Unexpected benchmark worker message: {status}")

        process = psutil.Process(worker.pid)
        peak_rss = baseline_rss
        result = None

        while worker.is_alive():
            try:
                peak_rss = max(peak_rss, process.memory_info().rss)
            except psutil.NoSuchProcess:
                break

            if recv_conn.poll():
                message = recv_conn.recv()
                if message[0] == "result":
                    result = message[1]
                    # Keep sampling until the worker exits.
                elif message[0] == "error":
                    pytest.fail(f"Benchmark worker failed for {path}: {message[1]}")
            time.sleep(SAMPLE_INTERVAL)

        worker.join()
        if result is None and recv_conn.poll():
            message = recv_conn.recv()
            if message[0] == "result":
                result = message[1]
            elif message[0] == "error":
                pytest.fail(f"Benchmark worker failed for {path}: {message[1]}")

        if worker.exitcode != 0:
            pytest.fail(f"Benchmark worker exited with code {worker.exitcode}")
        if result is None:
            pytest.fail(f"Benchmark worker returned no result for {path}")

        return peak_rss, baseline_rss, result
    finally:
        recv_conn.close()
        if worker.is_alive():
            worker.terminate()
            worker.join()


@pytest.mark.skipif(
    not RUN_BENCHMARK,
    reason="Set DRF_EXCEL_RUN_MEMORY_BENCHMARK=1 to run the opt-in RSS benchmark.",
)
def test_compare_regular_and_streaming_export_peak_rss():
    """Compare both endpoints against the same committed queryset."""
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

    endpoints = {
        "regular": "/examples/?format=xlsx",
        "streaming": "/examples/export-xlsx/",
    }
    results = {name: [] for name in endpoints}

    # Every sample gets a new worker process. Alternate order to reduce
    # systematic effects from database/cache state across repetitions.
    for repetition in range(REPETITIONS):
        order = (
            ("regular", "streaming")
            if repetition % 2 == 0
            else ("streaming", "regular")
        )
        for name in order:
            results[name].append(_measure_isolated_peak_rss(endpoints[name]))

    print("\nIsolated-process Peak RSS comparison")
    print(f"Records: {RECORD_COUNT:,}; repetitions: {REPETITIONS}")
    for name in endpoints:
        peak = median(sample[0] for sample in results[name])
        baseline = median(sample[1] for sample in results[name])
        growth = median(sample[0] - sample[1] for sample in results[name])
        output_size = median(sample[2] for sample in results[name])
        print(f"{name.title()} peak RSS: {peak / (1024 * 1024):.2f} MiB")
        print(f"{name.title()} baseline RSS: {baseline / (1024 * 1024):.2f} MiB")
        print(f"{name.title()} peak RSS increase: {growth / (1024 * 1024):.2f} MiB")
        print(f"{name.title()} XLSX output size: {output_size / (1024 * 1024):.2f} MiB")

    regular_growth = median(sample[0] - sample[1] for sample in results["regular"])
    streaming_growth = median(sample[0] - sample[1] for sample in results["streaming"])
    if regular_growth > 0:
        reduction = (regular_growth - streaming_growth) / regular_growth * 100
        print(f"Peak RSS increase reduction: {reduction:.1f}%")

    # No performance threshold assertion: RSS is environment-dependent.
