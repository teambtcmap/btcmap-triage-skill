## Final Verification Report

**Merchant**: {merchant_name}  
**Issue**: #{issue_number}  
**Generated**: {timestamp}  
**Agent**: BTC Map Triage Bot

---

### Final Confidence Score: {final_score}%
**Level**: {confidence_level}  
**Recommendation**: {recommendation}

---

### Score Breakdown

#### Phase 1 (Automated): {phase1_score}%
- OSM Verification: {osm_score}/30
- Website Check: {website_score}/25
- Social Media: {social_score}/20
- Cross-Reference: {crossref_score}/15
- Data Consistency: {consistency_score}/10

#### Phase 2 (Outreach): +{phase2_bonus}%
- Email Confirmation: {email_score}/20 ({email_status})
- Social DM Confirmation: {dm_score}/15 ({dm_status})

**Total**: {final_score}%

---

### Reasoning

{reasoning}

---

### Action Items

{action_items}

---

### OSM Edit Suggestion

For Shadowy Supertaggers, here are the suggested OSM tags:

#### Required Tags:
```
currency:XBT=yes
check_date:currency:XBT={check_date}
```

#### Optional Tags (if applicable):
```
payment:lightning={lightning_status}
payment:onchain={onchain_status}
```

#### Changeset Comment:
```
Add Bitcoin acceptance for {merchant_name}
#btcmap issue:{issue_number}
Source: Verified via {verification_sources}
```

#### OSM Edit Links:
- [View on OSM]({osm_view_url})
- [Edit on OSM]({osm_edit_url})

---

### Notes for Human Reviewers

{human_notes}

---

*Verification complete. This report was generated automatically by the BTC Map Triage Bot.*
