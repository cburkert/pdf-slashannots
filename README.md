# pdf-slashannots – Redact PDF Annotation Metadata

**By annotating PDFs you leave metadata** along with the annotation content like
your **name and the date and time** when you created and last modified each
annotation.
This metadata can be **seen and exploited by anyone** with access to the annotated
PDF file.

That way, others could for instance **infer how long you took to read** through and
comment on a document and even individual pages,
or infer when you made breaks or did something else.

pdf-slashannots aims at redacting that annotation metadata from PDFs so that
you can pass them along without revealing your habits.


## Installation

pdf-slashannots is available on PyPI:

```
python3 -m pip install pdf-slashannots
```

## Usage

Simply run `pdf-slashannots input.pdf redacted.pdf` and you are done.

Okay, there is more. If you run the command without any options then all
annotations are equally redacted and the dates set to _none_ precision (January
1st, 1970).
Check out `pdf-slashannots --help` for the more advanced
features like

- specify a subset of annotation authors to redact
- specify the precision to which the dates are reduced
- redact also the authors' name

