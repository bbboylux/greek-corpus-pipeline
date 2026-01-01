# Greek Corpus Pipeline — user guide

This guide takes nothing for granted. You do not need to program and you do not
need statistics. A Word version, laid out for printing, is in
[docs/GCP_user_guide.docx](docs/GCP_user_guide.docx); it is generated from this
file and says exactly the same things.

To install the program: [INSTRUCTIONS.md](INSTRUCTIONS.md). For parameters,
fingerprints and tests: [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

---

## Before you start: three words and an idea

### What a treebank is

A **treebank** is a Greek text in which every single word has been given a
record. For each word someone has written down how it is spelled in the text,
under which dictionary entry it is looked up, which grammatical form it is, and
which other word of the sentence it depends on.

Take the beginning of Aeschines, *Against Timarchus*. The first word is
**οὐδένα**, and its record says: the form is οὐδένα; the lemma, that is the
dictionary entry, is οὐδείς; the grammatical tag is `p-s---ma-`; the function in
the sentence is `OBJ`, an argument governed by the verb; and the word it depends
on is word number 15 of the same sentence.

A treebank is this, multiplied by hundreds of thousands of words. The program
reads these records and checks that they are well made.

### What the nine-slot tag is

That strange string, `p-s---ma-`, is not a secret code: it is a row of nine
slots, and each slot always answers the same question. In order: which part of
speech, which person, which number, which tense, which mood, which voice, which
gender, which case, which degree.

It reads like this: `p` means pronoun; the person slot holds a hyphen, and the
hyphen means “this question does not apply here”; `s` means singular; then three
hyphens, because tense, mood and voice are not asked of a pronoun; `m` means
masculine; `a` means accusative; and the last hyphen says that the degree is not
marked.

> The hyphen has two different meanings, and the difference matters. From the
> second slot onwards it means “category that does not apply”. In the **first**
> slot it does not: every word has a part of speech, so a hyphen there is a datum
> that is really missing. The program keeps the two apart.

### What a finding is

The program does not say “here is an error”. It says “here is something to look
at”, and it explains why. Every time one of its checks finds something, it
produces a row: that row is called a finding.

And here is the idea that holds the whole program together. Findings are not all
of the same nature, and treating them as if they were is the fastest way to spoil
a corpus. There are three kinds, and the program always tells you which one you
are looking at.

| Kind of finding | What it means |
|---|---|
| **Scheme violation** | The datum breaks a written rule: the tag has eight slots instead of nine, the syntactic function is not in the list, the word says it depends on a word that is not in the sentence. You do not need to read Greek to notice it: it is like a date written with month number thirteen. |
| **Systematic variant** | The datum is not wrong: it follows a different habit. In the Gorman corpus, for example, about eleven thousand words have an underscore where the reference format wants a hyphen. For a reader it is the same thing; for a computer they are two different characters. Bringing it back to the standard is a choice, not a correction. |
| **Case to check** | The program has found an unusual spot, but only the context can say whether anything is really wrong. Here the program stops and hands the word to you. |

Next to this there is a second question, which is different from the first: what
can be done about it. Some things have a single right answer known in advance,
and the program proposes it; others are a choice that depends on what you want to
do with the corpus; others still can only be decided by reading the sentence.

> The program **never corrects anything by itself**. Not a single word. It
> proposes, and you decide case by case. And the corpus you loaded is never
> touched: your decisions build a second version, kept separate.

---

## The map: ten numbered steps in the left-hand column, and a reference page

You do not have to follow them in order, but the first three come before the
others: without a corpus that has been loaded and checked, the other pages have
nothing to show.

| Step | What it is for |
|---|---|
| 1 · Load a corpus | You tell the program which files to look at. |
| 2 · Overview | It tells you what is inside: how many texts, by which authors, of which century. |
| 3 · Diagnostic findings | It runs the checks of the catalogue and shows you what it found. |
| 4 · Variation n-gram | It looks for the places where the same thing is annotated in two different ways. A second way of looking, independent of the checks. |
| 5 · Correct | This is where you decide, one finding at a time. |
| 6 · Search the corpus | You look for a word or a lemma and see where it occurs and how it is analysed. |
| 7 · Statistics | The portrait of the corpus in numbers. |
| 8 · Charts | The same numbers, drawn. |
| 9 · Compare the models | Two automatic programs re-analyse the same text and their answers are put side by side. |
| 10 · Revised corpus | The result of your work: what changed, and how to take it away. |

Under the heading **REFERENCE**, at the foot of the column and without a number,
there is one more page, **The AGDT 2.0 scheme**: the manual inside the program,
with the tag and the syntactic functions explained.

A step that cannot be taken yet stays greyed out, and the column says why: “Load
a corpus first”, “Run the check first”.

At the top right there is the language menu. The whole program switches between
Italian and English at the moment you change it, without restarting and without
losing the work done.

On almost every page there is a button **How to read this page**: it opens a
panel that explains, on that page and in its own words, what you are looking at.
Above every table there is **How to read this table**, which does the same for
the columns.

---

## Step 1 · Load a corpus

**What it is for.** To tell the program which XML files to read. Until you have
done it, almost all the other pages stay greyed out.

### What to do

Either press one of the ready-made corpus buttons, or point to your own files,
and then press **Load the corpus**. Before loading, decide what to leave out of
the analysis (the three boxes below): you can change them afterwards too, but
the check has to be run again.

### The six ready-made buttons

Each one downloads a ready-made corpus from the internet and loads it, so you do
not have to find or download anything.

- **Gorman** — Attic prose and historiography, about 625,000 records,
  hand-annotated.
- **Pedalion** — prose, poetry and papyri, about 280,000 records, produced in
  Leuven by correcting a first automatic parse by hand.
- **GLAUx, declared sample** and **confirmation sample** — two samples of a huge
  corpus (some twenty million words), mostly analysed by an automatic program,
  about 300,000 and 270,000 records. The whole corpus cannot be loaded: no tool
  that wants to show you every finding inside its sentence can cope with twenty
  million rows.
- **GLAUx, the two hand-annotated portions** of the two samples, about 22,000 and
  29,000 records. They are small, and serve as a term of comparison with the
  automatic portions of the same resource.

The corpora are **not** part of the program: they are downloaded from their own
public repositories, and each one has its own authors and its own licence (see
[docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) and
[reproducibility/ACQUISITION.md](reproducibility/ACQUISITION.md)).

### Loading your own files

**Folder on this computer**: press *Choose folder…*, point to the folder where
your XML files are, and the program reads all of them, subfolders included.
**GitHub address**: paste the address of a folder in a public repository and the
program downloads the files by itself.

The field *Name for this corpus* is only for you, to find it again later in the
list of saved jobs at the foot of the page, where each job is reopened with
**Open** and removed with **Delete**.

> The program recognises two formats: that of AGDT 1.x and that of AGDT 2.0. If
> your file is made in some other way, it tells you so instead of reading it
> badly and giving you wrong numbers.

### What to leave out of the analysis

Three boxes. They decide which rows of the file enter the check. They do not
delete anything.

| Box | What it leaves out, and why |
|---|---|
| **Elliptic nodes** | The words that are not in the text. When the annotator considers a word to be understood, it is added to the tree as a placeholder: some corpora write it `[0]`, GLAUx writes it `E`. They are not typos, they are reconstructions. Leaving them out is the most cautious choice, because they usually have neither a lemma nor an analysis, and the program would end up reporting hundreds of times that a word that is not there lacks its analysis. The box is ticked at the start. |
| **Records with no Greek letters** | Numbers, sigla, Latin letters left inside the edition. |
| **Punctuation** | Commas and full stops. In an AGDT treebank punctuation too has a row and a syntactic function of its own. |

> Whatever you leave out, the **Overview** counts it and shows it all the same, in
> three separate panels. Leaving out does not mean losing sight.

### Metadata, if the corpus is yours

At the foot of the page: **Load your CSV…** to add author, work, period, genre and
dialect to your files; **Download the example** to get the template with its
header already written; **Back to the shipped metadata** to put things back as
they were. How to write that file is explained in step 2.

### What it does not mean

Loading a corpus **does not modify it and does not copy over the original**: the
program makes its own reading of it in a `workspace/` folder next to itself, and
your files stay where they are, as they are.

### The commands of this page

The six ready-made corpora · *Folder on this computer* / *GitHub address* ·
*Choose folder…* · **Load the corpus** · the three boxes of what to leave out ·
*Load your CSV…* · *Download the example* · *Back to the shipped metadata* ·
*Open* and *Delete* on the saved jobs.

---

## Step 2 · Overview

**What it is for.** It answers a single question: what have I loaded? It is the
place to notice at once that you have loaded the wrong folder.

### What to do

Nothing: the page fills itself as soon as the corpus is loaded. You read it, and
export it if you need to.

### What the numbers say

| Number | What it counts |
|---|---|
| Imported records | The rows of the file: one row per word, punctuation and elliptic nodes included. |
| Words (punctuation and empty placeholders excluded) | As above, but without commas and full stops. |
| Sentences | How many sentences: in the file each sentence is a block of its own, numbered. |
| Documents · Authors · Works | How many files, by how many authors, of how many different works. |
| Distinct forms | How many *different* words. If καί occurs five thousand times, that is five thousand records and a single form. |
| Distinct lemmas | How many different dictionary entries. |
| Average sentence length | How many **words** a sentence has on average: punctuation and empty placeholders do not count. |
| Longest sentence | The words of the longest sentence, counted in the same way. |

Just below you find three separate numbers: how many elliptic nodes, how much
punctuation and how many records with no Greek letters. If the corresponding box
is ticked, the panel says how many were taken out; if it is off, it says how many
there are and that they stayed in. There is never a silent zero. The three
categories overlap (an empty elliptic node has no Greek letters, and neither has
punctuation), so each number counts its own category in full and they are not
meant to be added up.

### Where author, century, genre and dialect come from

An XML file is called, for example, `hdt-1-1-19-bu3-2019.xml`. It does not say
Herodotus, it does not say fifth century, it does not say Ionic: that
information is not inside the file.

The program takes it from separate tables, plain CSV files in the `data/` folder.
There is one for Gorman, one for Pedalion and one for GLAUx, compiled text by
text. This is why, if you load Gorman or Pedalion, author and century appear by
themselves. If you load a corpus of your own, the program cannot guess: all the
counts remain valid, but they cannot be broken down by author or by century, and
the files it does not recognise are declared as such instead of disappearing.

Two things are worth knowing. The program knows an author only from what the file
declares about itself inside the XML (a TLG identifier, looked up in the
shipped catalogue of authors and works) or from the catalogue of a resource it
has recognised by the fingerprint of the corpus, or from the CSV that you load:
**the file name never counts**, and a file called `medea.xml` does not become
Euripides. And only one source applies at a time: your CSV *replaces* the shipped
catalogue, it does not complete it field by field, because a mixture would be
invisible.

In the tables of this page the Italian form of the author's name is in the column
*author (Italian)* and the English one in *author (English)*; the same holds for
the titles of the works.

### How to write your own metadata catalogue

It is a CSV file: the first row holds the names of the columns, each following row
describes a file of your corpus. The template with its header already written can
be downloaded from step 1, or is in `data/user_metadata_EXAMPLE.csv`.

| Column | What goes in it |
|---|---|
| `filename` | **Required.** The exact name of the XML file, extension included. It is the key: it has to match in every respect. |
| `corpus` | The name you give to the collection. It only serves to tell several catalogues apart. |
| `author_it` · `author_en` | The author in Italian and in English: Erodoto / Herodotus. `author_it` is **required**: it is what the column *author (Italian)* shows. If you have no Italian form, repeat the English name there. |
| `tlg_author_id` | The TLG identifier of the author, for example `tlg0016`. If you do not know it, leave it empty. |
| `work_it` · `work_en` | The title of the work in the two languages. |
| `date_start` · `date_end` | The years, as whole numbers. Years BCE with a minus sign: `-484`. |
| `date_label` | The dating as you would write it: “ca. 484–425 BCE”. It is the form read in the tables. |
| `century` | The century: “5th c. BCE”. |
| `period` | Archaic, Classical, Hellenistic, Imperial, Late antique. |
| `dialect` | Attic, Ionic, Koine, Doric… |
| `genre` | Historiography, Oratory, Tragedy, Philosophy… |
| `origin` | The author's place of origin: Halicarnassus. |

> The columns you cannot fill are left empty: the program notices and does not
> invent anything; what is missing is shown as “Unknown”. The only indispensable
> columns are `filename` and `author_it`, and neither may be empty on a row you
> want used. A column the program does not know is ignored, and the program says
> so. A file name that appears twice is read once: the last row wins.

### The manifest: where every number comes from

The button *Export the manifest* writes a file with the provenance of everything
the program is showing you. A number without its provenance cannot be checked,
and this file is what you need to check it:

| What it contains | What it is for |
|---|---|
| version of the program and of Python | knowing which code produced those numbers |
| name of the corpus and its fingerprint | knowing that it is exactly that corpus, not a similar one |
| the filters in force | knowing what was left out |
| the counting units with their counts: imported records, active records, words, analysable links, analysable sentences, sentences | knowing what was counted |
| the denominator of every percentage | being able to redo the count |
| the catalogue: how many checks, by class and by treatment | knowing which version of the catalogue |
| every scientific list, with its version and fingerprint | being able to say exactly which grammatical lemmas |
| where the metadata come from and how much they cover | knowing with which attribution an analysis by author was made |
| the state of the comparison with the models | knowing whether those numbers exist and what they refer to |

The keys of the manifest file are Italian names, the names under which the
program stores its data, and some of its descriptive values are in Italian too
(see “Language” in the README). If you attach it to your results, whoever reads
them can check them without asking you anything.

### What it does not mean

The numbers on this page **say nothing about the quality of the annotation**.
They describe the size and composition of the resource, not its state of health:
that begins at step 3. And a corpus without metadata **is not an incomplete
corpus**: it simply cannot be broken down by author or by period.

### The commands of this page

*Export the manifest* · *Export as CoNLL-U* · on every table, *Columns ▾* to
choose which columns to see, *Copy*, and *⤓ Save as CSV*.

---

## Step 3 · Diagnostic findings

**What it is for.** It is the heart of the program. Here the checks of the catalogue
pass over the corpus and show you everything they found, each finding inside its
own sentence.

### What to do

Choose which families of checks to run with the boxes at the top, then press
**Run the check** (from the second time on the button is called *Run the check
again*). On a large corpus it takes a few minutes. When it has finished, filter the
table and click a row to open the panel on the right.

### Which checks to run

| Family | What it looks at |
|---|---|
| Morphological tag | That it is nine characters long, that every slot holds an expected value, that the filled slots are the ones that belong to that part of speech. |
| Lemmatisation | That the lemma is there, that it does not end in a digit, that the same word does not occur under two different entries for no reason. |
| Syntactic structure | That every word depends on a word that exists, that there are no loops, that the sentence has a single root. |
| Text and encoding | Impossible accents, a final sigma in the middle of a word, Latin letters inside a Greek word, apostrophes encoded in different ways. |
| Agreement and government | Whether article and noun agree, whether the subject is in the expected case, whether an argument of the verb is in a case that an argument cannot have. |

There is a sixth box, **Annotation comparisons**, normally off. It does something
different and slower: it compares every word with the other occurrences of the
same word in the same context. On a large corpus it takes a few minutes, and it is
the same analysis that step 4 shows in full.

### The summary

| Number | What it says |
|---|---|
| Findings | How many rows the program produced in all. |
| Records involved | How many *records* are involved. It is smaller than the first number, because several checks can fire on the same record. |
| % of the corpus | What percentage of the corpus is touched by at least one finding. |
| Scheme violations | How many of the findings break a written rule. |
| Variants and cases to check | All the others. Usually the vast majority. |
| Automatically correctable | How many have a correction proposal that the program can formulate by itself. They still have to be accepted one by one. |
| Rules that fired | How many checks found at least one case. |

Under the boxes, one line breaks the findings down into the three diagnostic
classes with their numbers: verifiable violation, systematic variant, case to
check.

### The table and the panel

One row per finding. Three menus at the top filter it: **Family**, **Diagnostic
class** and **Rule** — the last one with, beside each name, how many findings it
produced. The table is sorted by clicking the headers, reduced to the columns you
want with *Columns ▾*, and saved as CSV.

Clicking a row opens the panel on the right, and that is where you work: the whole
Greek sentence with the word highlighted, the analysis spelled out in words
(“noun, plural, masculine, genitive” instead of `n-p---mg-`), and two separate
boxes that it is important not to confuse:

- **What this check looks for** — the description of the check taken from the
  catalogue. It is the same for all occurrences of the same rule.
- **What does not add up here** — what was found *here*, with the values of this
  row. It changes from one occurrence to the next.

When a check says “this form has more than one lemma”, the panel shows **all** the
readings that the form receives in the corpus, with how many times each occurs and
an example. Without that list the finding would be unusable.

### What it does not mean

> The big number, the number of findings, **is not the number of errors**. On
> Gorman there are more than a hundred thousand, but the true violations of the
> scheme are fewer than two thousand. The rest are habits of the project, applied
> with perfect consistency. Reading the raw total as a count of errors is the
> easiest mistake to make with this program.

Two corpora **cannot be compared** on the number of findings: many checks measure
the variation *inside* the resource that has been loaded, and a larger and more
varied corpus produces more of it without being worse annotated. And a finding,
finally, **is not a correction**: nothing changes here, you only look.

### The commands of this page

*How to read this page* · the six family boxes · **Run the check** / *Run the
check again* · the three menus *Family*, *Diagnostic class*, *Rule* · on every
table the field *Filter*, *How to read this table*, *Columns ▾*, *Copy*, *⤓ Save
as CSV*.

---

## Step 4 · Variation n-gram

**What it is for.** Step 3 asks the corpus whether it respects rules. This step asks
it something else: **whether it says different things twice about the same
thing.**

If the word καί, in the same context of three words, once carries the tag of the
conjunction and another time that of the adverb, one of the two is wrong — and
the program does not know which. It shows you the spot and lets you decide.

The method is not an invention of this program, but it does not all come from the
same source either. The morphology plane and the context plane derive from the
*variation n-gram* of Dickinson and Meurers (2003a); the dependencies plane adapts
the pair representation of Boyd et al. (2008), without the NIL nuclei and without
the context heuristics of that work; the tag-slots plane and the lemmas plane are
extensions of GCP and have no source.

### What to do

Press **Find the nuclei** and wait: it is the slowest analysis in the program. Then
choose one of the five tabs and read.

### The five planes

Each tab is a different way of saying “the same thing”.

| Plane | What it holds fixed |
|---|---|
| Morphology | the form; the whole tag varies |
| Tag slots | the form; a single slot of the tag varies |
| Context | the form and the two words around it; the tag varies |
| Dependencies | the pair of linked words; the relation or the direction varies |
| Lemmas | the form and the part of speech; the lemma varies |

The **context** plane is the narrowest and usually the most useful: a word that
oscillates on its own may simply be ambiguous, but a word that oscillates while
the neighbouring words stay identical, word for word, is almost always wrong.

### What is counted

A **variation nucleus** arises when the same analytical key is associated, in the
corpus, with more than one annotation value. The key changes in the five planes —
it is the column “what it holds fixed” of the table above — and with the key the
value changes: the whole tag, a single slot of the tag, the tag of the central word
of the trigram, the relation and the direction of the pair, the lemma. A key with a
single value is not a nucleus.

An empty tag **does not count as a tag**. A record without a morphological tag does
not carry a competing analysis: it carries the absence of an analysis, which is
something else and which step 3 reports on its own as “PoS tag missing”.

### What it does not mean

A nucleus **is not an error**, and it does not say which of the two annotations is
the right one: it says that two similar passages have been treated differently and
that at least one of the two deserves a second reading. The Greek language admits
genuinely ambiguous words, and those produce perfectly legitimate nuclei.

These five planes **are not an independent verification** of the checks of step 3:
they look at the same data with the same tools. They are another question put to
the same data, not a second opinion.

There is no column that says whether a variation is legitimate. A pair of tags
that the scheme admits *in the corpus* is not a pair admitted *at that point of
the text*, and marking the row as legitimate would invite not looking at it.

### The commands of this page

*How to read this page* · **Find the nuclei** · the five tabs · on every table *How
to read this table*, *Columns ▾*, *Copy*, *⤓ Save as CSV*.

---

## Step 5 · Correct

**What it is for.** It is where decisions are taken. The program applies nothing by
itself: it proposes, and waits. This page opens only after step 3 has produced
findings.

### What to do

Two roads, and you can use both. Either you load a CSV dictionary of corrections
you have already decided and apply it in bulk; or you go through the proposals one
by one and press **Accept this proposal** or **Reject** on each. When you have
finished, press **Apply the decisions I took**.

### One · Your form dictionary

If you already have a file with the corrections you want to apply, you load it
with *Choose the file…* and apply it in bulk. It is the only thing the program
does in bulk, and you are the one who does it.

| Column | Required? | What goes in it |
|---|---|---|
| `form` | yes | The form as it occurs in the text, with accents and breathings. |
| `postag` | one of the two | The nine-slot tag that this form must have. |
| `lemma` | one of the two | The lemma that this form must have. |

- `form` must be there, and at least one of `postag` and `lemma`. If both are
  missing, the program refuses the file and tells you why.
- An empty cell means “leave as it is”: it never deletes anything.
- The comparison is exact: accents, breathings and capitals count. The only thing
  levelled is the way the computer composes the accents, so a form typed with
  another keyboard is recognised all the same.
- Before applying, the program says how many rows found a match and how many did
  not, and how many words would change.

> You do not have to write the header by hand: *Download a ready-made CSV
> template* gives it to you with the header already written, and instructions
> inside. *Remove the dictionary* detaches it without having applied anything.

### Two · The proposals, one at a time

For every finding that carries a proposal, the row shows the present value and the
proposed one **side by side**: `n-p---mn` → `n-p---mn-`, or στρατιώτης1 →
στρατιώτης. In the panel on the right you re-read the sentence, the analysis in
words, the proposal in full, and two buttons: **Accept this proposal** or
**Reject**. Two boxes reduce the list to *Only cases that carry a proposal* and to
*Only the ones I have not decided yet*.

If you want to write a correction yourself, you write it in the field and press
**Save this correction**; **Remove a correction** takes it away.

A rejected proposal stays in the log and does not touch the corpus. It is there so
that in six months you know you have already looked at that case.

### The log of decisions

Every decision is written down: which file, which sentence, which word, how it was
before, how it is after, which check had raised the case, when, and with what
status. With **Save my decisions as a dictionary** you export them in the same CSV
format that the program reads back: what you decided on one corpus you can
re-apply to another.

### What it does not mean

Accepting a proposal **never modifies the original corpus**. Your decisions build
a second version, and the original stays intact as the term of comparison.

And a proposal **is not a verdict**: the program proposes the value that the corpus
itself, or the scheme, makes by far the most probable. On the cases to check there
is no proposal, and this is intended: when the answer depends on the context,
suggesting one would be an invitation to apply it without reading.

### The commands of this page

*Download a ready-made CSV template* · *Choose the file…* · *Remove the
dictionary* · *Save my decisions as a dictionary* · *Only cases that carry a
proposal* · *Only the ones I have not decided yet* · **Accept this proposal** ·
**Reject** · *Save this correction* · *Remove a correction* · **Apply the
decisions I took** · *Go to the revised corpus →*.

---

## Step 6 · Search the corpus

**What it is for.** To find a word or a lemma and see where it occurs and how it is
analysed. It has nothing to do with the diagnosis: it is the concordance.

### What to do

Type in the form line and press **Search this form**, or type in the lemma line
and press **Search this lemma**. Then click the row that interests you. *Clear*
empties everything.

### How to write what you are looking for

You do not need a Greek keyboard and you do not need accents. These three
spellings find the same occurrences:

```
ἄνθρωπος        ανθρωπος        anthropos
```

The program reduces both what you type and the words of the corpus to a common
form — accents off, breathings off, capitals off, Latin letters converted to Greek
— and compares those. The corpus is not modified.

On long and short vowels it is cautious: if you type `e` it searches for both ε
and η, if you type `o` it searches for both ο and ω. For the long vowel only, type
`ē` or `ō`, or type directly in Greek.

### Form and lemma are two different searches

Two separate lines, each with its own button. The search by **form** finds the
word exactly as it is written; the search by **lemma** finds all the forms under
that dictionary entry. Searching by form never filters by lemma, and vice versa.

### What it gives you back

First a list: one row per occurrence, with the sentence around it. Then, on the row
you choose, five things and nothing else: **morphology** (the tag spelled out, with
the original string in brackets), **syntactic function**, **lemma**, **head lemma**
(the dictionary entry of the word this one depends on: the quickest way to see
whether a genitive depends on whom you expect) and **author**.

### What it does not mean

The number of occurrences you read here **is a count in the loaded corpus**, not a
frequency of Greek: it changes with the corpus, with the filters of step 1 and with
the spelling. And the search **does not judge** the analysis it shows: it reports it
and nothing more.

### The commands of this page

**Search this form** · **Search this lemma** · *Clear* · on the tables *Columns ▾*,
*Copy*, *⤓ Save as CSV*.

---

## Step 7 · Statistics

**What it is for.** The portrait of the corpus in numbers. It is not for finding
errors — step 3 does that — but for describing the text and for checking that the
annotation holds up.

### What to do

At the top there are two menus, *Dimension* and *Value*. The first chooses **what to
look at**: whole corpus, document, author, work, period, genre, dialect. The second
chooses **which one**: which document, which author, which period. Document is
always there, because it comes from the files you imported; the others appear only
if the corpus carries those metadata, and if it does not the program tells you so
instead of inventing them.

Then choose the tab and press **Compute**. Nothing computes by itself: that tab
starts and nothing else. What you have already computed stays ready, and when you
change tab it comes back at once.

The page has four tabs: *Morphology*, *Syntax*, *Frequency lists* and *Lemma
profile*.

> **What is counted.** The statistics start from the **active records**, that is,
> what remains after the inclusion choices of step 1, and the words are the active
> records minus punctuation and technical records. They are the same units in which
> the program expresses its rates: the number you read here and the number you read
> elsewhere are the same number. Under every tab it is written what that tab counts,
> and every percentage carries its own denominator.

**Morphology.** Six tables: parts of speech, cases, moods, tenses, voices, persons.
For each value the code, what it means, how often it occurs and with what
percentage. Above every table it is written what the percentage is calculated on:
the moods on the verbs that have a mood, the cases on the categories that carry a
case.

**Syntax.** How many dependency links there are in the chosen group, how many
different labels, what share of the links crosses another link, and in how many
sentences that happens at least once. Below, the frequency of every syntactic
function. The count also declares how many sentences were left out and why: a
sentence with no computed arcs does not enter.

**Frequency lists.** Forms or lemmas, with absolute frequency, frequency per ten
thousand words of the group, percentage, cumulative percentage and rank. The menu
*Exclude frequent words* has four profiles:

| Profile | What it does |
|---|---|
| no filter | all the words |
| without function words | off go articles, prepositions, conjunctions, particles, pronouns, negations and grammatical adverbs, both by tag and by lemma |
| content words only | nouns, adjectives, verbs and lexical adverbs remain, ranked by TF-IDF |
| custom list | the grammatical list with your additions and your removals |

With *content words only* the order is not the bare frequency. A verb like εἰμί
sits at the top of any list without saying anything about the text, because it sits
at the top everywhere; the program looks at how many documents a lemma occurs in
and lightens those that are everywhere. No word is removed by this, only moved
lower — and if the group you chose contains a single document, the weighting does
not apply and the page tells you so.

The buttons *Add lemmas*, *Remove lemmas*, *Reset*, *Export list* and *Import list*,
behind *Advanced options*, work on the list of excluded words. The tab *Excluded
words* shows what was left out and for which of the three reasons: the tag, the
list, or the fact that the lemma is not a word.

**Lemma profile.** Type a lemma and press *Compute*.

A list of collocations asks “which words occur near λέγω”. A treebank allows the
right question: **what is the typical subject of λέγω, what is its object, in which
case.** The tab *Associations* answers it, and beside every pair it puts the
**logDice** score, which does not depend on the size of the corpus and is therefore
comparable between different authors.

Beside the score there is always the number of co-occurrences, and it is not a
detail: logDice rewards rarity, so a high score seen only once must be read for
what it is. There is no minimum threshold: a pair seen once is shown.

> **The numbering of lemmas.** Gorman writes λέγω as `λέγω3` 1,738 times, as `λέγω2`
> 98 times, as `λέγω` 51 times and as `λέγω1` 21 times (counted on the 616,646
> active records of the Gorman corpus). The digit is a number that the lemmatisation
> tool appends to tell homographs apart, not a lexical distinction: the profile
> counts them together, and they are 1,908. The tab *Spellings of the lemma* shows
> you which spellings the count comes from.
>
> The program does **not** merge two different lemmas, for example νοῦς and νόος:
> harmonising two dictionary entries is an operation between different resources,
> and here one resource at a time is being looked at.

A word whose relation field is empty counts as an occurrence of the lemma — it is a
real word, which is there in the text — but it produces no association: the absence
of a relation is not a relation.

The other tabs — *Forms*, *Tags*, *Relations*, *Documents*, *Examples* — say with
which forms the lemma occurs, with which tags, in which relations, in which
documents, and a few sentences in which to read it. The heads and the dependents of
the lemma are not tabs of their own, because they would be the raw counts of the
same pairs that *Associations* measures.

### What it does not mean

There is no “expected” interval and no conclusion about date or style: you draw
those. An unusual morphological distribution **is not proof of a wrong
annotation**, and may very well be proof of a literary genre.

Two groups of different size **cannot be compared on absolute counts**: that is what
the percentages and the rate per ten thousand words are for, which the page puts
beside every number.

### The commands of this page

The two menus *Dimension* and *Value* · **Compute**, on every tab · *Advanced
options* · the menu *Exclude frequent words* · *Add lemmas*, *Remove lemmas*,
*Reset*, *Export list*, *Import list* · *How to read this page* · on the tables
*Columns ▾*, *Copy*, *⤓ Save as CSV*.

---

## Step 8 · Charts

**What it is for.** The same numbers, drawn. The list is on the left, the chart on
the right.

### What to do

Choose the chart from the list on the left. At the top there is *Compare by* again:
every chart is split according to that choice.

### What you see

There are six: findings by family, findings by diagnostic class, the checks that
report most, finding density by document, agreement between corpus and models, and
the three-way comparison of corpus, Stanza and UDPipe. The first four re-use the
counts that step 3 has already produced and do not re-run the diagnosis; the last
two appear only if the comparison with the models has been run on *this* corpus.

Under every chart there is a line that says **what the chart counts and on which
denominator**, and the line changes when the chart is split by group: split by
author, the same bar is no longer a count but a share of that author's total,
because between groups of different size a count compares the length of the texts
and nothing else.

The density is **findings per 10,000 active records**: it is the same rate, on the
same unit and with the same factor, that the program uses everywhere.

### What it does not mean

A taller bar **does not mean a worse-annotated text**: almost always it means a
longer text, which is why the charts split by group switch to shares. And a chart
**adds nothing** to what step 3 has already counted: it is the same measure, drawn.

### The commands of this page

*How to read this page* · the menu *Compare by* · *⤓ Save this chart* · *Export all
charts*, which generates all of them at 300 dpi with the captions already written.
Every chart can be enlarged and copied.

---

## Step 9 · Compare the models

**What it is for.** It takes the corpus you have loaded **now** and has two automatic
programs, **Stanza** and **UDPipe**, analyse it again from scratch; then it lines up
the answers and shows where they do not coincide.

### What to do

Press **Run Stanza**, and then **Run UDPipe**. The first time the models have to be
downloaded: about 60 MB in all, once only. If the two programs are not installed, the page
says so and the buttons stay greyed out; how to install them is written in the
[README](README.md).

### “The model is there” and “the comparison has been done” are two different things

The page keeps them apart, and for each of the two models it tells you where you
stand:

| What you read | What it means |
|---|---|
| not available in this environment | the model is not installed on this machine |
| model available | the model is there, but the comparison on this corpus has not been done yet |
| to be run on this corpus | there is a saved comparison, but it concerns another corpus or another configuration, and it is **not** shown |
| run on this corpus | the comparison holds, and below you find its numbers with their provenance |

A saved comparison is re-used **only** if all of these match: the fingerprint of the
corpus given to the model, the version of the program, the filters, the units, the
model, its version, the fingerprint of its resources and the version of the
evaluation definition. If even one differs, the comparison is run again. The old one
is not deleted: it is simply not the answer to the question you are asking.

### What the model receives and what is measured

They are not the same thing, and the difference matters.

The model gets **the text**: the words and the real punctuation. A tagger reads the
marks too, and removing them changes the analysis of the words around them. Only the
technical records are left out, that is, the ones that are not in the text: elliptic
nodes, lacunae, unannotated passages.

The measurement, on the other hand, is made on the **words only**: a rate of
agreement on lemmas cannot have a comma in its denominator.

Every rate declares its own denominator. A word for which the model produces nothing
**stays in the denominator and counts as a disagreement**: the share of words for
which a prediction exists is called coverage and is read separately, so that a model
cannot improve its own result by losing the difficult cases on the way.

Lemmas are compared after normalising the encoding and removing the tool's numbering
on both sides. Without that, a corpus published in decomposed form — GLAUx writes
252,047 of the 300,292 lemmas of the declared automatic sample that way — would show
disagreement almost everywhere for a typographical reason.

The morphological tag is compared **only if it is the same kind of thing**. A
nine-character AGDT positional tag and a Universal Dependencies `UPOS` cannot be
compared with an equality of strings, and the result would be zero by construction:
if the tags that the model returns do not have the right shape, that measure stops
and the page says why.

The tabs: **Overview**; **Corpus, Stanza, UDPipe** word by word; **Slot by slot**;
**Model disagreements**, that is, the cases in which the two models say different
things from each other, where disagreement with the corpus means nothing; **Does the
model reproduce the noise?**; and **By author**.

### What it does not mean

> A model that says something different from the corpus **does not prove that the
> corpus is wrong**. Models make mistakes, and often. The useful signal is another
> one: where the *two* models agree with each other and together disagree with the
> corpus, it is worth re-reading. It is not proof, it is a good place to look.

And the rate of agreement **is not a measure of the quality of the corpus**: it is a
measure of the distance between two annotations, made with different criteria and on
different schemes. A corpus can be right against both models.

### The commands of this page

*How to read this page* · **Run Stanza** · **Run UDPipe** · the six tabs · on the
tables *Columns ▾*, *Copy*, *⤓ Save as CSV*.

---

## Step 10 · Revised corpus

**What it is for.** Step 5 is where you decide; this is where you look at what came
out of it and take it away. A table compares the original and your version, only for
the words you touched: lemma before and after, tag before and after.

### What to do

You look at the tab *What changed*, and then export in the format you need. If you
have not decided anything yet, the page tells you and sends you back to the step
*Correct*: until the decisions are applied, a revised corpus does not exist, and the
export buttons say so instead of writing a file identical to the original.

Six panels summarise the work: how many records were imported, how many manual
corrections you made, how many records actually changed, what share of the corpus
that is, and how many lemmas were missing before and are missing now.

| Format | What it is for |
|---|---|
| AGDT XML | The same format you started from. It can be loaded into the program again. |
| CSV | A spreadsheet, one row per word. It opens in Excel. |
| CoNLL-U | The format of the Universal Dependencies tools. |

**Save to disk** puts the revised version and all the decisions that produced it into
a single file: you put it aside, send it to a colleague, reload it in a month with
*Load a saved version* and resume where you were.

### What it does not mean

> A frank remark about CoNLL-U: what the program does is a conversion of **format**,
> not of **scheme**. The nine-slot tag stays whole in one column and the morphology
> is spelled out in another, but the syntactic functions stay those of AGDT and do
> not become those of Universal Dependencies. The file is a well-formed CoNLL-U and
> does not claim to be more.

And this version **is not a gold standard**. The program does not call it that, and
not out of modesty: a copy corrected by a single person is not a gold standard (the
interface mentions the phrase only to say that it does not apply here). To deserve
that name you need a written annotation protocol, more than one annotator, a declared
procedure for controversial cases, a measure of agreement between annotators, a
frozen and citable version, and a statement of what the resource covers. The program
makes that road *possible* — it separates the original from the corrected version,
keeps the decisions and reopens them — but it does not walk it in your place.

### The commands of this page

*How to read this page* · *Go to the «Correct» step →* · **Export as AGDT XML** ·
**Export as CSV** · **Export as CoNLL-U** · *Save to disk* · *Load a saved version* ·
*Open the comparison of original, revised corpus, Stanza and UDPipe*.

---

## The AGDT 2.0 scheme (reference page)

**What it is for.** It is the manual inside the program, and it does not need a loaded
corpus: you can read it as soon as the program is open. It sits at the foot of the
left-hand column, under the heading REFERENCE, and it has no number because it is not
a step of the path.

### What to do

Nothing: you read it. The two sections are the tag and the syntactic functions.

**The morphological tag**: the nine slots one by one, what each one records, all the
admitted values with the meaning of each letter, what the hyphen means, and a few
real tags read character by character. For example `v3piia---` reads: verb, third
person, plural, imperfect, indicative, active; the last three slots hold a hyphen
because gender, case and degree are not asked of a finite verb.

**The syntactic functions**: all the relations of the inventory with an explanation
in plain words — `PRED` the predicate, `SBJ` the subject, `OBJ` the governed
argument, `ATR` the attribute, `ADV` the adverbial, `AuxP` the prepositions, `COORD`
coordination, and the others. Then the two suffixes and the infix, which are the part
that disorients whoever reads an AGDT tree for the first time: `_CO` marks a member
of a coordination, `_AP` a member of an apposition, and they can be added together —
in Gorman there really is an `ADV_AP_CO` — while `_ExD` marks a node that stands in
the place of an elided head and declares what function the missing element would have
had.

### What it does not mean

This page describes **the scheme, not the corpus you have loaded**: it says which
values AGDT 2.0 admits, not which ones your corpus uses. And it does not replace the
annotation guidelines of the individual projects, which on hard cases may have
conventions of their own — precisely those that step 3 classifies as variants.

> This page is not written by hand: the program builds it by reading the same table
> that it uses for the checks. It therefore cannot say one thing and check another.

---

## Four things to remember

**The total number of findings is not the number of errors.** It is the sum of three
different things: true violations, habits of the project and spots to read. The three
are treated in incompatible ways, and adding them up gives a number that cannot be
used for anything.

**The program does not correct by itself.** It proposes. Every word that changes in
your version is a word on which you decided, and it stays written when and why.

**The original is never touched.** Whatever happens, the corpus you loaded stays
exactly as it was, and serves as the term of comparison.

**Every number says what it is counted on.** The units are five and are always the
same: the imported records, the active records after the filters, the words, the
analysable links and the analysable sentences. A percentage without a denominator
appears nowhere, and the manifest collects them all in one file.
