# Installation and first start

This page is only for getting the program to start. To understand what it does and how
it is used, go to **[GUIDE.md](GUIDE.md)**.

---

## Windows, without touching the terminal

1. **Install Python.** Download it from <https://www.python.org/downloads/> — version
   3.11 or later is needed. During the installation tick **“Add Python to PATH”**
   before clicking *Install*: it is the only step in which you can go wrong, and
   without that tick nothing else works.
2. **Extract the program.** Open the ZIP file and drag the folder it contains wherever
   you like, for example onto the Desktop. Everything that follows is done inside that
   folder.
3. **Double-click `setup.bat`.** It creates a separate environment and downloads what is
   needed. The first time it takes a few minutes. At the end it asks whether you also
   want to install Stanza and UDPipe, which are needed only by step 9 and weigh some
   hundred megabytes: **press Enter to skip them**, they can be added whenever you
   like. Then it prints “Installation complete!”.
4. **Double-click `run.bat`.** The program opens.

From the second time on only `run.bat` is needed. If you like, right-click `run.bat` →
*Send to* → *Desktop*, and you have a launch icon.

## macOS and Linux, or Windows from the terminal

Open the terminal **inside the program folder**, the one you have just extracted, where
you can see `app_qt.py` and `README.md`:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .

python app_qt.py
```

To have the comparison with the automatic models as well (step 9), when you need it:

```bash
pip install -e ".[models]"
```

On Windows, from the program folder:

```
.venv\Scripts\python.exe -m pip install -e ".[models]"
```

## If something does not work

**`setup.bat` says that Python is not installed.** Almost always it is the “Add Python to
PATH” tick that was forgotten. Reinstall Python and tick it.

**The program does not open and says nothing.** `run.bat` starts without a black window,
so any error stays invisible. Open `run.bat` with Notepad, remove the letter `w` from
`pythonw.exe` (it must become `python.exe`), save, try again: now the error can be read.

**I want to know what this computer is really running.** Double-click `CHECK_INSTALL.bat`.
It writes next to itself a text file with the version, which copy of the code is loaded
and how long the machine takes to work. It is the file to attach if you ask for help.

**Loading a corpus stops halfway.** If you pointed to a folder that also holds files
which are not AGDT treebanks, the program reports them instead of reading them badly.
Check that you pointed to the folder of the XML files and not to the one that contains
it.

**The comparison with the models does not start.** Stanza and UDPipe are optional and
`setup.bat` installs them only if you answer yes. To add them later, from the program
folder: `.venv\Scripts\python.exe -m pip install -e ".[models]"`. On first use the
program downloads their model files, about 60 MB in all.

**I do not have the permissions to write.** The program writes into the `workspace/`
folder next to itself. If you put it in `Program Files` or in a system folder, move it to
a folder of your own (Desktop, Documents).

## Where the data end up

Everything stays on your computer, in the `workspace/` folder next to the program: the
loaded corpus, the findings, your decisions, the corrected version. Nothing is sent
anywhere. The only connection to the internet is used to download the example corpora,
and only if you press those buttons.

## From the command line

For those who prefer the script to the button:

```bash
greek-corpus-cli --help
```

It runs loading, diagnosis and export without opening the window: useful to redo an
analysis on many corpora, or inside another workflow.

## Checking that everything works

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest -q          # on Windows: set QT_QPA_PLATFORM=offscreen
```

Some tests need something that is not part of the package — the six frozen corpora, the
UDPipe model — or are measurements of time that must be made on a quiet machine: they
skip themselves, saying why (`pytest -rs` prints the reasons). The number of passed and
skipped tests depends on what is installed; the figures obtained on the reference
environment are given in [README.md](README.md), and how to run the skipped ones is
explained in [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).
