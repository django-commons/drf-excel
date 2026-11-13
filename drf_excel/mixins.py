from tempfile import TemporaryFile

from django.http import FileResponse
from django.utils.encoding import escape_uri_path
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.views import SheetView
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_excel.renderers import XLSXRenderer
from drf_excel.utilities import XLSXStyle, get_attribute, set_cell_style


class XLSXFileMixin:
    filename = "export.xlsx"
    xlsx_iterator_chunk_size = 2000

    def get_filename(self, request=None, *args, **kwargs):
        return self.filename

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if (
            isinstance(response, Response)
            and response.accepted_renderer.format == "xlsx"
        ):
            filename = self.get_filename(request, *args, **kwargs)
            response["content-disposition"] = (
                f"attachment; filename={escape_uri_path(filename)}"
            )
        return response

    def list(self, request, *args, **kwargs):
        if request.accepted_renderer.format != "xlsx":
            return super().list(request, *args, **kwargs)

        queryset = self.filter_queryset(self.get_queryset())

        if not callable(getattr(queryset, "iterator", None)):
            raise TypeError(
                "XLSX streaming export requires a queryset "
                "that supports iterator()."
            )

        chunk_size = self.xlsx_iterator_chunk_size

        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
            raise TypeError("xlsx_iterator_chunk_size must be a positive integer.")

        if chunk_size <= 0:
            raise ValueError("xlsx_iterator_chunk_size must be a positive integer.")

        serializer = self.get_serializer()
        renderer = XLSXRenderer()
        self._configure_renderer(renderer, serializer)

        return self._build_streaming_response(
            request,
            queryset,
            renderer,
            chunk_size,
            *args,
            **kwargs,
        )


class XLSXHyperlinkMixin:
    def get_cell_hyperlink(self, row, column):
        return None

    def _get_cell_hyperlink(self, row, column):
        hyperlink = self.get_cell_hyperlink(row, column)

        if hyperlink is None:
            return None

        if not isinstance(hyperlink, str):
            raise TypeError("get_cell_hyperlink() must return a string or None.")

        return hyperlink or None


    def _configure_renderer(self, renderer, serializer):
        """
        Reuse the existing renderer's serializer and field-flattening logic
        so streaming exports follow the regular XLSX field conventions.
        """
        renderer.specify_headers = getattr(self, "xlsx_specify_headers", None)
        renderer.ignore_headers = getattr(self, "xlsx_ignore_headers", [])
        renderer.boolean_display = getattr(self, "xlsx_boolean_labels", None)

        renderer.column_data_styles = (
            get_attribute(self, "column_data_styles", {}) or {}
        )

        renderer.custom_cols = getattr(self, "xlsx_custom_cols", {}) or {}
        renderer.custom_mappings = getattr(self, "xlsx_custom_mappings", {}) or {}

        renderer.fields_dict = renderer._serializer_fields(serializer)

        renderer.list_sep = getattr(renderer, "list_sep", ", ")
        renderer.hyperlink_getter = getattr(self, "_get_cell_hyperlink", None)

        use_labels = getattr(self, "xlsx_use_labels", False)

        serializer_headers = renderer._flatten_serializer_keys(
            serializer,
            use_labels=use_labels,
        )

        if renderer.custom_cols:
            custom_headers = {
                key: value.get("label") or key
                for key, value in renderer.custom_cols.items()
            }

            renderer.combined_header_dict = {
                **serializer_headers,
                **custom_headers,
            }
        else:
            renderer.combined_header_dict = serializer_headers

        body = get_attribute(self, "body", {}) or {}

        renderer.body_style = XLSXStyle(body["style"]) if "style" in body else None

        renderer.sheet_view_options = (
            get_attribute(self, "sheet_view_options", {}) or {}
        )

    def _build_streaming_response(
        self,
        request,
        queryset,
        renderer,
        chunk_size,
        *args,
        **kwargs,
    ):
        """
        Build the XLSX workbook one row at a time and return it as a
        disk-backed FileResponse.
        """
        header = get_attribute(self, "header", {}) or {}
        column_header = get_attribute(self, "column_header", {}) or {}
        body = get_attribute(self, "body", {}) or {}

        # Write-only worksheets do not support the regular image API.
        # Fail explicitly rather than silently generating an incomplete export.
        if header.get("img"):
            raise NotImplementedError(
                "Images in the XLSX header are not supported "
                "by the streaming exporter."
            )

        headers = [key for key in renderer.combined_header_dict if key != "row_color"]

        use_header = bool(header) and header.get("use_header", True)

        workbook = Workbook(write_only=True)

        worksheet = workbook.create_sheet(title=header.get("tab_title", "Report"))

        # Write-only worksheets serialize view settings with the first row.
        if renderer.sheet_view_options:
            worksheet.views.sheetView[0] = SheetView(**renderer.sheet_view_options)

        # Write-only worksheets serialize column dimensions with the first row,
        # so configure widths before appending any rows.
        column_width = column_header.get("column_width", 20)

        for index in range(len(headers)):
            column_letter = get_column_letter(index + 1)

            if isinstance(column_width, list):
                if index < len(column_width):
                    worksheet.column_dimensions[column_letter].width = column_width[
                        index
                    ]
            else:
                worksheet.column_dimensions[column_letter].width = column_width

        current_row = 1

        # Write the report title, if configured.
        # Write-only worksheets do not support merged cells.
        if use_header:
            title_cell = WriteOnlyCell(
                worksheet,
                value=header.get("header_title", "Report"),
            )

            if "style" in header:
                set_cell_style(title_cell, XLSXStyle(header["style"]))

            worksheet.row_dimensions[current_row].height = header.get("height", 45)

            worksheet.append([title_cell])
            current_row += 1

        # Keep the original renderer's column order and omit row_color,
        # which is a row-level formatting field rather than a data column.
        column_titles = column_header.get("titles", [])

        column_style = (
            XLSXStyle(column_header["style"]) if "style" in column_header else None
        )

        header_cells = []

        for index, key in enumerate(headers):
            if index < len(column_titles):
                title = column_titles[index]
            else:
                title = renderer.combined_header_dict[key]

            cell = WriteOnlyCell(worksheet, value=title)

            if column_style:
                set_cell_style(cell, column_style)

            header_cells.append(cell)

        # Always write column headers, including for an empty queryset.
        header_row = current_row

        if header_cells:
            worksheet.row_dimensions[header_row].height = column_header.get(
                "height", 45
            )

            worksheet.append(header_cells)
            current_row += 1

        auto_filter = get_attribute(self, "xlsx_auto_filter", False)

        # iterator() avoids QuerySet's normal result cache.
        # Serialize and append one record at a time.
        records = queryset.iterator(chunk_size=chunk_size)

        for instance in records:
            row_data = self.get_serializer(instance).data
            flattened_row = renderer._flatten_data(row_data)

            cells = []

            for key in headers:
                field = flattened_row.get(key)

                if field is not None:
                    if renderer.hyperlink_getter:
                        field.hyperlink = renderer.hyperlink_getter(row_data, key)

                    cell = field.write_only_cell(worksheet)
                else:
                    cell = WriteOnlyCell(worksheet, value=None)

                cells.append(cell)

            # Preserve the existing row_color behavior.
            row_color = row_data.get("row_color")

            if row_color and cells:
                fill = PatternFill(
                    fill_type="solid",
                    start_color=row_color,
                )

                for cell in cells:
                    cell.fill = fill

            worksheet.row_dimensions[current_row].height = body.get("height", 40)

            worksheet.append(cells)
            current_row += 1

        if auto_filter and headers:
            last_row = max(header_row, current_row - 1)
            last_column = get_column_letter(len(headers))

            worksheet.auto_filter.ref = f"A{header_row}:{last_column}{last_row}"

        # Generate the XLSX archive into a temporary disk-backed file.
        temporary_file = TemporaryFile(mode="w+b")

        try:
            workbook.save(temporary_file)
            temporary_file.seek(0)
        except Exception:
            temporary_file.close()
            raise

        # Reuse XLSXFileMixin.get_filename() when available.
        filename_getter = getattr(self, "get_filename", None)

        if callable(filename_getter):
            filename = filename_getter(request, *args, **kwargs)
        else:
            filename = getattr(self, "filename", "export.xlsx")

        return FileResponse(
            temporary_file,
            as_attachment=True,
            filename=filename,
            content_type=XLSXRenderer.media_type,
        )
