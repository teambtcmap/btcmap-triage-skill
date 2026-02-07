#!/usr/bin/env python3
"""
Gitea API Client Module

Handles all interactions with the Gitea API:
- Fetching issues
- Posting comments
- Updating labels
"""

import time
from typing import Dict, List, Optional
import json


class GiteaClient:
    """Client for Gitea API interactions."""
    
    def __init__(self, config: Dict):
        """Initialize with configuration."""
        self.base_url = config.get('base_url', 'https://gitea.btcmap.org')
        self.token = config.get('token', '')
        self.repo = config.get('repo', 'teambtcmap/btcmap-data')
        
        if not self.token:
            raise ValueError("Gitea API token is required. Set GITEA_TOKEN environment variable or configure in config.yaml")
    
    def fetch_issues(self, 
                     limit: int = 10, 
                     labels: Optional[List[str]] = None,
                     state: str = 'open',
                     skip_assigned: bool = True) -> List[Dict]:
        """Fetch issues from the repository.
        
        Args:
            limit: Maximum number of issues to fetch
            labels: List of label names to filter by
            state: Issue state ('open', 'closed', 'all')
            skip_assigned: If True, skip issues already assigned to someone
            
        Returns:
            List of issue dictionaries
        """
        issues = []
        page = 1
        per_page = min(limit, 50)  # Gitea max is typically 50
        
        while len(issues) < limit:
            url = f"{self.base_url}/api/v1/repos/{self.repo}/issues"
            params = {
                'state': state,
                'page': page,
                'limit': per_page
            }
            
            if labels:
                params['labels'] = ','.join(labels)
            
            headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/json'
            }
            
            # AGENT: This is a reference implementation. Make the actual API call using WebFetch:
            #   WebFetch GET {url} with headers: Authorization: token {self.token}
            #   Query params: state, page, limit, labels (comma-separated)
            #   Response: JSON array of issue objects (see references/GITEA_API_REFERENCE.md)
            print(f"  [API] GET {url}")
            print(f"  [API] Params: {params}")
            
            # Simulate API call (replace with actual WebFetch in agent execution)
            time.sleep(0.5)
            
            # Mock data for demonstration/testing only
            mock_issues = self._get_mock_issues(limit - len(issues))
            
            for issue in mock_issues:
                # Filter by assignment if requested
                if skip_assigned and issue.get('assignee'):
                    continue
                
                issues.append(issue)
                
                if len(issues) >= limit:
                    break
            
            # Rate limiting
            time.sleep(60 / 30)  # 30 requests per minute
            page += 1
            
            # Break if no more issues
            if len(mock_issues) < per_page:
                break
        
        return issues[:limit]
    
    def post_comment(self, issue_number: int, body: str) -> int:
        """Post a comment to an issue.
        
        Args:
            issue_number: The issue number
            body: Comment body (markdown)
            
        Returns:
            Comment ID
        """
        url = f"{self.base_url}/api/v1/repos/{self.repo}/issues/{issue_number}/comments"
        
        headers = {
            'Authorization': f'token {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        data = {'body': body}
        
        # AGENT: Make the actual API call using WebFetch:
        #   WebFetch POST {url} with headers and JSON body: {"body": "<markdown>"}
        #   Response: JSON object with "id" field (the new comment ID)
        #   See references/GITEA_API_REFERENCE.md for full response format
        print(f"  [API] POST {url}")
        print(f"  [API] Body length: {len(body)} characters")
        
        # Simulate API call (replace with actual WebFetch in agent execution)
        time.sleep(0.5)
        
        # Mock comment ID for demonstration only
        return 12345
    
    def update_comment(self, comment_id: int, body: str) -> bool:
        """Update an existing comment.
        
        Args:
            comment_id: The comment ID to update
            body: New comment body
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/api/v1/repos/{self.repo}/issues/comments/{comment_id}"
        
        headers = {
            'Authorization': f'token {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        data = {'body': body}
        
        # AGENT: Make the actual API call using WebFetch:
        #   WebFetch PATCH {url} with headers and JSON body: {"body": "<markdown>"}
        #   Response: JSON object with updated comment
        print(f"  [API] PATCH {url}")
        
        # Simulate API call (replace with actual WebFetch in agent execution)
        time.sleep(0.5)
        
        return True
    
    def add_label(self, issue_number: int, label: str) -> bool:
        """Add a label to an issue.
        
        Args:
            issue_number: The issue number
            label: Label name to add
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/api/v1/repos/{self.repo}/issues/{issue_number}/labels"
        
        headers = {
            'Authorization': f'token {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # AGENT: The Gitea labels endpoint expects label IDs (integers), not names.
        #   First fetch available labels: GET /api/v1/repos/{repo}/labels
        #   Then find the ID for the label name, and POST with: {"labels": [<label_id>]}
        #   See references/GITEA_API_REFERENCE.md for label endpoints
        data = {'labels': [label]}
        
        print(f"  [API] POST {url} - Add label: {label}")
        
        return True
    
    def close_issue(self, issue_number: int) -> bool:
        """Close an issue.
        
        Args:
            issue_number: The issue number
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/api/v1/repos/{self.repo}/issues/{issue_number}"
        
        headers = {
            'Authorization': f'token {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        data = {'state': 'closed'}
        
        # AGENT: Make the actual API call using WebFetch:
        #   WebFetch PATCH {url} with headers and JSON body: {"state": "closed"}
        print(f"  [API] PATCH {url} - Close issue")
        
        return True
    
    def _get_mock_issues(self, count: int) -> List[Dict]:
        """Generate mock issues for demonstration."""
        mock_data = [
            {
                'number': 12079,
                'title': 'Coldwater Mountain Brewpub',
                'body': '''Id: 8378
Origin: square
Name: Coldwater Mountain Brewpub
Category: bar_club_lounge

Extra fields:

{
"address": "1208 Walnut Ave Anniston AL 36201 US",
"icon_url": "https://example.com/icon.png",
"description": "GREAT FOOD & FRESH LOCAL CRAFT BEER",
"opening_hours": "Mo-Th 11:30-21:00; Fr-Sa 11:30-23:00; Su 13:00-19:00",
"last_updated": "2026-02-07T09:35:24.301597294Z"
}

OpenStreetMap viewer link: https://www.openstreetmap.org/#map=21/33.650462/-85.834185
OpenStreetMap editor link: https://www.openstreetmap.org/edit#map=21/33.650462/-85.834185''',
                'labels': [
                    {'name': 'type/location-submission'},
                    {'name': 'import/square'},
                    {'name': 'us'}
                ],
                'state': 'open',
                'assignee': None
            },
            {
                'number': 12080,
                'title': 'Borjulink communications Eastlands',
                'body': '''Merchant name: Borjulink communications Eastlands 
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
Created at: 2026-02-07T05:40:05.459Z''',
                'labels': [
                    {'name': 'type/location-submission'},
                    {'name': 'bitcoin-dada-nairobi'},
                    {'name': 'ke'}
                ],
                'state': 'open',
                'assignee': None
            },
            {
                'number': 12081,
                'title': 'Pizza Palace Downtown',
                'body': '''Merchant name: Pizza Palace Downtown
Address: 123 Main St, New York, NY 10001
Lat: 40.7128
Long: -74.0060
Category: Restaurant
Payment methods: lightning, onchain
Website: https://pizzapalace.example.com
Phone: +1-555-0123
Opening hours: Mo-Su 11:00-22:00
Data Source: Website
Contact: owner@pizzapalace.example.com''',
                'labels': [
                    {'name': 'type/location-submission'},
                    {'name': 'us'}
                ],
                'state': 'open',
                'assignee': None
            }
        ]
        
        return mock_data[:count]
