"""python3 tests/test_convert.py  -- runs on the example exports, no prompts."""
import contextlib, csv, io, json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import convert

EX = ROOT / "example_data"
tmp = Path(tempfile.mkdtemp())
convert.USERS = tmp / "users.json"
seed = {
    "student.trois": ["student.three@school.edu"],
    "student.four": ["student.four@school.edu", "student.four@personal.email"],
    "skip": ["student.five@personal.email"],
}

def run(course, *extra):
    """Run the converter on one course's examples with a fresh users.json; return the output rows."""
    convert.CONFIG = ROOT / f"CIS{course}-config.json.example"
    convert.USERS.write_text(json.dumps(seed))
    out = tmp / "out.csv"
    convert.main([str(EX / f"example_comptia_{course}_export.csv"), str(EX / f"example_d2l_{course}_export.csv"), "--out", str(out), *extra])
    return list(csv.reader(out.open()))

# --- CIS145: old header format, labs only, 30 pts per week from the D2L header ---
rows = {r[1]: r for r in run("145", "--week", "3")}
# week 2 possible = 6+10+3+4+7+3 = 33; everyone matched earned 6 -> 6/33*30
assert rows["#student.one"][2] == "5.45", rows["#student.one"]
assert rows["#student.trois"][2] == "5.45"        # name-mapped account
assert rows["#student.four"][2] == "5.45"         # two accounts, max per lab, 2.1.7 not in week 2
assert rows["#student.one"][3] == "0"             # week 3 filled with 0
assert rows["#student.one"][4] == ""              # week 4 untouched
assert rows["#student.five"][2] == ""             # skipped -> reported missing, left blank
assert json.loads(convert.USERS.read_text())["student.one"] == ["student.one@school.edu"]   # auto-matched and saved

# --- CIS140L: new header format, 25 pts per week from D2L, quizzes; --week 4 fills quizzes due weeks 2 and 4 ---
out = run("140L", "--week", "4", "--quizzes", str(EX / "example_comptia_140L_quiz_export.csv"))
hdr, rows = out[0], {r[1]: r for r in out[1:]}
col = lambda s: next(i for i, h in enumerate(hdr) if h.startswith(s))
W1, W2, W3, W10 = col("Week 1 "), col("Week 2 "), col("Week 3 "), col("Week 10 ")
Q1, Q2, Q3 = col("CompTIA Quiz 1"), col("CompTIA Quiz 2"), col("CompTIA Quiz 3")
assert rows["#student.one"][W1] == "25"           # 3/3 * 25 (D2L header), config has no points
assert rows["#student.one"][W2] == "25"           # 4/4 * 25
assert rows["#student.four"][W2] == "25"          # one account blank, the other full -> max
assert rows["#student.one"][W3] == "0"            # week 3 due, nothing done
assert rows["#student.one"][W10] == ""            # no config entry -> untouched
assert rows["#student.one"][Q1] == "22.5"         # 18/20 * 25
assert rows["#student.two"][Q1] == "22.09"        # 17.67/20 * 25
assert rows["#student.one"][Q2] == "0"            # due week 4, not taken
assert rows["#student.four"][Q1] == "22.5" and rows["#student.four"][Q2] == "25"   # two same-name rows merged
assert rows["#student.trois"][Q1] == "23.75"      # quiz name -> lab email -> D2L username
assert rows["#student.one"][Q3] == ""             # due week 6 -> blank
assert rows["#student.five"][Q1] == ""            # skipped via lab email, quiz row follows
assert "Five, Student" in json.loads(convert.USERS.read_text())["skip"]

# --- --keep-existing leaves filled cells alone; default overwrites ---
convert.CONFIG = ROOT / "CIS145-config.json.example"
pre = tmp / "prefilled.csv"
src = list(csv.reader((EX / "example_d2l_145_export.csv").open()))
src[1][2] = "30"                                  # student.one week 2 already graded
csv.writer(pre.open("w", newline="")).writerows(src)
lab145 = str(EX / "example_comptia_145_export.csv")
convert.USERS.write_text(json.dumps(seed))
convert.main([lab145, str(pre), "--week", "2", "--out", str(tmp / "k.csv"), "--keep-existing"])
rows = {r[1]: r for r in csv.reader((tmp / "k.csv").open())}
assert rows["#student.one"][2] == "30" and rows["#student.two"][2] == "5.45"
convert.main([lab145, str(pre), "--week", "2", "--out", str(tmp / "o.csv")])
assert {r[1]: r for r in csv.reader((tmp / "o.csv").open())}["#student.one"][2] == "5.45"

# --- --stdout prints the CSV, --table prints a readable grid; neither writes a file ---
def capture(*extra):
    buf = io.StringIO()
    convert.USERS.write_text(json.dumps(seed))
    with contextlib.redirect_stdout(buf):
        convert.main([lab145, str(EX / "example_d2l_145_export.csv"), "--week", "2", *extra])
    return buf.getvalue()
os.chdir(tmp)
csv_out = capture("--stdout")
assert csv_out.splitlines()[0].startswith("OrgDefinedId,Username,") and "#student.one,5.45," in csv_out
tbl = capture("--table").splitlines()
assert tbl[0].split() == ["Username"] + [t for w in range(2, 10) for t in ("Week", str(w))]
assert tbl[1].split() == ["student.one", "5.45"]
assert not (tmp / "d2l_import.csv").exists()

assert convert.week_points({"a": 1, "b": 3}, ["a", "b"], {"a": 4, "b": 4}, 25) == 12.5
print("ok")
