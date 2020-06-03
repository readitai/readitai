import os
import re
import yaml
from yaml.loader import Reader, Scanner, Parser, Composer, SafeConstructor, Resolver
from glob import glob
from urllib.request import urlopen
from selectolax.parser import HTMLParser
# import for pdf to text
import io
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from PyPDF2 import PdfFileReader, PdfFileWriter
# epub converter
import ebooklib
from ebooklib import epub


__all__ = ['ingest_config', 'ProcessEpub', 'ProcessHtml', 'ProcessPDF']


def get_text_selectolax(html):
    html = html.strip()

    if len(html) == 0:
        return None

    tree = HTMLParser(html)
    for tag in tree.css('script'):
        tag.decompose()
    for tag in tree.css('style'):
        tag.decompose()

    text = tree.body.text(separator='\n')
    return text


def ingest_config(configfile):
    with open(configfile, 'r') as s:
        config = yaml.load(s, Loader=MySafeLoader)

    config.name = config.outputfile.name
    config.outputdir = os.path.join(config.outputfile.dir, config.name)
    config.outputdir_audio = os.path.join(config.outputdir, config.outputfile.subdir_audio)
    os.makedirs(config.outputdir_audio, exist_ok=True)

    if config.inputfile.type == 'pdf':
        pass
    elif config.inputfile.type == 'html':
        pass
    elif config.inputfile.type == 'epub':
        pass

    return config


class ProcessEpub:
    def __init__(self, epub_path, outputdir, param_epub):
        self.epub_path = epub_path
        self.book_name = os.path.basename(outputdir)
        self.param = param_epub
        self.param.cut_start = None if not self.param.get('cut_start') else param_epub.cut_start
        self.param.cut_end = None if not self.param.get('cut_end') else -param_epub.cut_end
        self.chapterstextprefix = os.path.join(outputdir, 'chaptertexts', self.book_name)
        os.makedirs(os.path.dirname(self.chapterstextprefix), exist_ok=True)

    def process(self):
        chapters_html = self.epub2html()
        chapters_text = self.html2text(chapters_html)
        chapters_text = chapters_text[self.param.cut_start: self.param.cut_end]

        for i, chapter_text in enumerate(chapters_text):
            # save the chapters text
            with open('{}_chapter{:03d}.txt'.format(self.chapterstextprefix, i + 1), 'w') as f:
                f.write(chapter_text)

        return chapters_text

    @ staticmethod
    def html2text(chapters_html):
        chapters_text = []
        for html_ in chapters_html:
            text_ = get_text_selectolax(html_).replace('\x0c', '').replace('\xa0', '')
            text_ = re.sub('\n{3,}', '\n', text_)
            chapters_text.append(text_)
        return chapters_text

    def epub2html(self):
        """
        extract html from epub book. Assumes the book is pre-split into chapters
        :return: chapters in html format
        """
        book = epub.read_epub(self.epub_path)
        chapters_html = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                chapters_html.append(item.get_content())
        return chapters_html


class ProcessHtml:
    def __init__(self, webpage, outputdir, param_html, maxsplit=1):
        self.webpage = webpage
        self.param = param_html
        self.param.cut_start = None if not self.param.get('cut_start') else param_html.cut_start
        self.param.cut_end = None if not self.param.get('cut_end') else -param_html.cut_end
        self.maxsplit = maxsplit
        self.book_name = os.path.basename(outputdir)
        self.chapterstextprefix = os.path.join(outputdir, 'chaptertexts', self.book_name)
        os.makedirs(os.path.dirname(self.chapterstextprefix), exist_ok=True)

    def process(self):
        html = self.extract_html()
        chapters_html = re.split(self.param.split_regex, html)
        chapters_html = chapters_html[self.param.cut_start: self.param.cut_end]
        chapters_html = [i + '.\n' + j for i, j in zip(chapters_html[::2], chapters_html[1::2])]

        chapters_text = []
        for i, chapter_html in enumerate(chapters_html):
            chapter_text = get_text_selectolax(chapter_html).replace('\x0c', '').replace('\xa0', '')
            chapter_text = re.sub('\n{4,}', '\n', chapter_text)
            # chapters_text[i] = 'CHAPTER {}.\n'.format(i+1) + chapters_text[i]
            chapters_text.append(chapter_text)
            # save the chapters text
            with open('{}_chapter{:03d}.txt'.format(self.chapterstextprefix, i + 1), 'w') as f:
                f.write(chapter_text)

        return chapters_text

    def extract_html(self):
        try:  # try to open as a url first
            with urlopen(self.webpage) as f:
                _, html = f.read().split(b'\r\n\r\n', maxsplit=self.maxsplit)
        except ValueError:  # if not then try as a html file
            with open(self.webpage, 'r') as f:
                html = f.read()

        return html


class ProcessPDF:
    def __init__(self, pdf_path, outputdir, param_pdf):
        self.pdf_path = pdf_path
        self.ch_page_list = param_pdf.ch_page_list
        self.book_name = os.path.basename(outputdir)
        self.chapterstextprefix = os.path.join(outputdir, 'chaptertexts', self.book_name)
        self.chapterspdfprefix = os.path.join(outputdir, 'chapterpdfs', self.book_name)
        os.makedirs(os.path.dirname(self.chapterspdfprefix), exist_ok=True)
        os.makedirs(os.path.dirname(self.chapterstextprefix), exist_ok=True)

    def process(self):
        self.pdf_splitter()
        chapterpdfs = sorted(glob(self.chapterspdfprefix + '*.pdf'), key=os.path.basename)
        chapters_text = []
        for i, chapterpdf in enumerate(chapterpdfs):
            print('----- Chapter %d -----' % (i + 1))
            chapter_text = self.convert_pdf_to_txt(chapterpdf).replace('\x0c', '').replace('\xa0', '')

            # save the chapters text
            with open('{}_chapter{:03d}.txt'.format(self.chapterstextprefix, i + 1), 'w') as f:
                f.write(chapter_text)

            chapters_text.append(chapter_text)

        return chapters_text

    @ staticmethod
    def convert_pdf_to_txt(filepath):
        rsrcmgr = PDFResourceManager()
        retstr = io.StringIO()
        codec = 'utf-8'
        laparams = LAParams()
        device = TextConverter(rsrcmgr, retstr, laparams=laparams)
        fp = open(filepath, 'rb')
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        password = ""
        maxpages = 0
        caching = True
        pagenos = set()

        for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages,
                                      password=password,
                                      caching=caching,
                                      check_extractable=True):
            interpreter.process_page(page)

        fp.close()
        device.close()
        text = retstr.getvalue()
        retstr.close()
        return text

    def pdf_splitter(self):
        inputfile = open(self.pdf_path, 'rb')
        pdf = PdfFileReader(inputfile)
        last_page = self.ch_page_list.pop(-1)
        # loop through each chapter start page
        for i, ch_page_num in enumerate(self.ch_page_list):
            pdf_writer = PdfFileWriter()
            end_page_num = self.ch_page_list[i+1] - 1 if not len(self.ch_page_list) == i+1 else last_page

            # loop through pages in each chapter
            for page in range(ch_page_num, end_page_num+1):
                pdf_writer.addPage(pdf.getPage(page-1))
            output_filename = '{}_chapter{}.pdf'.format(self.chapterspdfprefix, i + 1)
            with open(output_filename, 'wb') as out:
                pdf_writer.write(out)
            print('Created: {}'.format(output_filename))
        inputfile.close()


class MyDict(dict):
    def __getattr__(self, name):
        return self[name]


class MySafeConstructor(SafeConstructor):
    def construct_yaml_map(self, node):
        data = MyDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)


MySafeConstructor.add_constructor(u'tag:yaml.org,2002:map', MySafeConstructor.construct_yaml_map)


class MySafeLoader(Reader, Scanner, Parser, Composer, MySafeConstructor, Resolver):
    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        MySafeConstructor.__init__(self)
        Resolver.__init__(self)


def split_html_to_chapters(html, regex='<p><a id="chap[0-9]{2,2}"/></p>', cut=(0, 0), start_chapter=1):
    with open(html, 'r') as f:
        html_text = f.read()

    results = re.split(regex, html_text)
    cut_start = None if not cut[0] else cut[0]
    cut_end = None if not cut[1] else -cut[1]
    results = results[cut_start: cut_end]
    print(cut_start, cut_end, len(results))

    for i, result in enumerate(results):
        fn = os.path.join(os.path.dirname(html), 'chapter{:02d}.html'.format(i+start_chapter))
        with open(fn, 'w') as f:
            f.write(results[i])
