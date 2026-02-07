---
name: btcmap-triage
description: Automates BTC Map issue triage including two-phase verification of location submissions (automated checks and outreach), confidence scoring, and posting verification reports to Gitea. Use when working with BTC Map location submissions, merchant verifications, or verifying Bitcoin-accepting businesses. Handles location-submission and location-verification issues from the btcmap-data repository.
license: MIT
compatibility: Requires Python 3.9+, internet access, Gitea API token, and agent email skill for Phase 2 outreach. Optional: Matrix skill for joining Supertagger room.
metadata:
  author: btcmap-community
  version: "1.0.0"
  btcmap_version: compatible with current Gitea API
allowed-tools: Bash(python3:*) WebFetch Read Write
---

# BTC Map Triage Skill

This skill automates the verification and triage of BTC Map location issues. It performs two-phase verification, calculates confidence scores, and posts detailed reports to Gitea.

## Quick Start

1. **Configure the skill**:
   ```bash
   cp config/config.example.yaml config/config.yaml
   # Edit config.yaml with your Gitea token
   ```

2. **Join the Matrix room** (optional but recommended):
   ```
   Join #btcmap-taggers:matrix.org
   ```

3. **Run triage**:
   ```bash
   python scripts/triage.py
   ```

## Configuration

Copy `config/config.example.yaml` to `config/config.yaml` and set:

```yaml
gitea:
  token: "your-gitea-api-token-here"  # Required
  
# Optional: Configure rate limits
rate_limiting:
  gitea_requests_per_minute: 30
  web_scrape_delay_seconds: 2
```

**Required Environment Variables**:
- `GITEA_TOKEN`: Your Gitea API token from https://gitea.btcmap.org/user/settings/applications

## How It Works

### Phase 1: Automated Verification

For each issue, the skill automatically checks:

1. **OSM Verification** (30% weight)
   - Check if merchant exists in OpenStreetMap
   - Verify coordinates match
   - Check for existing `currency:XBT` tags
   - Validate address consistency

2. **Website Verification** (25% weight)
   - Scrape submitted website for Bitcoin acceptance
   - Look for "Bitcoin accepted" text, BTC logos, payment mentions
   - Check for conflicting information

3. **Social Media Verification** (20% weight)
   - Check Twitter/X account existence
   - Look for Bitcoin-related posts
   - Verify business legitimacy

4. **Cross-Reference Verification** (15% weight)
   - Check Google Maps for business listing
   - Verify Yelp presence
   - Cross-check other mapping sources

5. **Data Consistency Check** (10% weight)
   - Validate address format for country
   - Check phone number format
   - Verify opening hours syntax
   - Validate category against BTC Map taxonomy

### Phase 2: Outreach Verification

If Phase 1 confidence is below threshold (default: 70%), the skill initiates outreach:

1. **Email Verification** (+20% if confirmed)
   - Draft professional verification email
   - Send to submitted contact email
   - Wait for response

2. **Social Media DM** (+15% if confirmed)
   - Draft direct message for Twitter/Instagram
   - Send to verified merchant account
   - Track response

**Note**: Phase 2 relies on the agent's existing email skill.

### Confidence Scoring

```
Phase 1 Score (0-100%):
  OSM Check: 30%
  Website Check: 25%
  Social Media: 20%
  Cross-Reference: 15%
  Data Consistency: 10%

Phase 2 Bonus (up to +35%):
  Email Confirmation: +20%
  Social DM Confirmation: +15%

Final Score Thresholds:
  90-100%: HIGH confidence → Recommend approval
  70-89%: MEDIUM confidence → Recommend approval with notes
  50-69%: LOW confidence → Needs human review
  0-49%: VERY LOW → Recommend rejection/more info
```

All weights are configurable in `config/config.yaml`.

## Workflow

### Step-by-Step

1. **Fetch Issues**
   ```bash
   # The skill will ask: "How many issues to process?"
   python scripts/triage.py
   ```

2. **Phase 1 Processing**
   - Automated checks run for each issue
   - Results compiled into report

3. **Post Phase 1 Report**
   - Report posted as comment to Gitea issue
   - Includes breakdown of all checks

4. **Phase 2 Processing** (if needed)
   - Outreach emails/DMs sent
   - Responses tracked

5. **Post Final Report**
   - Final confidence score calculated
   - Recommendation posted
   - OSM edit suggestions provided

### Example Run

```
$ python scripts/triage.py
BTC Map Triage Bot
==================

How many issues would you like to process? [10]: 5

Fetching 5 open issues from btcmap-data...
Found 5 issues to process.

Processing issue #12079: Coldwater Mountain Brewpub
[Phase 1] Checking OSM... ✓ Found
[Phase 1] Checking website... ✓ Bitcoin accepted
[Phase 1] Checking social media... ✓ Active Twitter
[Phase 1] Cross-referencing... ✓ Google Maps match
[Phase 1] Validating data... ✓ All fields valid

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
[Phase 1] Checking OSM... ✗ Not found
[Phase 1] Checking website... ✗ No website provided
[Phase 1] Checking social media... ✗ Not found
[Phase 1] Cross-referencing... ✗ Not on Google Maps
[Phase 1] Validating data... ✓ Address format valid

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

## Gitea Integration

The skill interacts with Gitea to:

1. **Fetch Issues**
   ```python
   GET /api/v1/repos/teambtcmap/btcmap-data/issues
   Params: state=open, labels=type/location-submission
   ```

2. **Parse Issue Data**
   - Extract merchant name, address, coordinates
   - Parse payment methods, website, contact info
   - Identify issue type (submission vs verification)

3. **Post Comments**
   ```python
   POST /api/v1/repos/teambtcmap/btcmap-data/issues/{number}/comments
   Body: {verification_report_markdown}
   ```

4. **Update Labels** (optional)
   - Add `status/pending` during processing
   - Add `status/added` when approved
   - Add `status/rejected` when rejected

## Matrix Integration

Join the Shadowy Supertagger room for coordination:

```
Room: #btcmap-taggers:matrix.org
```

The skill will remind you to join this room if you have Matrix skill enabled.

## OSM Edit Suggestions

For verified merchants, the skill generates copy-paste ready OSM edit suggestions:

**Example Output**:
```
Suggested OSM Tags:
  currency:XBT=yes
  payment:lightning=yes
  payment:onchain=yes
  check_date:currency:XBT=2026-02-07

Changeset Comment:
  Add Bitcoin acceptance for Coldwater Mountain Brewpub
  #btcmap issue:12079
  Source: Verified via website and email confirmation
```

## Edge Cases & Error Handling

### Website Unavailable
- **Action**: Skip website check, reduce confidence
- **Report**: Note website timeout in report

### OSM API Error
- **Action**: Retry with exponential backoff (max 3 attempts)
- **Fallback**: Skip OSM check, note error in report

### Email Bounces
- **Action**: Mark email check as failed
- **Report**: Note bounce in Phase 2 report

### No Contact Information
- **Action**: Skip Phase 2 entirely
- **Report**: Recommend physical verification by local tagger

### Conflicting Information
- **Example**: Website says "Bitcoin accepted" but Twitter says "Bitcoin not accepted"
- **Action**: Flag for human review, note conflict in report
- **Confidence Impact**: Reduce overall score

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

## Best Practices

1. **Start Small**: Process 5-10 issues first to validate configuration
2. **Monitor Rate Limits**: Default is conservative; adjust based on Gitea API limits
3. **Review Reports**: Check Phase 1 reports before Phase 2 outreach
4. **Use Descriptive Changeset Comments**: Helps other OSM contributors understand edits
5. **Keep Config Updated**: Adjust weights based on real-world results

## References

- [Verification Workflow](references/VERIFICATION_WORKFLOW.md)
- [Confidence Algorithm](references/CONFIDENCE_ALGORITHM.md)
- [Example Issues](references/EXAMPLE_ISSUES.md)
- [Gitea API Reference](references/GITEA_API_REFERENCE.md)

## Troubleshooting

### "Gitea token not found"
- Ensure `GITEA_TOKEN` environment variable is set
- Or set directly in `config/config.yaml`

### "Rate limit exceeded"
- Increase delays in `config.yaml`:
  ```yaml
  rate_limiting:
    gitea_requests_per_minute: 10
  ```

### "No email skill available"
- Phase 2 will be skipped
- Set `enable_phase2: false` in config to suppress warnings

### "Issue body format unrecognized"
- Check if issue format has changed
- Update parsing logic in `scripts/gitea_client.py`

## Contributing

This skill follows the [agentskills.io specification](https://agentskills.io/specification).

To contribute:
1. Fork the repository
2. Make changes
3. Test with example issues
4. Submit pull request

## License

MIT License - See LICENSE file for details
