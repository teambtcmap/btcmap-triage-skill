---
name: btcmap-triage
description: >
  Automates BTC Map issue triage including two-phase verification of location 
  submissions (automated checks and outreach), confidence scoring, and posting 
  verification reports to Gitea. Use when working with BTC Map location 
  submissions, merchant verifications, or verifying Bitcoin-accepting businesses. 
  Handles location-submission and location-verification issues from the 
  btcmap-data repository.
license: MIT
compatibility: >
  Requires Python 3.9+, internet access, Gitea API token, and agent email skill
  for Phase 2 outreach. Optional: Matrix skill for joining Supertagger room.
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
   This is where the Shadowy Supertaggers coordinate. Useful for requesting
   local verification and avoiding duplicate work.

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

1. **OSM Verification** (20% weight)
   - Search for existing nodes within **100m radius** of submitted coordinates
   - Use Overpass API: `node["name"](around:100,{lat},{lon})`
   - Check for existing `currency:XBT` tags on nearby nodes
   - Verify coordinates match merchant location (not just exact lat/lon)
   - Note: Many legitimate businesses are not yet on OSM, so absence is
     not heavily penalized — this check is a bonus for existing presence
   - **Report format:** "No existing node within 100m of {lat}, {lon}"

2. **Website Verification** (30% weight)
   - Scrape submitted website for Bitcoin acceptance
   - Look for "Bitcoin accepted" text, BTC logos, payment mentions
   - Primary verification signal for new submissions

3. **Social Media Verification** (20% weight) - **REQUIRED**
   - **Search Facebook** for merchant name + location
   - **Search Instagram** for merchant name + location
   - **Check Twitter/X** if applicable
   - **Evidence to capture:**
     - Social media profile URLs (`contact:facebook=`, `contact:instagram=`)
     - Business legitimacy indicators (posting activity, followers, location tags)
     - Photos of storefront/operations
   - **MUST include in Gitea comment:** All found social URLs with verification status
   - **MUST include in OSM tags:** `contact:facebook=` and/or `contact:instagram=` when found
   - **Scoring:**
     - 20/20: Multiple active social profiles found and verified
     - 10/20: One social profile found, limited activity
     - 5/20: Profile found but unverified/unclaimed
     - 0/20: No social presence found or search blocked

4. **Cross-Reference Verification** (20% weight)
   - Check Google Maps for business listing
   - Verify Yelp presence
   - Cross-check other mapping sources

5. **Data Consistency Check** (10% weight)
   - Validate address format for country
   - Check phone number format
   - Verify opening hours syntax
   - Validate category against BTC Map taxonomy

### Square Import Verification (Trusted Source)

Issues with the `import/square` label are **automatically verified** for Bitcoin acceptance:

- **Trust basis**: Square is a known Bitcoin payment processor
- **Bitcoin verification**: CONFIRMED (no Phase 2 outreach needed)
- **Scoring adjustment**: 
  - Bitcoin Check: 30/30 (verified via Square import)
  - Website Check: N/A (Square provides Bitcoin verification)
  - Phase 2: SKIPPED (not required)
- **Confidence floor**: Minimum 30% from Bitcoin verification alone

**Example scoring for Square import:**
```
OSM Check: 5/20 (not found)
Bitcoin Check: 30/30 (verified via Square)
Cross-Reference: 15/20 (Yelp/Google match)
Social Media: 5/20 (limited presence)
Data Consistency: 10/10 (valid)
Total: 65% → MEDIUM confidence, APPROVED for import
```

**Required Square OSM Tags:**
For merchants imported via Square, include these tags in the OSM edit:

```
currency:XBT=yes
payment:lightning=yes
payment:lightning_contactless=no
payment:onchain=no
payment:lightning:operator=square
check_date:currency:XBT=YYYY-MM-DD
check_date=YYYY-MM-DD
source=square  # For new nodes only
```

Note: Square imports still require OSM verification (does node exist?) and
should follow the complete tagging guidance at:
https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki/Tagging-Square-Merchants

### Phase 2: Outreach Verification

Phase 2 is **only triggered** if Phase 1 confidence is below threshold (default: 70%).

**Capability check**: Before starting Phase 2, check whether you have email-sending
and social media DM capabilities. If you do not:
- Set `enable_phase2: false` in config, OR
- Skip the outreach steps and post the drafted messages in the Gitea comment
  for a human reviewer to send manually.
- Note the skipped checks in the final report with reason "Agent lacks email/DM capability".

If you **do** have outreach capability:

1. **Email Verification** (+20% if confirmed)
   - Draft professional verification email
   - Send to submitted contact email
   - Wait for response (default timeout: 24 hours)

2. **Social Media DM** (+15% if confirmed)
   - Draft direct message for Twitter/Instagram
   - Send to verified merchant account
   - Track response

### Confidence Scoring

```
Phase 1 Score (0-100%):
  OSM Check: 20%       (bonus — absence is not a heavy penalty)
  Website Check: 30%   (primary signal)
  Social Media: 20%
  Cross-Reference: 20%
  Data Consistency: 10%

Phase 2 Bonus (up to +35%):
  Email Confirmation: +20%
  Social DM Confirmation: +15%

Final Score Thresholds:
  90-100%: HIGH confidence → Recommend approval
  70-89%: MEDIUM confidence → Recommend approval with notes
  50-69%: LOW confidence → Needs human review
  0-49%: VERY LOW → Recommend rejection/more info

**Square Import Adjustment:**
For issues with `import/square` label, the Website Check score is automatically
set to 30/30 (Bitcoin confirmed), and Phase 2 is skipped. Minimum Phase 1 score
is 30% from Bitcoin verification alone.
```

All weights are configurable in `config/config.yaml`.

## Tool Mapping

Each verification step maps to a specific tool from `allowed-tools`:

| Step | Tool | Usage |
|------|------|-------|
| Fetch Gitea issues | `WebFetch` | `GET https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues?state=open&labels=type/location-submission` with `Authorization: token {GITEA_TOKEN}` header |
| Post Gitea comment | `WebFetch` | `POST .../issues/{number}/comments` with JSON body `{"body": "<report markdown>"}` |
| OSM verification | `WebFetch` | `POST https://overpass-api.de/api/interpreter` with Overpass QL query (see `scripts/osm_client.py`) |
| Website check | `WebFetch` | `GET {merchant_website}` and search returned content for Bitcoin keywords |
| Social media check | `WebFetch` | `GET https://twitter.com/search?q={merchant_name}` or similar |
| Cross-reference | `WebFetch` | `GET https://www.google.com/maps/search/{merchant_name}` and Yelp search |
| Parse issue body | `Read` | Read `scripts/phase1_verify.py` for regex patterns, or parse directly |
| Run triage script | `Bash` | `python3 scripts/triage.py --config config/config.yaml` |
| Edit config | `Write` | Write Gitea token and custom weights to `config/config.yaml` |

The `scripts/` directory contains **reference implementations** with `# AGENT:` comments
marking where you should use the tools above instead of the stub/mock code.

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

For a detailed example run with sample output, see [references/EXAMPLES_AND_CUSTOMIZATION.md](references/EXAMPLES_AND_CUSTOMIZATION.md#example-run).

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

The **Shadowy Supertaggers** are the BTC Map community members who verify submissions
and apply OSM edits. They coordinate in a Matrix room:

```
Room: #btcmap-taggers:matrix.org
```

Join this room to:
- **Request help** with low-confidence verifications that need local knowledge
- **Coordinate** to avoid duplicate work when multiple taggers are active
- **Ask for physical verification** when a submission can't be verified remotely
  (e.g., no website, no social media, no email response)
- **Share findings** such as conflicting information or suspected spam patterns

### Responding to Mentions

If `respond_to_mentions` is enabled, monitor the room for messages that mention
the bot or ask about specific issues. When mentioned:

1. **Issue queries** (e.g., "what's the status of #12079?") — Look up the issue
   on Gitea and reply with the current status, labels, and latest triage comment.
2. **Verification requests** (e.g., "can someone check this shop in Nairobi?") —
   If coordinates or an issue number are provided, run Phase 1 checks and reply
   with a summary. Post the full report to the Gitea issue.
3. **General questions** — Reply with relevant info from the skill's reference
   docs (scoring algorithm, tag reference, etc.).

Keep Matrix replies short and conversational. The detailed reports belong in
Gitea issue comments, not in chat.

### Daily Summary

If `daily_summary` is enabled, post a summary to the room once per day:

```
BTC Map Triage Summary (2026-02-07):
- Issues processed: 12
- Approved: 4
- Needs review: 6
- Rejected: 2
- Oldest unprocessed issue: #11982 (3 days old)
```

This keeps taggers informed without spamming per-issue notifications — individual
issue progress is tracked via Gitea comments instead.

## OSM Edit Suggestions

For verified merchants, the skill generates tags formatted for direct copy-paste
into the OSM iD editor tag panel (one `key=value` per line, no extra formatting):

**Example Output**:
```
currency:XBT=yes
payment:lightning=yes
payment:onchain=yes
check_date:currency:XBT=2026-02-07
contact:facebook=https://facebook.com/merchantname
contact:instagram=https://instagram.com/merchantname
```

**Required social media verification:**
- Search Facebook and Instagram for the merchant by name + location
- Include found URLs in both the Gitea comment AND OSM `contact:` tags
- If search is blocked (403, JS-required), note this in the report
- Score 0/20 for social verification if not attempted or blocked

Changeset comment (paste into the changeset comment field):
```
Add Bitcoin acceptance for Coldwater Mountain Brewpub #btcmap issue:12079 Source: Verified via website and email confirmation
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

For detailed customization instructions (adjusting weights, changing thresholds,
adding custom verification checks), see [references/EXAMPLES_AND_CUSTOMIZATION.md](references/EXAMPLES_AND_CUSTOMIZATION.md#customization).

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
- [Examples and Customization](references/EXAMPLES_AND_CUSTOMIZATION.md)
- [Common Parsing Pitfalls](references/PARSING_PITFALLS.md) - Important for agent implementations

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
