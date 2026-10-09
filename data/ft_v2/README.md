# Briefing candidate corpus

Rebuild offline with `uv run python scripts/build_ft_v2_dataset.py`.

`manifest.json` records counts, hashes, source dates, purged days and duplicate
removal. The environmental inputs come from the existing recorded Open-Meteo
CAMS air-quality / ERA5 weather archive-derived `data/eval/gono_rows.jsonl`.
These are gridded model/reanalysis products, not personal measurements or a
field trial. The source SHA-256 lets each row be traced to that exact snapshot.

Every assistant target is **synthetic deterministic prose**, authored from the
serving policy and selected environmental facts. Targets are neither human
preference labels nor independently validated health outcomes. The builder
does not read future target bands, future NAQI, or the old row decision label.
Missing precipitation probability stays `null`; it does not become zero.

Recorded input days are split chronologically 70/15/15, with two full source
days purged at each boundary. A coarse environmental fingerprint removes
cross-cohort near duplicates, ignoring park names, hour formatting, and target
style. This conservative deduplication changes the natural archive distribution;
report cohort and decision denominators with every metric.

Training includes explicitly marked synthetic safety augmentations. Validation
and `test.jsonl` contain recorded archive inputs only. `stress.jsonl` is a
separate, entirely synthetic threshold/composition/missing-data/injection suite;
its scores must not be combined with real archive scores or described as
observational evidence. No heldout prompt is identical to a training prompt.

The contract checker compares decisions, typed numbers, air bands, critical
hazards, selected known parks, and prohibited claims. It is a conservative
finite-language validator, not complete semantic verification of arbitrary
prose. Evaluate raw generations first, then report fallback/gated performance
and fallback counts separately. Template loss or contract success cannot
establish actual outdoor safety, clinical validity, or user benefit. Review
candidate generations by hand before promoting a model.
