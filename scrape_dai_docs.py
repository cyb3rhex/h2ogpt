import contextlib
import json
import os
import shutil

from docutils import core


def parse_rst_file(filepath):
    with open(filepath, 'r') as f:
        input_data = f.read()
    settings_overrides = {'initial_header_level': 2}
    document = core.publish_doctree(
        source=input_data,
        source_path=filepath,
        settings_overrides=settings_overrides,
    )
    qa_pairs = []
    current_section = None
    current_question = ""
    current_answer = ""
    for node in document.traverse():
        if node.__class__.__name__ == 'section':
            current_section = ""
        elif current_section is not None:
            if node.__class__.__name__ == 'Text':
                if node.astext()[-1] == "?":
                    if current_question:
                        qa_pairs.append((current_question, current_answer))
                    current_question = node.astext()
                    current_answer = ""
                else:
                    current_answer += node.astext()
    if current_answer:
        qa_pairs.append((current_question, current_answer))
    return {k: v for k, v in qa_pairs}


def test_scrape_dai_docs():
    file = "/home/arno/h2oai/docs/faq.rst"
    qa_pairs = parse_rst_file(file)
    save_thing = [{"instruction": k, "output": v} for k, v in qa_pairs.items()]
    output_file = "dai_faq.json"
    with open(output_file, "wt") as f:
        f.write(json.dumps(save_thing, indent=2))


def test_scrape_dai_docs_all():
    """
    pytest scrape_dai_docs.py::test_scrape_dai_docs_all
    """
    import numpy as np
    import glob
    import nltk
    nltk.download('punkt')
    dd = {}
    np.random.seed(1234)
    home = os.path.expanduser('~')
    files = list(glob.glob(os.path.join(home, "h2oai/docs/**/*rst")))
    np.random.shuffle(files)
    val_count = int(0.05 * len(files))
    train_files = files[val_count:]
    valid_files = files[:val_count]
    things = [
        ("dai_docs.train.json", train_files),
        ("dai_docs.valid.json", valid_files)
    ]
    for LEN in [100, 200, 500]:
        for output_file, ff in things:
            if output_file not in dd:
                dd[output_file] = []
            for f in ff:
                with open(f) as input:
                    blob = input.read()
                    blob = blob.replace("~~", "")
                    blob = blob.replace("==", "")
                    blob = blob.replace("''", "")
                    blob = blob.replace("--", "")
                    blob = blob.replace("**", "")
                    dd[output_file].extend(get_sentences(blob, length=LEN))
    for output_file, _ in things:
        save_thing = [{"output": k} for k in dd[output_file]]
        with open(output_file, "wt") as f:
            f.write(json.dumps(save_thing, indent=2))


def get_sentences(blob, length):
    """
    break-up input text into sentences and then output list of sentences of about length in size
    :param blob:
    :param length:
    :return:
    """
    from nltk.tokenize import sent_tokenize
    sentences = sent_tokenize(blob)
    my_sentences = []
    my_string = ""
    for sentence in sentences:
        if len(my_string) < length:
            my_string += " " + sentence
        else:
            my_sentences.append(my_string)
            my_string = ""
    return my_sentences


def test_scrape_dai_docs_all_pandoc():
    """
    pytest scrape_dai_docs.py::test_scrape_dai_docs_all_pandoc
    :return:
    """
    home = os.path.expanduser('~')
    import glob
    files = list(glob.glob(os.path.join(home, "h2oai/docs/**/*"), recursive=True))

    # pandoc can't find include files
    dst = "working_dir_docs"
    remove(dst)
    os.makedirs(dst)
    for fil in files:
        if os.path.isfile(fil):
            shutil.copy(fil, dst)
    files = list(glob.glob(os.path.join(dst, '*rst'), recursive=True))

    # os.system('pandoc -f rst -t plain ./expert_settings/nlp_settings.rst')
    import pypandoc
    outputs = []
    basedir = os.path.abspath(os.getcwd())
    for fil in files:
        os.chdir(basedir)
        os.chdir(os.path.dirname(fil))
        fil = os.path.basename(fil)
        print("Processing %s" % fil, flush=True)
        # out_format can be one of: asciidoc, asciidoctor, beamer, biblatex, bibtex, commonmark, commonmark_x,
        # context, csljson, docbook, docbook4, docbook5, docx, dokuwiki,
        # dzslides, epub, epub2, epub3, fb2, gfm, haddock, html, html4, html5, icml,
        # ipynb, jats, jats_archiving, jats_articleauthoring, jats_publishing, jira,
        # json, latex, man,
        # markdown, markdown_github, markdown_mmd, markdown_phpextra, markdown_strict,
        # mediawiki, ms, muse, native, odt, opendocument, opml, org, pdf, plain, pptx,
        # revealjs, rst, rtf, s5, slideous, slidy, tei, texinfo, textile, xwiki, zimwiki
        out_format = 'plain'
        # avoid extra new lines injected into text
        extra_args = ['--wrap=preserve', '--resource path="%s" % dst']

        plain_list = []
        try:
            # valid for expert settings
            input_rst = pypandoc.convert_file(fil, 'rst')
            input_list = input_rst.split('\n``')
            for input_subrst in input_list:
                input_plain = pypandoc.convert_text(input_subrst, format='rst', to='plain')
                plain_list.append(input_plain)
        except Exception as e:
            print("file exception: %s %s" % (fil, str(e)), flush=True)

        if not plain_list:
            LEN = 100
            # if failed to process as pieces of rst, then
            output = pypandoc.convert_file(fil, out_format, extra_args=extra_args, format='rst')
            outputs = get_sentences(output, length=LEN)
            for oi, output in enumerate(outputs):
                output = output.replace('\n\n', '\n')
                plain_list.append(output)
        outputs.extend(plain_list)

    os.chdir(basedir)
    remove(dst)
    MIN_LENGTH = 30  # to avoid bare headers
    save_thing = [{"output": k} for k in outputs if len(k) > MIN_LENGTH]
    output_file = "dai_docs.train_cleaned.json"
    with open(output_file, "wt") as f:
        f.write(json.dumps(save_thing, indent=2))


def remove(path: str):
    try:
        if path is not None and os.path.exists(path):
            if os.path.isdir(path):
                shutil_rmtree(path, ignore_errors=True)
            else:
                with contextlib.suppress(FileNotFoundError):
                    os.remove(path)
    except:
        pass


def shutil_rmtree(*args, **kwargs):
    path = args[0]
    return shutil.rmtree(*args, **kwargs)
