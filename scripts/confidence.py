#!/usr/bin/env python3
"""
Confidence Scoring Module

Calculates verification confidence scores and provides recommendations.
"""

from typing import Dict


class ConfidenceScorer:
    """Calculate confidence scores for verification results."""
    
    def __init__(self, config: Dict):
        """Initialize with configuration."""
        self.config = config
        self.weights = config.get('weights', {
            'osm_check': 20,
            'website_check': 30,
            'social_media': 20,
            'cross_reference': 20,
            'data_consistency': 10
        })
        self.phase2_weights = config.get('phase2_weights', {
            'email_confirmation': 20,
            'social_dm_confirmation': 15
        })
        self.thresholds = config.get('thresholds', {
            'high': 90,
            'medium': 70,
            'low': 50
        })
    
    def calculate_phase1_score(self, phase1_results: Dict) -> int:
        """Calculate Phase 1 confidence score."""
        if 'checks' not in phase1_results:
            return 0
        
        total_score = sum(check.get('score', 0) for check in phase1_results['checks'].values())
        return min(total_score, 100)  # Cap at 100
    
    def calculate_phase2_bonus(self, phase2_results: Dict) -> int:
        """Calculate Phase 2 bonus score."""
        if not phase2_results:
            return 0
        
        bonus = 0
        
        # Email confirmation
        email_result = phase2_results.get('email', {})
        if email_result.get('status') == 'confirmed':
            bonus += self.phase2_weights.get('email_confirmation', 20)
        
        # Social DM confirmation
        dm_result = phase2_results.get('social_dm', {})
        if dm_result.get('status') == 'confirmed':
            bonus += self.phase2_weights.get('social_dm_confirmation', 15)
        
        return bonus
    
    def calculate_final_score(self, phase1_score: int, phase2_results: Dict) -> int:
        """Calculate final confidence score."""
        phase2_bonus = self.calculate_phase2_bonus(phase2_results)
        final_score = phase1_score + phase2_bonus
        return min(final_score, 100)  # Cap at 100
    
    def get_recommendation(self, score: int) -> str:
        """Get recommendation based on confidence score."""
        high_threshold = self.thresholds.get('high', 90)
        medium_threshold = self.thresholds.get('medium', 70)
        low_threshold = self.thresholds.get('low', 50)
        
        if score >= high_threshold:
            return "HIGH CONFIDENCE - Recommend Approval"
        elif score >= medium_threshold:
            return "MEDIUM CONFIDENCE - Recommend Approval with Notes"
        elif score >= low_threshold:
            return "LOW CONFIDENCE - Needs Human Review"
        else:
            return "VERY LOW CONFIDENCE - Recommend Rejection or More Info"
    
    def get_detailed_recommendation(self, score: int, phase1_results: Dict, phase2_results: Dict = None) -> Dict:
        """Get detailed recommendation with reasoning."""
        recommendation = {
            'score': score,
            'level': self._get_confidence_level(score),
            'recommendation': self.get_recommendation(score),
            'reasoning': [],
            'action_items': []
        }
        
        # Analyze Phase 1 results
        if phase1_results and 'checks' in phase1_results:
            for check_name, check_result in phase1_results['checks'].items():
                if check_result.get('score', 0) < check_result.get('max_score', 0) * 0.5:
                    recommendation['reasoning'].append(
                        f"{check_name}: {check_result.get('status', 'unknown')} - {check_result.get('details', {}).get('note', 'Check failed')}"
                    )
        
        # Analyze Phase 2 results
        if phase2_results:
            if phase2_results.get('email', {}).get('status') == 'confirmed':
                recommendation['reasoning'].append("Email verification confirmed")
            elif phase2_results.get('email', {}).get('status') == 'sent':
                recommendation['action_items'].append("Waiting for email response")
            
            if phase2_results.get('social_dm', {}).get('status') == 'confirmed':
                recommendation['reasoning'].append("Social DM verification confirmed")
        
        # Generate action items based on score
        if score < self.thresholds['medium']:
            recommendation['action_items'].append("Consider physical verification by local tagger")
            
            # Check what's missing
            if phase1_results and 'checks' in phase1_results:
                if phase1_results['checks'].get('website', {}).get('status') == 'fail':
                    recommendation['action_items'].append("Request website URL")
                if phase1_results['checks'].get('social', {}).get('status') == 'fail':
                    recommendation['action_items'].append("Request social media handles")
        
        return recommendation
    
    def _get_confidence_level(self, score: int) -> str:
        """Get confidence level string."""
        high_threshold = self.thresholds.get('high', 90)
        medium_threshold = self.thresholds.get('medium', 70)
        low_threshold = self.thresholds.get('low', 50)
        
        if score >= high_threshold:
            return "HIGH"
        elif score >= medium_threshold:
            return "MEDIUM"
        elif score >= low_threshold:
            return "LOW"
        else:
            return "VERY LOW"
    
    def explain_score(self, phase1_results: Dict, phase2_results: Dict = None) -> str:
        """Generate human-readable explanation of score calculation."""
        lines = ["Confidence Score Breakdown:", "=" * 40, ""]
        
        # Phase 1 breakdown
        lines.append("Phase 1 - Automated Checks:")
        if phase1_results and 'checks' in phase1_results:
            for check_name, check_result in phase1_results['checks'].items():
                score = check_result.get('score', 0)
                max_score = check_result.get('max_score', 0)
                status = check_result.get('status', 'unknown')
                lines.append(f"  {check_name}: {score}/{max_score} ({status})")
        
        phase1_total = self.calculate_phase1_score(phase1_results)
        lines.append(f"  Phase 1 Total: {phase1_total}%")
        lines.append("")
        
        # Phase 2 breakdown
        if phase2_results:
            lines.append("Phase 2 - Outreach Verification:")
            
            email = phase2_results.get('email', {})
            email_score = email.get('score', 0)
            email_max = self.phase2_weights.get('email_confirmation', 20)
            email_status = email.get('status', 'skipped')
            lines.append(f"  Email Confirmation: +{email_score}/{email_max} ({email_status})")
            
            dm = phase2_results.get('social_dm', {})
            dm_score = dm.get('score', 0)
            dm_max = self.phase2_weights.get('social_dm_confirmation', 15)
            dm_status = dm.get('status', 'skipped')
            lines.append(f"  Social DM Confirmation: +{dm_score}/{dm_max} ({dm_status})")
            
            phase2_total = self.calculate_phase2_bonus(phase2_results)
            lines.append(f"  Phase 2 Bonus: +{phase2_total}%")
            lines.append("")
        
        # Final score
        final_score = self.calculate_final_score(phase1_total, phase2_results or {})
        lines.append(f"FINAL SCORE: {final_score}%")
        lines.append(f"Level: {self._get_confidence_level(final_score)}")
        lines.append(f"Recommendation: {self.get_recommendation(final_score)}")
        
        return "\n".join(lines)
