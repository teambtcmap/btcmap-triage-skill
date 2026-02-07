# BTC Map Verification Workflow

## Overview

This document describes the two-phase verification workflow used by the BTC Map Triage skill.

## Issue Lifecycle

### 1. Submission
Issues are created in the btcmap-data repository via:
- **Square Imports**: Automated imports from Square payment processor
- **Manual Submissions**: Submitted through the BTC Map "Add Location" form
- **Verification Requests**: Users requesting verification of existing locations

### 2. Phase 1: Automated Verification

#### 2.1 OSM Verification (30% weight)
**Purpose**: Verify if merchant exists in OpenStreetMap

**Checks**:
- Search for existing node/way within 50m of coordinates
- Check if merchant name matches
- Verify address consistency
- Check for existing `currency:XBT` tags

**Scoring**:
- Full match (name + coordinates + address): 30/30
- Partial match (coordinates only): 15/30
- No match: 0/30

**Actions**:
- If exists with Bitcoin tags: Recommend closing issue
- If exists without Bitcoin tags: Suggest adding tags
- If not exists: Continue to other checks

#### 2.2 Website Verification (25% weight)
**Purpose**: Verify Bitcoin acceptance via merchant website

**Checks**:
- Scrape website homepage
- Look for "Bitcoin accepted" text
- Look for BTC/Lightning logos
- Check payment methods page
- Look for cryptocurrency mentions

**Scoring**:
- Explicit "Bitcoin accepted" mention: 25/25
- Cryptocurrency mention (not specific): 15/25
- Website exists but no mention: 5/25
- No website: 0/25

**Red Flags**:
- "We don't accept Bitcoin" text
- Outdated information
- Website offline

#### 2.3 Social Media Verification (20% weight)
**Purpose**: Verify business legitimacy and Bitcoin activity

**Checks**:
- Search Twitter/X for merchant handle
- Check Instagram presence
- Look for Bitcoin-related posts
- Verify account activity
- Check follower count (legitimacy indicator)

**Scoring**:
- Active account with Bitcoin posts: 20/20
- Active account, no Bitcoin mention: 10/20
- Inactive/empty account: 5/20
- No social media: 0/20

**Indicators**:
- Recent posts (within 6 months)
- Engagement (replies, likes)
- Bitcoin hashtags (#Bitcoin, #BTC, #LightningNetwork)

#### 2.4 Cross-Reference Verification (15% weight)
**Purpose**: Verify business existence on other platforms

**Checks**:
- Google Maps listing
- Yelp presence
- TripAdvisor (for hospitality)
- Local business directories

**Scoring**:
- Listed on 3+ platforms: 15/15
- Listed on 2 platforms: 10/15
- Listed on 1 platform: 5/15
- Not listed: 0/15

**Consistency Check**:
- Name matches across platforms
- Address is consistent
- Phone number matches
- Hours are similar

#### 2.5 Data Consistency (10% weight)
**Purpose**: Validate data format and completeness

**Checks**:
- Address format valid for country
- Phone number format valid
- Opening hours syntax correct
- Coordinates within valid range
- Category in BTC Map taxonomy

**Scoring**:
- All fields valid: 10/10
- Minor issues: 5/10
- Major issues: 0/10

### 3. Phase 1 Decision Point

After Phase 1, calculate confidence score:

```
Score = OSM + Website + Social + CrossRef + Consistency
```

**If Score >= Threshold (default 70%)**:
- Skip Phase 2
- Post final report
- Provide recommendation

**If Score < Threshold**:
- Proceed to Phase 2
- Post Phase 1 report
- Initiate outreach

### 4. Phase 2: Outreach Verification

Phase 2 is only triggered if Phase 1 confidence is below threshold.

#### 4.1 Email Verification (+20% if confirmed)

**Process**:
1. Draft professional verification email
2. Send to submitted contact email
3. Wait for response (default 24 hours)
4. Parse response

**Email Template**:
```
Subject: Verification Request: {merchant_name}

Dear {merchant_name} Team,

I'm writing to verify information about your business for BTC Map 
(https://btcmap.org), a community-driven project mapping Bitcoin-accepting 
businesses worldwide.

We received a submission indicating {merchant_name} accepts Bitcoin. 
Could you please confirm:

1. Do you currently accept Bitcoin payments?
2. Do you accept on-chain Bitcoin?
3. Do you accept Lightning Network payments?

If you don't accept Bitcoin, please let us know so we can update our records.

Thank you for your time!

Best regards,
BTC Map Verification Team
```

**Response Parsing**:
- Confirmed Bitcoin acceptance: +20%
- Denied Bitcoin acceptance: Issue flagged for removal
- No response: No bonus, flag for manual review

#### 4.2 Social Media DM (+15% if confirmed)

**Process**:
1. Find merchant social media accounts
2. Draft direct message
3. Send DM (Twitter/Instagram)
4. Wait for response

**DM Template**:
```
Hi! We're verifying Bitcoin acceptance for {merchant_name} on BTC Map.
Could you confirm you accept Bitcoin payments?

Thanks!
```

**Response**:
- Confirmed: +15%
- Denied: Flag for removal
- No response: No bonus

### 5. Final Scoring

```
Final Score = Phase 1 Score + Phase 2 Bonus
Maximum: 100%
```

**Score Interpretation**:

| Score | Level | Recommendation | Action |
|-------|-------|----------------|--------|
| 90-100% | HIGH | Approve | Post approval, provide OSM edit template |
| 70-89% | MEDIUM | Approve with Notes | Post approval, note any caveats |
| 50-69% | LOW | Needs Review | Request additional verification |
| 0-49% | VERY LOW | Reject/More Info | Request website, social media, or phone |

### 6. Reporting

#### Phase 1 Report Posted

```markdown
## Phase 1 Verification Report

**Merchant**: {name}
**Issue**: #{number}
**Score**: {score}%

### Automated Checks:
- OSM: {status} ({score}/30)
- Website: {status} ({score}/25)
- Social: {status} ({score}/20)
- Cross-Ref: {status} ({score}/15)
- Consistency: {status} ({score}/10)

[Details for each check]
```

#### Final Report Posted

```markdown
## Final Verification Report

**Merchant**: {name}
**Issue**: #{number}
**Phase 1**: {phase1_score}%
**Final Score**: {final_score}%
**Recommendation**: {recommendation}

### Phase 2 Results:
- Email: {status} (+{score}%)
- Social DM: {status} (+{score}%)

### OSM Edit Suggestion:
[Copy-paste template]
```

### 7. OSM Editing

For approved locations, generate OSM edit suggestions:

**Required Tags**:
```
currency:XBT=yes
check_date:currency:XBT=YYYY-MM-DD
```

**Optional Tags**:
```
payment:lightning=yes
payment:onchain=yes
payment:lightning_contactless=yes
payment:lightning:operator=square
```

**Changeset Comment**:
```
Add Bitcoin acceptance for {merchant_name}
#btcmap issue:{issue_number}
Source: Verified via website and email confirmation
```

### 8. Issue Resolution

**Approve**:
- Post final report
- Add `status/pending` label
- Close issue when OSM is updated

**Reject**:
- Post report with reasoning
- Add `status/rejected` label
- Close issue

**Needs More Info**:
- Post report with specific requests
- Add comment requesting:
  - Website URL
  - Social media handles
  - Phone number
  - Physical verification

### 9. Edge Cases

#### Website Unavailable
- Score: 0/25 for website check
- Note: "Website timeout"
- Continue with other checks

#### Conflicting Information
Example: Website says "Bitcoin accepted" but email says "We don't accept Bitcoin"

**Action**:
- Flag for human review
- Reduce confidence score
- Request clarification

#### No Contact Information
- Skip Phase 2 entirely
- Recommend physical verification
- Tag with local community

#### Duplicate Submission
- Check for existing issues with same merchant
- Merge or close duplicate
- Reference original issue

### 10. Quality Assurance

**Human Review Triggers**:
- Score 50-69%
- Conflicting information
- Unusual patterns (multiple submissions from same IP)
- High-risk categories (online-only businesses)

**Spot Checks**:
- Randomly review 10% of auto-approved locations
- Verify OSM edits were applied correctly
- Check for false positives

### 11. Metrics

Track these metrics to improve the workflow:

- Average time to verification
- Phase 1 vs Phase 2 accuracy
- False positive rate
- False negative rate
- Most common missing information
- Most reliable verification sources

## Best Practices

1. **Verify Independently**: Don't rely solely on submitted information
2. **Document Sources**: Always note where verification came from
3. **Be Conservative**: When in doubt, flag for human review
4. **Respond Quickly**: Process issues within 48 hours when possible
5. **Communicate Clearly**: Use simple language in reports
6. **Stay Updated**: Adjust weights based on real-world results

## References

- [Confidence Algorithm](CONFIDENCE_ALGORITHM.md)
- [Example Issues](EXAMPLE_ISSUES.md)
- [Gitea API Reference](GITEA_API_REFERENCE.md)
- [BTC Map Tagging Guide](https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki/Tagging-Merchants)
