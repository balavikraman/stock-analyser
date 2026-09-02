# Market-data reliability checklist

## Safety contract

- [ ] A real-symbol analysis must never substitute demo data after a live-data failure.
- [ ] Missing critical price data must return a structured blocked report, not an exception.
- [ ] Every displayed price series must show provider, retrieval time, and cache age.

## Resilience

- [ ] Cache successful daily price, benchmark and watchlist requests locally.
- [ ] Share cached benchmark/watchlist data across analyses.
- [ ] Retry transient rate-limit/network failures with bounded exponential backoff.
- [ ] Add an independent, terms-compliant secondary end-of-day provider.
- [ ] Record each provider failure and fallback decision.

## Integrity

- [ ] Reconcile independently sourced daily close/volume values before using them for an actionable decision.
- [ ] Block actionable prices on a material source disagreement.
- [ ] Preserve the exact provider and evidence used in each frozen prediction.

## Degraded operation

- [ ] Allow a clearly labelled research-only report from recent verified cached data.
- [ ] Never use stale cached data for an actionable intraday entry.
- [ ] Show the exact missing, stale, or conflicting input in the dashboard.
