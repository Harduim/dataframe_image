from pandas.io.formats.style import Styler

from .screenshot import Screenshot

MAX_COLS = 30
MAX_ROWS = 100


def to_img(
    obj,
    filename,
    fontsize=14,
    max_rows=None,
    max_cols=None,
    table_conversion="chrome",
    chrome_path=None,
):
    is_styler = isinstance(obj, Styler)
    df = obj.data if is_styler else obj

    if table_conversion == "chrome":
        converter = Screenshot(
            max_rows=max_rows,
            max_cols=max_cols,
            chrome_path=chrome_path,
            fontsize=fontsize,
            encode_base64=False,
            limit_crop=False,
        ).run
    else:
        from .matplotlib_table import TableMaker

        converter = TableMaker(fontsize=fontsize, encode_base64=False, for_document=False).run

    if df.shape[0] > MAX_ROWS and max_rows is None:
        error_msg = (
            f"Your DataFrame has more than {MAX_ROWS} rows and will produce a huge "
            "image file, possibly causing your computer to crash. Override this error "
            "by explicitly setting `max_rows`. Use -1 for all rows."
        )
        if is_styler:
            error_msg = (
                f"Your Styled DataFrame has more than {MAX_ROWS} rows and will produce "
                "a huge image file, possibly causing your computer to crash. Override "
                "this error by explicitly setting `max_rows` to -1 for all columns. "
                "Styled DataFrames are unable to select a subset of rows or columns "
                "and therefore do not work with the `max_rows` and `max_cols` parameters"
            )
        raise ValueError(error_msg)
    if max_rows == -1:
        max_rows = None

    if df.shape[1] > MAX_COLS and max_cols is None:
        error_msg = (
            f"Your DataFrame has more than {MAX_COLS} columns and will produce a huge "
            "image file, possibly causing your computer to crash. Override this error "
            "by explicitly setting `max_cols`. Use -1 for all columns."
        )
        if is_styler:
            error_msg = (
                f"Your Styled DataFrame has more than {MAX_COLS} columns and will "
                "produce a huge image file, possibly causing your computer to crash. "
                "Override this error by explicitly setting `max_cols` to -1 for "
                "all columns. Styled DataFrames are unable to select a subset of "
                "rows or columns and therefore do not work with the `max_rows` "
                "and `max_cols` parameters"
            )
        raise ValueError(error_msg)

    if max_cols == -1:
        max_cols = None

    if is_styler:
        html = "<div>" + obj.render() + "</div>"
    else:
        html = obj.to_html(max_rows=max_rows, max_cols=max_cols, notebook=True)

    img_str = converter(html)

    if isinstance(filename, str):
        open(filename, "wb").write(img_str)
    elif hasattr(filename, "write"):
        filename.write(img_str)


setattr(Styler, "export_png", to_img)