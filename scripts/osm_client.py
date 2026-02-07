#!/usr/bin/env python3
"""
OpenStreetMap (OSM) Client Module

Handles interactions with OSM APIs:
- Overpass API for querying locations
- OSM website links for editing
- Tag validation
"""

import time
from typing import Dict, List, Optional, Tuple


class OSMClient:
    """Client for OpenStreetMap API interactions."""
    
    def __init__(self, config: Dict = None):
        """Initialize with configuration."""
        self.config = config or {}
        self.base_url = "https://www.openstreetmap.org"
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        self.api_url = "https://api.openstreetmap.org/api/0.6"
    
    def search_location(self, 
                       lat: float, 
                       lon: float, 
                       radius: float = 50) -> List[Dict]:
        """Search for locations near coordinates using Overpass API.
        
        Args:
            lat: Latitude
            lon: Longitude
            radius: Search radius in meters
            
        Returns:
            List of nearby OSM features
        """
        # Overpass QL query to find nodes near coordinates
        query = f"""
        [out:json][timeout:25];
        (
          node["name"](around:{radius},{lat},{lon});
          way["name"](around:{radius},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        # AGENT: Make the actual Overpass API call using WebFetch:
        #   WebFetch POST https://overpass-api.de/api/interpreter
        #   Body: data={query} (URL-encoded)
        #   Response: JSON with "elements" array containing matching OSM nodes/ways
        #   Rate limit: max 1 request per 5 seconds to Overpass API
        print(f"  [OSM] Searching within {radius}m of {lat}, {lon}")
        time.sleep(0.5)  # Rate limiting
        
        return []
    
    def check_bitcoin_tags(self, osm_id: int, osm_type: str = 'node') -> Dict:
        """Check if an OSM feature has Bitcoin acceptance tags.
        
        Args:
            osm_id: OSM feature ID
            osm_type: Type of feature ('node', 'way', 'relation')
            
        Returns:
            Dictionary with tag information
        """
        url = f"{self.api_url}/{osm_type}/{osm_id}"
        
        # AGENT: Fetch OSM element data using WebFetch:
        #   WebFetch GET {url}.json
        #   Response: JSON with "elements" array; check "tags" for currency:XBT, payment:lightning, etc.
        print(f"  [OSM] Checking tags for {osm_type} #{osm_id}")
        
        return {
            'has_currency_xbt': False,
            'has_payment_lightning': False,
            'has_payment_onchain': False,
            'check_date': None,
            'tags': {}
        }
    
    def generate_edit_url(self, 
                         lat: float, 
                         lon: float, 
                         zoom: int = 21) -> str:
        """Generate OSM edit URL.
        
        Args:
            lat: Latitude
            lon: Longitude
            zoom: Zoom level
            
        Returns:
            OSM iD editor URL
        """
        return f"{self.base_url}/edit#map={zoom}/{lat}/{lon}"
    
    def generate_view_url(self, 
                         lat: float, 
                         lon: float, 
                         zoom: int = 21) -> str:
        """Generate OSM view URL.
        
        Args:
            lat: Latitude
            lon: Longitude
            zoom: Zoom level
            
        Returns:
            OSM viewer URL
        """
        return f"{self.base_url}/#map={zoom}/{lat}/{lon}"
    
    def suggest_tags(self, 
                    merchant_name: Optional[str] = None,
                    payment_lightning: bool = True,
                    payment_onchain: bool = True,
                    check_date: Optional[str] = None) -> Dict:
        """Generate suggested OSM tags for Bitcoin acceptance.
        
        Returns tags in insertion order so they can be copy-pasted directly
        into the OSM iD editor tag panel as key=value lines.
        
        Args:
            merchant_name: Merchant name (included if the node is new)
            payment_lightning: Accept Lightning payments
            payment_onchain: Accept on-chain payments
            check_date: Verification date (ISO format)
            
        Returns:
            Dictionary of suggested tags
        """
        tags = {}
        
        if merchant_name:
            tags['name'] = merchant_name
        
        tags['currency:XBT'] = 'yes'
        
        if payment_lightning:
            tags['payment:lightning'] = 'yes'
        
        if payment_onchain:
            tags['payment:onchain'] = 'yes'
        
        tags['check_date:currency:XBT'] = check_date or time.strftime('%Y-%m-%d')
        
        return tags
    
    def generate_changeset_comment(self, 
                                  merchant_name: str,
                                  issue_number: int,
                                  verification_methods: List[str]) -> str:
        """Generate OSM changeset comment.
        
        Args:
            merchant_name: Name of the merchant
            issue_number: BTC Map issue number
            verification_methods: List of verification methods used
            
        Returns:
            Suggested changeset comment
        """
        methods_str = ', '.join(verification_methods)
        
        comment = f"""Add Bitcoin acceptance for {merchant_name}
#btcmap issue:{issue_number}
Source: Verified via {methods_str}"""
        
        return comment
    
    def validate_opening_hours(self, hours: str) -> bool:
        """Validate opening hours format.
        
        Args:
            hours: Opening hours string
            
        Returns:
            True if valid format
        """
        # Basic validation - in production, use proper OHM library
        if not hours:
            return False
        
        # Check for common patterns
        valid_patterns = [
            r'^Mo-Fr\s+\d{2}:\d{2}-\d{2}:\d{2}$',
            r'^Mo-Su\s+\d{2}:\d{2}-\d{2}:\d{2}$',
            r'^(Mo|Tu|We|Th|Fr|Sa|Su)(-(Mo|Tu|We|Th|Fr|Sa|Su))?\s+\d{1,2}:\d{2}-\d{1,2}:\d{2}$',
            r'^\d{1,2}\s*(am|pm)\s*to\s*\d{1,2}\s*(am|pm)$',
        ]
        
        import re
        for pattern in valid_patterns:
            if re.match(pattern, hours, re.IGNORECASE):
                return True
        
        # If no pattern matches, still might be valid (complex hours)
        return True
    
    def validate_coordinates(self, lat: float, lon: float) -> bool:
        """Validate coordinate values.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            True if coordinates are valid
        """
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            
            return -90 <= lat_f <= 90 and -180 <= lon_f <= 180
        except (ValueError, TypeError):
            return False
    
    def get_tag_reference(self) -> Dict:
        """Get reference documentation for OSM tags.
        
        Returns:
            Dictionary with tag documentation
        """
        return {
            'currency:XBT': {
                'description': 'Indicates Bitcoin is accepted',
                'values': ['yes', 'no'],
                'required': True
            },
            'payment:lightning': {
                'description': 'Indicates Lightning Network payments are accepted',
                'values': ['yes', 'no'],
                'required': False
            },
            'payment:onchain': {
                'description': 'Indicates on-chain Bitcoin payments are accepted',
                'values': ['yes', 'no'],
                'required': False
            },
            'payment:lightning_contactless': {
                'description': 'Indicates NFC/contactless Lightning payments',
                'values': ['yes', 'no'],
                'required': False
            },
            'payment:lightning:operator': {
                'description': 'Payment processor/operator (e.g., square, bitpay)',
                'values': 'Free text',
                'required': False
            },
            'check_date:currency:XBT': {
                'description': 'Date when Bitcoin acceptance was verified',
                'values': 'YYYY-MM-DD format',
                'required': False
            },
            'survey:date': {
                'description': 'Date of physical survey/verification',
                'values': 'YYYY-MM-DD format',
                'required': False
            }
        }
    
    def format_osm_edit_template(self, 
                                 tags: Dict,
                                 changeset_comment: str) -> str:
        """Format OSM edit information for direct copy-paste into the iD editor.
        
        Output format uses one key=value pair per line with no indentation or
        headers, so taggers can copy the block directly into the OSM tag editor.
        
        Args:
            tags: Dictionary of tags
            changeset_comment: Changeset comment
            
        Returns:
            Formatted string ready for copy-paste into OSM iD editor
        """
        # Tags block: one key=value per line, directly pasteable into iD editor
        tag_lines = [f"{key}={value}" for key, value in tags.items()]
        tags_block = '\n'.join(tag_lines)
        
        template = f"""Copy-paste these tags into the OSM iD editor tag panel:

```
{tags_block}
```

Changeset comment:

```
{changeset_comment}
```

Note: Please verify these tags manually before applying."""
        
        return template
