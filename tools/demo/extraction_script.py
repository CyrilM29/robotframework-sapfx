"""Le COMMENTAIRE de la démo d'extraction, en anglais.

Fichier de variables Robot : la suite l'importe et y trouve ``${SCRIPT}``.

Chaque réplique porte DEUX formes, et c'est la seule subtilité du fichier.
``text`` est ce que le spectateur LIT dans le bandeau, avec l'orthographe
technique exacte (SE16, DD03L, ALV, CSV). ``speech`` est ce que la synthèse
vocale DIT, où les sigles sont épelés et les nombres écrits en chiffres, parce
qu'une voix de synthèse lit « SE16 » de façon imprévisible alors qu'elle lit
« S E sixteen » toujours pareil. Les deux formes disent la même chose : la
seconde n'est qu'une prononciation de la première.

Les chiffres cités sont MESURÉS sur la cible (A4H, release 754) et la suite les
ASSERTE avant de les faire dire : un commentaire ne doit pas pouvoir annoncer un
résultat que le système n'a pas produit.
"""

SCRIPT = [
    {
        "id": "c01",
        "text": "A live SAP system, driven from Robot Framework.",
        "speech": (
            "This is a live S A P system: an ABAP stack running in a Docker "
            "container on this machine. Everything you are about to see is "
            "driven from Robot Framework, through the S A P GUI scripting "
            "interface. Nothing is simulated, and nothing is replayed."
        ),
    },
    {
        "id": "c02",
        "text": "The task: take a very large table out of SAP, as usable files.",
        "speech": (
            "The task is easy to state, and surprisingly easy to get wrong: "
            "take a very large table out of S A P, and turn it into files that "
            "an analyst, or a data pipeline, can actually use."
        ),
    },
    {
        "id": "c03",
        "text": "Transaction SE16, the Data Browser, on table DD03L.",
        "speech": (
            "We open the Data Browser, transaction S E sixteen, on table "
            "D D zero three L. That table is the ABAP dictionary field "
            "catalogue: it describes every field of every table in the system, "
            "which makes it one of the largest tables a standard system carries."
        ),
    },
    {
        "id": "c04",
        "text": "How many rows? 1,819,533. Answered by the database, not the screen.",
        "speech": (
            "Before reading anything, we ask S A P how many rows the table "
            "holds. The answer comes from the database, not from the screen: "
            "1,819,533 rows."
        ),
    },
    {
        "id": "c05",
        "text": "We bound the reading with SAP's own hit limit: 5,000 rows.",
        "speech": (
            "We are not going to put 1.8 million rows on a screen, and we "
            "should not pretend to. We bound the selection with S A P's own "
            "maximum number of hits, 5,000 rows, and we let the grid render them."
        ),
    },
    {
        "id": "c06",
        "text": "5,000 rows, 31 columns: 155,000 cells.",
        "speech": (
            "5,000 rows, 31 columns. That is 155,000 cells. And this is exactly "
            "where a naive extraction goes quietly wrong."
        ),
    },
    {
        "id": "c07",
        "text": "An ALV grid renders only the window you are looking at.",
        "speech": (
            "An A L V grid does not materialise all of its rows. It renders the "
            "window you are looking at, and it hands back every row you have not "
            "scrolled to as empty cells. It never raises an error."
        ),
    },
    {
        "id": "c08",
        "text": "So a naive read returns 5,000 rows: right shape, hollow content.",
        "speech": (
            "So a reader that simply asks for 5,000 rows gets 5,000 rows back. "
            "The right count, the right columns, and most of them empty. The "
            "file that comes out is complete in shape and hollow in content."
        ),
    },
    {
        "id": "c09",
        "text": "The library scrolls the grid to force every row to materialise.",
        "speech": (
            "The library therefore scrolls the grid, window by window, forcing "
            "every row to materialise before it reads a single cell. That is "
            "what you are watching now."
        ),
    },
    {
        "id": "c10",
        "text": "155,000 values, one scripting call per cell.",
        "speech": (
            "This is the slow part, and it is slow for an honest reason. The "
            "scripting interface returns one cell per call, so the whole table "
            "crosses that boundary value by value: 155,000 of them."
        ),
    },
    {
        "id": "c11",
        "text": "Reading what the screen really holds, not what it claims to hold.",
        "speech": (
            "A little over eighty seconds, for a table this wide. That is the "
            "price of reading what the screen really holds, instead of what it "
            "appears to hold."
        ),
    },
    {
        "id": "c12",
        "text": "Rows read: 5,000. Rows declared: 5,000. Blank rows: 0.",
        "speech": (
            "Then the extract is confronted with its own contract. Rows read: "
            "5,000. Rows the grid declares: 5,000. Blank rows: zero."
        ),
    },
    {
        "id": "c13",
        "text": "Without that check, a truncated read and a complete one are the same file.",
        "speech": (
            "That comparison is the whole point. Without it, the sentence "
            "\"the table fits in 5,000 rows\" and the sentence \"the reading "
            "stopped at 5,000 rows\" produce exactly the same file, and the "
            "second one is an extract presented as an inventory."
        ),
    },
    {
        "id": "c14",
        "text": "One keyword, five formats: SVG, Excel, CSV, JSON Lines, Parquet.",
        "speech": (
            "Now the restitution. A single keyword writes that same extract "
            "into five formats: an S V G document, an Excel workbook, a "
            "C S V file, Jason Lines, and Parquet."
        ),
    },
    {
        "id": "c15",
        "text": "Each file is read back and compared row by row against the screen.",
        "speech": (
            "And every one of them is written, then read back from disk and "
            "compared row by row with what was read on the screen. A file that "
            "exists, and weighs a plausible number of bytes, is not a correct file."
        ),
    },
    {
        "id": "c16",
        "text": "The destination folder: the same 155,000 cells, five times over.",
        "speech": (
            "Here is the destination folder. The same 155,000 cells, written "
            "five times over."
        ),
    },
    {
        "id": "c17",
        "text": "4.9 MB for the SVG, down to 83 KB for Parquet: 62 times smaller.",
        "speech": (
            "Look at the spread. Nearly 5 megabytes for the S V G, because it "
            "is a drawn document and every cell is a piece of text. 2.4 for "
            "Jason Lines. Around half a megabyte for the workbook and the "
            "C S V. And 83 kilobytes for Parquet, which stores by column and "
            "compresses: sixty times smaller, for the very same data."
        ),
    },
    {
        "id": "c18",
        "text": "The CSV, raw. The header carries SAP's technical field names.",
        "speech": (
            "The C S V, opened raw. Notice the header line: those are the "
            "technical field names S A P uses internally, not translated column "
            "titles, because a technical name reads the same in every language."
        ),
    },
    {
        "id": "c19",
        "text": "The same extract in Excel: 31 columns, 5,000 rows plus the header.",
        "speech": (
            "The same extract in Excel. Jump to the last cell, and there it is: "
            "column 31, row 5,001, header included. Every value is stored as "
            "text, deliberately. Let a spreadsheet infer types, and a client "
            "number like zero zero zero becomes a single zero."
        ),
    },
    {
        "id": "c20",
        "text": "And the SVG: 5,000 rows of vector document, readable anywhere.",
        "speech": (
            "And the S V G: 5,000 rows of vector document, readable in a "
            "browser, with neither S A P nor Excel needed at the other end."
        ),
    },
    {
        "id": "c21",
        "text": "A bounded reading, proved against what the grid declared.",
        "speech": (
            "One table of 1.8 million rows. One bounded reading, proved against "
            "what the grid itself declared. And five files that carry exactly "
            "what the screen carried. That is the difference between a "
            "screenshot and an extraction."
        ),
    },
]
