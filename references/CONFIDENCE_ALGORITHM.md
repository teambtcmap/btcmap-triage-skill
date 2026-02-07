# Confidence Scoring Algorithm

## Overview

The confidence scoring algorithm determines the reliability of a BTC Map location submission through a weighted two-phase verification system.

## Algorithm Structure

### Phase 1: Automated Verification (0-100%)

Phase 1 uses weighted checks that don't require external responses:

```
Phase1Score = OSM_Check + Website_Check + Social_Media + Cross_Reference + Data_Consistency

Where each component is 0 to its maximum weight
```

#### Default Weights

| Check | Weight | Rationale |
|-------|--------|-----------|
| OSM Verification | 20% | Bonus for existing presence - many legitimate businesses are not yet on OSM |
| Website Check | 30% | Primary signal - merchants control their own website |
| Social Media | 20% | Secondary validation - shows active business presence |
| Cross-Reference | 20% | Third-party validation - independent confirmation business exists |
| Data Consistency | 10% | Quality indicator - properly formatted data |

**Total: 100%**

### Phase 2: Outreach Verification (Bonus +0-35%)

Phase 2 provides bonus points for confirmed outreach responses:

```
Phase2Bonus = Email_Confirmation + Social_DM_Confirmation

Where:
- Email_Confirmation: +20% (if confirmed)
- Social_DM_Confirmation: +15% (if confirmed)
```

**Maximum Phase 2 Bonus: 35%**

### Final Score Calculation

```
FinalScore = min(Phase1Score + Phase2Bonus, 100)
```

The final score is capped at 100%.

## Confidence Levels

### Score Thresholds

| Range | Level | Color | Description |
|-------|-------|-------|-------------|
| 90-100% | HIGH | 🟢 | Very reliable - auto-approve candidate |
| 70-89% | MEDIUM | 🟡 | Reliable - approve with minor notes |
| 50-69% | LOW | 🟠 | Questionable - needs human review |
| 0-49% | VERY LOW | 🔴 | Unreliable - reject or request more info |

### Recommendations by Level

#### HIGH (90-100%)
- **Recommendation**: Approve
- **Action**: Generate OSM edit template
- **Human Review**: Optional spot-check only
- **Typical Scenario**: 
  - Existing in OSM with Bitcoin tags (20%)
  - Website confirms Bitcoin (30%)
  - Active social media (20%)
  - Listed on Google Maps (20%)
  - All data valid (10%)
  - **Total**: 100%

#### MEDIUM (70-89%)
- **Recommendation**: Approve with Notes
- **Action**: Generate OSM edit template, note caveats
- **Human Review**: Quick review recommended
- **Typical Scenario**:
  - Not in OSM yet (5% baseline)
  - Website confirms Bitcoin (30%)
  - Active social media (20%)
  - Listed on Google Maps (20%)
  - All data valid (10%)
  - **Total**: 85%

#### LOW (50-69%)
- **Recommendation**: Needs Human Review
- **Action**: Request additional verification
- **Human Review**: Required
- **Typical Scenario**:
  - Not in OSM (5% baseline)
  - Website exists but no Bitcoin mention (10%)
  - Social media inactive (5%)
  - Listed on 1 platform (5%)
  - Data has minor issues (5%)
  - **Total**: 30% (triggers Phase 2)
  - After email confirmation: +20% = 50% → LOW

#### VERY LOW (0-49%)
- **Recommendation**: Reject or Request More Info
- **Action**: Post detailed report requesting missing info
- **Human Review**: Required
- **Typical Scenario**:
  - Not in OSM (5% baseline)
  - No website (0%)
  - No social media (0%)
  - Not listed anywhere (0%)
  - Only coordinates valid (4%)
  - **Total**: 9%

## Scoring Details

### OSM Verification (20 points)

Many legitimate businesses are not yet mapped in OpenStreetMap. This check is
a **bonus for existing presence**, not a penalty for absence. A business that
is not on OSM should still be able to score well from the other checks.

```python
def score_osm(osm_data, max_score=20):
    # Baseline: don't penalize absence from OSM
    score = max(5, int(max_score * 0.25))
    
    # Location exists in OSM — strong positive signal
    if osm_data['exists']:
        score = int(max_score * 0.5)  # 10/20
        
        # Coordinates match (within 50m)
        if osm_data['coordinates_match']:
            score += int(max_score * 0.15)  # +3
            
        # Name matches
        if osm_data['name_matches']:
            score += int(max_score * 0.15)  # +3
            
        # Has Bitcoin tags (already verified by community)
        if osm_data['has_bitcoin_tags']:
            score += int(max_score * 0.2)  # +4
    
    return min(score, max_score)
```

**Interpretation**:
- 20/20: Exists in OSM with Bitcoin tags (already community-verified)
- 16/20: Exists, matches coordinates and name
- 13/20: Exists, coordinates match
- 10/20: Exists but different location/name
- 5/20: Not in OSM (baseline — absence is common and not heavily penalized)

### Website Check (30 points)

```python
def score_website(website_data, max_score=30):
    score = 0
    
    if not website_data['url']:
        return 0
    
    # Website accessible
    if website_data['accessible']:
        score += 5
        
        # Bitcoin explicitly mentioned
        if website_data['bitcoin_mentioned']:
            score += 25
        elif website_data['cryptocurrency_mentioned']:
            score += 15
        else:
            score += 5  # Website exists but no mention
    
    return min(score, max_score)
```

**Interpretation**:
- 30/30: "Bitcoin accepted" explicitly stated
- 25/30: Strong Bitcoin indicators (logos, payment page)
- 20/30: Cryptocurrency mentioned (not specific)
- 10/30: Website accessible, neutral
- 5/30: Website accessible, no crypto mention
- 0/30: No website or inaccessible

### Social Media (20 points)

```python
def score_social(social_data):
    score = 0
    
    # Has social media accounts
    if social_data['has_accounts']:
        score += 5
        
        # Account is active (posts within 6 months)
        if social_data['is_active']:
            score += 5
            
            # Bitcoin-related posts found
            if social_data['bitcoin_posts']:
                score += 10
            else:
                score += 5
    
    return min(score, 20)
```

**Interpretation**:
- 20/20: Active account with Bitcoin posts
- 15/20: Active account, no Bitcoin mention
- 10/20: Inactive account
- 5/20: Account exists but empty
- 0/20: No social media presence

### Cross-Reference (20 points)

```python
def score_crossref(crossref_data, max_score=20):
    score = 0
    
    platforms = crossref_data['platforms_found']
    
    if platforms >= 3:
        score = 15
    elif platforms == 2:
        score = 10
    elif platforms == 1:
        score = 5
    
    # Bonus for consistency across platforms
    if crossref_data['information_consistent']:
        score = min(score + 5, max_score)
    
    return score
```

**Interpretation**:
- 20/20: Listed on 3+ platforms with consistent info
- 15/20: Listed on 3+ platforms (some inconsistency)
- 10/20: Listed on 2 platforms
- 5/20: Listed on 1 platform
- 0/20: Not found on any platform

### Data Consistency (10 points)

```python
def score_consistency(data):
    score = 0
    
    # Address format valid for country
    if data['address_valid']:
        score += 3
    
    # Phone format valid
    if data['phone_valid']:
        score += 2
    
    # Opening hours format valid
    if data['hours_valid']:
        score += 2
    
    # Coordinates valid
    if data['coordinates_valid']:
        score += 2
    
    # Category recognized
    if data['category_valid']:
        score += 1
    
    return score
```

**Interpretation**:
- 10/10: All fields valid
- 7-9/10: Minor format issues
- 4-6/10: Some validation failures
- 0-3/10: Major data quality issues

## Phase 2 Bonuses

### Email Confirmation (+20 points)

```python
def score_email_confirmation(email_result):
    if email_result['response_received']:
        if email_result['confirmed_bitcoin']:
            return 20
        elif email_result['denied_bitcoin']:
            return -50  # Flag for removal
    return 0
```

**Interpretation**:
- +20: Email confirms Bitcoin acceptance
- 0: No response
- Flag: Explicit denial

### Social DM Confirmation (+15 points)

```python
def score_dm_confirmation(dm_result):
    if dm_result['response_received']:
        if dm_result['confirmed_bitcoin']:
            return 15
        elif dm_result['denied_bitcoin']:
            return -50  # Flag for removal
    return 0
```

**Interpretation**:
- +15: DM confirms Bitcoin acceptance
- 0: No response
- Flag: Explicit denial

## Special Cases

### Conflicting Information

When sources conflict (e.g., website says yes, email says no):

```python
def handle_conflict(scores, sources):
    # Reduce confidence
    penalty = 20
    
    # Flag for human review
    needs_review = True
    
    # Note conflict in report
    conflict_note = f"Conflicting info: {sources}"
    
    return max(0, sum(scores) - penalty), needs_review, conflict_note
```

### Duplicate Detection

If merchant already exists in BTC Map:

```python
def handle_duplicate(existing_issue):
    # Close current issue
    action = "close_duplicate"
    
    # Reference original
    reference = f"Duplicate of #{existing_issue['number']}"
    
    # Check if needs update
    if existing_issue['needs_update']:
        action = "suggest_update"
    
    return action, reference
```

## Weight Adjustment Guidelines

### When to Adjust Weights

**Increase OSM Weight** (+5-10):
- Your region has high OSM coverage
- OSM data is consistently accurate
- Community is very active

**Increase Website Weight** (+5-10):
- Most merchants have websites
- Website information is reliable
- Quick verification needed

**Decrease Social Media Weight** (-5-10):
- Merchants in your region rarely use social media
- Many false positives from social search
- Privacy-conscious businesses

**Increase Cross-Reference Weight** (+5):
- Strong local business directories
- Google Maps very comprehensive
- Yelp/ TripAdvisor popular

### Regional Variations

**Developed Countries** (US, EU, etc.):
- OSM: 20% (high coverage, but still many unmapped businesses)
- Website: 30% (businesses have websites)
- Social: 20% (standard)
- Cross-ref: 25% (many platforms)
- Consistency: 5%

**Developing Countries**:
- OSM: 15% (lower coverage — even less reason to penalize absence)
- Website: 20% (fewer websites)
- Social: 25% (primary online presence)
- Cross-ref: 25% (limited platforms but Google Maps important)
- Consistency: 15%

**Rural Areas**:
- OSM: 10% (very low coverage — absence is expected)
- Website: 15% (rarely have websites)
- Social: 25% (Facebook common)
- Cross-ref: 30% (Google Maps critical for confirming existence)
- Consistency: 20%

## Confidence Calibration

### Measuring Accuracy

Track these metrics monthly:

```python
metrics = {
    'total_verified': 0,
    'high_confidence_approved': 0,
    'high_confidence_false_positive': 0,
    'low_confidence_rejected': 0,
    'low_confidence_false_negative': 0,
    'average_resolution_time': 0
}

# Calculate error rates
false_positive_rate = (
    metrics['high_confidence_false_positive'] / 
    metrics['high_confidence_approved']
)

false_negative_rate = (
    metrics['low_confidence_false_negative'] / 
    metrics['low_confidence_rejected']
)
```

### Adjusting Thresholds

**If false positive rate > 5%**:
- Increase `high` threshold from 90% to 95%
- Increase OSM weight by 5%
- Add mandatory cross-reference check

**If false negative rate > 10%**:
- Decrease `medium` threshold from 70% to 65%
- Decrease website weight by 5%
- Increase social media weight by 5%

**If resolution time > 48 hours**:
- Increase Phase 1 threshold to skip more Phase 2
- Automate more checks
- Pre-draft common responses

## Implementation

### Configuration

```yaml
weights:
  osm_check: 20           # Bonus for existing presence (absence is common)
  website_check: 30       # Primary signal
  social_media: 20
  cross_reference: 20     # Confirms business exists independently
  data_consistency: 10

phase2_weights:
  email_confirmation: 20
  social_dm_confirmation: 15

thresholds:
  high: 90
  medium: 70
  low: 50
```

### Scoring Example

```python
# Example: High confidence merchant (existing on OSM)
phase1 = {
    'osm': {'score': 20, 'exists': True, 'has_bitcoin_tags': True},
    'website': {'score': 30, 'bitcoin_mentioned': True},
    'social': {'score': 20, 'bitcoin_posts': True},
    'crossref': {'score': 20, 'platforms': 3},
    'consistency': {'score': 10, 'all_valid': True}
}

phase1_score = 20 + 30 + 20 + 20 + 10  # = 100%

# Phase 2 not needed (100% >= 70% threshold)
final_score = 100%
recommendation = "HIGH CONFIDENCE - Recommend Approval"
```

```python
# Example: Medium confidence merchant (NOT on OSM — still scores well)
phase1 = {
    'osm': {'score': 5, 'exists': False},        # Baseline, not penalized
    'website': {'score': 30, 'bitcoin_mentioned': True},
    'social': {'score': 15, 'active': True, 'bitcoin_posts': False},
    'crossref': {'score': 10, 'platforms': 2},
    'consistency': {'score': 10, 'all_valid': True}
}

phase1_score = 5 + 30 + 15 + 10 + 10  # = 70%

# Phase 2 not triggered (70% >= 70% threshold)
final_score = 70%
recommendation = "MEDIUM CONFIDENCE - Recommend Approval with Notes"
```

## Testing

### Unit Tests

```python
def test_perfect_merchant():
    scorer = ConfidenceScorer(config)
    
    phase1 = {
        'osm': {'score': 30},
        'website': {'score': 25},
        'social': {'score': 20},
        'crossref': {'score': 15},
        'consistency': {'score': 10}
    }
    
    score = scorer.calculate_phase1_score(phase1)
    assert score == 100
    assert scorer.get_recommendation(score) == "HIGH CONFIDENCE - Recommend Approval"

def test_low_confidence():
    phase1 = {
        'osm': {'score': 0},
        'website': {'score': 5},
        'social': {'score': 5},
        'crossref': {'score': 0},
        'consistency': {'score': 4}
    }
    
    score = scorer.calculate_phase1_score(phase1)
    assert score == 14
    assert scorer.get_recommendation(score) == "VERY LOW CONFIDENCE - Recommend Rejection or More Info"
```

## Version History

- **v1.0.0** (Current): Initial algorithm with 5 Phase 1 checks and 2 Phase 2 bonuses
- Weights and thresholds should be adjusted based on real-world performance

## References

- [Verification Workflow](VERIFICATION_WORKFLOW.md)
- [Example Issues](EXAMPLE_ISSUES.md)
- [Gitea API Reference](GITEA_API_REFERENCE.md)
