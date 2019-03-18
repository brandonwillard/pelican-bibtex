"""
Pelican BibTeX
==============

A Pelican plugin that populates the context with a list of formatted
citations, loaded from a BibTeX file at a configurable path.

The use case for now is to generate a ``Publications'' page for academic
websites.

Author: brandonwillard
Original Author: Vlad Niculae <vlad@vene.ro>
Unlicense (see UNLICENSE for details)
"""

import logging
from operator import itemgetter

from pybtex.database.input.bibtex import Parser
from pybtex.database.output.bibtex import Writer
from pybtex.database import BibliographyData, PybtexError
from pybtex.backends import html

from pybtex.style.formatting import toplevel
from pybtex.style.formatting.unsrt import Style, pages, date
from pybtex.richtext import Tag

from pybtex.style.template import (
    first_of,
    field,
    join,
    optional,
    optional_field,
    href,
    words,
    sentence,
    tag)

from pelican import signals

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


logger = logging.getLogger(__name__)
__version__ = '0.2.1'


class MyStyle(Style):
    """ Custom style that does better with urls.
    """

    def format_article(self, entry):
        volume_and_pages = first_of[
            # volume and pages, with optional issue number
            optional[
                join[
                    field('volume'),
                    optional['(', field('number'), ')'],
                    ':', pages
                ],
            ],
            # pages only
            optional[
                words['pages', pages]
            ],
        ]
        template = toplevel[
            self.format_title(entry, 'title'),
            self.format_names('author'),
            sentence[
                tag('em')[field('journal')],
                optional[volume_and_pages],
                date],
            sentence[optional_field('note')],
            self.format_web_refs(entry),
        ]
        return template.format_data(entry)

    def format_unpublished(self, entry):
        template = toplevel[
            self.format_title(entry, 'title'),
            sentence[self.format_names('author')],
            sentence[
                words[
                    first_of[
                        optional_field('type'),
                        'Unpublished',
                    ],
                    optional_field('number'),
                ],
                date,
            ],
            sentence[optional_field('note')],
            self.format_web_refs(entry),
        ]
        return template.format_data(entry)

    def format_techreport(self, entry):
        template = toplevel[
            self.format_title(entry, 'title'),
            sentence[self.format_names('author')],
            sentence[
                words[
                    first_of[
                        optional_field('type'),
                        'Technical Report',
                    ],
                    optional_field('number'),
                ],
                field('institution'),
                optional_field('address'),
                date,
            ],
            sentence[optional_field('note')],
            self.format_web_refs(entry),
        ]
        return template.format_data(entry)

    def format_doi(self, entry):
        """ Kills doi printout.
        """
        return []

    def format_title(self, entry, which_field, as_sentence=True):

        formatted_title = field(
            which_field,
            apply_func=lambda text: Tag('b', text.capitalize())
        )
        if as_sentence:
            return sentence[formatted_title]
        else:
            return formatted_title

    def format_url(self, entry):
        return ['[', href[field('url'), join(' ')['URL']], ']']


def add_publications(generator):
    """
    Populates context with a list of BibTeX publications.

    Configuration
    -------------
    generator.settings['PUBLICATIONS_SRC']:
        local path to the BibTeX file to read.

    Output
    ------
    generator.context['publications']:
        List of tuples (key, year, text, bibtex, url, slides, poster).
        See Readme.md for more details.
    """
    if 'PUBLICATIONS_SRC' not in generator.settings:
        return

    refs_file = generator.settings['PUBLICATIONS_SRC']
    try:
        bibdata_all = Parser().parse_file(refs_file)
    except PybtexError as e:
        logger.warn('`pelican_bibtex` failed to parse file %s: %s' % (
            refs_file,
            str(e)))
        return

    # format entries
    plain_style = MyStyle()
    html_backend = html.Backend()
    formatted_entries = plain_style.format_entries(
        bibdata_all.entries.values())

    publications = []
    reports = []
    unpublished = []
    for formatted_entry in formatted_entries:
        key = formatted_entry.key
        entry = bibdata_all.entries[key]

        try:
            year = int(entry.fields.get('year', None))
        except TypeError:
            year = None

        journal = entry.fields.get('journal', "")

        sort_key = (year, journal)

        # Render the bibtex string for the entry.
        bib_buf = StringIO()
        bibdata_this = BibliographyData(entries={key: entry})
        Writer().write_stream(bibdata_this, bib_buf)

        text = formatted_entry.text.render(html_backend)

        entry_res = (key, text, bib_buf.getvalue(), sort_key)

        if entry.type == 'article':
            publications.append(entry_res)
        elif entry.type == 'unpublished':
            unpublished.append(entry_res)
        else:
            reports.append(entry_res)

    generator.context['publications'] = sorted(publications,
                                               key=itemgetter(-1),
                                               reverse=True)
    generator.context['reports'] = sorted(reports,
                                          key=itemgetter(-1),
                                          reverse=True)
    generator.context['unpublished'] = sorted(unpublished,
                                              key=itemgetter(-1),
                                              reverse=True)


def register():
    signals.generator_init.connect(add_publications)
