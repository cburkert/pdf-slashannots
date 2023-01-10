import argparse
from datetime import datetime
import enum
import logging
import sys
from typing import *

import PyPDF2
from PyPDF2.generic import NameObject, TextStringObject


logger = logging.getLogger(__name__)


DEFAULT_REDACTED_AUTHOR = "unknown"


class DatePrecision(enum.IntEnum):
    NONE = 0
    YEAR = 1
    MONTH = 2
    DAY = 3
    HOUR = 4
    MINUTE = 5
    SECOND = 6
    MICRO = 7

    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DatePrecision[s.upper()]
        except KeyError:
            return s


class AnnotationStats:
    def __init__(self) -> None:
        self.authorship_ctr: Counter[str] = Counter()
        self.redacted_authorships: Counter[str] = Counter()
        self.redacted_cdates: Counter[str] = Counter()
        self.redacted_mdates: Counter[str] = Counter()

    def pprint_stats(self, out=sys.stdout) -> None:
        authors = set(self.authorship_ctr.keys())
        assert authors.issuperset(self.redacted_authorships.keys())
        assert authors.issuperset(self.redacted_cdates.keys())
        assert authors.issuperset(self.redacted_mdates.keys())
        lines = [
            (
                f"{author}: {self.authorship_ctr[author]} annots, "
                f"redacted {self.redacted_authorships[author]} names, "
                f"{self.redacted_cdates[author]} cdates, "
                f"{self.redacted_mdates[author]} mdates"
            )
            for author in sorted(authors)
        ]
        out.writelines(lines)
        if lines:
            # finish output with newline
            out.write("\n")


class PdfAnnotationRedacter:
    def __init__(
        self,
        included_authors: Optional[List[str]] = None,
        redact_author: bool = True,
        precision: DatePrecision = DatePrecision.NONE,
        redacted_author_name: str = DEFAULT_REDACTED_AUTHOR,
    ):
        self.included_authors = set(included_authors or [])
        self.redact_author = redact_author
        self.precision = precision
        self.redacted_author = redacted_author_name
        self.stats = AnnotationStats()

    @property
    def is_clear_all(self) -> bool:
        return not self.included_authors  # no filter given

    def redact(self, infile: BinaryIO, outfile: BinaryIO):
        reader = PyPDF2.PdfReader(infile)  # type: ignore
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            if "/Annots" in page:
                for annot in page["/Annots"]:  # type: ignore
                    self.redact_annotation(annot)
            # add page to writer
            writer.add_page(page)
        # write new pdf
        with outfile:
            writer.write(outfile)  # type: ignore

    def redact_annotation(self, annotation):
        obj = annotation.get_object()
        subtype = obj["/Subtype"]
        # ignore /Link
        if subtype == "/Link":
            return
        # check redact author
        if "/T" in obj:
            author = obj["/T"]
            self.stats.authorship_ctr[author] += 1
            if not self.is_clear_all and author not in self.included_authors:
                # this author should not be redacted nor any of their metadata
                return
            if self.redact_author:
                obj[NameObject("/T")] = TextStringObject(self.redacted_author)
                self.stats.redacted_authorships[author] += 1
        else:
            # No author information for this type of Annotation
            logger.debug("No author for %s", subtype)
            # only continue redacting dates for this annotation if we are in
            # clear-all mode, i.e., if no author filter was given
            # Rational: Otherwise we would redact objects that may not be
            # created by the authors in the filter
            if not self.is_clear_all:
                return
            author = ""
        # redact dates
        if "/CreationDate" in obj:
            self.redact_date(obj, "/CreationDate")
            self.stats.redacted_cdates[author] += 1
        else:
            logger.debug("No creation date for %s", subtype)
        if "/M" in obj:
            self.redact_date(obj, "/M")
            self.stats.redacted_mdates[author] += 1
        else:
            logger.debug("No modification date for %s", subtype)

    def redact_date(self, obj: PyPDF2.generic.PdfObject, date_type: str):
        date = parse_date(obj[date_type])  # type: ignore
        if self.precision < DatePrecision.MICRO:
            date = date.replace(microsecond=0)
        if self.precision < DatePrecision.SECOND:
            date = date.replace(second=0)
        if self.precision < DatePrecision.MINUTE:
            date = date.replace(minute=0)
        if self.precision < DatePrecision.HOUR:
            date = date.replace(hour=0)
        if self.precision < DatePrecision.DAY:
            date = date.replace(day=1)
        if self.precision < DatePrecision.MONTH:
            date = date.replace(month=1)
        if self.precision < DatePrecision.YEAR:
            date = date.replace(year=1970)
        obj[NameObject(date_type)] = TextStringObject(format_date(date))  # type: ignore


def parse_date(rdate: str) -> datetime:
    rdate = rdate.replace("'", "")
    return datetime.strptime(rdate, "D:%Y%m%d%H%M%S%z")


def format_date(date: datetime) -> str:
    return date.strftime("D:%Y%m%d%H%M%S%z")


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", type=argparse.FileType("rb"),
                        help="PDF input file")
    parser.add_argument("output", type=argparse.FileType("wb"),
                        help="PDF output file")
    parser.add_argument("-r", "--redact-author-name", action="store_true",
                        help="Flag to control redaction of author names")
    parser.add_argument("-a", "--authors", type=str, nargs="+",
                        help="Name of authors who's annotation metadata to redact")
    parser.add_argument("-n", "--redacted-author-name", type=str,
                        default=DEFAULT_REDACTED_AUTHOR,
                        help="Name to use for redacted authors")
    parser.add_argument("-p", "--precision", type=DatePrecision.argparse,
                        choices=list(DatePrecision),
                        default=DatePrecision.NONE,
                        help="Precision to which dates get redacted")
    args = parser.parse_args()
    redacter = PdfAnnotationRedacter(
        included_authors=args.authors,
        redact_author=args.redact_author_name,
        precision=args.precision,
        redacted_author_name=args.redacted_author_name,
    )
    redacter.redact(args.input, args.output)
    redacter.stats.pprint_stats()


if __name__ == "__main__":
    main()
