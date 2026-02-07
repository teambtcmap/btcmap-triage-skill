# Examples and Customization

## Example Run

```
$ python scripts/triage.py
BTC Map Triage Bot
==================

How many issues would you like to process? [10]: 5

Fetching 5 open issues from btcmap-data...
Found 5 issues to process.

Processing issue #12079: Coldwater Mountain Brewpub
[Phase 1] Checking OSM... Found
[Phase 1] Checking website... Bitcoin accepted
[Phase 1] Checking social media... Active Twitter
[Phase 1] Cross-referencing... Google Maps match
[Phase 1] Validating data... All fields valid

Phase 1 Confidence: 70%
Posting Phase 1 report to Gitea...

[Phase 2] Sending verification email...
Email sent to: info@coldwatermountainbrewpub.com
Waiting for response... (timeout: 24 hours)

Response received: Confirmed Bitcoin acceptance

Final Confidence: 90% (HIGH)
Recommendation: APPROVE

Posting final report to Gitea...
OSM edit suggestions generated.

---

Processing issue #12080: Borjulink Communications...
[Phase 1] Checking OSM... Not found
[Phase 1] Checking website... No website provided
[Phase 1] Checking social media... Not found
[Phase 1] Cross-referencing... Not on Google Maps
[Phase 1] Validating data... Address format valid

Phase 1 Confidence: 5%
Posting Phase 1 report to Gitea...

Recommendation: NEEDS MORE INFO
Missing: Website, social media, or phone verification needed.

---

Completed processing 5 issues.
Summary:
- Approved: 1
- Needs Review: 3
- Rejected: 1
```

## Customization

### Adjusting Weights

Edit `config/config.yaml`:

```yaml
weights:
  osm_check: 35          # Increase if OSM accuracy is critical
  website_check: 20      # Decrease if many merchants lack websites
  social_media: 15       # Adjust based on your region
  cross_reference: 20
  data_consistency: 10
```

### Changing Thresholds

```yaml
thresholds:
  high: 85        # Lower if you want more auto-approvals
  medium: 65      # Adjust based on your risk tolerance
  low: 40
```

### Custom Verification Checks

Add custom checks by extending `scripts/phase1_verify.py`:

```python
def custom_check(issue_data):
    # Your custom verification logic
    score = calculate_score()
    return {
        'status': 'pass' if score > 50 else 'fail',
        'score': score,
        'details': {...}
    }
```

### Regional Weight Adjustments

See [CONFIDENCE_ALGORITHM.md](CONFIDENCE_ALGORITHM.md#regional-variations) for
recommended weight adjustments by region (developed countries, developing countries,
rural areas).
