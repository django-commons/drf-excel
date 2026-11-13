import io
from collections.abc import Callable

from django.http import HttpResponseBase

import pytest
from openpyxl.reader.excel import load_workbook
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet


@pytest.fixture
def workbook() -> Workbook:
    return Workbook()


@pytest.fixture
def worksheet(workbook: Workbook) -> Worksheet:
    return Worksheet(workbook)


@pytest.fixture
def workbook_reader() -> Callable[[bytes | str | HttpResponseBase, bool], Workbook]:
    def reader_func(
        buffer: bytes | str | HttpResponseBase,
        read_only: bool = True,
    ) -> Workbook:
        if isinstance(buffer, HttpResponseBase):
            if buffer.streaming:
                buffer = b"".join(buffer.streaming_content)
            else:
                buffer = buffer.content

        io_buffer = io.BytesIO(buffer)
        return load_workbook(io_buffer, read_only=read_only)

    return reader_func
