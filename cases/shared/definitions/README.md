# The shared case definitions

Two files hold the cases the public drill runs on.

| File | Version | Company | Lines | Mode |
| --- | --- | --- | --- | --- |
| `halyard-v4.json` | halyard-v4, 13 September 2026 | Halyard Provisioning Group, Inc. | 14 | practice |
| `brightwater-v4.json` | brightwater-v4, 13 September 2026 | Brightwater Dental Partners, PLLC | 5 | assessment |
| `halyard-v3.json` | halyard-v3, 13 September 2026 | Halyard Provisioning Group, Inc. | 14 | practice, retired |
| `brightwater-v3.json` | brightwater-v3, 13 September 2026 | Brightwater Dental Partners, PLLC | 5 | assessment, retired |
| `brightwater-v2.json` | brightwater-v2, 13 September 2026 | Brightwater Dental Partners, PLLC | 5 | practice, retired |

The retired files are kept because responses were scored against them and a superseded key has to
stay readable. The page loads the v4 pair only, and rows scored against one version are never
pooled with rows scored against another. Each v4 file carries a `changeLog` array recording what
moved from v3 and why.

## The basis key

Every card carries `basisKey`, the set of basis chips that are correct on that card. A chip
outside that set contradicts the key for that card, which is why `wrong account` on a clean line
is wrong rather than merely unhelpful. The page counts the reason as right when the player tapped
at least one chip in the key and no chip outside it, and it counts that apart from the call.

A card the key lets stand carries `the figure and reason hold` and nothing else, because a chip
naming a defect contradicts a line that has none. `build-cases.cjs` refuses to write if a stand
carries anything else, if a flag carries the hold chip, or if a key names a chip the page does
not offer.

No card in either case has an amount booked in an account it does not belong in, so
`wrong account` is in no key in this release. Tapping it on all nineteen lines scores zero on
reason. That is the point of counting the reason separately: the same run scored 14 of 14 and 5
of 5 on the call in the 13 September review.

The reason score is a compatibility check on the stated basis and not a rubric score. It never
moves the rank or the badges, which read the call score only. A participant who taps
`no source on file` on every flag and the hold chip on every stand would score well on reason
without having reasoned, so the three-dimension reasoning rubric stays with a person outside the
page, and reviewer disagreements are retained rather than settled by the key.

Each file carries the company and period, the threshold policy and a sentence on its scope, a
note on what On file means, the ledger rows, the statement groups, and one entry per line with
the memo sentence, the on-file facts, the key, the error type, the reveal reason, the tell, and
the over-flag note where there is one. A file with `"mode": "assessment"` also carries
`assessmentNote`, the sentence the bridge screen prints to say what is already settled.

## The assessment case, brightwater-v4

Round two is an independent assessment rather than more practice, so the page suppresses every
signal that would leak correctness: no reveal between lines, no running score, no streak, and no
track. All five verdicts arrive together on a results screen once the fifth call is in.

Every one of the five lines tests causal evidence. Every figure in every sentence ties to the
ledger, every direction word matches the sign of the movement, and every threshold reading in the
memo is correct. Every line carries a sentence naming a cause, so on all five the only question
is whether something on file carries that cause. The mix is three unsupported-cause flags, lines
1, 3 and 4, and two supported-cause stands, lines 2 and 5.

| Line | Account | May | June | Change | Percent | Owes commentary | Call | Type | Basis key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5210 Dental supplies and lab fees | $138,500 | $191,200 | +$52,700 | 38.1% | yes | Flag | unsupported driver | no source on file |
| 2 | 6110 Hygienist wages | $214,000 | $268,900 | +$54,900 | 25.7% | yes | Let it stand | clean line | the figure and reason hold |
| 3 | 4220 Orthodontic plan revenue | $96,000 | $138,400 | +$42,400 | 44.2% | yes | Flag | unsupported driver | wrong period; no source on file |
| 4 | 4010 Patient service revenue, net | $742,000 | $803,500 | +$61,500 | 8.3% | no | Flag | unsupported driver | no source on file |
| 5 | 6610 Marketing and patient outreach | $18,400 | $24,100 | +$5,700 | 31.0% | no | Let it stand | clean line | the figure and reason hold |

The two stands are carried by a document. Line 2 has a June payroll register putting the whole
$54,900 on the two hygienists hired for the second chair, with no other hygienist pay moving.
Line 5 has the vendor invoice for the mailer and $18,400 of unchanged recurring spend, which
together reconcile the whole of June's $24,100.

The three flags name a cause nothing supplied establishes. Line 1 attributes $52,700 to a new
surgical suite with no case mix report, no lab invoice summary and no implant count on file.
Line 3 attributes $42,400 to thirty-one plans that started in June, and the only plan schedule on
file is dated 31 May and covers the plans running before June, so a genuine document is on file
and it relates to the wrong period. Line 4 attributes $61,500 to two associate dentists with no
production report by provider and no visit count on file.

Line 3 is the line that stops document presence from being an automatic answer. A participant who
reads "schedule on file" and lets the sentence stand has not checked what period the schedule
covers.

Lines 4 and 5 both say plainly on file that the threshold required no commentary and the memo
explained the line anyway, so the question on both is the explanation rather than whether one was
owed. That sentence appears on both, so it separates nothing except the evidence.

### What a shortcut scores

Stated rather than claimed away. Three lines clear both legs of the threshold and two clear one
leg each.

| Strategy | Calls | Right |
| --- | --- | --- |
| The key | flag, stand, flag, flag, stand | 5 of 5 |
| Flag every line over both legs | flag, flag, flag, stand, stand | 3 of 5 |
| Flag every line | flag, flag, flag, flag, flag | 3 of 5 |
| Let every line stand | stand, stand, stand, stand, stand | 2 of 5 |

Two shortcuts reach 3 of 5 on the call. Five items cannot separate judgment from a shortcut on
their own, which is why the fresh case is reported as five-item decision accuracy on a second
unseen set, scored the same way as round one, and never as proof of transfer or of a learning
gain. The reason score is the second reading, and a shortcut carries no reason with it.

`build-cases.cjs` enforces the assessment contract. It refuses to write if a memo states a dollar
figure the account does not produce, states a percent that is not the movement, uses a direction
word against the sign, if an assessment line carries no memo sentence, or if an assessment line
is a no-explanation line. A silent line has no cause to judge, so it belongs in the practice case
and not in the scored one.

## How the page reads them

`index.html` fetches both files at load. When the fetch fails, which is what happens when the
file is opened from a folder rather than served, the page falls back to a copy of the same JSON
written into the file between the `BUILD:CASES-START` and `BUILD:CASES-END` markers.

The JSON files are the source of truth. After editing either one, run:

```
node build-cases.cjs
```

That rewrites the inline copy and refuses to write if a card points at an account that is not in
the ledger, if a card's figures do not tie to the ledger row, if a card is missing its key, its
reason or its tell, or if a basis key breaks the rules above. Never hand-edit the generated
block.

`window.__BTM_CASES` on the live page reports which of the two paths won, and the version and
date ride into the response record on question A and into the local copy.

## For the checker lane

`checker.html` ships a Halyard sample. It must be regenerated from `halyard-v4.json` by the
checker lane; nothing in this folder changes the checker, and the game lane does not edit
`checker.html` or `CHECKER.md`.

The checker's ledger already matches all fourteen game accounts. Its sample memo does not. The
differences known on 13 September 2026:

1. **The sample is thirteen lines, the game is fourteen.** The two are different memo versions,
   not the same text at different lengths.
2. **"Both revenue lines."** The sample restores a sentence tying the two revenue lines together.
   The game's card 12 turns on the memo never making that connection, so the sample resolves the
   line the game asks the player to catch.
3. **Pump-price assertions.** The sample asserts lower pump prices as the fleet fuel driver. The
   game's card 9 stands on a narrow statement with no driver asserted, and on case facts that
   state June consumption and June invoices are the same population.
4. **Billing assertions placed inside the draft.** The sample has the draft assert its own
   support. A draft's assertion about its own support is not independent evidence, and cards 4,
   8, 12 and 14 in halyard-v4 now turn on exactly that distinction.
5. **No separate case-fact summary.** The game supplies On file facts per line as verified case
   assumptions. The checker supplies none, so a clean verdict in the game does not transfer to
   the checker sample without the matching evidence.

Until the sample is regenerated, label it in `CHECKER.md` as a different memo version with
unresolved issues rather than as the same case. Do not port a clean verdict from the game to the
checker sample without the evidence the game card rests on.

## What changed in halyard-v4 and brightwater-v4

Written on 13 September 2026 after an independent release review. Each file's own `changeLog`
carries the same entries in machine-readable form.

| Line | Call | Change |
| --- | --- | --- |
| Halyard 4, service revenue | stand, unchanged | The reveal no longer says billing in arrears puts each fee in the month it was earned. It says the service dates and the earned revenue bridge place the full $229,000 in June, and billing timing is background. The review's objection: billing does not determine when service revenue is earned. |
| Halyard 14, interest expense | flag, unchanged | The on-file fact that read "No draw dates, daily balances, rates or fee schedule were supplied" now reads "Other draw and repayment dates, daily balances, rates and fees were not supplied", because the file had already supplied the 3 June draw date. |
| Halyard 13, cost of product sold | stand, unchanged | The reveal, the over-flag note and a new `stillOpen` line say the stand is provisional: the calculation holds, and the mix cause is a hypothesis until the category sales and cost bridge is on file. |
| Brightwater 3, orthodontic plan revenue | flag, unchanged | No longer a silent line. It carries a memo sentence whose figures tie and whose named cause rests on a plan schedule dated 31 May, so the type moves from no explanation to unsupported driver. |
| All nineteen | unchanged | Every card gained a `basisKey`, and the page scores the call and the reason separately. |

## What changed in halyard-v3 and brightwater-v2

These are the 13 September revisions that produced halyard-v3 and the retired brightwater-v2.
brightwater-v3 replaced v2 the same day and is described above.

Substance changed on six lines. The rest kept their call and tightened the reasoning.

| Line | Call | Change |
| --- | --- | --- |
| Halyard 2, repairs | flag, unchanged | Dropped the inference that completion alone decides the accrual. Asks what June work was performed, recorded and unrecorded, and raises repair against improvement. |
| Halyard 4, service revenue | stand, unchanged | Gained service dates for the twelve contracts and an earned revenue bridge on file that reconciles $812,000 plus $229,000 to $1,041,000. |
| Halyard 8, bad debt | flag, unchanged | Dropped $42,000 as an established component and the routine $5,000 provision. Asks for a reserve rollforward. |
| Halyard 12, product revenue | flag, unchanged | Dropped the exact $65,000 transfer. Keeps the challenge to the demand attribution and asks for a billing bridge by customer. |
| Halyard 13, cost of product sold | stand, unchanged | Memo now separates gross profit dollars from the margin percentage and writes the mix claim as a hypothesis with a bridge requested. |
| Brightwater 5, hygienist wages | flag, unchanged | Dropped the merit increase residual. Asks for a payroll bridge. |

Everywhere else, "fabricated" became "not established from supplied evidence", and derived causes
became requests for a bridge: billing bridge, payroll bridge, reserve rollforward, depot revenue
bridge. A flag can be correct while its explanation is wrong, so a reveal credits the call and
corrects the reasoning separately.
