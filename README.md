# DRF Excel: Django REST Framework Excel Spreadsheet (xlsx) Renderer


[![PyPI - License](https://img.shields.io/pypi/l/drf-excel)](https://opensource.org/license/BSD-3-Clause)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI version](https://badge.fury.io/py/drf-excel.svg)](https://pypi.python.org/pypi/drf-excel/)
[![PyPI python versions](https://img.shields.io/pypi/pyversions/drf-excel.svg)](https://pypi.python.org/pypi/drf-excel/)
[![PyPI django versions](https://img.shields.io/pypi/djversions/drf-excel.svg)](https://pypi.org/project/drf-excel/)
[![PyPI status](https://img.shields.io/pypi/status/drf-excel.svg)](https://pypi.python.org/pypi/drf-excel)
[![CI](https://github.com/django-commons/drf-excel/actions/workflows/test.yml/badge.svg)](https://github.com/django-commons/drf-excel/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/django-commons/drf-excel/graph/badge.svg?token=EETTI9XRNO)](https://codecov.io/gh/django-commons/drf-excel)

`drf-excel` provides an Excel spreadsheet (xlsx) renderer for Django REST Framework. It uses OpenPyXL to create the spreadsheet and provide the file to the end user.

## Requirements

We aim to support Django's [currently supported versions](https://www.djangoproject.com/download/), as well as:

* Django REST Framework >= 3.14
* OpenPyXL >= 2.4

## Installation

```bash
pip install drf-excel
```

Then add the following to your `REST_FRAMEWORK` settings:

```python
REST_FRAMEWORK = {
    ...

    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'drf_excel.renderers.XLSXRenderer',
    ),
}
```

To avoid having a file streamed without a filename (which the browser will often default to the filename "download", with no extension), we need to use a mixin to override the `Content-Disposition` header. If no `filename` is provided, it will default to `export.xlsx`. For example:

```python
from rest_framework.viewsets import ReadOnlyModelViewSet
from drf_excel.mixins import XLSXFileMixin
from drf_excel.renderers import XLSXRenderer

from .models import MyExampleModel
from .serializers import MyExampleSerializer

class MyExampleViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = MyExampleModel.objects.all()
    serializer_class = MyExampleSerializer
    renderer_classes = (XLSXRenderer,)
    filename = 'my_export.xlsx'
    pagination_class = None  # Only required if custom pagination is used
```

The `XLSXFileMixin` also provides a `get_filename()` method which can be overridden, if you prefer to provide a filename programmatically instead of the `filename` attribute.

## Upgrading to 2.0.0

To upgrade to `drf_excel` 2.0.0 from `drf_renderer_xlsx`, update your import paths:

* `from drf_renderer_xlsx.mixins import XLSXFileMixin` becomes `from drf_excel.mixins import XLSXFileMixin`.
* `drf_renderer_xlsx.renderers.XLSXRenderer` becomes `drf_excel.renderers.XLSXRenderer`.
* `xlsx_date_format_mappings` has been removed in favor of `column_data_styles` which provides more flexibility

## Configuring Styles

Styles can be added to your worksheet header, column header row, body and column data from view attributes `header`, `column_header`, `body`, `column_data_styles`. Any arguments from [the OpenPyXL package](https://openpyxl.readthedocs.io/en/stable/styles.html) can be used for font, alignment, fill and border_side (border will always be all side of cell).

If provided, column data styles will override body style

Note that column data styles can take an extra 'format' argument that follows [openpyxl formats](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/styles/numbers.html).

```python
class MyExampleViewSet(XLSXFileMixin, ReadOnlyModelViewSet):
    queryset = MyExampleModel.objects.all()
    serializer_class = MyExampleSerializer
    renderer_classes = (XLSXRenderer,)

    column_header = {
        'titles': [
            "Column_1_name",
            "Column_2_name",
            "Column_3_name",
        ],
        'column_width': [17, 30, 17],
        'height': 25,
        'style': {
            'fill': {
                'fill_type': 'solid',
                'start_color': 'FFCCFFCC',
            },
            'alignment': {
                'horizontal': 'center',
                'vertical': 'center',
                'wrapText': True,
                'shrink_to_fit': True,
            },
            'border_side': {
                'border_style': 'thin',
                'color': 'FF000000',
            },
            'font': {
                'name': 'Arial',
                'size': 14,
                'bold': True,
                'color': 'FF000000',
            },
        },
    }
    body = {
        'style': {
            'fill': {
                'fill_type': 'solid',
                'start_color': 'FFCCFFCC',
            },
            'alignment': {
                'horizontal': 'center',
                'vertical': 'center',
                'wrapText': True,
                'shrink_to_fit': True,
            },
            'border_side': {
                'border_style': 'thin',
                'color': 'FF000000',
            },
            'font': {
                'name': 'Arial',
                'size': 14,
                'bold': False,
                'color': 'FF000000',
            }
        },
        'height': 40,
    }
    column_data_styles = {
        'distance': {
            'alignment': {
                'horizontal': 'right',
                'vertical': 'top',
            },
            'format': '0.00E+00'
        },
        'created_at': {
            'format': 'd.m.y h:mm',
        }
    }
```

You can dynamically generate style attributes in methods `get_body`, `get_header`, `get_column_header`, `get_column_data_styles`.

```python
def get_header(self):
    start_time, end_time = parse_times(request=self.request)
    datetime_format = "%H:%M:%S %d.%m.%Y"
    return {
        'tab_title': 'MyReport', # title of tab/workbook
        'use_header': True,  # show the header_title
        'header_title': 'Report from {} to {}'.format(
            start_time.strftime(datetime_format),
            end_time.strftime(datetime_format),
        ),
        'height': 45,
        'img': 'app/images/MyLogo.png',
        'style': {
            'fill': {
                'fill_type': 'solid',
                'start_color': 'FFFFFFFF',
            },
            'alignment': {
                'horizontal': 'center',
                'vertical': 'center',
                'wrapText': True,
                'shrink_to_fit': True,
            },
            'border_side': {
                'border_style': 'thin',
                'color': 'FF000000',
            },
            'font': {
                'name': 'Arial',
                'size': 16,
                'bold': True,
                'color': 'FF000000',
            }
        }
    }
```

Also, you can add the `row_color` field to your serializer and fill body rows.

```python
class ExampleSerializer(serializers.Serializer):
    row_color = serializers.SerializerMethodField()

    def get_row_color(self, instance):
        color_map = {'w': 'FFFFFFCC', 'a': 'FFFFCCCC'}
        return color_map.get(instance.alarm_level, 'FFFFFFFF')
```

## Configuring Sheet View Options

View options follow [openpyxl sheet view options](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/worksheet/views.html#SheetView)

They can be set in the view as a property `sheet_view_options`:

```python
class MyExampleViewSet(serializers.Serializer):
    sheet_view_options = {
        'rightToLeft': True,
        'showGridLines': False
    }
```

or using method `get_sheet_view_options`:

```python
class MyExampleViewSet(serializers.Serializer):

    def get_sheet_view_options(self):
        return {
            'rightToLeft': True,
            'showGridLines': False
        }
```
## Controlling XLSX headers and values

### Use Serializer Field labels as header names

By default, headers will use the same 'names' as they are returned by the API. This can be changed by setting `xlsx_use_labels = True` inside your API View.

Instead of using the field names, the export will use the labels as they are defined inside your Serializer. A serializer field defined as `title = serializers.CharField(label=_("Some title"))` would return `Some title` instead of `title`, also supporting translations. If no label is set, it will fall back to using `title`.

### Ignore fields

By default, all fields are exported, but you might want to exclude some fields from your export. To do so, you can set an array with fields you want to exclude: `xlsx_ignore_headers = [<excluded fields>]`.

This also works with nested fields, separated with a dot (i.e. `icon.url`).

### Date/time and number formatting
Formatting for cells follows [openpyxl formats](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/styles/numbers.html).

To set global formats, set the following variables in `settings.py`:

```python
# Date formats
DRF_EXCEL_DATETIME_FORMAT = 'mm-dd-yy h:mm AM/PM'
DRF_EXCEL_DATE_FORMAT = 'mm-dd-yy'
DRF_EXCEL_TIME_FORMAT = 'h:mm AM/PM'

# Number formats
DRF_EXCEL_INTEGER_FORMAT = '0%'
DRF_EXCEL_DECIMAL_FORMAT = '0.00E+00'
```

### Name boolean values

`True` and `False` as values for boolean fields are not always the best representation and don't support translation.

This can be controlled with in you API view with `xlsx_boolean_labels`.

```
xlsx_boolean_labels = {True: _('Yes'), False: _('No')}
```

will replace `True` with `Yes` and `False` with `No`.

This can also be set globally in settings.py:

```
DRF_EXCEL_BOOLEAN_DISPLAY = {True: _('Yes'), False: _('No')}
```


### Custom columns

You might find yourself explicitly returning a dict in your API response and would like to use its data to display additional columns. This can be done by passing `xlsx_custom_cols`.

```python
xlsx_custom_cols = {
    'my_custom_col.val1.title': {
        'label': 'Custom column!',
        'formatter': custom_value_formatter
    }
}

### Example function:
def custom_value_formatter(val):
    return val + '!!!'

### Example response:
{
    results: [
        {
            title: 'XLSX renderer',
            url: 'https://github.com/django-commons/drf-excel'
            returned_dict: {
                val1: {
                    title: 'Sometimes'
                },
                val2: {
                    title: 'There is no way around'
                }
            }
        }
    ]
}
```

When no `label` is passed, `drf-excel` will display the key name in the header.

`formatter` is also optional and accepts a function, which will then receive the value it is mapped to (it would receive "Sometimes" and return "Sometimes!!!" in our example).

### Custom mappings

Assuming you have a field that returns a `dict` instead of a simple `str`, you might not want to return the whole object but only a value of it. Let's say `status` returns `{ value: 1, display: 'Active' }`. To return the `display` value in the `status` column, we can do this:

```python
xlsx_custom_mappings = {
    'status': 'display'
}
```

A more common case is that you want to change how a value is formatted. `xlsx_custom_mappings` also takes functions as values. Assuming we have a field `description`, and for some strange reason want to reverse the text, we can do this:

```python
def reverse_text(val):
    return val[::-1]

xlsx_custom_mappings = {
    'description': reverse_text
}
```

## Release Notes and Contributors

* [Release notes](https://github.com/django-commons/drf-excel/releases)
* [Our wonderful contributors](https://github.com/django-commons/drf-excel/graphs/contributors)

## Maintainers

* [Timothy Allen](https://github.com/FlipperPA) at [The Wharton School](https://github.com/wharton)
* [Thomas Willems](https://github.com/willtho89)
* [Mathieu Rampant](https://github.com/rptmat57)
* [Bruno Alla](https://github.com/browniebroke)

This package is a member of [Django Commons](https://github.com/django-commons/) and adheres to the community's [Code of Conduct](https://github.com/django-commons/membership/blob/main/CODE_OF_CONDUCT.md). This package was created by the staff of [Wharton Research Data Services](https://wrds.wharton.upenn.edu/). We are thrilled that [The Wharton School](https://www.wharton.upenn.edu/) allows us a certain amount of time to contribute to open-source projects. We add features as they are necessary for our projects, and try to keep up with Issues and Pull Requests as best we can. Due to constraints of time (our full time jobs!), Feature Requests without a Pull Request may not be implemented, but we are always open to new ideas and grateful for contributions and our users.
