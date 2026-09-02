# Decision-engine validation checklist

The goal is not to predict every stock. The goal is to prove which frozen
decision conditions add value after costs, and to abstain when evidence is weak.

## A. Record every decision

- [x] Freeze the analysis, model version, price and decision on the signal date.
- [x] Save allowed/blocked reasons, regime, breadth, sector, liquidity, forensic and filing context.
- [x] Keep long-term and swing records separate.
- [x] Preserve non-actionable and failed decisions.

## B. Measure outcomes honestly

- [x] Measure fixed swing and long-term horizons prospectively.
- [x] Include estimated round-trip costs and Nifty benchmark return.
- [x] Track maximum favourable/adverse excursion.
- [x] Record frozen swing target/stop outcomes; mark same-day double touches as ambiguous.
- [ ] Run outcome maturation regularly on the user's machine.

## C. Establish whether a rule works

- [x] Split completed results by market regime, breadth, sector and forensic risk.
- [x] Label samples below 30 comparable completed outcomes as insufficient.
- [ ] Compare each active rule against its no-filter baseline and Nifty.
- [ ] Compute uncertainty intervals, not only win rates.
- [ ] Attribute outcomes to exact rule combinations, not one indicator in isolation.
- [ ] Flag a rule as keep, review or retire using predefined evidence thresholds.

## D. Prevent misleading conclusions

- [x] Use chronological, purged walk-forward splits only.
- [x] Keep model versions frozen while they are measured.
- [x] Do not show unvalidated confidence as a probability.
- [ ] Require at least 100 completed comparable swing outcomes before probability calibration.
- [ ] Require a longer prospective record for long-term probability calibration.

## E. Review cycle

- [ ] Review completed results by horizon and model version.
- [ ] Retire or weaken rules that fail out-of-sample and after costs.
- [ ] Promote only rules with enough prospective evidence and positive benchmark-relative results.
- [ ] Document every rule change as a new model version; never rewrite old results.

## Deferred operational work

- [ ] Configure the Windows daily validation scheduler.
- [ ] Configure read-only Zerodha portfolio reconciliation.
- [ ] Configure Telegram research alerts.
