import argparse
from datetime import datetime
import enum
import logging
from typing import *

import PyPDF2


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
        self.stats: Counter[str] = Counter()

    @property
    def is_clear_all(self) -> bool:
        return not self.included_authors  # no filter given

    def redact(self, infile: BinaryIO, outfile: BinaryIO):
        reader = PyPDF2.PdfReader(infile)
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            if "/Annots" not in page:
                # no annotation on that page
                continue
            for annot in page["/Annots"]:
                self.redact_annotation(annot)
            # add page to writer
            writer.add_page(page)
        # write new pdf
        with outfile:
            writer.write(outfile)

    def redact_annotation(self, annotation):
        obj = annotation.get_object()
        subtype = obj["/Subtype"]
        # ignore /Link
        if subtype == "/Link":
            return
        # check redact author
        if "/T" in obj:
            author = obj["/T"]
            if not self.is_clear_all and author not in self.included_authors:
                # this author should not be redacted nor any of their metadata
                return
            if self.redact_author:
                obj[PyPDF2.generic.NameObject("/T")] = PyPDF2.generic.TextStringObject(
                    self.redacted_author
                )
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
        else:
            logger.debug("No creation date for %s", subtype)
        if "/M" in obj:
            self.redact_date(obj, "/M")
        else:
            logger.debug("No modification date for %s", subtype)

    def redact_date(self, obj: PyPDF2.generic.PdfObject, date_type: str):
        date = parse_date(obj[date_type])
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
        obj[PyPDF2.generic.NameObject(date_type)] = PyPDF2.generic.TextStringObject(
            format_date(date)
        )


def parse_date(rdate: str) -> datetime:
    rdate = rdate.replace("'", "")
    return datetime.strptime(rdate, "D:%Y%m%d%H%M%S%z")


def format_date(date: datetime) -> str:
    return date.strftime("D:%Y%m%d%H%M%S%z")


def main():
    parser = argparse.ArgumentParser()
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


if __name__ == "__main__":
    main()
