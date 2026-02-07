# Example BTC Map Issues

This document provides example issue data for testing and development.

## Issue Types

### 1. Square Import Format

Issues imported automatically from Square payment processor.

```yaml
issue_number: 12079
title: Coldwater Mountain Brewpub
type: location-submission
source: square
labels:
  - type/location-submission
  - import/square
  - us
body: |
  Id: 8378
  Origin: square
  Name: Coldwater Mountain Brewpub
  Category: bar_club_lounge

  Extra fields:

  {
  "address": "1208 Walnut Ave Anniston AL 36201 US",
  "icon_url": "https://square-web-production-f.squarecdn.com/files/abc123",
  "description": "GREAT FOOD & FRESH LOCAL CRAFT BEER",
  "opening_hours": "Mo-Th 11:30-21:00; Fr-Sa 11:30-23:00; Su 13:00-19:00",
  "last_updated": "2026-02-07T09:35:24.301597294Z"
  }

  OpenStreetMap viewer link: https://www.openstreetmap.org/#map=21/33.650462/-85.834185
  OpenStreetMap editor link: https://www.openstreetmap.org/edit#map=21/33.650462/-85.834185

  To verify this imported place:
  1. Check if the place already exists in OSM.
  2. If it exists: Confirm it has a currency:XBT tag, then close this ticket.
  3. If it does not exist: Contact the merchant or verify its existence using at least one other source.

  Check this page for more instructions: https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki/Tagging-Merchants

expected_results:
  phase1_score: 70
  osm_check: 15  # Coordinates provided but not verified
  website_check: 25  # Has Square presence
  social_check: 10  # Needs manual verification
  crossref_check: 10  # Needs manual verification
  consistency_check: 10  # All data provided
  phase2_needed: true
  recommendation: "MEDIUM CONFIDENCE - Recommend Approval with Notes"
```

### 2. Manual Submission Format

Issues submitted manually through the BTC Map web form.

#### Example 2a: Complete Information

```yaml
issue_number: 12080
title: Pizza Palace Downtown
type: location-submission
source: manual
labels:
  - type/location-submission
  - us
body: |
  Merchant name: Pizza Palace Downtown
  Address: 123 Main St, New York, NY 10001
  Lat: 40.7128
  Long: -74.0060
  Associated areas: Bitcoin NYC (bitcoin-nyc), New York (us)
  OSM: https://www.openstreetmap.org/edit#map=21/40.7128/-74.0060
  Category: Restaurant
  Payment methods: lightning, onchain
  Website: https://pizzapalace.example.com
  Phone: +1-555-0123
  Opening hours: Mo-Su 11:00-22:00
  Notes: Accepts Bitcoin for dine-in and delivery
  Data Source: Website
  Details (if applicable): Verified on payment page
  Contact: owner@pizzapalace.example.com
  Created at: 2026-02-07T10:30:00.000Z

  If you are a new contributor please read our Tagging Instructions [here](https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki/Tagging-Merchants).

expected_results:
  phase1_score: 85
  osm_check: 0  # Not in OSM yet
  website_check: 25  # Website confirms Bitcoin
  social_check: 20  # Active on Twitter
  crossref_check: 15  # Listed on Google Maps and Yelp
  consistency_check: 10  # All fields valid
  phase2_needed: false
  recommendation: "MEDIUM CONFIDENCE - Recommend Approval"
```

#### Example 2b: Minimal Information

```yaml
issue_number: 12081
title: Borjulink Communications Eastlands
type: location-submission
source: manual
labels:
  - type/location-submission
  - bitcoin-dada-nairobi
  - ke
body: |
  Merchant name: Borjulink communications Eastlands 
  Address: Cdf manyanja Road
  Lat: -1.2930565029175691
  Long: 36.88961190449126
  Associated areas: Bitcoin Dada Nairobi (bitcoin-dada-nairobi), Kenya (ke), The Core (the-core), Bitcoin Nairobi (bitcoin-nairobi)
  OSM: https://www.openstreetmap.org/edit#map=21/-1.2930565029175691/36.88961190449126
  Category: Phone accessories shop
  Payment methods: lightning
  Website: 
  Phone: 0723144074
  Opening hours: 10 am to 6pm
  Notes: 
  Data Source: Other
  Details (if applicable): Bitbiashara Bitcoin circular economy 
  Contact: rosalinewaithiegeni@gmail.com
  Created at: 2026-02-07T05:40:05.459Z

  If you are a new contributor please read our Tagging Instructions [here](https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki/Tagging-Merchants).

expected_results:
  phase1_score: 10
  osm_check: 0  # Not in OSM
  website_check: 0  # No website
  social_check: 5  # Difficult to find
  crossref_check: 0  # Not on major platforms
  consistency_check: 5  # Hours format informal
  phase2_needed: true
  recommendation: "VERY LOW CONFIDENCE - Recommend Rejection or More Info"
  action_items:
    - "Request website URL"
    - "Request social media handles"
    - "Email verification sent"
```

### 3. Verification Request Format

Issues requesting verification of existing locations.

```yaml
issue_number: 12082
title: The Bitcoin Hardware Store - Verification
type: location-verification
labels:
  - type/location-verification
  - bitcoin-beach
  - sv
body: |
  Merchant name: The Bitcoin Hardware Store
  Merchant location: https://btcmap.org/map#18/13.4981821/-89.4394507
  Coordinates: 13.4981821, -89.4394507
  Associated areas: Bitcoin Beach (bitcoin-beach), Bitcoin Coast (bitcoin_coast)
  Edit link: https://www.openstreetmap.org/edit?node=11618720783
  Current information correct: Yes
  Outdated information: 
  How did you verify this?: Visited the store Feb. 02, 2026
  Created at: 2026-02-07T04:55:18.189Z

  If you are a new contributor please read our Tagging Instructions [here](https://gitea.btcmap.org/teambtcmap/btcmap-general/wiki/Tagging-Merchants).

expected_results:
  phase1_score: 100
  osm_check: 30  # Already in OSM
  website_check: 25  # Has website
  social_check: 20  # Active
  crossref_check: 15  # Listed
  consistency_check: 10  # Valid
  phase2_needed: false
  recommendation: "HIGH CONFIDENCE - Recommend Approval"
  action: "Update check_date:currency:XBT tag in OSM"
```

### 4. Community Submission Format

Issues for Bitcoin community groups and meetups.

```yaml
issue_number: 12083
title: Bitcoin Beach Community
type: community-submission
labels:
  - type/community-submission
  - bitcoin-beach
  - sv
body: |
  Community name: Bitcoin Beach Community
  Location: El Zonte, El Salvador
  Lat: 13.4944
  Long: -89.4342
  Associated areas: Bitcoin Beach (bitcoin-beach)
  OSM: https://www.openstreetmap.org/edit#map=21/13.4944/-89.4342
  Type: Community
  Description: Bitcoin circular economy community in El Zonte
  Website: https://bitcoinbeach.com
  Social: @bitcoinbeach (Twitter)
  Contact: info@bitcoinbeach.com
  Data Source: Official website
  Created at: 2026-02-07T08:00:00.000Z

expected_results:
  phase1_score: 95
  osm_check: 25  # Community areas are different
  website_check: 25  # Strong web presence
  social_check: 20  # Very active
  crossref_check: 15  # Media coverage
  consistency_check: 10  # Complete data
  phase2_needed: false
  recommendation: "HIGH CONFIDENCE - Recommend Approval"
```

## Test Scenarios

### Scenario 1: High Confidence Auto-Approval

**Input**: Square import with website, active social media, matches Google Maps

**Expected**:
- Phase 1: 70-100%
- Phase 2: Not needed
- Recommendation: Approve
- Action: Generate OSM edit template

### Scenario 2: Medium Confidence with Phase 2

**Input**: Manual submission with website but no social media

**Expected**:
- Phase 1: 50-70%
- Phase 2: Email verification
- After email: 70-90%
- Recommendation: Approve with notes

### Scenario 3: Low Confidence - Needs Review

**Input**: Minimal information, no website, no social media

**Expected**:
- Phase 1: 0-30%
- Phase 2: Email sent
- After no response: Still < 50%
- Recommendation: Request more info
- Action: Ask for website, social media, or phone

### Scenario 4: Conflicting Information

**Input**: Website says "Bitcoin accepted" but email says "We don't accept Bitcoin"

**Expected**:
- Phase 1: High score (based on website)
- Phase 2: Email denial
- Final: Flagged for human review
- Action: Request clarification

### Scenario 5: Duplicate Detection

**Input**: Merchant already exists as issue #10000

**Expected**:
- Detected as duplicate
- Close current issue
- Reference original issue
- Suggest update if needed

### Scenario 6: Outdated Location

**Input**: Verification request for merchant that closed

**Expected**:
- Phase 1: High (still in OSM)
- User report: "Closed down"
- Recommendation: Remove from map
- Action: Update OSM to remove Bitcoin tags

## JSON Structure

### Issue Object (from Gitea API)

```json
{
  "id": 12350,
  "number": 12079,
  "title": "Coldwater Mountain Brewpub",
  "body": "...",
  "state": "open",
  "labels": [
    {
      "id": 1307,
      "name": "import/square",
      "color": "0052cc"
    },
    {
      "id": 901,
      "name": "type/location-submission",
      "color": "009800"
    }
  ],
  "user": {
    "id": 4,
    "login": "btcmap-bot",
    "full_name": "BTC Map Bot"
  },
  "assignee": null,
  "created_at": "2026-02-07T09:45:22Z",
  "updated_at": "2026-02-07T09:45:22Z",
  "comments": 0
}
```

### Parsed Issue Data

```json
{
  "name": "Coldwater Mountain Brewpub",
  "source": "square",
  "category": "bar_club_lounge",
  "address": "1208 Walnut Ave Anniston AL 36201 US",
  "lat": "33.650462",
  "lon": "-85.834185",
  "opening_hours": "Mo-Th 11:30-21:00; Fr-Sa 11:30-23:00; Su 13:00-19:00",
  "description": "GREAT FOOD & FRESH LOCAL CRAFT BEER",
  "website": null,
  "phone": null,
  "contact": null,
  "osm_view_url": "https://www.openstreetmap.org/#map=21/33.650462/-85.834185",
  "osm_edit_url": "https://www.openstreetmap.org/edit#map=21/33.650462/-85.834185"
}
```

## Testing Checklist

Use these examples to verify the skill works correctly:

- [ ] Parse Square import format correctly
- [ ] Parse manual submission format correctly
- [ ] Parse verification request format correctly
- [ ] Calculate Phase 1 scores accurately
- [ ] Trigger Phase 2 when needed
- [ ] Generate appropriate recommendations
- [ ] Post reports to Gitea correctly
- [ ] Generate OSM edit suggestions
- [ ] Handle edge cases (no website, conflicting info)
- [ ] Respect rate limits

## References

- [Verification Workflow](VERIFICATION_WORKFLOW.md)
- [Confidence Algorithm](CONFIDENCE_ALGORITHM.md)
- [Gitea API Reference](GITEA_API_REFERENCE.md)
