#!/usr/bin/env python3
"""
Phase 1 Verification Module

Performs automated verification checks that don't require external responses:
- OSM verification
- Website scraping
- Social media checks
- Cross-reference with other sources
- Data consistency validation
"""

import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import json


class Phase1Verifier:
    """Phase 1 automated verification."""
    
    def __init__(self, config: Dict):
        """Initialize with configuration."""
        self.config = config
        self.weights = config['weights']
        
    def verify(self, issue: Dict) -> Dict:
        """Run all Phase 1 verification checks."""
        # Parse issue data
        issue_data = self._parse_issue(issue)
        
        results = {
            'issue_number': issue['number'],
            'merchant_name': issue_data.get('name', issue['title']),
            'checks': {},
            'score': 0,
            'max_score': 100
        }
        
        # Run each check (max scores come from configured weights)
        print("  [Phase 1] Checking OSM...", end=" ")
        results['checks']['osm'] = self._check_osm(issue_data)
        print(f"{results['checks']['osm']['status']} ({results['checks']['osm']['score']}/{self.weights['osm_check']})")
        
        time.sleep(self.config['rate_limiting']['web_scrape_delay_seconds'])
        
        print("  [Phase 1] Checking website...", end=" ")
        results['checks']['website'] = self._check_website(issue_data)
        print(f"{results['checks']['website']['status']} ({results['checks']['website']['score']}/{self.weights['website_check']})")
        
        time.sleep(self.config['rate_limiting']['web_scrape_delay_seconds'])
        
        print("  [Phase 1] Checking social media...", end=" ")
        results['checks']['social'] = self._check_social_media(issue_data)
        print(f"{results['checks']['social']['status']} ({results['checks']['social']['score']}/{self.weights['social_media']})")
        
        time.sleep(self.config['rate_limiting']['web_scrape_delay_seconds'])
        
        print("  [Phase 1] Cross-referencing...", end=" ")
        results['checks']['cross_reference'] = self._check_cross_reference(issue_data)
        print(f"{results['checks']['cross_reference']['status']} ({results['checks']['cross_reference']['score']}/{self.weights['cross_reference']})")
        
        print("  [Phase 1] Validating data...", end=" ")
        results['checks']['consistency'] = self._check_data_consistency(issue_data)
        print(f"{results['checks']['consistency']['status']} ({results['checks']['consistency']['score']}/{self.weights['data_consistency']})")
        
        # Calculate total score
        results['score'] = sum(check['score'] for check in results['checks'].values())
        results['issue_data'] = issue_data
        
        return results
    
    def _parse_issue(self, issue: Dict) -> Dict:
        """Parse issue body to extract merchant data."""
        body = issue.get('body', '')
        data = {
            'name': issue['title'],
            'raw_body': body,
            'source': 'unknown'
        }
        
        # Detect issue type (Square import vs manual submission)
        if 'Origin: square' in body or 'Id:' in body and 'square' in body.lower():
            data['source'] = 'square'
            data.update(self._parse_square_format(body))
        elif 'Merchant name:' in body:
            data['source'] = 'manual'
            data.update(self._parse_manual_format(body))
        
        return data
    
    def _parse_square_format(self, body: str) -> Dict:
        """Parse Square import format."""
        data = {}
        
        # Extract fields using regex
        patterns = {
            'id': r'Id:\s*(\d+)',
            'origin': r'Origin:\s*(\w+)',
            'name': r'Name:\s*(.+?)(?=\n|$)',
            'category': r'Category:\s*(.+?)(?=\n|$)',
            'address': r'"address":\s*"([^"]+)"',
            'lat': r'lat[=:]\s*(-?\d+\.\d+)',
            'lon': r'lon[=:]\s*(-?\d+\.\d+)',
            'opening_hours': r'"opening_hours":\s*"([^"]+)"',
            'description': r'"description":\s*"([^"]+)"',
            'website': r'website[=:]\s*(https?://\S+)',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                data[field] = match.group(1).strip()
        
        # Extract coordinates from OSM link if present
        osm_match = re.search(r'openstreetmap\.org.*map=\d+/(-?\d+\.\d+)/(-?\d+\.\d+)', body)
        if osm_match:
            data['lat'] = osm_match.group(1)
            data['lon'] = osm_match.group(2)
        
        return data
    
    def _parse_manual_format(self, body: str) -> Dict:
        """Parse manual submission format."""
        data = {}
        
        # Extract fields using regex
        patterns = {
            'name': r'Merchant name:\s*(.+?)(?=\n|$)',
            'address': r'Address:\s*(.+?)(?=\n|Lat:|$)',
            'lat': r'Lat:\s*(-?\d+\.\d+)',
            'lon': r'Long:\s*(-?\d+\.\d+)',
            'category': r'Category:\s*(.+?)(?=\n|$)',
            'payment_methods': r'Payment methods:\s*(.+?)(?=\n|$)',
            'website': r'Website:\s*(https?://\S+|\S+\.\S+)',
            'phone': r'Phone:\s*([\d\s\-\+\(\)]+)',
            'opening_hours': r'Opening hours:\s*(.+?)(?=\n|$)',
            'contact': r'Contact:\s*(\S+@\S+)',
            'data_source': r'Data Source:\s*(.+?)(?=\n|$)',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value and value.lower() not in ['', 'n/a', 'none']:
                    data[field] = value
        
        # Extract coordinates from OSM link
        osm_match = re.search(r'openstreetmap\.org.*map=\d+/(-?\d+\.\d+)/(-?\d+\.\d+)', body)
        if osm_match:
            data['lat'] = osm_match.group(1)
            data['lon'] = osm_match.group(2)
        
        return data
    
    def _check_osm(self, data: Dict) -> Dict:
        """Check OpenStreetMap for existing location.
        
        Note: Many legitimate businesses are not yet on OSM, so absence is not
        heavily penalized. This check is a bonus for existing presence rather
        than a penalty for absence.
        """
        max_score = self.weights['osm_check']
        result = {
            'check_name': 'OSM Verification',
            'status': 'fail',
            'score': 0,
            'max_score': max_score,
            'details': {}
        }
        
        if not data.get('lat') or not data.get('lon'):
            result['details']['error'] = 'No coordinates provided'
            return result
        
        try:
            lat, lon = float(data['lat']), float(data['lon'])
            
            result['details']['coordinates'] = {'lat': lat, 'lon': lon}
            result['details']['location_provided'] = True
            
            # AGENT: Use WebFetch to query the Overpass API for nearby OSM nodes:
            #   POST https://overpass-api.de/api/interpreter
            #   Query: [out:json][timeout:25];(node["name"](around:50,{lat},{lon});way["name"](around:50,{lat},{lon}););out body;
            #   Then check if any returned elements match the merchant name.
            #
            #   Scoring (OSM presence is a bonus, not a requirement):
            #   - Full match (name + coords + bitcoin tags): max_score
            #   - Partial match (coords only): max_score * 0.6
            #   - Not found on OSM: max_score * 0.25 (baseline — don't penalize absence)
            #   Many legitimate businesses simply haven't been mapped yet.
            #   See references/CONFIDENCE_ALGORITHM.md for full scoring rubric.
            result['status'] = 'unclear'
            result['score'] = max(5, int(max_score * 0.25))  # Baseline for valid coordinates
            result['details']['note'] = 'Coordinates provided. Not being on OSM is common and not heavily penalized.'
            
        except (ValueError, TypeError) as e:
            result['details']['error'] = f'Invalid coordinates: {e}'
        
        return result
    
    def _check_website(self, data: Dict) -> Dict:
        """Check merchant website for Bitcoin acceptance."""
        result = {
            'check_name': 'Website Verification',
            'status': 'fail',
            'score': 0,
            'max_score': self.weights['website_check'],
            'details': {}
        }
        
        website = data.get('website', '')
        if not website:
            result['details']['note'] = 'No website provided'
            return result
        
        # Normalize website URL
        if not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        
        result['details']['website'] = website
        
        try:
            # AGENT: Use WebFetch to scrape the merchant website:
            #   WebFetch GET {website}
            #   Search the returned content for Bitcoin acceptance indicators:
            #     - "bitcoin", "btc", "lightning", "crypto" keywords
            #     - Payment method sections mentioning Bitcoin
            #     - BTC/Lightning logos or payment processor badges
            #   Also extract any social media links found on the page (Twitter,
            #   Instagram, Facebook URLs) — store them in result['details']['social_links']
            #   so they can be included as contact:* OSM tags.
            #   Score 30/30 if explicit "Bitcoin accepted", 20/30 for crypto mention,
            #   5/30 if website exists but no mention, 0/30 if no website.
            #   See references/CONFIDENCE_ALGORITHM.md for full scoring rubric.
            result['status'] = 'unclear'
            result['score'] = 5  # Partial credit for having a website
            result['details']['note'] = f'Website URL provided: {website}. Manual verification needed.'
            result['details']['verified_website'] = website  # Captured for OSM contact:website tag
            result['details']['indicators_to_check'] = [
                'Bitcoin accepted text',
                'BTC/Lightning logos',
                'Payment methods section',
                'Cryptocurrency mentions',
                'Social media links (for contact:* OSM tags)'
            ]
            # AGENT: If you find social links on the website, populate this dict:
            result['details']['social_links'] = {}  # e.g. {"twitter": "https://twitter.com/merchant"}
            
        except Exception as e:
            result['details']['error'] = str(e)
        
        return result
    
    def _check_social_media(self, data: Dict) -> Dict:
        """Check social media presence."""
        result = {
            'check_name': 'Social Media Verification',
            'status': 'fail',
            'score': 0,
            'max_score': self.weights['social_media'],
            'details': {}
        }
        
        # Try to extract social media from various sources
        social_handles = []
        
        # Check if social media mentioned in website or contact
        website = data.get('website', '')
        
        # Look for common social patterns
        social_patterns = {
            'twitter': r'twitter\.com/(\w+)',
            'instagram': r'instagram\.com/(\w+)',
            'facebook': r'facebook\.com/(\w+)',
        }
        
        # AGENT: Use WebFetch to check social media presence:
        #   1. Search Twitter/X: WebFetch GET https://twitter.com/search?q={merchant_name}
        #   2. Search Instagram: WebFetch GET https://www.instagram.com/{handle}/
        #   Look for: account existence, recent activity, Bitcoin-related posts/hashtags
        #   Score 20/20 if active with Bitcoin posts, 10/20 if active without,
        #   5/20 if inactive, 0/20 if no social media found.
        #
        #   IMPORTANT: When you find social media accounts, store them in
        #   result['details']['discovered_handles'] — these will be included as
        #   contact:twitter, contact:instagram, etc. OSM tags in the edit template.
        #   Use full URLs (e.g. "https://twitter.com/merchant"), not just handles.
        #   See references/CONFIDENCE_ALGORITHM.md for full scoring rubric.
        result['status'] = 'unclear'
        result['score'] = 5  # Partial credit
        result['details']['note'] = 'Social media verification requires manual search'
        result['details']['suggested_search'] = f"Search Twitter/Instagram for: {data.get('name', '')}"
        # AGENT: Populate with discovered accounts, e.g.:
        #   {"twitter": "https://twitter.com/merchant", "instagram": "https://instagram.com/merchant"}
        result['details']['discovered_handles'] = {}
        
        return result
    
    def _check_cross_reference(self, data: Dict) -> Dict:
        """Cross-reference with other mapping services."""
        result = {
            'check_name': 'Cross-Reference Verification',
            'status': 'fail',
            'score': 0,
            'max_score': self.weights['cross_reference'],
            'details': {}
        }
        
        if not data.get('name'):
            result['details']['error'] = 'No merchant name provided'
            return result
        
        # AGENT: Use WebFetch to cross-reference on other platforms:
        #   1. Google Maps: WebFetch GET https://www.google.com/maps/search/{name}
        #   2. Yelp: WebFetch GET https://www.yelp.com/search?find_desc={name}
        #   Check if business is listed, and if name/address/phone are consistent.
        #   Score 15/15 if on 3+ platforms with consistent info, 10/15 for 2,
        #   5/15 for 1, 0/15 if not found anywhere.
        #   See references/CONFIDENCE_ALGORITHM.md for full scoring rubric.
        name = data['name']
        address = data.get('address', '')
        
        result['details']['google_maps_search'] = f"https://www.google.com/maps/search/{name.replace(' ', '+')}"
        result['details']['yelp_search'] = f"https://www.yelp.com/search?find_desc={name.replace(' ', '+')}"
        
        result['status'] = 'unclear'
        result['score'] = 5  # Partial credit for having search links
        result['details']['note'] = 'Cross-reference requires manual verification'
        
        return result
    
    def _check_data_consistency(self, data: Dict) -> Dict:
        """Check data consistency and format validity."""
        result = {
            'check_name': 'Data Consistency',
            'status': 'pass',
            'score': 0,
            'max_score': self.weights['data_consistency'],
            'details': {}
        }
        
        score = 0
        
        # Check address
        if data.get('address'):
            score += 3
            result['details']['address'] = 'provided'
        else:
            result['details']['address'] = 'missing'
        
        # Check coordinates
        if data.get('lat') and data.get('lon'):
            try:
                lat = float(data['lat'])
                lon = float(data['lon'])
                # Basic coordinate validation
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    score += 4
                    result['details']['coordinates'] = 'valid'
                else:
                    result['details']['coordinates'] = 'invalid range'
            except (ValueError, TypeError):
                result['details']['coordinates'] = 'invalid format'
        else:
            result['details']['coordinates'] = 'missing'
        
        # Check phone
        if data.get('phone'):
            score += 2
            result['details']['phone'] = 'provided'
        else:
            result['details']['phone'] = 'missing'
        
        # Check category
        if data.get('category'):
            score += 1
            result['details']['category'] = 'provided'
        else:
            result['details']['category'] = 'missing'
        
        result['score'] = min(score, self.weights['data_consistency'])
        result['status'] = 'pass' if score >= 5 else 'partial'
        
        return result
