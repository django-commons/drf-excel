import json
from collections.abc import Iterable, MutableMapping
from tempfile import TemporaryFile

from django.utils.functional import Promise
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.views import SheetView
from openpyxl.writer.excel import save_workbook
from rest_framework.fields import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    Field,
    FloatField,
    IntegerField,
    ListField,
    TimeField,
)
from rest_framework.renderers import BaseRenderer
from rest_framework.serializers import Serializer

from drf_excel.fields import (
    XLSXBooleanField,
    XLSXDateField,
    XLSXField,
    XLSXListField,
    XLSXNumberField,
)
from drf_excel.utilities import XLSXStyle, get_attribute, set_cell_style


class XLSXRenderer(BaseRenderer):
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    format = "xlsx"
    combined_header_dict = {}
    fields_dict = {}
    specify_headers = None
    ignore_headers = []
    boolean_display = None
    column_data_styles = None
    custom_mappings = None
    custom_cols = None
    list_sep = ", "
    body_style = None
    sheet_view_options = {}
    hyperlink_getter = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""

        if not self._check_validation_data(data, renderer_context):
            return json.dumps(data)

        wb = Workbook()
        self.ws = wb.active

        results = data["results"] if "results" in data else data

        drf_view = renderer_context.get("view")
        self.hyperlink_getter = getattr(drf_view, "_get_cell_hyperlink", None)

        header = get_attribute(drf_view, "header", {})
        use_header = header and header.get("use_header", True)
        self.ws.title = header.get("tab_title", "Report")
        header_title = header.get("header_title", "Report")
        img_addr = header.get("img")
        if img_addr:
            img = Image(img_addr)
            self.ws.add_image(img, "A1")
        header_style = (
            XLSXStyle(header.get("style")) if header and "style" in header else None
        )

        column_header = get_attribute(drf_view, "column_header", {})
        column_header_style = (
            XLSXStyle(column_header.get("style"))
            if column_header and "style" in column_header
            else None
        )
        column_count = 0
        row_count = 1
        if use_header:
            row_count += 1
        column_titles = column_header.get("titles", [])

        auto_filter = get_attribute(drf_view, "xlsx_auto_filter", False)

        if len(results):
            use_labels = getattr(drf_view, "xlsx_use_labels", False)

            self.specify_headers = getattr(drf_view, "xlsx_specify_headers", None)
            self.ignore_headers = getattr(drf_view, "xlsx_ignore_headers", [])

            self.boolean_display = getattr(drf_view, "xlsx_boolean_labels", None)

            self.column_data_styles = get_attribute(
                drf_view, "column_data_styles", dict()
            )

            self.custom_cols = getattr(drf_view, "xlsx_custom_cols", dict())

            self.custom_mappings = getattr(drf_view, "xlsx_custom_mappings", dict())

            self.fields_dict = self._serializer_fields(drf_view.get_serializer())

            xlsx_header_dict = self._flatten_serializer_keys(
                drf_view.get_serializer(), use_labels=use_labels
            )
            if self.custom_cols:
                custom_header_dict = {
                    key: self.custom_cols[key].get("label", None) or key
                    for key in self.custom_cols.keys()
                }
                self.combined_header_dict = dict(
                    list(xlsx_header_dict.items()) + list(custom_header_dict.items())
                )
            else:
                self.combined_header_dict = xlsx_header_dict

            for column_name, column_label in self.combined_header_dict.items():
                if column_name == "row_color":
                    continue
                column_count += 1
                if column_count > len(column_titles):
                    column_name_display = column_label
                else:
                    column_name_display = column_titles[column_count - 1]

                header_cell = self.ws.cell(
                    row=row_count, column=column_count, value=column_name_display
                )
                set_cell_style(header_cell, column_header_style)
            self.ws.row_dimensions[row_count].height = column_header.get("height", 45)

        if use_header:
            last_col_letter = get_column_letter(column_count) if column_count else "G"
            self.ws.merge_cells(f"A1:{last_col_letter}1")

            cell = self.ws.cell(row=1, column=1, value=header_title)
            set_cell_style(cell, header_style)
            self.ws.row_dimensions[1].height = header.get("height", 45)

        column_width = column_header.get("column_width", 20)
        if isinstance(column_width, list):
            for i, width in enumerate(column_width):
                col_letter = get_column_letter(i + 1)
                self.ws.column_dimensions[col_letter].width = width
        else:
            for ws_column in range(1, column_count + 1):
                col_letter = get_column_letter(ws_column)
                self.ws.column_dimensions[col_letter].width = column_width

        body = get_attribute(drf_view, "body", {})
        self.body_style = (
            XLSXStyle(body.get("style")) if body and "style" in body else None
        )
        if isinstance(results, dict):
            self._make_body(body, results, row_count)
        elif isinstance(results, list):
            for row in results:
                self._make_body(body, row, row_count)
                row_count += 1

        if auto_filter and column_count:
            self.ws.auto_filter.ref = f"A1:{get_column_letter(column_count)}{row_count}"

        self.sheet_view_options = get_attribute(drf_view, "sheet_view_options", dict())
        self.ws.views.sheetView[0] = SheetView(**self.sheet_view_options)

        return self._save_virtual_workbook(wb)

    def _save_virtual_workbook(self, wb):
        with TemporaryFile() as tmp:
            save_workbook(wb, tmp)
            tmp.seek(0)
            virtual_workbook = tmp.read()

        return virtual_workbook

    def _check_validation_data(self, data, renderer_context=None):
        response = (renderer_context or {}).get("response")
        if response is not None:
            return 200 <= response.status_code < 300
        detail_key = "detail"
        return detail_key not in data

    def _serializer_fields(self, serializer, parent_key="", key_sep="."):
        _fields_dict = {}
        for k, v in serializer.fields.items():
            new_key = f"{parent_key}{key_sep}{k}" if parent_key else k
            if isinstance(v, Serializer):
                _fields_dict.update(self._serializer_fields(v, new_key, key_sep))
            elif isinstance(v, Field):
                _fields_dict[new_key] = v
        return _fields_dict

    def _is_specified(self, key, key_sep):
        if self.specify_headers is None:
            return True
        return any(
            key == header
            or key.startswith(f"{header}{key_sep}")
            or header.startswith(f"{key}{key_sep}")
            for header in self.specify_headers
        )

    def _flatten_serializer_keys(
        self,
        serializer,
        parent_key="",
        parent_label="",
        key_sep=".",
        list_sep=", ",
        label_sep=" > ",
        use_labels=False,
    ):
        def _get_label(parent_label, label_sep):
            return (
                f"{parent_label}{label_sep}{v.label}" if parent_label else str(v.label)
            )

        _header_dict = {}
        _fields = serializer.fields
        for k, v in _fields.items():
            new_key = f"{parent_key}{key_sep}{k}" if parent_key else k
            if (
                not self._is_specified(new_key, key_sep)
                or new_key in self.ignore_headers
                or getattr(v, "write_only", False)
            ):
                continue
            if isinstance(v, Serializer):
                if use_labels and getattr(v, "label", None):
                    _header_dict.update(
                        self._flatten_serializer_keys(
                            v,
                            new_key,
                            _get_label(parent_label, label_sep),
                            key_sep,
                            list_sep,
                            label_sep,
                            use_labels,
                        )
                    )
                else:
                    _header_dict.update(
                        self._flatten_serializer_keys(
                            v,
                            new_key,
                            key_sep=key_sep,
                            list_sep=list_sep,
                            label_sep=label_sep,
                            use_labels=use_labels,
                        )
                    )
            elif isinstance(v, Field):
                if use_labels and getattr(v, "label", None):
                    _header_dict[new_key] = _get_label(parent_label, label_sep)
                else:
                    _header_dict[new_key] = new_key

        return _header_dict

    def _flatten_data(self, data, parent_key="", key_sep=".") -> dict[str, XLSXField]:
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{key_sep}{k}" if parent_key else k

            if isinstance(v, Promise):
                v = v.__class__._proxy____cast(v)

            if isinstance(v, MutableMapping):
                items.extend(self._flatten_data(v, new_key, key_sep=key_sep).items())
            else:
                xlsx_field = self._drf_to_xlsx_field(key=new_key, value=v)
                items.append((new_key, xlsx_field))

        return dict(items)

    def _make_body(self, body, row, row_count):
        column_count = 0
        row_count += 1
        flattened_row = self._flatten_data(row)

        for header_key in self.combined_header_dict:
            if header_key == "row_color":
                continue

            column_count += 1
            field = flattened_row.get(header_key)

            if field:
                if self.hyperlink_getter:
                    field.hyperlink = self.hyperlink_getter(row, header_key)

                field.cell(self.ws, row_count, column_count)
            else:
                self.ws.cell(row_count, column_count)

        self.ws.row_dimensions[row_count].height = body.get("height", 40)

        if "row_color" in row:
            last_letter = get_column_letter(column_count)
            cell_range = self.ws[f"A{row_count}" : f"{last_letter}{row_count}"]
            fill = PatternFill(fill_type="solid", start_color=row["row_color"])

            for r in cell_range:
                for c in r:
                    c.fill = fill

    def _drf_to_xlsx_field(self, key, value) -> XLSXField:
        field = self.fields_dict.get(key)

        cell_style = (
            XLSXStyle(self.column_data_styles.get(key))
            if key in self.column_data_styles
            else None
        )

        kwargs = {
            "key": key,
            "value": value,
            "field": field,
            "style": self.body_style,
            "mapping": self.custom_cols.get(key, {}).get("formatter")
            or self.custom_mappings.get(key),
            "cell_style": cell_style,
        }

        if isinstance(field, BooleanField):
            return XLSXBooleanField(boolean_display=self.boolean_display, **kwargs)
        elif isinstance(field, IntegerField | FloatField | DecimalField):
            return XLSXNumberField(**kwargs)
        elif isinstance(field, DateTimeField | DateField | TimeField):
            return XLSXDateField(**kwargs)
        elif (
            isinstance(field, ListField)
            or isinstance(value, Iterable)
            and not isinstance(value, str)
        ):
            return XLSXListField(list_sep=self.list_sep, **kwargs)

        return XLSXField(**kwargs)
