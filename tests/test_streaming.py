import gc
import os

import psutil
import pytest
from rest_framework.test import APIClient

from tests.testapp.models import ExampleModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def read_streaming_response(response):
    """Consume the response so the XLSX workbook can be inspected."""
    return b"".join(response.streaming_content)


def measure_peak_rss(api_client):
    """
    Measure the process RSS increase while consuming
    the streaming XLSX response.
    """
    process = psutil.Process(os.getpid())

    gc.collect()
    baseline = process.memory_info().rss
    peak = baseline

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert response.streaming is True

    try:
        for _chunk in response.streaming_content:
            current = process.memory_info().rss
            peak = max(peak, current)
    finally:
        response.close()

    return max(0, peak - baseline)


def test_streaming_export_returns_all_queryset_records(
    api_client,
    workbook_reader,
):
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title="First",
                description="First description",
            ),
            ExampleModel(
                title="Second",
                description="Second description",
            ),
            ExampleModel(
                title="Third",
                description="Third description",
            ),
        ]
    )

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert response.streaming is True

    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    assert "my_export.xlsx" in response["Content-Disposition"]

    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=True,
    )

    rows = list(workbook.worksheets[0].values)

    assert rows == [
        ("title", "description"),
        ("First", "First description"),
        ("Second", "Second description"),
        ("Third", "Third description"),
    ]


def test_streaming_export_handles_empty_queryset(
    api_client,
    workbook_reader,
):
    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200
    assert response.streaming is True

    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=True,
    )

    rows = list(workbook.worksheets[0].values)

    assert rows == [
        ("title", "description"),
    ]


def test_streaming_export_uses_queryset_iterator(
    api_client,
    monkeypatch,
):
    from django.db.models.query import QuerySet

    original_iterator = QuerySet.iterator
    iterator_calls = []

    def tracked_iterator(queryset, *args, **kwargs):
        if queryset.model is ExampleModel:
            iterator_calls.append(kwargs.get("chunk_size"))

        return original_iterator(queryset, *args, **kwargs)

    monkeypatch.setattr(
        QuerySet,
        "iterator",
        tracked_iterator,
    )

    ExampleModel.objects.create(
        title="Iterator test",
        description="Checking iterator usage",
    )

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200

    for _chunk in response.streaming_content:
        pass

    assert iterator_calls == [2000]


def test_streaming_export_handles_many_records(
    api_client,
    workbook_reader,
):
    record_count = 1500

    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(record_count)
        ]
    )

    response = api_client.get("/examples/export-xlsx/")

    assert response.status_code == 200

    workbook = workbook_reader(
        read_streaming_response(response),
        read_only=True,
    )

    rows = workbook.worksheets[0].iter_rows(values_only=True)

    assert next(rows) == ("title", "description")

    exported_rows = list(rows)

    assert len(exported_rows) == record_count
    assert exported_rows[0] == (
        "Record 0",
        "Description 0",
    )
    assert exported_rows[-1] == (
        f"Record {record_count - 1}",
        f"Description {record_count - 1}",
    )


def test_streaming_export_memory_growth(api_client):
    import tracemalloc

    def measure_peak_memory():
        gc.collect()
        tracemalloc.start()

        try:
            response = api_client.get("/examples/export-xlsx/")
            assert response.status_code == 200

            for _chunk in response.streaming_content:
                pass

            _, peak = tracemalloc.get_traced_memory()
            response.close()

            return peak
        finally:
            tracemalloc.stop()

    # Warm-up
    ExampleModel.objects.create(
        title="Warmup",
        description="Warmup",
    )
    measure_peak_memory()
    ExampleModel.objects.all().delete()

    # Small dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(500)
        ]
    )

    small_peak = measure_peak_memory()
    ExampleModel.objects.all().delete()

    # Large dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(20000)
        ]
    )

    large_peak = measure_peak_memory()

    growth_mb = (large_peak - small_peak) / (1024 * 1024)

    print(f"\n500 records peak: {small_peak / 1024 / 1024:.2f} MB")
    print(f"20000 records peak: {large_peak / 1024 / 1024:.2f} MB")
    print(f"Memory growth: {growth_mb:.2f} MB")

    assert growth_mb < 14, (
        f"Memory grew by {growth_mb:.2f} MB "
        "when increasing records from 500 to 20000."
    )


def test_streaming_export_rss_memory_growth(api_client):
    # Warm-up
    ExampleModel.objects.create(
        title="Warmup",
        description="Warmup",
    )

    measure_peak_rss(api_client)
    ExampleModel.objects.all().delete()

    # Small dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(500)
        ]
    )

    small_peak = measure_peak_rss(api_client)
    ExampleModel.objects.all().delete()
    gc.collect()

    # Large dataset
    ExampleModel.objects.bulk_create(
        [
            ExampleModel(
                title=f"Record {index}",
                description=f"Description {index}",
            )
            for index in range(20000)
        ]
    )

    large_peak = measure_peak_rss(api_client)

    small_mb = small_peak / (1024 * 1024)
    large_mb = large_peak / (1024 * 1024)
    growth_mb = (large_peak - small_peak) / (1024 * 1024)

    print("\n========== RSS MEMORY RESULTS ==========")
    print(f"500 records:    {small_mb:.2f} MB")
    print(f"20,000 records: {large_mb:.2f} MB")
    print(f"Difference:     {growth_mb:.2f} MB")
    print("========================================")
