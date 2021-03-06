# (c) Ilya V. Schurov, 2016
# Available under MIT license (see LICENSE file in the root folder)


import sys
import os
import xml.etree.ElementTree as et

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'indentml'))

from parser import QqTag, QqParser
from textwrap import dedent
# from qqmbr.indexedlist import IndexedList

import unittest
class TestQqTagMethods(unittest.TestCase):
    def test_create_qqtag(self):
        q = QqTag({'a': 'b'})
        self.assertEqual(q.name, 'a')
        self.assertEqual(q.value, 'b')

        q = QqTag('a', [
            QqTag('b', 'hello'),
            QqTag('c', 'world'),
            QqTag('b', 'this'),
            QqTag('--+-', [
                QqTag('b', 'way'),
                "this"
            ])])

        self.assertEqual(q.name, 'a')
        # self.assertEqual(q._children, IndexedList([QqTag('b', ['hello']), QqTag('c', ['world']), QqTag('b', ['this']),
        #                                           QqTag('--+-', [QqTag('b', ['way']), 'this'])]))
        # self.assertEqual(eval(repr(q)), q)
        self.assertEqual(q.as_list(),
                         ['a', ['b', 'hello'], ['c', 'world'],
                          ['b', 'this'], ['--+-', ['b', 'way'], 'this']])

    def test_qqtag_accessors(self):
        q = QqTag('a', [
            QqTag('b', 'hello'),
            QqTag('c', 'world'),
            QqTag('b', 'this'),
            QqTag('--+-', [
                QqTag('b', 'way'),
                "this"
            ])])

        self.assertEqual(q.b_.value, 'hello')
        self.assertEqual(q.c_.value, 'world')
        self.assertEqual([b.as_list() for b in q('b')], [['b', 'hello'],
                                                         ['b', 'this']])
        self.assertEqual(q.find('--+-').b_.value, 'way')
        self.assertEqual(q[0].value, 'hello')
        self.assertEqual(q[1].value, 'world')
        self.assertEqual(q[3][0].value, 'way')

    def test_qqtag_backlinks(self):
        q = QqTag('a', [
            QqTag('b', 'hello'),
            QqTag('c', 'world'),
            QqTag('b', 'this'),
            QqTag('--+-', [
                QqTag('b', 'way'),
                "this"
            ])])
        self.assertTrue(q._is_consistent())
        new_tag = QqTag({'qqq' : 'bbb'})
        q.append_child(new_tag)
        self.assertEqual(new_tag.idx, 4)
        del q[0]
        self.assertEqual(new_tag.idx, 3)
        self.assertTrue(q._is_consistent())

        other_tag = QqTag({'other': ['some', 'values']})
        q.insert(2, other_tag)
        self.assertEqual(other_tag.idx, 2)
        self.assertEqual(new_tag.idx, 4)

        third_tag = QqTag({'this': 'hi'})
        q[3] = third_tag
        self.assertEqual(third_tag.idx, 3)
        self.assertTrue(q._is_consistent())

    def test_qqtag_prev_next(self):
        q = QqTag('a', [
            QqTag('b', 'hello'),
            QqTag('c', 'world'),
            QqTag('b', 'this'),
            QqTag('--+-', [
                QqTag('b', 'way'),
                "this"
            ])])

        self.assertEqual(q.c_.prev().value, 'hello')
        self.assertEqual(q.b_.next().value, 'world')
        self.assertEqual(q.c_.next().value, 'this')

    def test_qqtag_insert(self):
        z = QqTag("z")
        w = QqTag("w")
        q = QqTag('a', [
            "Hello",
            "World",
            z,
            "This"])
        self.assertEqual(q[2], z)
        q.insert(0, w)
        self.assertEqual(q[0], w)
        self.assertEqual(q[3], z)
        self.assertEqual(q[3].idx, 3)
        self.assertTrue(q._is_consistent())

    def test_qqtag_del(self):
        z = QqTag("z")
        w = QqTag("w")
        q = QqTag('a', [
            "Hello",
            "World",
            z,
            "This",
            w
        ])
        del q[2]
        self.assertTrue(q._is_consistent())
        self.assertEqual(q[3], w)
        self.assertEqual(q[3].idx, 3)
        self.assertEqual(q.as_list(),
                         ["a", "Hello", "World", "This", ["w"]])


class TestQqParser(unittest.TestCase):
    def test_block_tags1(self):
        doc = r"""Hello
\tag
    World
"""
        parser = QqParser(allowed_tags={'tag'})
        tree = parser.parse(doc)
        print(tree.as_list())
        self.assertEqual(tree[0], "Hello")

        self.assertEqual(tree.tag_.name, 'tag')
        self.assertEqual(tree.tag_.value, 'World')


    def test_block_tags_nested(self):
        doc = r"""Hello
\tag
    World
    \othertag
        This
        Is
    A test
The end

Blank line before the end
"""
        parser = QqParser(allowed_tags={'tag', 'othertag'})
        tree = parser.parse(doc)
        print(tree.as_list())
        self.assertEqual(tree[0], "Hello")
        self.assertEqual(tree.tag_[0], "World")
        self.assertEqual(tree.tag_.othertag_._children, ["This\nIs"])
        self.assertEqual(tree.tag_[2], 'A test')
        self.assertEqual(tree[2], 'The end\n\nBlank line before the end')
        self.assertEqual(tree.tag_.parent, tree)
        self.assertEqual(tree.tag_.othertag_.parent, tree.tag_)

    def test_block_additional_indent(self):
        doc = r"""Hello
\tag
    First
        Second
    Third
End"""
        parser = QqParser(allowed_tags={'tag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.tag_._children,
                         ['First\n    Second\nThird'])

    def test_match_bracket(self):
        doc = dedent("""\
            hello { world {
                some test } {
                okay { }
            this is a test }} test
        """)
        parser = QqParser()
        parser.parse_init(doc)
        start = parser.position(0, 6)
        stop = parser.position(None, 0)
        out = parser.match_bracket(start, stop)
        self.assertEqual(out.clipped_line(stop),
                         "} test\n")

    def test_inline_tag_contents(self):
        doc = dedent("""\
                    haha \\tag{this}{
                        that}[another]{this
                        }[okay test] stop
                """)
        parser = QqParser(allowed_tags={"tag"})
        parser.parse_init(doc)
        start = parser.position(0, 0)
        stop = parser.position(None, 0)
        tag_position, tag, type, after = parser.locate_tag(start, stop)
        self.assertEqual(start.clipped_line(tag_position), "haha ")
        self.assertEqual(tag, "tag")
        self.assertEqual(type, "inline")

        items = parser.inline_tag_contents(after, stop)
        contents = ["".join(item['start'].lines_before(item['stop']))
                    for item in items]
        self.assertEqual(contents,
                         ["this", "\n    that",
                          "another", "this\n    ", "okay test"])
        self.assertEqual([item['type'] for item in items],
                         ['{', '{', '[', '{', '['])

    def test_scan_after_attribute_tag(self):
        doc = dedent("""\
                        test \\tag this \\tag{inline \\tag{} \\tag}q \\tag
                        other tag
                        """)
        parser = QqParser(allowed_tags={"tag"})
        parser.parse_init(doc)
        start = parser.position(0, 0)
        stop = parser.position(None, 0)
        tag_position, tag, type, after = parser.locate_tag(start, stop)

        start = after.copy()
        before = parser.scan_after_attribute_tag(start, stop)
        self.assertEqual(start.clipped_line(before),
                         'this \\tag{inline \\tag{} \\tag}q ')

    def test_scan_after_attribute_tag2(self):
        doc = dedent("""\
                        test \\tag this \\tag{inline \\tag{} \\tag}\\tag
                        other tag
                        """)
        parser = QqParser(allowed_tags={"tag"})
        parser.parse_init(doc)
        start = parser.position(0, 0)
        stop = parser.position(None, 0)
        tag_positoin, tag, type, after = parser.locate_tag(start, stop)

        start = after.copy()
        before = parser.scan_after_attribute_tag(start, stop)
        self.assertEqual(start.clipped_line(before),
                         'this \\tag{inline \\tag{} \\tag}')

    def test_inline_tag1(self):
        doc = r"""Hello, \tag{inline} tag!
"""
        parser = QqParser(allowed_tags={'tag'})
        tree = parser.parse(doc)
        self.assertEqual(tree[0], 'Hello, ')
        self.assertEqual(tree.tag_.value, 'inline')
        self.assertEqual(tree[2], ' tag!')

    def test_inline_tag2(self):
        doc = r"""Hello, \othertag{\tag{inline} tag}!
"""
        parser = QqParser(allowed_tags={'tag', 'othertag'})
        tree = parser.parse(doc)
       # self.assertEqual(tree._othertag._tag.value, 'inline')
        self.assertEqual(tree.as_list(), ['_root', 'Hello, ',
                                          ['othertag', ['tag', 'inline'],
                                           ' tag'], '!'])

    def test_inline_tag3(self):
        doc = r"""Hello, \tag{
this is a continuation of inline tag on the next line

the next one\othertag{okay}}
"""
        parser = QqParser(allowed_tags={'tag', 'othertag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(), [
            '_root', 'Hello, ',
            [
                'tag',
                ('\nthis is a continuation of inline tag on the next line'
                 '\n\nthe next one'),
                [
                    'othertag',
                    'okay'
                ]
            ], ''
        ])

    def test_inline_tag4(self):
        doc = r"Hello, \tag{I'm [your{taggy}] tag} okay"
        parser = QqParser(allowed_tags={'tag', 'othertag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(), [
            '_root', 'Hello, ',
            [
                'tag',
                "I'm [your{taggy}] tag"
            ],
            " okay"
        ])

        def test_block_and_inline_tags(self):
            doc = r"""Hello,
    \tag
        I'm your \othertag{tag}
        \tag
            {
            \tag
                {
                this \tag{is a {a test}
                okay}
            }
        }
    """
            parser = QqParser(allowed_tags={'tag', 'othertag'})
            tree = parser.parse(doc)
            self.assertEqual(tree.as_list(), [
                '_root', 'Hello,\n',
                [
                    'tag',
                    "I'm your ",
                    ['othertag', 'tag'],
                    '\n',
                    [
                        'tag',
                        '{\n',
                        [
                            'tag',
                            '{\nthis ',
                            [
                                'tag',
                                'is a {a test}\nokay',
                            ],
                            '\n'
                        ],
                        '}\n'
                    ],
                    '}\n'
                ]
            ])

    def test_sameline_tags(self):
        self.maxDiff = None
        doc = r"""    Hello!
    \h1 Intro to qqmbr

    \h2 Fresh documentation system

    **qqmbr** is a documentation system intended to be extremely simple and extremely extensible.
    It was written to allow writing rich content that can be compiled into different formats.
    One source, multiple media: HTML, XML, LaTeX, PDF, eBooks, any other. Look below to see it in action.

    \h3 This is nice level-3 header

    Some paragraph text. See also \ref{sec:another} (reference to different header).

    There are LaTeX formulas here:

    \eq
        x^2 + y^2 = z^2

    `\\eq` is a qqtag. It is better than tag, because it is auto-closing (look at the indent, like Python).

    Here is formula with the label:

    \equation \label eq:Fermat
        x^n + y^n = z^n, \quad n>2

    Several formulas with labels:

    \gather
        \item \label eq:2x2
            2\times 2 = 4
        \item \label eq:3x3
            3\times 3 = 9

    We can reference formula \eqref{eq:Fermat} and \eqref{eq:2x2} just like we referenced header before.

    \h3 Another level-3 header \label sec:another

    Here is the header we referenced.

    \h3 More interesting content

    \figure
        \source http://example.com/somefig.png
        \caption Some figure
        \width 500px

    \question
        Do you like qqmbr?
        \quiz
            \choice \correct false
                No.
                \comment You didn't even try!
            \choice \correct true
                Yes, i like it very much!
                \comment And so do I!
"""
        parser = QqParser(
            allowed_tags={'h1', 'h2', 'h3', 'eq', 'equation', 'label',
                          'gather', 'inlne', 'item', 'ref', 'eqref',
                          'source', 'caption', 'width', 'question',
                          'quiz', 'choice',
                          'comment', 'correct', 'figure'})
        tree = parser.parse(doc)
        print(tree.as_list())
        self.assertEqual(tree.as_list(), ['_root',
                                          'Hello!',
                                          ['h1', 'Intro to qqmbr'],
                                          '',
                                          ['h2',
                                           'Fresh documentation system'],
                                          '\n**qqmbr** is a documentation system intended to be extremely simple and extremely extensible.\nIt was written to allow writing rich content that can be compiled into different formats.\nOne source, multiple media: HTML, XML, LaTeX, PDF, eBooks, any other. Look below to see it in action.\n',
                                          ['h3',
                                           'This is nice level-3 header'],
                                          '\nSome paragraph text. See also ',
                                          ['ref', 'sec:another'],
                                          ' (reference to different header).\n\nThere are LaTeX formulas here:\n',
                                          ['eq',
                                           'x^2 + y^2 = z^2'],
                                          '\n`\\eq` is a qqtag. It is better than tag, because it is auto-closing (look at the indent, like Python).\n\nHere is formula with the label:\n',
                                          ['equation',
                                           ['label', 'eq:Fermat'],
                                           'x^n + y^n = z^n, \\quad n>2'],
                                          '\nSeveral formulas with labels:\n',
                                          ['gather',
                                           ['item',
                                            ['label', 'eq:2x2'],
                                            '2\\times 2 = 4'],
                                           ['item',
                                            ['label', 'eq:3x3'],
                                            '3\\times 3 = 9']],
                                          '\nWe can reference formula ',
                                          ['eqref', 'eq:Fermat'],
                                          ' and ',
                                          ['eqref', 'eq:2x2'],
                                          ' just like we referenced header before.\n',
                                          ['h3',
                                           'Another level-3 header ',
                                           ['label',
                                            'sec:another']],
                                          '\nHere is the header we referenced.\n',
                                          ['h3',
                                           'More interesting content'],
                                          '',
                                          ['figure',
                                           ['source',
                                            'http://example.com/somefig.png'],
                                           ['caption',
                                            'Some figure'],
                                           ['width', '500px']],
                                          '',
                                          ['question',
                                           'Do you like qqmbr?',
                                           ['quiz',
                                            ['choice',
                                             ['correct', 'false'],
                                             'No.',
                                             ['comment',
                                              "You didn't even try!"]],
                                            ['choice',
                                             ['correct', 'true'],
                                             'Yes, i like it very much!',
                                             ['comment',
                                              'And so do I!']]]]])

    def test_inline_tag_at_the_beginning_of_the_line(self):
        doc = r"""\tag
    some content here here and here and we have some inline
    \tag{here and \othertag{there}}
    """
        parser = QqParser(allowed_tags={'tag', 'othertag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(), ['_root', ['tag','some content '
                                                          'here here and '
                                                          'here and we '
                                                          'have some '
                                                          'inline\n',
                                          ['tag', 'here and ',['othertag',
                                                               'there']],
                                                    '']])

    def test_alias2tag(self):
        doc = r"""\# Heading 1
\## Heading 2
Hello
"""
        parser = QqParser(allowed_tags={'h1', 'h2'},
                          alias2tag={"#": 'h1', "##": 'h2'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         ["_root", ["h1", "Heading 1"],
                          ["h2", "Heading 2"], "Hello"])

    def test_non_allowed_tag_with_bracket(self):
        doc = r"""Hello \inlinetag{some \forbiddentag{here} okay} this"""
        parser = QqParser(allowed_tags={'inlinetag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(), ["_root", "Hello ", ["inlinetag", "some \\forbiddentag{here} okay"], " this"])

    def test_escape_unescape(self):
        doc = r"""Hello
\sometag test
\\sometag test
\sometag
    \ here we are
    we are here
some \inline{tag with \{ curve bracket inside} okay
some \inline[square bracket \[ inside] okay
"""
        parser = QqParser(allowed_tags={'sometag', 'inline'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(), [
            "_root", "Hello",
            ["sometag", "test"],
            "\\sometag test",
            ["sometag", " here we are\nwe are here"],
            "some ",
            ["inline", "tag with { curve bracket inside"],
            " okay\nsome ",
            ["inline",
             ["_item", "square bracket [ inside"]],
            " okay"
        ])

    def test_square_bracket_inline(self):
        doc = r"Some inline \tag[with][multiple][arguments]"
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         [
                             "_root", "Some inline ",
                             ["tag",
                              ["_item", "with"],
                              ["_item", "multiple"],
                              ["_item", "arguments"]
                             ]
                         ])

    def test_mixed_brackets_inline(self):
        doc = r"Some inline \tag[with]{multiple}[arguments]"
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         [
                             "_root", "Some inline ",
                             ["tag",
                              ["_item", "with"],
                              "multiple",
                              ["_item", "arguments"]
                              ]
                         ])

    def test_multiline_inline_with_attribute(self):
        doc = "\\tag{hello \\tag world \n this is \n a \\tag test}"
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         ['_root',
                          ['tag', 'hello ',
                           ['tag', 'world \n this is \n a'],
                           ['tag', 'test']]])

    def test_multiple_arguments2(self):
        doc = r"""\proof
    By \ref[existence
    and uniqueness theorem\nonumber][thm:4:eu] there exists
"""
        parser = QqParser(allowed_tags={"proof", "ref", "nonumber"})
        tree = parser.parse(doc)
        print(tree.as_list())
        self.assertEqual(tree.as_list(),
                         ['_root', ['proof', 'By ',
                                    ['ref',
                                     ['_item',
                                      'existence\nand uniqueness theorem',
                                      ['nonumber']],
                                     ['_item',
                                      'thm:4:eu']],
                                    ' there exists']])

    def test_empty_square_bracket_tag(self):
        doc = r"""\blocktag
    Some \empty[

    ] tag
"""
        parser = QqParser(allowed_tags={'blocktag', 'empty'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),["_root", ['blocktag', 'Some ',
                                                   ['empty',
                                                    ['_item', '\n']],
                                                   ' tag']])

    def test_blocktag_inside_inlinetag(self):
        doc = r"""\blocktag Some \inlinetag[Hello \blocktag test]"""
        parser = QqParser(allowed_tags={'inlinetag', 'blocktag'})
        tree = parser.parse(doc)

        self.assertEqual(tree.as_list(), ['_root', ['blocktag', 'Some ',
                                          ['inlinetag',
                                           ['_item', 'Hello ',
                                            ['blocktag', 'test']]]]])

        doc = r"""Some \inlinetag[Hello \blocktag test
        \blocktag another test]"""
        parser = QqParser(allowed_tags={'inlinetag', 'blocktag'})
        tree = parser.parse(doc)
        print(tree.as_list())
        self.assertEqual(tree.as_list(),
                         ['_root', 'Some ', ['inlinetag',
                                             ['_item', 'Hello ',
                                              ['blocktag', 'test'],
                                              ['blocktag',
                                               'another test']]]])

    def test_inlinetag_with_multiple_arguments(self):
        doc = r"""\blocktag Some \inlinetag[Hello][world]"""
        parser = QqParser(allowed_tags={'inlinetag', 'blocktag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         ["_root", ["blocktag", "Some ",
                                    ["inlinetag", ["_item", "Hello"],
                                     ["_item", "world"]]]])


    def test_end_with_empty_line(self):
        doc = dedent(r"""
        \tag
            
            """)
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)

    def test_as_etree(self):
        doc = dedent(r"""
        \tag
            some content
            \tag
                other content
            more text here
        """)
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)
        self.assertEqual(et.tostring(tree.as_etree()),
                         b'<_root><tag>some content'
                         b'<tag>other content'
                         b'</tag>more text here'
                         b'</tag></_root>')

    def test_newline(self):
        doc = dedent(r"""
        \tag
            Hello
        
        Stop.
        """)
        parser = QqParser(allowed_tags={'tag'})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         ['_root', '', ['tag', 'Hello'],
                          '\nStop.'])

    def test_children_tags(self):
        doc = dedent(r"""
                \tag
                    some content
                    \tag
                        other content
                    more text here
                    \tag
                        some other tag
                """)
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)
        childrens = (list(tree.tag_.children_tags()))
        self.assertEqual(childrens[0].as_list(), ["tag", "other content"])
        self.assertEqual(childrens[1].as_list(), ["tag",
                                                  "some other tag"])

    def test_blank_line_after_tag(self):
        doc = dedent(r"""
            \tag
            
                otherline
                \tag
                    othertag
        """)
        parser = QqParser(allowed_tags={"tag"})
        tree = parser.parse(doc)
        self.assertEqual(tree.as_list(),
                         ['_root', '',
                          ['tag', '\notherline', ['tag', 'othertag']]])