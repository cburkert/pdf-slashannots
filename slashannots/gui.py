"""Tkinter GUI for pdf-slashannots"""
import argparse
import os
import os.path
import io
from pathlib import Path

from tkinter import *
from tkinter import ttk
from tkinter import filedialog as tkfd
import tkinter.messagebox as tkmsg
from typing import *

import PyPDF2

from .main import PdfAnnotationRedacter, DatePrecision


class SlashAnnotsGUI(Tk):
    def __init__(self, pdffile: Optional[BinaryIO], *args, **kwargs) -> None:
        Tk.__init__(self, *args, **kwargs)
        title = "pdf-slashannots"
        self.title(title)
        self.minsize(400, 200)

        menubar = Menu(self)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.select_pdf,
                             accelerator="Command-o")
        filemenu.add_command(label="Quit", command=self.quit,
                             accelerator="Command-q")
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

        main_frame = ttk.Frame(self, padding=5)
        main_frame.pack(expand=True,fill=BOTH)
        # bottom controls
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(side=BOTTOM)
        quit_btn = ttk.Button(bottom_frame, text="Quit", command=self.destroy)
        quit_btn.pack(side=RIGHT)
        redactall_btn = ttk.Button(bottom_frame, text="Redact all",
                                   state=DISABLED,
                                   command=self.redact)
        redactall_btn.pack(side=LEFT)
        self.redactall_btn = redactall_btn
        redactsel_btn = ttk.Button(bottom_frame, text="Redact selected",
                                   state=DISABLED,
                                   command=self.redact_selected)
        redactsel_btn.pack()
        self.redactsel_btn = redactsel_btn

        # left frame
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=LEFT)
        # - file frame
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(side=TOP, fill="x", expand=True)
        file_label = ttk.Label(file_frame)
        file_label.pack(side=TOP)
        self.file_label = file_label
        open_button = ttk.Button(
            file_frame,
            text='Select PDF',
            command=self.select_pdf,
        )
        open_button.pack(side=BOTTOM)
        # also offer shortcuts
        self.bind("<Control-o>", lambda e: self.select_pdf())
        self.bind("<Meta_L><o>", lambda e: self.select_pdf())

        # - settings frame
        set_frame = ttk.Frame(left_frame)
        set_frame.pack(side=BOTTOM, pady=10)
        prec_label = ttk.Label(set_frame, text="Precision", padding=5)
        prec_label.pack(side=LEFT)
        prec_drop = ttk.Combobox(set_frame, width=10,
                                 values=[str(prec) for prec in DatePrecision],
                                 state="readonly")
        prec_drop.pack(side=RIGHT)
        prec_drop.set("hour")
        self.prec_drop = prec_drop

        # name frame (right)
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(side=RIGHT)
        name_label = ttk.Label(name_frame, text="Select Author(s)")
        name_label.pack(side=TOP)
        yscroll = ttk.Scrollbar(name_frame, orient=VERTICAL)
        yscroll.pack(side=RIGHT, fill="y")
        name_list = Listbox(name_frame, selectmode=MULTIPLE, border=0)
        def name_list_update(event: Event):
            selection = event.widget.curselection()
            if selection:
                self.allow_selected()
            else:
                self.disallow_selected()
        name_list.bind("<<ListboxSelect>>", name_list_update)

        self.name_list = name_list
        name_list.pack(side=LEFT, fill=BOTH, expand=True)
        name_list.config(yscrollcommand=yscroll.set)
        yscroll.config(command=name_list.yview)

        # init with optionally given PDF
        pdfpath: Optional[Path] = Path(pdffile.name) if pdffile else None
        if pdfpath:
            self.set_pdf(pdfpath)

    def select_pdf(self):
        filetypes = (
            ('PDF files', '*.pdf'),
            ('All files', '*.*')
        )
        filename = tkfd.askopenfilename(
            title='Select a PDF',
            initialdir=os.path.expanduser("~"),
            filetypes=filetypes,
        )
        if not filename:
            return  # do nothing on cancel
        self.set_pdf(Path(filename))

    def set_pdf(self, pdfpath: Path):
        self.pdfpath = pdfpath
        self.file_label.config(text=self.pdfpath.name)
        names = get_names(self.pdfpath)
        self.name_list.delete(0, END)  # clear box
        for i, name in enumerate(names):
            self.name_list.insert(i, name)
        # enable buttons
        self.redactall_btn["state"] = NORMAL

    def allow_selected(self):
        self.redactsel_btn["state"] = NORMAL

    def disallow_selected(self):
        self.redactsel_btn["state"] = DISABLED

    def redact_selected(self):
        selection = self.name_list.curselection()
        names = [
            self.name_list.get(i)
            for i in selection
        ]
        self.redact(names)

    def redact(self, authors: List[str] = []):
        if not self.pdfpath:
            return
        precision = self.prec_drop.get()
        redacter = PdfAnnotationRedacter(
            included_authors=authors,
            precision=DatePrecision.argparse(precision),
        )
        outpath = self.pdfpath.with_suffix(".redacted.pdf")
        with self.pdfpath.open("rb") as pdffp, outpath.open("wb") as outfp:
            redacter.redact(pdffp, outfp)
        statsout = io.StringIO()
        redacter.stats.pprint_stats(statsout)
        text = statsout.getvalue()
        tkmsg.showinfo("Redaction successful", text, icon="info")


def get_names(pdffile: Path) -> List[str]:
    reader = PyPDF2.PdfReader(pdffile)  # type: ignore
    authors: Set[str] = set()
    for page in reader.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:  # type: ignore
                obj = annot.get_object()
                if "/T" in obj:
                    author = obj["/T"]
                    authors.add(author)
    return list(sorted(authors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdffile", type=argparse.FileType("rb"), nargs="?")
    args = parser.parse_args()
    app = SlashAnnotsGUI(args.pdffile)
    app.mainloop()


if __name__ == "__main__":
    main()
