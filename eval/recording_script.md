# Recording script: Unhurried test data

These recordings are the raw material for the evaluation. Each line is recorded **in pieces**, so the data script knows exactly where to insert stammers and exactly when each answer really ends (`true_end_ms`). A few extra lines are recorded **whole, with natural thinking pauses**, to give a real-pauses group.

Groups produced from these files:

| Group | Made from | How |
| --- | --- | --- |
| **fluent** | the pieces | Joined with short natural gaps (150–300 ms) |
| **stammered** | the pieces | A block (short burst + 1–3 s silence) inserted before the digit or date piece; 3 variants per line |
| **pauses** | the `P_*` takes | Used as recorded; true end = where speech stops |

---

## Before you record

- **Consent:** if anyone other than me records, ask first. Tell them the files stay on this computer in `eval/data/recordings/` (git-ignored), are used only to measure timing, and will be deleted if they ask. Only my own demo samples are committed.
- **Room:** quiet room, phone or laptop mic, same position for every piece.
- **Format:** 16 kHz, mono, 16-bit WAV. Convert a phone recording with:

  ```
  ffmpeg -i A1_1.m4a -ar 16000 -ac 1 A1_1.wav
  ```

- **Each file:** start recording, wait about a second, read the piece, stop within about a second of finishing.
- **Pieces:** read each piece in the same tone and speed, as if it were part of one sentence. Don't drop your voice at the end of a piece unless it's the last one in the line.
- **Digits:** read them one at a time ("four five two one"). Say "oh" or "zero" for 0, whichever is natural.

---

## Part 1: Lines recorded in pieces

You are calling Northwind Energy. The automated line has just asked you a question.

File names: `<line>_<piece>.wav`, e.g. `A1_1.wav`, `A1_2.wav`, `A1_3.wav`.

### Account number (bot asked: "What's your account number?")

| Line | Piece 1 | Piece 2 | Piece 3 |
| --- | --- | --- | --- |
| A1 | My account number is | 4 5 2 1 | 8 8 3 0 |
| A2 | It's | 7 3 0 9 | 1 1 6 4 |
| A3 | Yes, my account number is | 2 6 0 4 | 9 9 1 8 |
| A4 | Okay, it's | 8 1 5 5 | 3 0 2 7 |

### Date of birth (bot asked: "What's your date of birth?")

| Line | Piece 1 | Piece 2 | Piece 3 |
| --- | --- | --- | --- |
| D1 | My date of birth is | the fourteenth of March | nineteen ninety nine |
| D2 | It's | the second of October | two thousand and four |

### Reason for calling (bot asked: "What are you calling about?")

| Line | Piece 1 | Piece 2 |
| --- | --- | --- |
| R1 | I'm calling about | my last bill |
| R2 | I want to set up | a payment plan |

### Confirmation (bot asked: "I have … Is that right?")

| Line | Piece 1 | Piece 2 | Piece 3 |
| --- | --- | --- | --- |
| C1 | Yes, that's right. | | |
| C2 | No, it's | 4 5 2 1 | 8 8 3 1 |

**Total: 26 files.**

---

## Part 2: Natural-pause takes (one file each)

Read the whole line in one go. Where it says *(pause)*, pause for as long as feels natural, like looking for a letter or remembering. Don't time it.

| File | Slot | Line |
| --- | --- | --- |
| `P_A2.wav` | account_number | It's *(pause)* hang on *(pause)* 7 3 0 9 *(pause)* 1 1 6 4. |
| `P_A4.wav` | account_number | Let me just find the letter. *(pause)* Okay, it's 8 1 5 5 3 0 2 7. |
| `P_D1.wav` | date_of_birth | My date of birth is *(pause)* the fourteenth of *(pause)* March nineteen ninety nine. |
| `P_R1.wav` | reason | I'm calling about *(pause)* um *(pause)* my last bill. |

**Total: 4 files.**

---

## Part 3: `lines.csv`

Save next to the WAVs as `eval/data/recordings/lines.csv`. `pieces` is how many files the line has (1 for the pause takes). Leave the *(pause)* marks out of `text`.

```csv
line,slot,pieces,text
A1,account_number,3,My account number is 4 5 2 1 8 8 3 0
A2,account_number,3,It's 7 3 0 9 1 1 6 4
A3,account_number,3,"Yes, my account number is 2 6 0 4 9 9 1 8"
A4,account_number,3,"Okay, it's 8 1 5 5 3 0 2 7"
D1,date_of_birth,3,My date of birth is the fourteenth of March nineteen ninety nine
D2,date_of_birth,3,It's the second of October two thousand and four
R1,reason,2,I'm calling about my last bill
R2,reason,2,I want to set up a payment plan
C1,confirm,1,"Yes, that's right."
C2,confirm,3,"No, it's 4 5 2 1 8 8 3 1"
P_A2,account_number,1,It's hang on 7 3 0 9 1 1 6 4
P_A4,account_number,1,"Let me just find the letter. Okay, it's 8 1 5 5 3 0 2 7"
P_D1,date_of_birth,1,My date of birth is the fourteenth of March nineteen ninety nine
P_R1,reason,1,I'm calling about um my last bill
```

---

## Checklist

- [ ] 26 piece files recorded (A1–A4, D1–D2, R1–R2, C1–C2)
- [ ] 4 pause takes recorded (`P_A2`, `P_A4`, `P_D1`, `P_R1`)
- [ ] All converted to 16 kHz mono WAV
- [ ] `lines.csv` saved next to them
- [ ] Listened to 2–3 files to check they're clean
- [ ] Ran the Ticket 2 data script and listened to 3 generated clips

## Limitations (for the write-up)

- One speaker (me) unless others record; results may partly reflect how I speak.
- Stammers are inserted, not real. Real-speech checking is Ticket 10 (SEP-28k).
- Joined pieces can sound slightly less natural than one continuous take.