import contextlib
import datetime
import json
from collections.abc import Iterable
from decimal import Decimal
from typing import Any, Callable, Union

from django.utils.dateparse import parse_date, parse_datetime, parse_time
from openpyxl.cell import Cell
from openpyxl.styles.numbers import (
    FORMAT_DATE_DATETIME,
    FORMAT_DATE_TIME4,
    FORMAT_DATE_YYYYMMDD2,
    FORMAT_NUMBER,
    FORMAT_NUMBER_00,
)
from openpyxl.worksheet.worksheet import Worksheet
from rest_framework import ISO_8601
from rest_framework.fields import (
    DateField,
    DateTimeField,
    DecimalField,
    Field,
    FloatField,
    IntegerField,
    TimeField,
)
from rest_framework.settings import api_settings as drf_settings

from drf_excel.utilities import XLSXStyle, get_setting, sanitize_value, set_cell_style


class XLSXField:
    sanitize = True

    def __init__(
        self,
        key: str,
        value: Any,
        field: Field,
        style: XLSXStyle,
        mapping: Union[str, Callable],
        cell_style: XLSXStyle,
    ):
        self.key = key
        self.original_value = value
        self.drf_field = field
        self.style = style
        self.mapping = mapping
        self.cell_style = cell_style
        self.value = self.init_value(value)

    def init_value(self, value):
        return value

    def custom_mapping(self):
        if type(self.mapping) is str:
            return self.value.get(self.mapping)
        if callable(self.mapping):
            return self.mapping(self.value)
        return self.value

    def prep_value(self) -> Any:
        return self.value

    def prep_cell(self, cell: Cell):
        set_cell_style(cell, self.style)

    def cell(self, ws: Worksheet, row, column) -> Cell:
        # If we have a custom mapping use it and done. If not prep value for output
        value = self.custom_mapping() if self.mapping else self.prep_value()
        if self.sanitize:
            value = sanitize_value(value)
        cell: Cell = ws.cell(row, column, value)
        self.prep_cell(cell)
        # Provided cell style always has priority
        if self.cell_style:
            set_cell_style(cell, self.cell_style)
        return cell


class XLSXNumberField(XLSXField):
    sanitize = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def init_value(self, value):
        with contextlib.suppress(Exception):
            if isinstance(self.drf_field, IntegerField) and type(value) is not int:
                return int(value)
            if isinstance(self.drf_field, FloatField) and type(value) is not float:
                return float(value)
            if (
                isinstance(self.drf_field, DecimalField) and type(value) is not Decimal
            ):
                return Decimal(value)

        return value

    def prep_cell(self, cell: Cell):
        super().prep_cell(cell)
        if isinstance(self.drf_field, IntegerField):
            cell.number_format = get_setting("INTEGER_FORMAT") or FORMAT_NUMBER
        else:
            cell.number_format = get_setting("DECIMAL_FORMAT") or FORMAT_NUMBER_00


class XLSXDateField(XLSXField):
    sanitize = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _parse_date(self, value, setting_format, iso_parse_func):
        # Parse format is Field format if provided.
        drf_format = getattr(self.drf_field, "format", None)
        # Otherwise, use DRF output format: DATETIME_FORMAT, DATE_FORMAT or TIME_FORMAT
        parse_format = drf_format or getattr(drf_settings, setting_format)
        if parse_format.lower() == ISO_8601:
            return iso_parse_func(value)
        parsed_datetime = datetime.datetime.strptime(value, parse_format)
        if isinstance(self.drf_field, TimeField):
            return parsed_datetime.time()
        if isinstance(self.drf_field, DateField):
            return parsed_datetime.date()
        return parsed_datetime

    def init_value(self, value):
        # Set tzinfo to None on datetime and time types since timezones are not supported in Excel
        try:
            if (
                isinstance(self.drf_field, DateTimeField)
                and type(value) is not datetime.datetime
            ):
                return self._parse_date(
                    value, "DATETIME_FORMAT", parse_datetime
                ).replace(tzinfo=None)
            if (
                isinstance(self.drf_field, DateField)
                and type(value) is not datetime.date
            ):
                return self._parse_date(value, "DATE_FORMAT", parse_date)
            if (
                isinstance(self.drf_field, TimeField)
                and type(value) is not datetime.time
            ):
                return self._parse_date(value, "TIME_FORMAT", parse_time).replace(
                    tzinfo=None
                )
        except Exception:
            pass
        return value

    def prep_cell(self, cell: Cell):
        super().prep_cell(cell)
        if isinstance(self.drf_field, DateTimeField):
            cell.number_format = get_setting("DATETIME_FORMAT") or FORMAT_DATE_DATETIME
        elif isinstance(self.drf_field, DateField):
            cell.number_format = get_setting("DATE_FORMAT") or FORMAT_DATE_YYYYMMDD2
        elif isinstance(self.drf_field, TimeField):
            cell.number_format = get_setting("TIME_FORMAT") or FORMAT_DATE_TIME4


class XLSXListField(XLSXField):
    def __init__(self, list_sep, **kwargs):
        self.list_sep = list_sep or ", "
        super().__init__(**kwargs)

    def prep_value(self) -> Any:
        if self.value is None:
            return super().prep_value()
        if (
            len(self.value) > 0
            and isinstance(self.value[0], Iterable)
            and not isinstance(self.value[0], str)
        ):
            # array of array; write as json
            return json.dumps(self.value, ensure_ascii=False)
        # Flatten the array into a comma separated string to fit
        # in a single spreadsheet column
        return self.list_sep.join(map(str, self.value))


class XLSXBooleanField(XLSXField):
    sanitize = False

    def __init__(self, boolean_display: dict, **kwargs):
        self.boolean_display = boolean_display
        super().__init__(**kwargs)

    def prep_value(self) -> Any:
        boolean_display = self.boolean_display or get_setting("BOOLEAN_DISPLAY")
        if boolean_display:
            return str(boolean_display.get(self.value, self.value))
        return self.value
