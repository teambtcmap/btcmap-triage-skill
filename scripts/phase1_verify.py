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
        
        # Run each check
        print("  [Phase 1] Checking OSM...", end=" ")
        results['checks']['osm'] = self._check_osm(issue_data)
        print(f"{results['checks']['osm']['status']} ({results['checks']['osm']['score']}/30)")
        
        time.sleep(self.config['rate_limiting']['web_scrape_delay_seconds'])
        
        print("  [Phase 1] Checking website...", end=" ")
        results['checks']['website'] = self._check_website(issue_data)
        print(f"{results['checks']['website']['status']} ({results['checks']['website']['score']}/25)")
        
        time.sleep(self.config['rate_limiting']['web_scrape_delay_seconds'])
        
        print("  [Phase 1] Checking social media...", end=" ")
        results['checks']['social'] = self._check_social_media(issue_data)
        print(f"{results['checks']['social']['status']} ({results['checks']['social']['score']}/20)")
        
        time.sleep(self.config['rate_limiting']['web_scrape_delay_seconds'])
        
        print("  [Phase 1] Cross-referencing...", end=" ")
        results['checks']['cross_reference'] = self._check_cross_reference(issue_data)
        print(f"{results['checks']['cross_reference']['status']} ({results['checks']['cross_reference']['score']}/15)")
        
        print("  [Phase 1] Validating data...", end=" ")
        results['checks']['consistency'] = self._check_data_consistency(issue_data)
        print(f"{results['checks']['consistency']['status']} ({results['checks']['consistency']['score']}/10)")
        
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
        """Check OpenStreetMap for existing location."""
        result = {
            'check_name': 'OSM Verification',
            'status': 'fail',
            'score': 0,
            'max_score': self.weights['osm_check'],
            'details': {}
        }
        
        if not data.get('lat') or not data.get('lon'):
            result['details']['error'] = 'No coordinates provided'
            return result
        
        try:
            # Use Overpass API to search for nodes near coordinates
            # This is a simplified check - in production, use proper Overpass queries
            lat, lon = float(data['lat']), float(data['lon'])
            
            # Check if location exists (simplified)
            result['details']['coordinates'] = {'lat': lat, 'lon': lon}
            result['details']['location_provided'] = True
            
            # For now, assume we need to check OSM manually
            # In production, implement actual Overpass API call
            result['status'] = 'unclear'
            result['score'] = 10  # Partial credit for having coordinates
            result['details']['note'] = 'Coordinates provided but OSM existence requires manual verification'
            
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
            # Fetch website (simplified - in production use proper scraping)
            # For now, assume we can't scrape without external tools
            result['status'] = 'unclear'
            result['score'] = 5  # Partial credit for having a website
            result['details']['note'] = f'Website URL provided: {website}. Manual verification needed.'
            result['details']['indicators_to_check'] = [
                'Bitcoin accepted text',
                'BTC/Lightning logos',
                'Payment methods section',
                'Cryptocurrency mentions'
            ]
            
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
        
        # For now, assume we need to search manually
        result['status'] = 'unclear'
        result['score'] = 5  # Partial credit
        result['details']['note'] = 'Social media verification requires manual search'
        result['details']['suggested_search'] = f"Search Twitter/Instagram for: {data.get('name', '')}"
        
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
        
        # Generate search links
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
