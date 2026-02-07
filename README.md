# BTC Map Triage Skill

## Overview

This is an [Agent Skill](https://agentskills.io) for automating the triage of BTC Map location issues. It performs two-phase verification (automated checks and outreach), calculates confidence scores, and posts detailed reports to Gitea.

## Features

- **Two-Phase Verification**:
  - Phase 1: Automated checks (OSM, website, social media, cross-reference, data consistency)
  - Phase 2: Outreach verification (email, social media DMs)

- **Confidence Scoring**: Weighted algorithm with configurable thresholds

- **Gitea Integration**: Automatically fetches issues and posts verification reports

- **OSM Edit Suggestions**: Generates copy-paste ready OpenStreetMap edit templates

- **Matrix Support**: Can join Shadowy Supertagger room for coordination

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd btcmap-triage
cp config/config.example.yaml config/config.yaml
```

### 2. Configure

Edit `config/config.yaml`:

```yaml
gitea:
  token: "your-gitea-api-token-here"
```

Get your Gitea token from: https://gitea.btcmap.org/user/settings/applications

### 3. Run

```bash
python scripts/triage.py
```

The bot will ask: "How many issues would you like to process?"

## Directory Structure

```
btcmap-triage/
├── SKILL.md                      # Main skill documentation
├── README.md                     # This file
├── config/
│   ├── config.example.yaml       # Example configuration
│   └── config.yaml               # Your configuration (created from example)
├── scripts/
│   ├── triage.py                 # Main orchestrator
│   ├── phase1_verify.py          # Automated verification
│   ├── phase2_verify.py          # Outreach verification
│   ├── confidence.py             # Scoring algorithm
│   ├── gitea_client.py           # Gitea API client
│   └── osm_client.py             # OSM API client
├── references/
│   ├── VERIFICATION_WORKFLOW.md  # Detailed workflow
│   ├── CONFIDENCE_ALGORITHM.md   # Scoring algorithm details
│   ├── EXAMPLE_ISSUES.md         # Example issue data
│   └── GITEA_API_REFERENCE.md    # API documentation
└── assets/
    └── templates/
        ├── phase1_report.md      # Phase 1 report template
        ├── final_report.md       # Final report template
        ├── email_template.txt    # Outreach email template
        └── dm_template.txt       # Social DM template
```

## How It Works

### Phase 1: Automated Verification (0-100%)

1. **OSM Verification** (30%): Check if merchant exists in OpenStreetMap
2. **Website Check** (25%): Scrape website for Bitcoin acceptance
3. **Social Media** (20%): Check Twitter/Instagram presence
4. **Cross-Reference** (15%): Verify on Google Maps, Yelp
5. **Data Consistency** (10%): Validate address, phone, hours format

### Phase 2: Outreach Verification (Bonus +0-35%)

Triggered if Phase 1 score is below threshold (default 70%):

- **Email Confirmation** (+20%): Send verification email
- **Social DM Confirmation** (+15%): Send direct message

### Confidence Thresholds

| Score | Level | Action |
|-------|-------|--------|
| 90-100% | HIGH | Auto-approve, generate OSM edit template |
| 70-89% | MEDIUM | Approve with notes |
| 50-69% | LOW | Needs human review |
| 0-49% | VERY LOW | Request more information |

## Configuration

See `config/config.example.yaml` for all options.

Key settings:

```yaml
# Operation mode
operation_mode: ask  # single, batch, continuous, ask

# Phase settings
enable_phase1: true
enable_phase2: true
phase1_threshold: 70  # Skip Phase 2 if >= 70%

# Confidence weights (adjust based on your region)
weights:
  osm_check: 30
  website_check: 25
  social_media: 20
  cross_reference: 15
  data_consistency: 10

# Rate limiting
rate_limiting:
  gitea_requests_per_minute: 30
  web_scrape_delay_seconds: 2
```

## Examples

### High Confidence (90-100%)

```
Merchant: Pizza Palace Downtown
- OSM: Not exists (0/30)
- Website: Confirms Bitcoin (25/25)
- Social: Active with BTC posts (20/20)
- Cross-ref: Google Maps + Yelp (15/15)
- Consistency: All valid (10/10)

Phase 1: 70%
Phase 2: Email confirms (+20%)

Final: 90% - HIGH CONFIDENCE
Recommendation: Approve
```

### Medium Confidence (70-89%)

```
Merchant: Coffee Corner
- OSM: Not exists (0/30)
- Website: Confirms Bitcoin (25/25)
- Social: Active, no BTC mention (15/20)
- Cross-ref: Google Maps only (5/15)
- Consistency: All valid (10/10)

Phase 1: 55%
Phase 2: Not triggered (below 70% threshold)

Final: 55% - LOW CONFIDENCE
Recommendation: Needs Review
Action: Request social media handles
```

### Low Confidence (0-49%)

```
Merchant: Local Electronics Shop
- OSM: Not exists (0/30)
- Website: None (0/25)
- Social: Not found (0/20)
- Cross-ref: Not found (0/15)
- Consistency: Coordinates only (4/10)

Phase 1: 4%
Phase 2: Email sent (+20% if confirmed)

Final: 4% (or 24% with email) - VERY LOW
Recommendation: Request More Info
Action: Ask for website or phone verification
```

## Matrix Integration

The **Shadowy Supertaggers** are the community members who verify BTC Map submissions
and apply OSM edits. They coordinate via Matrix at `#btcmap-taggers:matrix.org`.

Join this room to engage with other taggers: request local/physical verification,
coordinate to avoid duplicate work, share findings, and announce triage runs.

```yaml
matrix:
  enabled: true
  room: "#btcmap-taggers:matrix.org"
  message_on_start: true      # Announce when a triage batch begins
  message_on_complete: true   # Post summary when batch finishes
```

Requires the agent to have Matrix skills configured.

## Development

### Adding New Checks

To add a new Phase 1 verification check:

1. Edit `scripts/phase1_verify.py`
2. Add a new method `_check_your_check()`
3. Update the `verify()` method to call it
4. Add weight to `config.yaml`

Example:

```python
def _check_your_check(self, data: Dict) -> Dict:
    result = {
        'check_name': 'Your Check',
        'status': 'pass',
        'score': 0,
        'max_score': self.weights['your_check'],
        'details': {}
    }
    
    # Your verification logic here
    if verification_successful:
        result['score'] = self.weights['your_check']
        result['status'] = 'pass'
    
    return result
```

### Testing

Run with example data:

```bash
python scripts/triage.py --config config/config.example.yaml --issues 3
```

This will process 3 mock issues to test the workflow.

### Debugging

Set logging level to DEBUG:

```yaml
logging:
  level: DEBUG
```

## Troubleshooting

### "Gitea token not found"

- Ensure `GITEA_TOKEN` environment variable is set, OR
- Set token directly in `config/config.yaml`

### "No email skill available"

- Phase 2 will be skipped for email verification
- Set `enable_phase2: false` to suppress warnings
- Or configure email skill in your agent

### "Rate limit exceeded"

- Increase delays in `config.yaml`:
  ```yaml
  rate_limiting:
    gitea_requests_per_minute: 10
  ```

### "Issue format not recognized"

- Check that the issue follows expected format
- Update parsing logic in `scripts/phase1_verify.py`
- See `references/EXAMPLE_ISSUES.md` for valid formats

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with example issues
5. Submit a pull request

## References

- [Agent Skills Specification](https://agentskills.io/specification)
- [BTC Map Wiki](https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki)
- [Verification Workflow](references/VERIFICATION_WORKFLOW.md)
- [Confidence Algorithm](references/CONFIDENCE_ALGORITHM.md)
- [Example Issues](references/EXAMPLE_ISSUES.md)
- [Gitea API Reference](references/GITEA_API_REFERENCE.md)

## License

MIT License - See LICENSE file for details

## Support

- BTC Map Matrix Room: `#btcmap:matrix.org`
- Shadowy Supertagger Room: `#btcmap-taggers:matrix.org`
- Issues: https://gitea.btcmap.org/teambtcmap/btcmap-data/issues
