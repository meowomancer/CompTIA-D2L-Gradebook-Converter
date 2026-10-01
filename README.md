# CompTIA to D2L gradebook converter

Turns CompTIA CertMaster Learn gradebook CSV exports into a D2L CSV gradebook files for import into D2L. Each week's CompTIA labs are combined into one D2L column. Quizzes copy over one to one. Both labs and quizzes are scaled from the CompTIA point values to the point values configured in the D2L gradebook.

This script requires Python 3.11. 

## Setup

1. Check that Python 3.11 or newer is installed. Nothing else is needed.

   ```bash
   python3 --version
   ```

2. Copy the config for your course to `config.json`. The file lists which CompTIA labs belong to each week and when each quiz is due.

   ```bash
   cp CIS140L-config.json.example config.json
   ```

   Use `CIS145-config.json.example` for CIS 145 and `CIS140L-config.json.example` for CIS 140L. Both example config files are in alignment with the D2L teach shells as of Oct. 1, 2026. Nonetheless, be sure to check your config for alignment with your schedule.

3. `users.json` is created the first time you run the script. It remembers which CompTIA account belongs to which D2L student.

## Running it

1. Export the lab gradebook from CompTIA with the "Show scores as points" option ticked and save it as `comptia.csv`.
2. Export your gradebook from D2L and save it as `d2l.csv`. Include the Org Defined ID, Username, and the CompTIA lab and quiz columns.
3. If you also want quiz grades, export the quiz report from CompTIA (you will need to create a custom report) and save it as `quizzes.csv`.
4. Put the files in this folder and run one of these:

```bash
# Labs only, through week 4
python3 convert.py comptia.csv d2l.csv --week 4

# Labs and quizzes
python3 convert.py comptia.csv d2l.csv --quizzes quizzes.csv --week 4

# Look at the result in the terminal before importing
python3 convert.py comptia.csv d2l.csv --quizzes quizzes.csv --week 4 --table

# Rerun without touching grades that are already in the D2L export.
python3 convert.py comptia.csv d2l.csv --week 4 --keep-existing
```

The result is written to `d2l_import.csv`. Import it in D2L under Grades -> Import.

Note: Unless the `--keep-existing` option is utilized, the script's default behavior is to overwrite existing D2L CompTIA grades with whatever scores are present in CompTIA. This is helpful for situations such as allowing the submission of late work, revisions of past submissions, and so on. 

### Options

| Option | What it does | Default |
| --- | --- | --- |
| `comptia.csv` | CompTIA lab gradebook export. Required. | |
| `d2l.csv` | D2L gradebook export. Required. | |
| `--week N` | Fill this week and every earlier week, plus any quiz due by then. Later weeks and quizzes stay blank. Required. | |
| `--quizzes FILE` | CompTIA quiz export. Quizzes are only synced when this is given. | off |
| `--keep-existing` | Leave any D2L cell that already has a value. Without it, computed grades replace what is there, which is what you want after accepting late or revised work. | overwrite |
| `--out FILE` | Where to write the import CSV. | `d2l_import.csv` |
| `--stdout` | Print the import CSV to the terminal instead of writing a file. | off |
| `--table` | Print a readable grid of the CompTIA columns instead of writing a file. | off |

Labs and quizzes a student never opened count as zero once their week is due. `--out`, `--stdout`, and `--table` cannot be combined.

### What it prints

- `missing:` lines list students who are in one system and not the other. A D2L student with no CompTIA account is left blank, not zeroed.
- `warning:` lines mean a week in `config.json` has no column in the D2L file, or a D2L column has no point value in its header.

## Matching students

CompTIA knows students by email and D2L by username. When the part of the email before the `@` matches a D2L username, the script links them on its own. Otherwise it guesses from the student's name and asks you:

```
CompTIA 'Doe, Jane' <jdoe3@pcc.edu> -> D2L [jane.doe]? Enter=accept, or type username / skip:
```

Press Enter if the guess is right. Type the correct D2L username if it is wrong. Type `skip` if the student has no D2L account, for example someone who dropped the class but is still in CompTIA.

Answers are saved in `users.json`, so each student is asked about once. The file looks like this:

```json
{
  "jane.doe": ["jdoe3@pcc.edu", "jane.doe@gmail.com", "Doe, Jane"],
  "skip": ["dropped.student@pcc.edu"]
}
```

The quiz export lists students by name only, so names are matched through the lab export and then saved alongside the emails. You are only asked about a quiz name that does not appear in the lab export.

A student with two CompTIA accounts gets both emails under one username, and the higher score on each lab or quiz counts. To fix a wrong match, edit the file in a text editor and run the script again. To stop skipping someone, delete their email from the `skip` list.

## Changing the lab mapping

Open `config.json`. Each week lists the CompTIA lab numbers that count toward it:

```json
"2": ["2.1.2", "2.1.16", "2.2.11", "2.2.13", "3.1.2", "3.5"],
```

Use the number at the start of the lab title in CompTIA, such as `2.1.16` for "2.1.16 Lab: Set Up a Desktop Computer". Keep the quotes and commas as they are. A student's week score is their share of the possible points across the listed labs, times the point value of that week's D2L column. If you list a lab number that is not in the CompTIA export, the script stops and names it.

Below the weeks, the `quizzes` table says which week each quiz is due, so `--week` knows when to start writing it:

```json
"quizzes": {"1": 2, "2": 4, "3": 6, "4": 8, "5": 10}
```

A quiz's D2L point value comes from the D2L column itself, and the CompTIA score is scaled to it, so 9 of 10 in CompTIA becomes 18 of 20 in D2L.

## Checking the script

Run the converter on the example exports for both courses. Successful tests will result in a final output of 'ok'

```bash
python3 tests/test_convert.py
```

