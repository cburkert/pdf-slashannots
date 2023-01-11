"""Tkinter GUI for pdf-slashannots"""
import argparse
from collections import Counter
import importlib.resources as ir
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

from .main import PdfAnnotationRedacter, AnnotationStats, DatePrecision


class SlashAnnotsGUI(Tk):
    def __init__(self, pdffile: Optional[BinaryIO], *args, **kwargs) -> None:
        Tk.__init__(self, *args, **kwargs)
        title = "pdf-slashannots"
        self.title(title)
        self.minsize(400, 200)
        iconres = ir.files("slashannots").joinpath("icon-trans.png")
        with ir.as_file(iconres) as iconfile:
            icon = PhotoImage(file=iconfile)
        self.iconphoto(True, icon)

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
        bottom_frame.pack(side=BOTTOM, pady=5)
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
        open_button.pack()
        # also offer shortcuts
        self.bind("<Control-o>", lambda e: self.select_pdf())
        self.bind("<Meta_L><o>", lambda e: self.select_pdf())
        self.pdfstats_var = StringVar(value="test")
        stats_label = ttk.Label(file_frame, textvariable=self.pdfstats_var,
                                justify=CENTER)
        stats_label.pack(side=BOTTOM)

        # - settings frame
        set_frame = ttk.Frame(left_frame)
        set_frame.pack(side=BOTTOM, pady=10)
        prec_label = ttk.Label(set_frame, text="Precision", padding=5)
        prec_label.grid(row=1, column=1)
        prec_drop = ttk.Combobox(set_frame, width=10,
                                 values=[str(prec) for prec in DatePrecision],
                                 state="readonly")
        prec_drop.grid(row=1, column=2)
        prec_drop.set("hour")
        self.prec_drop = prec_drop
        self.rednames_chk = BooleanVar(value=False)
        rednames_chk = ttk.Checkbutton(set_frame, text="Replace names with",
                                       variable=self.rednames_chk)
        rednames_chk.grid(row=2, column=1, columnspan=2)
        self.redname_rpl = StringVar(value="unknown")
        redname_entry = ttk.Entry(set_frame, width=20, justify=CENTER,
                                  state=DISABLED,
                                  textvariable=self.redname_rpl)
        redname_entry.grid(row=3, column=1, columnspan=2)
        def change_redname_state(*args) -> None:
            del args  # not needed
            if self.rednames_chk.get():
                redname_entry["state"] = NORMAL
            else:
                redname_entry["state"] = DISABLED
        self.rednames_chk.trace_add("write", change_redname_state)

        # name frame (right)
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(side=RIGHT, padx=10)
        name_label = ttk.Label(name_frame, text="Select Author(s)")
        name_label.pack(side=TOP)
        yscroll = ttk.Scrollbar(name_frame, orient=VERTICAL)
        yscroll.pack(side=RIGHT, fill="y")
        list_wrapper = Frame(name_frame, bg="white")
        list_wrapper.pack(side=LEFT, fill=BOTH, expand=True)
        name_list = Listbox(list_wrapper, selectmode=MULTIPLE, border=0,
                            bg=list_wrapper.cget("bg"))
        self.name_list = name_list
        name_list.pack(fill=BOTH, expand=True, padx=5, pady=5)
        def name_list_update(event: Event):
            selection = event.widget.curselection()
            if selection:
                self.allow_selected()
            else:
                self.disallow_selected()
        name_list.bind("<<ListboxSelect>>", name_list_update)
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
        names_ctr = get_names(self.pdfpath)
        names = list(sorted(names_ctr.keys()))
        self.name_list.delete(0, END)  # clear box
        for i, name in enumerate(names):
            self.name_list.insert(i, name)
        # enable buttons
        self.redactall_btn["state"] = NORMAL
        # update stats info
        total = names_ctr.total()
        if total > 0:
            self.pdfstats_var.set(" ".join((
                plural(total, "annotation"),
                "from",
                plural(len(names), "author"),
            )))
        else:
            self.pdfstats_var.set("0 annotations")

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
            redact_author=self.rednames_chk.get(),
            redacted_author_name=self.redname_rpl.get(),
            precision=DatePrecision.argparse(precision),
        )
        outpath = self.pdfpath.with_suffix(".redacted.pdf")
        with self.pdfpath.open("rb") as pdffp, outpath.open("wb") as outfp:
            redacter.redact(pdffp, outfp)
        stats = redacter.stats
        resview = ResultView(outpath, stats)
        resview.mainloop()


class ResultView(Toplevel):
    def __init__(self, outpath: Path, stats: AnnotationStats, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.title("Redaction result")
        self.minsize(400, 200)
        frame = ttk.Frame(self, padding=5)
        frame.pack()
        tree = ttk.Treeview(frame, columns=("annots", "nreds", "dreds"))
        tree.pack(side=TOP, fill=BOTH, expand=True)
        tree.column('annots', width=100, anchor='center')
        tree.heading('annots', text='Annotations')
        tree.column('nreds', width=100, anchor='center')
        tree.heading('nreds', text='Redact. Names')
        tree.column('dreds', width=100, anchor='center')
        tree.heading('dreds', text='Redact. Dates')
        # fill tree
        authors = set(stats.authorship_ctr.keys())
        for author in sorted(authors):
            tree.insert("", END, text=author, values=(
                stats.authorship_ctr[author],
                stats.redacted_authorships[author],
                stats.redacted_cdates[author],
            ))
        outframe = ttk.Frame(frame)
        outpathlabel = ttk.Label(outframe, text=f"Output:")
        outpathlabel.pack(side=LEFT)
        outpathvar = StringVar(value=str(outpath))
        outpathentry = Entry(outframe, state="readonly",
                             width=80,
                             textvariable=outpathvar)
        outpathentry.pack(side=RIGHT, fill=X, expand=True)
        outframe.pack()
        closebtn = ttk.Button(frame, text="Close", command=self.destroy)
        closebtn.pack(side=BOTTOM)


def get_names(pdffile: Path) -> Counter[str]:
    reader = PyPDF2.PdfReader(pdffile)  # type: ignore
    authors_ctr: Counter[str] = Counter()
    for page in reader.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:  # type: ignore
                obj = annot.get_object()
                if "/T" in obj:
                    author = obj["/T"]
                    authors_ctr[author] += 1
    return authors_ctr


def plural(num: int, thing: str) -> str:
    if num == 1:
        return f"1 {thing}"
    return f"{num} {thing}s"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdffile", type=argparse.FileType("rb"), nargs="?")
    args = parser.parse_args()
    app = SlashAnnotsGUI(args.pdffile)
    app.mainloop()


if __name__ == "__main__":
    main()
