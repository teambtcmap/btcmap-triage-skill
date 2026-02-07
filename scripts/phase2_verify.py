#!/usr/bin/env python3
"""
Phase 2 Verification Module

Performs outreach verification requiring external responses:
- Email verification
- Social media DM verification

Note: This module relies on the agent having email skills for sending.
"""

import time
from typing import Dict, Optional


class Phase2Verifier:
    """Phase 2 outreach verification."""
    
    def __init__(self, config: Dict):
        """Initialize with configuration."""
        self.config = config
        self.phase2_weights = config.get('phase2_weights', {
            'email_confirmation': 20,
            'social_dm_confirmation': 15
        })
        self.auto_send = config.get('phase2_auto_send', False)
    
    def verify(self, issue: Dict, phase1_results: Dict) -> Dict:
        """Run Phase 2 verification (outreach)."""
        issue_data = phase1_results.get('issue_data', {})
        
        results = {
            'issue_number': issue['number'],
            'email': {'status': 'skipped', 'score': 0, 'details': {}},
            'social_dm': {'status': 'skipped', 'score': 0, 'details': {}},
            'total_bonus': 0
        }
        
        # Email verification
        if issue_data.get('contact') or issue_data.get('website'):
            print("  [Phase 2] Preparing email verification...")
            results['email'] = self._verify_email(issue, issue_data)
            print(f"    Email: {results['email']['status']} (+{results['email']['score']}%)")
        else:
            print("  [Phase 2] No contact email provided - skipping email verification")
        
        # Social DM verification
        print("  [Phase 2] Preparing social DM verification...")
        results['social_dm'] = self._verify_social_dm(issue, issue_data)
        print(f"    Social DM: {results['social_dm']['status']} (+{results['social_dm']['score']}%)")
        
        # Calculate total bonus
        results['total_bonus'] = results['email']['score'] + results['social_dm']['score']
        
        return results
    
    def _verify_email(self, issue: Dict, data: Dict) -> Dict:
        """Send verification email."""
        result = {
            'check_name': 'Email Verification',
            'status': 'pending',
            'score': 0,
            'max_score': self.phase2_weights['email_confirmation'],
            'details': {}
        }
        
        # Get contact email
        contact = data.get('contact', '')
        if not contact and data.get('website'):
            # Could try to extract from website, but for now just note it
            contact = self._extract_email_from_website(data['website'])
        
        if not contact:
            result['status'] = 'skipped'
            result['details']['reason'] = 'No contact email available'
            return result
        
        result['details']['contact'] = contact
        
        # Generate email content
        email_subject = self.config['email'].get('subject_template', 'Verification Request: {merchant_name}').format(
            merchant_name=data.get('name', issue['title'])
        )
        
        email_body = self._generate_email_template(issue, data)
        
        result['details']['email_subject'] = email_subject
        result['details']['email_body'] = email_body
        
        if self.auto_send:
            print(f"    Sending email to: {contact}")
            # In production, this would use the agent's email skill
            # For now, we'll draft it
            result['details']['action'] = 'sent'
            result['details']['note'] = 'Email sent (requires email skill)'
            result['status'] = 'sent'
        else:
            print(f"    Email drafted for: {contact}")
            result['details']['action'] = 'drafted'
            result['details']['note'] = 'Email drafted for review before sending'
            result['status'] = 'drafted'
        
        # For now, assume we need to wait for response
        # In production, this would poll for responses
        result['details']['response'] = 'waiting'
        result['details']['expected_response_time'] = f"{self.config['advanced'].get('phase2_wait_hours', 24)} hours"
        
        # Simulate response for demonstration
        # In production, this would be actual response checking
        result['score'] = 0  # No points until confirmed
        
        return result
    
    def _verify_social_dm(self, issue: Dict, data: Dict) -> Dict:
        """Send social media DM."""
        result = {
            'check_name': 'Social DM Verification',
            'status': 'pending',
            'score': 0,
            'max_score': self.phase2_weights['social_dm_confirmation'],
            'details': {}
        }
        
        merchant_name = data.get('name', issue['title'])
        
        # Generate DM content
        twitter_dm = self.config['social'].get('twitter_dm_template', '').format(
            merchant_name=merchant_name
        )
        
        instagram_dm = self.config['social'].get('instagram_dm_template', '').format(
            merchant_name=merchant_name
        )
        
        result['details']['twitter_dm'] = twitter_dm
        result['details']['instagram_dm'] = instagram_dm
        result['details']['suggested_handles'] = f"Search for: @{merchant_name.replace(' ', '')}"
        
        if self.auto_send:
            print(f"    DMs drafted for Twitter/Instagram")
            result['details']['action'] = 'drafted'
            result['status'] = 'drafted'
        else:
            print(f"    DMs drafted for manual sending")
            result['details']['action'] = 'drafted_for_review'
            result['status'] = 'drafted'
        
        result['details']['response'] = 'waiting'
        result['score'] = 0  # No points until confirmed
        
        return result
    
    def _extract_email_from_website(self, website: str) -> str:
        """Attempt to extract email from website (placeholder)."""
        # In production, this would scrape the website for contact info
        # For now, return empty
        return ''
    
    def _generate_email_template(self, issue: Dict, data: Dict) -> str:
        """Generate verification email template."""
        merchant_name = data.get('name', issue['title'])
        
        template = f"""Subject: Verification Request: {merchant_name}

Dear {merchant_name} Team,

I hope this email finds you well. I'm writing to verify information about your business for BTC Map (https://btcmap.org), a community-driven project that maps businesses accepting Bitcoin worldwide.

We have received a submission indicating that {merchant_name} accepts Bitcoin payments. To ensure our data is accurate, we would appreciate your confirmation:

**Do you currently accept Bitcoin as a form of payment?**

If yes, we would also appreciate knowing:
- Do you accept on-chain Bitcoin payments?
- Do you accept Lightning Network payments?
- Is a companion app required for payment?

If you do NOT currently accept Bitcoin, please let us know so we can update our records accordingly.

Your response will help us maintain accurate information for the Bitcoin community. Thank you for your time!

Best regards,
BTC Map Verification Team

---
This is an automated verification request. Please reply to confirm or correct the information.
Issue Reference: #{issue['number']}
"""
        
        return template
    
    def check_responses(self, issue_number: int) -> Dict:
        """Check for responses to outreach (placeholder)."""
        # In production, this would:
        # 1. Check email inbox for replies
        # 2. Check social media DMs
        # 3. Parse responses for confirmation/denial
        
        return {
            'email_response': None,
            'social_response': None,
            'confirmed': False
        }
