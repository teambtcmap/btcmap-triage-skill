# Common Parsing Pitfalls

This document describes common issues when parsing BTC Map issue data and provides solutions.

## Issue Format Variations

### 1. Square Import Format

Square imports use **raw JSON** without markdown code fences:

```
Extra fields:

{
"address": "123 Main St",
"opening_hours": "Mo-Fr 09:00-17:00"
}
```

**Common mistake:** Looking for ` ```json ` fences that don't exist.

**Correct approach:**
```python
# Method 1: Look for raw JSON block after "Extra fields:"
extra_match = re.search(r'Extra fields:\s*\n\n(\{.*?\})', body, re.DOTALL)
if extra_match:
    data = json.loads(extra_match.group(1))

# Method 2: Fallback to individual field extraction
address = re.search(r'"address":\s*"([^"]+)"', body)
hours = re.search(r'"opening_hours":\s*"([^"]*)"', body)
```

### 2. Manual Submission Format

Manual submissions use a key-value format:

```
Merchant name: Pizza Palace
Address: 123 Main St
Lat: 40.7128
Long: -74.0060
```

**Note:** Field names may vary (e.g., `Lat:` vs `Latitude:`).

### 3. Mixed Formats

Some issues may have:
- Both Square and manual format sections
- Inconsistent field naming
- Missing optional fields
- HTML entities in text (e.g., `&quot;` instead of `"`)

## Robust Parsing Strategy

### Recommended Approach

```python
def parse_issue_body(body: str) -> Dict:
    """Robustly parse issue body regardless of format."""
    data = {}
    
    # Try Square JSON format first
    square_data = _parse_square_json(body)
    if square_data:
        data.update(square_data)
    
    # Try manual format as fallback/supplement
    manual_data = _parse_manual_format(body)
    data.update(manual_data)  # Manual fields override Square if present
    
    # Extract coordinates from OSM link if not already parsed
    if 'lat' not in data or 'lon' not in data:
        coords = _extract_osm_coords(body)
        data.update(coords)
    
    return data


def _parse_square_json(body: str) -> Optional[Dict]:
    """Parse Square import JSON format."""
    # Try fenced code block first (future-proofing)
    match = re.search(r'```json\s*\n(.*?)\n```', body, re.DOTALL)
    if not match:
        # Try raw JSON (current Square format)
        match = re.search(r'Extra fields:\s*\n\n(\{.*?\})', body, re.DOTALL)
    
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            # Handle HTML entities or malformed JSON
            json_str = match.group(1)
            json_str = html.unescape(json_str)  # Decode &quot; etc.
            return json.loads(json_str)
    
    return None


def _parse_manual_format(body: str) -> Dict:
    """Parse manual submission format."""
    data = {}
    
    # Flexible field matching
    patterns = [
        (r'Merchant name:\s*(.+?)(?=\n|$)', 'name'),
        (r'Address:\s*(.+?)(?=\n|Lat:|Long:|$)', 'address'),
        (r'(?:Lat|Latitude)[:=]\s*(-?\d+\.?\d*)', 'lat'),
        (r'(?:Long|Longitude|Lon|Lng)[:=]\s*(-?\d+\.?\d*)', 'lon'),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            data[key] = match.group(1).strip()
    
    return data


def _extract_osm_coords(body: str) -> Dict:
    """Extract coordinates from OSM links."""
    # Match various OSM URL formats
    patterns = [
        r'openstreetmap\.org.*map=\d+/(-?\d+\.\d+)/(-?\d+\.\d+)',
        r'lat[=:]\s*(-?\d+\.\d+).*lon[=:]\s*(-?\d+\.\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return {'lat': match.group(1), 'lon': match.group(2)}
    
    return {}
```

## Field Extraction Examples

### Address Parsing

Addresses come in various formats:
```
"227 W 5th St Ste 2 Winston Salem NC 27101-2825 US"  # Square
"123 Main St, New York, NY 10001"                     # Manual
"FHw5+FM9, El Zonte, El Salvador"                   # Plus code (El Salvador)
```

**Tip:** Use the address as-is for OSM's `addr:street`, don't try to parse components unless necessary.

### Opening Hours

Square format uses OSM syntax:
```
"Tu-Fr 08:00-18:00; Sa 08:00-16:00"
```

This is directly usable in OSM's `opening_hours` tag.

### Coordinates

Coordinates may be in the JSON or only in OSM links:
```
# In JSON
"lat": 36.0999
"lon": -80.2467

# In OSM link only
https://www.openstreetmap.org/#map=21/36.0999/-80.2467
```

Always check both locations.

## Testing Your Parser

Use the example issues in `EXAMPLE_ISSUES.md` to test:

```python
# Test script
from scripts.phase1_verify import Phase1Verifier

# Load test cases
with open('references/EXAMPLE_ISSUES.md') as f:
    examples = parse_yaml_examples(f)  # You'll need to implement this

verifier = Phase1Verifier(config)

for example in examples:
    parsed = verifier._parse_issue({'body': example['body']})
    
    # Verify key fields
    assert 'address' in parsed, f"Missing address in {example['title']}"
    assert 'lat' in parsed, f"Missing lat in {example['title']}"
    
    print(f"✓ {example['title']}: Parsed correctly")
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `JSONDecodeError` | HTML entities in JSON | Use `html.unescape()` before parsing |
| `AttributeError: 'NoneType'` | Regex didn't match | Add fallback patterns or default values |
| Missing fields | Wrong format detected | Try multiple format parsers |
| Coordinate mismatch | Parsed from wrong location | Prioritize explicit lat/lon over OSM link |

## Related Documentation

- [EXAMPLE_ISSUES.md](EXAMPLE_ISSUES.md) - Sample issue data for testing
- [GITEA_API_REFERENCE.md](GITEA_API_REFERENCE.md) - API interaction details
- [SKILL.md](../SKILL.md) - Main skill documentation
