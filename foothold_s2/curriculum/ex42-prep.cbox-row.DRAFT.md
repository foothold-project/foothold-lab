# DRAFT (not read by any code): C/box second-door row for exposure_at_E2

Status: draft by sonnet-code-lx 11/20 14:1x for lead-lx. The share value is left blank on purpose (lead and the team lead decide it).
Not a yaml on purpose: nothing globs this folder for .md, so no test or loader sees it.

Rule shape. C/box is family C kind box. The E2 plan has no such row today (its continuous kinds are family A only), so the
second door needs one new `positive` row, added only after the first door passes (graduation by ex42_v1_mapgain_boundary.py), at cap 1 first:

```yaml
      - family: C
        kind: box
        share: <BLANK: lead decides>
        level_cap: 1          # raised by the D axis; the design target is cap L5
```

Rules the row has to obey (what was measured or fixed, not new choices):
- The sum of the `share:` values of the `positive` rows stays at the bundle total (0.44 today). A new share is taken from the other rows,
  so the same edit must lower those, and the receipt test (test_ex42_exposure_receipt_cpu.py, START and moves) must be updated in the same commit.
- Mesh: C/box geometry sha is `b3758b1c` in easy10, b2m_rpy_lv and edge (identical), so the pin stays easy10 and no pin change is needed.
- Judge: C/box has no gap, so ex42_v1_mapgain_boundary.py counts envs alive at the end as "crossed"; the eval script takes `C/box=<level>` in --caps.
- Cap raising: through `kind_level_cap` (`end: 5`, `step_per_boundary: 1`) and `ladder_outcomes_list.json` entries for key `C/box`; no new code.
- Not decided here: when the row is added (which boundary), the share value, and whether the cap starts at 1 or higher.
