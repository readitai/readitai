from speak import speak_gwavenet, speak_tacotron2

from glob import glob
import argparse
import os
import nltk
from preprocessbook import *
# from io import BytesIO


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Ebook to Audiobook Converter w/ Realistic Speech Synthesis')
    parser.add_argument('configfile', help='yaml configuration file containing the input file path')

    args = parser.parse_args()

    config = ingest_config(args.configfile)

    if config.outputfile.use_exist_text:
        chapters_text = []
        text_dir = os.path.join(config.outputdir, 'chaptertexts')
        files = sorted(glob(text_dir + '/*.txt'), key=os.path.basename)
        for file in files:
            with open(file, 'r') as f:
                chapters_text.append(f.read())
    else:
        if config.inputfile.type == 'epub':
            epub_book = ProcessEpub(config.inputfile.path, config.outputdir, config.param_epub)
            chapters_text = epub_book.process()
        elif config.inputfile.type == 'html':
            html_book = ProcessHtml(config.inputfile.path, config.outputdir, config.param_html)
            chapters_text = html_book.process()
        elif config.inputfile.type == 'pdf':
            pdf_book = ProcessPDF(config.inputfile.path, config.outputdir, config.param_pdf)
            chapters_text = pdf_book.process()
        else:
            raise Exception("Input file type must be either epub, html file/link, or pdf.")

    if config.speech.read:
        title_ssml = '<emphasis level="strong"> {} </emphasis> ' \
                     '<break time="400ms"/> by {} ' \
                     '<break time="400ms"/> narrated by {}' \
                     '<break time="400ms"/>'.format(config.inputfile.book_name,
                                                    config.inputfile.author,
                                                    config.inputfile.narrator)
        title = '{}. by {}. narrated by {}.'.format(config.inputfile.book_name,
                                                    config.inputfile.author,
                                                    config.inputfile.narrator)

        # loop through each chapter and tts the sentences
        for i, this_chapter_text in enumerate(chapters_text):
            print('----- Chapter %d -----' % (i+1))

            sentences = nltk.tokenize.sent_tokenize(this_chapter_text)
            outputfn = os.path.join(config.outputdir_audio, '{}-Ch{:03d}.wav'.format(config.name, i+1))

            if config.speech.tech == 'gc_wavenet':
                if i == 0:  # insert title before the first chapter
                    sentences.insert(0, title_ssml)
                speak_gwavenet(sentences, speechparams=config.speech.params,
                               outputfn=outputfn, ssml=True)
            elif config.speech.tech == 'tacotron2':
                if i == 0:  # insert title before the first chapter
                    sentences.insert(0, title)
                speak_tacotron2(sentences, speechparams=config.speech.params, outputfn=outputfn)

