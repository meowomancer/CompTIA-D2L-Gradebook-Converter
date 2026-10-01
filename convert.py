#!/usr/bin/env python3
"""Convert CompTIA CertMaster Learn gradebook exports into a D2L import CSV.

    python3 convert.py COMPTIA_LABS.csv D2L.csv --week N [--quizzes COMPTIA_QUIZZES.csv]
                       [--keep-existing] [--out d2l_import.csv]

config.json  "weeks":   CompTIA lab numbers for each week; D2L points come from the
                        D2L column header (MaxPoints)
             "quizzes": the week each quiz is due (quiz columns map one-to-one)
users.json   D2L username -> CompTIA emails (labs) and names (quizzes). Built
             automatically; you are prompted only for accounts that cannot be
             matched on their own. Entries under the key "skip" are ignored.

Lab weeks and quizzes due in week N or earlier are filled (unattempted work
counts as 0); later ones stay blank. Two CompTIA accounts for one student merge
by taking the higher score per lab or quiz. Cells that already hold a value are
overwritten unless --keep-existing is given. Other D2L columns are untouched.
"""
import argparse, csv, difflib, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = HERE / "config.json"
USERS = HERE / "users.json"

LAB_ID = re.compile(r"^Lab - (\S+)")                 # "Lab - 2.1.16 Lab: ..." -> "2.1.16"
QUIZ_ID = re.compile(r"Quiz (\d+)")                  # "CIS140L Quiz 1 (2026)" -> "1"
STUDENT = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")    # "Last, First (email)"
D2L_WEEK = re.compile(r"\bWeek (\d+)\b")             # lab column: also contains "CompTIA Lab"
D2L_QUIZ = re.compile(r"CompTIA Quiz (\d+)")
MAXPTS = re.compile(r"MaxPoints:(\d+)")


def read_comptia(path, id_re):
    """Return ({col: points_possible}, [(name, email_or_None, {col: score})])."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if any(r)]
    if "points" not in rows[1][0].lower():
        sys.exit(f"{path}: second row must be the Points Possible row, got {rows[1][0]!r}")
    cols = [(m.group(1) if (m := id_re.search(h)) else h) for h in rows[0][1:]]
    possible = dict(zip(cols, (float(v or 0) for v in rows[1][1:])))
    students = []
    for row in rows[2:]:
        m = STUDENT.match(row[0])
        name, email = (m.group(1), m.group(2).lower()) if m else (row[0], None)
        students.append((name, email, {c: float(v) for c, v in zip(cols, row[1:]) if v.strip()}))
    return possible, students


def owner(users, ident):
    return next((u for u, ids in users.items() if ident in ids), None)


def ask(users, ident, name, usernames):
    """Prompt for the D2L username that owns a CompTIA email or name; record the answer."""
    last, _, first = name.partition(", ")
    by_words = {u.replace(".", " "): u for u in usernames}
    close = difflib.get_close_matches(f"{first} {last}".lower(), by_words, n=1, cutoff=0.5)
    guess = by_words[close[0]] if close else "skip"
    ans = input(f"CompTIA '{name}' <{ident}> -> D2L [{guess}]? Enter=accept, or type username / skip: ").strip()
    users.setdefault(ans or guess, []).append(ident)


def link(users, students, usernames, by_name={}):
    """Give every CompTIA row a D2L owner in users; return {username: [score dicts]}."""
    out = {}
    for name, email, scores in students:
        ident = email or name
        if owner(users, ident) is None:
            if email and email.split("@")[0] in usernames:
                users.setdefault(email.split("@")[0], []).append(ident)
            elif not email and name in by_name:             # quiz row known from the lab export
                users.setdefault(by_name[name], []).append(ident)
            else:
                ask(users, ident, name, usernames)
        out.setdefault(owner(users, ident), []).append(scores)
    return out


def merge(score_dicts):
    merged = {}
    for d in score_dicts:
        for k, v in d.items():
            merged[k] = max(merged.get(k, 0), v)
    return merged


def week_points(scores, labs, possible, pts):
    tot = sum(possible[l] for l in labs)
    got = sum(scores.get(l, 0) for l in labs)
    return round(got / tot * pts, 2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comptia", help="CompTIA lab gradebook export")
    ap.add_argument("d2l", help="D2L gradebook export")
    ap.add_argument("--week", type=int, required=True, help="fill this week and all earlier weeks")
    ap.add_argument("--quizzes", help="CompTIA quiz export; quizzes are synced only when given")
    ap.add_argument("--keep-existing", action="store_true", help="never overwrite a cell that already has a value")
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--out", default="d2l_import.csv")
    out.add_argument("--stdout", action="store_true", help="print the CSV to the terminal instead of writing a file")
    out.add_argument("--table", action="store_true", help="print a readable table of the CompTIA columns instead of writing a file")
    args = ap.parse_args(argv)
    warn = lambda msg: print(f"warning: {msg}", file=sys.stderr)

    cfg = json.loads(CONFIG.read_text())
    weeks = {w: (v["labs"] if isinstance(v, dict) else v) for w, v in cfg["weeks"].items()}  # old format had {"points", "labs"}
    due = cfg.get("quizzes", {})
    lab_possible, lab_students = read_comptia(args.comptia, LAB_ID)
    if bad := [l for labs in weeks.values() for l in labs if l not in lab_possible]:
        sys.exit(f"config.json labs not found in CompTIA export: {bad}")

    with open(args.d2l, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if any(r)]   # D2L exports end with a blank line
    usernames = [r[1].lstrip("#") for r in rows[1:]]

    users = json.loads(USERS.read_text()) if USERS.exists() else {}
    labs_by_user = link(users, lab_students, usernames)
    quiz_possible, quizzes_by_user = {}, {}
    if args.quizzes:
        quiz_possible, quiz_students = read_comptia(args.quizzes, QUIZ_ID)
        by_name = {name: owner(users, email) for name, email, _ in lab_students}
        quizzes_by_user = link(users, quiz_students, usernames, by_name)
    USERS.write_text(json.dumps(users, indent=2, sort_keys=True) + "\n")

    lab_cols, quiz_cols = {}, {}   # week/quiz number -> (column index, D2L max points)
    for i, h in enumerate(rows[0]):
        m = D2L_QUIZ.search(h) or ("CompTIA Lab" in h and D2L_WEEK.search(h))
        if not m:
            continue
        if not (pts := MAXPTS.search(h)):
            warn(f"skipping {h!r}: no MaxPoints in the header")
            continue
        (quiz_cols if m.re is D2L_QUIZ else lab_cols)[m.group(1)] = (i, int(pts.group(1)))
    for w in weeks.keys() - lab_cols.keys():
        warn(f"week {w} in config.json has no column in the D2L file")

    for row in rows[1:]:
        u = row[1].lstrip("#")

        def put(col, val):
            if not (args.keep_existing and row[col].strip()):
                row[col] = f"{val:g}"

        if u in labs_by_user:
            got = merge(labs_by_user[u])
            for w, (col, pts) in lab_cols.items():
                if w in weeks and int(w) <= args.week:
                    put(col, week_points(got, weeks[w], lab_possible, pts))
        else:
            print(f"missing: {row[1]} is in D2L but not CompTIA", file=sys.stderr)
        if u in quizzes_by_user:
            got = merge(quizzes_by_user[u])
            for q, (col, pts) in quiz_cols.items():
                if q in due and due[q] <= args.week and quiz_possible.get(q):
                    put(col, round(got.get(q, 0) / quiz_possible[q] * pts, 2))
        elif args.quizzes:
            print(f"missing: {row[1]} is in D2L but not the quiz export", file=sys.stderr)

    for u in (labs_by_user.keys() | quizzes_by_user.keys()) - set(usernames) - {"skip"}:
        print(f"missing: '{u}' is in CompTIA but not D2L", file=sys.stderr)

    if args.table:
        by_num = lambda d: sorted(d.items(), key=lambda kv: int(kv[0]))
        cols = {"Username": 1} | {f"Week {w}": c for w, (c, _) in by_num(lab_cols)} | {f"Quiz {q}": c for q, (c, _) in by_num(quiz_cols)}
        table = [list(cols)] + [[r[c].lstrip("#") for c in cols.values()] for r in rows[1:]]
        widths = [max(len(t[i]) for t in table) for i in range(len(cols))]
        for t in table:
            print("  ".join(v.ljust(w) for v, w in zip(t, widths)).rstrip())
    elif args.stdout:
        csv.writer(sys.stdout, lineterminator="\n").writerows(rows)
    else:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
