# (c) Ilya V. Schurov, 2016
# Available under MIT license (see LICENSE file in the root folder)

from qqmbr.qqdoc import QqTag
from yattag import Doc
from collections import namedtuple
import mistune
import re
import inspect
import hashlib
import os
import urllib.parse

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt

def mk_safe_css_ident(s):
    # see http://stackoverflow.com/a/449000/3025981 for details
    s = re.sub(r"[^a-zA-Z\d_-]", "_", s)
    if re.match(r"([^a-zA-Z]+)", s):
        m = re.match(r"([^a-zA-Z]+)", s)
        first = m.group(1)
        s = s[len(first):] + "__" + first
    return s

# FROM http://stackoverflow.com/a/14364249/3025981

def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise

# END FROM



class Counter():
    """
    Very simple class that support latex-style counters with subcounters.
    For example, if new section begins, the enumeration of subsections resets.
    If `showparents` option is set, str(counter) contains numbers of all its parents
    That's all.
    """

    def __init__(self, showparents=False):
        self.value = 0
        self.child = None
        self.parent = None
        self.showparents = showparents

    def reset(self):
        self.value = 0
        if self.child:
            self.child.reset()

    def increase(self):
        self.value += 1
        if self.child:
            self.child.reset()

    def spawn_child(self):
        self.child = Counter()
        self.child.parent = self
        return self.child

    def __str__(self):
        my_str = str(self.value)
        if self.parent and self.showparents:
            my_str = str(self.parent) + "." + my_str
        return my_str

def join_nonempty(*args, sep=" "):
    return sep.join(x for x in args if x)

Chapter = namedtuple('Chapter', ('header', 'content'))

class QqHTMLFormatter(object):

    def __init__(self, root: QqTag=None):

        self.label2number = {}
        self.label2title = {}
        self.label2tag = {}
        self.label2chapter = {}
        self.root = root
        self.counters = {}
        self.chapters = []


        self.mode = 'wholedoc'
        #: how to render the doc? the following options are available:
        #: - 'wholedoc' - the whole document on one page
        #: - 'bychapters' - every chapter on its own page

        self.counters['h1'] = Counter()
        self.counters['h2'] = self.counters['h1'].spawn_child()
        self.counters['h3'] = self.counters['h2'].spawn_child()
        self.counters['h4'] = self.counters['h3'].spawn_child()

        self.counters['equation'] = self.counters['h1'].spawn_child()
        self.counters['figure'] = self.counters['h1'].spawn_child()

        self.enumerateable_envs = {name: name.capitalize() for name in ['remark', 'theorem', 'example', 'exercise',
                                                                     'definition', 'proposition', 'lemma']}

        # You can make self.localnames = {} to use plain English localization

        self.localnames = {
            'Remark': 'Замечание',
            'Theorem': 'Теорема',
            'Example': 'Пример',
            'Exercise': 'Упражнение',
            'Definition': 'Определение',
            'Proposition': 'Утверждение',
            'Lemma': 'Лемма',
            'Proof': 'Доказательство',
            'Proof outline': 'Набросок доказательства',
            'Figure': 'Рисунок',
            'Fig.': "Рис."
        }

        self.formulaenvs = {'eq', 'equation'}

        enum_envs_counter = self.counters['h1'].spawn_child()

        for env in self.enumerateable_envs:
            self.counters[env] = enum_envs_counter

        mistune_renderer = mistune.Renderer(escape=False)
        self.markdown = mistune.Markdown(renderer=mistune_renderer)
        self.figures_dir = "fig"

        self.figures_prefix = "/fig/"
        #: prefix for urls to figures_dir

        self.default_figname = "fig"

        plt.rcParams['figure.figsize'] = (6, 4)

        self.pythonfigure_globals = {'plt': plt}



    def make_python_fig(self, code: str, exts=('pdf', 'svg'), tight_layout=True):
        if isinstance(exts, str):
            exts = (exts, )
        hashsum = hashlib.md5(code.encode('utf8')).hexdigest()
        prefix = hashsum[:2]
        path = os.path.join(self.figures_dir, prefix, hashsum)
        needfigure = False
        for ext in exts:
            if not os.path.isfile(os.path.join(path, self.default_figname + "." + ext)):
                needfigure = True
                break

        if needfigure:
            make_sure_path_exists(path)
            loc = {}
            gl = self.pythonfigure_globals
            exec(code, gl, loc)
            if tight_layout:
                plt.tight_layout()
            for ext in exts:
                plt.savefig(os.path.join(path, self.default_figname + "." + ext))
        return os.path.join(prefix, hashsum)


    def uses_tags(self):
        members = inspect.getmembers(self, predicate=inspect.ismethod)
        handles = [member for member in members if member[0].startswith("handle_") or member[0] == 'preprocess']
        alltags = set([])
        for handle in handles:
            if handle[0].startswith("handle_"):
                alltags.add(handle[0][len("handle_"):])
            doc = handle[1].__doc__
            if not doc:
                continue
            for line in doc.splitlines():
                m = re.search(r"Uses tags:(.+)", line)
                if m:
                    tags = m.group(1).split(",")
                    tags = [tag.strip() for tag in tags]
                    alltags.update(tags)
        alltags.update(self.enumerateable_envs.keys())
        return alltags

    def localize(self, s):
        return self.localnames.get(s, s)

    def handle(self, tag):
        name = tag.name
        default_handler = 'handle_'+name
        if re.match(r"h\d$",name):
            return self.handle_h(tag)
        elif name in self.enumerateable_envs:
            return self.handle_enumerateable(tag)
        elif hasattr(self, default_handler):
            return getattr(self, default_handler)(tag)
        else:
            return ""

    def safe_markdown(self, s):
        #    print("Got line: " + s)
        #    print("-----")
        m = re.match(r"(\s*).*\S(\s*)", s)
        if m:
            pre, post = m.groups()
        else:
            pre = post = ""

        chunk = self.markdown(s)
        r = re.compile(r"<p>(.+)</p>$", re.DOTALL)
        m = re.match(r, chunk)
        if m:
            chunk = m.group(1)
        chunk = pre + chunk + post
        #    print("Return line: " + chunk)
        #    print("------")
        return chunk

    def label2id(self, label):
        return "label_" + mk_safe_css_ident(label.strip())

    def format(self, content, markdown = False) -> str:
        """

        :param content: could be QqTag or any iterable of QqTags
        :param markdown: use markdown (True or False)
        :return: str: text of tag
        """
        if content is None:
            return ""

        out = []

        for child in content:
            if isinstance(child, str):
                if markdown:
                    # Preserve whitespaces (markdown will remove it)
                    out.append(self.safe_markdown(child))
                else:
                    out.append(child)
            else:
                out.append(self.handle(child))
        return "".join(out)

    def handle_h(self, tag: QqTag) -> str:
        """
        Uses tags: h1, h2, h3, h4, label, number

        :param tag:
        :return:
        """
        doc, html, text = Doc().tagtext()
        with html(tag.name):
            doc.attr(id=self.h_id(tag))
            if tag.find("number"):
                with html("span", klass="section__number"):
                    text(tag._number.value + ". ")
            text(self.format(tag))
        ret = doc.getvalue()
        if tag.next() and isinstance(tag.next(), str):
            ret += "<p>"
        return doc.getvalue()


    def handle_eq(self, tag: QqTag) -> str:
        """
        :param tag:
        :return:
        """
        doc, html, text = Doc().tagtext()
        with html("div", klass="latex_eq"):
            text("\\[\n")
            text(self.format(tag))
            text("\\]\n")
        return doc.getvalue()

    def handle_equation(self, tag: QqTag) -> str:
        """
        Uses tags: equation, number, label

        :param tag:
        :return:
        """
        doc, html, text = Doc().tagtext()
        with html("div", klass="latex_equation"):
            text("\\[\n")
            text("\\begin{equation}\n")
            if tag.find('number'):
                text("\\tag{{{}}}\n".format(tag._number.value))
            if tag.find('label'):
                doc.attr(id=self.label2id(tag._label.value))
            text(self.format(tag))
            text("\\end{equation}\n")
            text("\\]\n")
        return doc.getvalue()

    def handle_ref(self, tag: QqTag):
        """
        :param tag:
        :return:
        """
        doc, html, text = Doc().tagtext()
        label = tag.value.strip()
        number = self.label2number.get(label, "???")
        target = self.label2tag[label]
        href = ""
        if self.mode == 'bychapters':
            if self.tag2chapter(tag) != self.tag2chapter(target):
                href = self.url_for_chapter(self.tag2chapter(target))

        href += "#"+self.label2id(label)

        with html("span", klass="ref"):
            with html("a", klass="a-ref", href=href,
                      title=self.label2title.get(label, "")):
                if self.label2tag.get(label) and self.label2tag[label].name in self.formulaenvs:
                    text("(" + number + ")")
                else:
                    text(number)
        return doc.getvalue()

    def handle_eqref(self, tag: QqTag) -> str:
        """
        Alias to handle_ref

        Refs to formulas are ALWAYS in parenthesis

        :param tag:
        :return:
        """
        return self.handle_ref(tag)

    def handle_enumerateable(self, tag):
        """
        Uses tags: label, number, name
        Add tags used manually from enumerateable_envs

        :param tag:
        :return:
        """
        doc, html, text = Doc().tagtext()
        name = tag.name
        env_localname = self.localize(self.enumerateable_envs[name])
        with html("div", klass="env env__" + name):
            if tag.find("label"):
                doc.attr(id=self.label2id(tag._label.value))

            number = tag.get("number", "")
            with html("span", klass="env-title env-title__" + name):
                text(join_nonempty(env_localname, number) + ".")

            doc.asis(" "+self.format(tag, markdown = True))
        return "<p>"+doc.getvalue()+"</p>\n<p>"

    def handle_proof(self, tag: QqTag) -> str:
        """
        Uses tags: proof, label, outline, of
        :param tag:
        :return: HTML of proof
        """
        doc, html, text = Doc().tagtext()
        with html("div", klass="env env__proof"):
            if tag.find("label"):
                doc.attr(id=self.label2id(tag._label.value))
            with html("span", klass="env-title env-title__proof"):
                if tag.exists("outline"):
                    proofline = 'Proof outline'
                else:
                    proofline = 'Proof'
                doc.asis(join_nonempty(self.localize(proofline),
                                       self.format(tag.find("of")))+".")
            doc.asis(" "+self.format(tag, markdown = True))
            doc.asis("&#8718;")
        return doc.getvalue()+"\n<p>"

    def handle_paragraph(self, tag: QqTag):
        """
        :param tag:
        :return:
        """
        doc, html, text = Doc().tagtext()
        with html("span", klass="paragraph"):
            doc.asis(self.format(tag, markdown = True)+".")
        return "<p>" + doc.getvalue()+" "

    def handle_figure(self, tag: QqTag) -> str:
        """
        Currently, only python-generated figures are supported.

        Synopsis:

        \figure \label fig:figure
            \pythonfigure
                plt.plot([1, 2, 3], [1, 4, 9])
            \caption
                Some figure

        Uses tags: figure, label, pythonfigure, caption, number

        :param tag: QqTag
        :return: HTML of figure
        """
        doc, html, text = Doc().tagtext()
        with html("div", klass="figure"):
            if tag.find("label"):
                doc.attr(id=self.label2id(tag._label.value))
            for child in tag:
                if child.name == 'pythonfigure':
                    path = self.make_python_fig(child.text_content, exts=("svg"))
                    with html("img", klass="figure", src=self.figures_prefix + path + "/" + self.default_figname + ".svg"):
                        pass
                elif child.name == 'caption':
                    with html("div", klass="figure_caption"):
                        text(join_nonempty(self.localize("Fig."), tag.get("number"))+": ")
                        doc.asis(self.format(child, markdown=True))
        return doc.getvalue()

    def handle_snippet(self, tag: QqTag) -> str:
        """
        :param tag:
        :return:
        """
        return self.format(tag, markdown=True)

    def handle_hide(self, tag: QqTag) -> str:
        """
        :param tag:
        :return:
        """
        return ""

    def preprocess(self, root: QqTag):
        """
        Uses tags: number, label, nonumber

        :return:
        """
        for tag in root:
            if isinstance(tag, QqTag):
                name = tag.name
                if (name in self.counters or name in self.enumerateable_envs) and not (tag.find('number') or
                                                                                           tag.exists('nonumber')):
                    counter = self.counters[name]
                    counter.increase()
                    tag.append_child(QqTag({'number': str(counter)}))
                    if tag.find('label'):
                        label = tag._label.value.strip()
                        self.label2number[label] = str(counter)
                        self.label2title[label] = tag.text_content
                if tag.find('label') and tag.find('number'):
                    self.label2number[tag._label.value.strip()] = tag._number.value
                if tag.find('label'):
                    self.label2tag[tag._label.value.strip()] = tag
                self.preprocess(tag)


    def mk_chapters(self):
        curchapter = Chapter(QqTag("_zero_chapter"),  [])
        self.chapters = []
        for tag in self.root:
            if isinstance(tag, QqTag) and tag.name == 'h1':
                self.add_chapter(curchapter)
                curchapter = Chapter(tag, [])
            curchapter.content.append(tag)
        self.add_chapter(curchapter)

    def tag2chapter(self, tag) -> int:
        """
        Returns the number of chapter to which tag belongs.

        Chapters are separated by `h1` tag. Chapter before the first `h1` tag has number zero.

        :param tag:
        :return:
        """

        granny = tag.get_granny()
        headers = self.root("h1")
        i = 0
        for i, header in enumerate(headers, 1):
            if granny.my_index < header.my_index:
                return i - 1
        return i

    def url_for_chapter(self, index=None, label=None) -> str:
        assert index is not None or label is not None
        if index:
            label = self.chapters[index].header.find("label")
            if not label:
                return "/chapter/index/" + urllib.parse.quote(str(index))
        return "/chapter/label/" + urllib.parse.quote(label.value.strip())

    def add_chapter(self, chapter):
        if chapter.header.find("label"):
            self.label2chapter[chapter.header._label.value] = len(self.chapters)
        self.chapters.append(chapter)


    def do_format(self):
        self.preprocess(self.root)
        return self.format(self.root, markdown=True)

    def h_id(self, tag) -> str:
        """
        Returns id of h:
        - If it has label, it is label-based
        - If it does not have label, but have number (which is true after preprocess for all h's), it is number-based
        :param tag:
        :return: str id
        """
        if tag.find("label"):
            return self.label2id(tag._label.value)
        elif tag.find("number"):
            return self.label2id(tag.name+"_number_"+str(tag._number.value))
        else:
            return ""

    def mk_toc(self, maxlevel=2, chapter = None) -> str:
        """
        Makes TOC (Table Of Contents)

        :param maxlevel: maximum heading level to include to TOC (default: 2)
        :param chapter: if None, we assume to have whole document on the same page and TOC contains only local links.
        If present, it is equal to index of current chapter
        :return: str with HTML content of TOC
        """
        doc, html, text = Doc().tagtext()
        curlevel = 1

        curchapter = 0
        # chapter before first h1 has index 0

        with html("ul", klass="nav"):
            for child in self.root:
                chunk = []
                if isinstance(child, QqTag):
                    m = re.match(r'h(\d)', child.name)
                    if m:
                        hlevel = int(m.group(1))

                        # h1 header marks new chapter, so increase curchapter counter
                        if hlevel == 1:
                            curchapter += 1

                        if hlevel > maxlevel:
                            continue
                        while hlevel > curlevel:
                            chunk.append("<li><ul class='nav'>\n")
                            curlevel += 1
                        while hlevel < curlevel:
                            chunk.append("</ul></li>\n")
                            curlevel -= 1

                        targetpage = ""
                        if chapter is not None and curchapter != chapter:
                            targetpage = self.url_for_chapter(index=curchapter)

                        item_doc, item_html, item_text = Doc().tagtext()
                        with item_html("li", klass = "toc_item toc_item_level_%i" % curlevel):
                            with item_html("a", href=targetpage+"#"+self.h_id(child)):
                                item_text(self.format(child))
                        chunk.append(item_doc.getvalue())
                        doc.asis("".join(chunk))
        return doc.getvalue()





