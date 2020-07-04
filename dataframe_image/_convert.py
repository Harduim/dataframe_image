import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import re
import io
import shutil
import urllib.parse

import nbformat
from nbconvert import MarkdownExporter, PDFExporter
from nbconvert.preprocessors import ExecutePreprocessor
from traitlets.config import Config

from ._preprocessors import (MarkdownPreprocessor, 
                             NoExecuteDataFramePreprocessor, 
                             ChangeOutputTypePreprocessor)
from ._screenshot import Screenshot


class Converter:
    KINDS = ['pdf', 'md', 'markdown']
    DISPLAY_DATA_PRIORITY = [
        "image/png",
        "text/html",
        "application/pdf",
        "text/latex",
        "image/svg+xml",
        "image/jpeg",
        "text/markdown",
        "text/plain",
    ]

    def __init__(self, filename, to, use, center_df, latex_command, max_rows, max_cols, ss_width, 
                 ss_height, chrome_path, limit, document_name, execute, save_notebook, 
                 output_dir, table_conversion, web_app):
        self.filename = Path(filename)
        self.use = use
        self.center_df = center_df
        self.max_rows = max_rows
        self.max_cols = max_cols
        self.ss_width = ss_width
        self.ss_height = ss_height
        self.chrome_path = chrome_path
        self.limit = limit
        self.table_conversion = table_conversion
        self.web_app = web_app
        self.td = TemporaryDirectory()

        self.nb_home = self.filename.parent
        self.nb_name = self.filename.stem
        self.to = self.get_to(to)
        self.latex_command = self.get_latex_command(latex_command)
        self.nb = self.get_notebook()

        self.document_name = self.get_document_name(document_name)
        self.execute = execute
        self.save_notebook = save_notebook
        self.final_nb_home = self.get_new_notebook_home(output_dir)
        self.image_dir_name = self.nb_name + '_files'
        
        self.return_data = {}
        self.resources = self.get_resources()
        self.first = True

    def get_to(self, to):
        if isinstance(to, str):
            to = [to]
        elif not isinstance(to, list):
            raise TypeError('`to` must either be a string or a list. '
                            'Possible values are "pdf" and "md"')
        to = set(to)
        if 'markdown' in to:
            to.remove('markdown')
            to.add('md')
        for kind in to:
            if kind not in self.KINDS:
                raise TypeError(
                    "`to` must either be a string or a list. "
                    'Possible values are "pdf" or "markdown"/"md"'
                    f' and not {kind}.'
                )
        to = list(to)
        if len(to) == 2:
            to = ['md', 'pdf']
        return to

    def get_latex_command(self, latex_command):
        if self.use == 'latex' and 'pdf' in self.to:
            if latex_command is None:
                texs = ['xelatex', 'pdflatex', 'texi2pdf']
                final_tex = ''
                for tex in texs:
                    if shutil.which(tex):
                        final_tex = tex
                        break
                if not final_tex:
                    raise OSError('No latex installation found. Try setting `use="browser" to '\
                                  'convert via browser (without latex).\n'\
                                  'Find out how to install latex here: '\
                                  'https://nbconvert.readthedocs.io/en/latest/install.html#installing-tex')
                latex_command = [final_tex, '{filename}']
                if final_tex == 'xelatex':
                    latex_command.append('-quiet')
            return latex_command

    def get_notebook(self):
        with open(self.filename) as f:
            nb = nbformat.read(f, as_version=4)

        if isinstance(self.limit, int):
            nb["cells"] = nb["cells"][:self.limit]

        return nb

    def get_document_name(self, document_name):
        if document_name:
            return document_name
        else:
            return self.nb_name

    def get_new_notebook_home(self, output_dir):
        if output_dir:
            p = Path(output_dir)
            if not p.exists():
                raise FileNotFoundError(f'Directory {p} does not exist')
            elif not p.is_dir():
                raise FileNotFoundError(f'{p} is not a directory')
            return p
        else:
            return Path(self.nb_home)

    def get_resources(self):
        if self.table_conversion == 'chrome':
            converter = Screenshot(center_df=self.center_df, max_rows=self.max_rows, 
                                    max_cols=self.max_cols, ss_width=self.ss_width, 
                                    ss_height=self.ss_height, chrome_path=self.chrome_path).run
        else:
            from ._matplotlib_table import converter

        resources = {'metadata': {'path': str(self.nb_home), 
                                  'name': self.document_name},
                     'converter': converter,
                     'image_data_dict': {}}
        return resources
        
    def get_code_to_run(self):
        code = (
            "import pandas as pd;"
            "from dataframe_image._screenshot import make_repr_png;"
            f"_repr_png_ = make_repr_png(center_df={self.center_df}, max_rows={self.max_rows}, "
            f"max_cols={self.max_cols}, ss_width={self.ss_width}, "
            f"ss_height={self.ss_height}, "
            f"chrome_path={self.chrome_path});"
            "pd.DataFrame._repr_png_ = _repr_png_;"
            "from pandas.io.formats.style import Styler;"
            "Styler._repr_png_ = _repr_png_;"
            "del make_repr_png, _repr_png_"
        )
        return code

    def preprocess(self):
        preprocessors = []
        mp = MarkdownPreprocessor()
        preprocessors.append(mp)

        if self.execute:
            code = self.get_code_to_run()
            extra_arguments = [f"--InteractiveShellApp.code_to_run='{code}'"]
            pp = ExecutePreprocessor(timeout=600, allow_errors=True, 
                                     extra_arguments=extra_arguments)
            preprocessors.append(pp)
        else:
            preprocessors.append(NoExecuteDataFramePreprocessor())

        preprocessors.append(ChangeOutputTypePreprocessor())

        for pp in preprocessors:
            self.nb, self.resources = pp.preprocess(self.nb, self.resources)

    def to_md(self):
        self.preprocess()
        me = MarkdownExporter(config={'NbConvertBase': {'display_data_priority': 
                                                        self.DISPLAY_DATA_PRIORITY}})
        md_data, self.resources = me.from_notebook_node(self.nb, self.resources)
        # the base64 encoded binary files are saved in output_resources

        image_data_dict = {**self.resources['outputs'], **self.resources['image_data_dict']}
        for filename in image_data_dict:
            new = str(Path(self.image_dir_name) / filename)
            new = urllib.parse.quote(new)
            md_data = md_data.replace(filename, new)

        if self.web_app:
            self.return_data['md_data'] = md_data
            self.return_data['md_images'] = image_data_dict
            self.return_data['image_dir_name'] = self.image_dir_name
        else:
            image_dir = self.final_nb_home / self.image_dir_name
            if image_dir.is_dir():
                shutil.rmtree(image_dir)
            image_dir.mkdir()

            for filename, value in image_data_dict:
                with open(image_dir / filename, 'wb') as f:
                    f.write(value)
            
            fn = self.final_nb_home / (self.document_name + '.md')
            with open(fn, mode='w') as f:
                f.write(md_data)
        self.reset_resources()

    def to_pdf(self):
        if self.use == 'browser':
            return self.to_chrome_pdf()

        self.resources['temp_dir'] = Path(self.td.name)
        self.preprocess()
        pdf = PDFExporter(config={'NbConvertBase': {'display_data_priority': 
                                                    self.DISPLAY_DATA_PRIORITY}})
        pdf_data, self.resources = pdf.from_notebook_node(self.nb, self.resources)
        self.return_data['pdf_data'] = pdf_data
        if not self.web_app:
            fn = self.final_nb_home / (self.document_name + '.pdf')
            with open(fn, mode='wb') as f:
                f.write(pdf_data)

    def to_chrome_pdf(self):
        self.preprocess()

        from ._browser_pdf import BrowserExporter
        be = BrowserExporter()

        pdf_data, self.resources = be.from_notebook_node(self.nb, self.resources)
        self.return_data['pdf_data'] = pdf_data
        if not self.web_app:
            fn = self.final_nb_home / (self.document_name + '.pdf')
            with open(fn, mode='wb') as f:
                f.write(pdf_data)

    def reset_resources(self):
        self.first = False
        del self.resources['outputs']
        del self.resources['output_extension']

    def save_notebook_to_file(self):
        # TODO: save image dir when pdf
        if self.save_notebook:
            name = self.nb_name + '_dataframe_image.ipynb'
            file = self.final_nb_home / name
            if self.web_app:
                buffer = io.StringIO()
                nbformat.write(self.nb, buffer)
                self.return_data['notebook'] = buffer.getvalue()
            else:
                nbformat.write(self.nb, file)

    def convert(self):
        for kind in self.to:
            getattr(self, f'to_{kind}')()
        self.save_notebook_to_file()


def convert(filename, to='pdf', use='latex', center_df=True, latex_command=None, 
            max_rows=30, max_cols=10, ss_width=1400, ss_height=900,
            chrome_path=None, limit=None, document_name=None, execute=False, 
            save_notebook=False, output_dir=None, table_conversion='chrome'):
    """
    Convert a Jupyter Notebook to pdf or markdown using images for pandas
    DataFrames instead of their normal latex/markdown representation. 
    The images will be screenshots of the DataFrames as they appear in a 
    chrome browser.

    By default, the new file will be in the same directory where the 
    notebook resides and use the same name but with appropriate extension.

    When converting to markdown, a folder with the title 
    {notebook_name}_files will be created to hold all of the images.

    Caution, this is computationally expensive and takes a long time to 
    complete with many DataFrames. You may wish to begin by using the 
    `limit` parameter to convert just a few cells.

    Parameters
    ----------
    filename : str
        Path to Jupyter Notebook '.ipynb' file that you'd like to convert.

    to : str or list, default 'pdf'
        Choose conversion format. Either 'pdf' or 'markdown'/'md' or a 
        list with all formats.

    use : 'latex' or 'browser', default 'latex'
        Choose to convert using latex or chrome web browser when converting 
        to pdf. Output is significantly different for each. Use 'latex' when
        you desire a formal report. Use 'browser' to get output similar to
        that when printing to pdf within a chrome web browser.

    center_df : bool, default True
        Choose whether to center the DataFrames or not in the image. By 
        default, this is True, though in Jupyter Notebooks, they are 
        left-aligned. Use False to make left-aligned.

    latex_command: list, default None
        Pass in a list of commands that nbconvert will use to convert the 
        latex document to pdf. The latex document is created temporarily when
        converting to pdf with the `use` option set to 'latex'. By default,
        it is set to this list: ['xelatex', {filename}, 'quiet']

        If the xelatex command is not found on your machine, then pdflatex 
        will be substituted for it. You must have latex installed on your 
        machine for this to work. Get more info on how to install latex -
        https://nbconvert.readthedocs.io/en/latest/install.html#installing-tex

    max_rows : int, default 30
        Maximum number of rows to output from DataFrame. This is forwarded to 
        the `to_html` DataFrame method.

    max_cols : int, default 10
        Maximum number of columns to output from DataFrame. This is forwarded 
        to the `to_html` DataFrame method.

    ss_width : int, default 1400
        Width of the screenshot in pixels. This may need to be increased for 
        larger monitors. If this value is too small, then smaller DataFrames will 
        appear larger. It's best to keep this value at least as large as the 
        width of the output section of a Jupyter Notebook.

    ss_height : int, default 900
        Height of the screen shot. The height of the image is automatically 
        cropped so that only the relevant parts of the DataFrame are shown.

    chrome_path : str, default `None`
        Path to your machine's chrome executable. When `None`, it is 
        automatically found. Use this when chrome is not automatically found.

    limit : int, default `None`
        Limit the number of cells in the notebook for conversion. This is 
        useful to test conversion of a large notebook on a smaller subset. 

    document_name : str, default `None`
        Name of newly created pdf/markdown document without the extension. If not
        provided, the current name of the notebook will be used.

    execute : bool, default `False`
        Whether or not to execute the notebook first.

    save_notebook : bool, default `False`
        Whether or not to save the notebook with pandas DataFrames as images as 
        a new notebook. The filename will be '{notebook_name}_dataframe_image.ipynb'

    output_dir : str, default `None`
        Directory where new pdf and/or markdown files will be saved. By default, 
        this will be the same directory as the notebook. The directory 
        for images will also be created in here. If `save_notebook` is set to
        True, it will be saved here as well.

        Provide a relative or absolute path.
    
    table_conversion : 'chrome' or 'matplotlib'
        DataFrames (and other tables) will be inserted in your document
        as an image using a screenshot from Chrome. If this doesn't
        work, use matplotlib, which will always work and produce
        similar results.
    """
    c = Converter(filename, to, use, center_df, latex_command, max_rows, max_cols, 
                  ss_width, ss_height, chrome_path, limit, document_name, 
                  execute, save_notebook, output_dir, table_conversion, 
                  web_app=False)
    c.convert()
