#!/usr/bin/env python3
"""
BTC Map Triage - Main Orchestrator

This script orchestrates the two-phase verification workflow:
1. Phase 1: Automated verification (OSM, website, social media)
2. Phase 2: Outreach verification (email, social DMs)

Usage:
    python triage.py [--config path/to/config.yaml]
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from phase1_verify import Phase1Verifier
from phase2_verify import Phase2Verifier
from confidence import ConfidenceScorer
from gitea_client import GiteaClient
from osm_client import OSMClient


class TriageOrchestrator:
    """Main orchestrator for BTC Map issue triage."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize with configuration."""
        self.config = self._load_config(config_path)
        self.gitea = GiteaClient(self.config['gitea'])
        self.phase1 = Phase1Verifier(self.config)
        self.phase2 = Phase2Verifier(self.config)
        self.scorer = ConfidenceScorer(self.config)
        
    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML file."""
        config_file = Path(path)
        if not config_file.exists():
            # Try example config
            example_path = Path(path).parent / "config.example.yaml"
            if example_path.exists():
                print(f"Config not found at {path}, using example config")
                config_file = example_path
            else:
                raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Expand environment variables
        config = self._expand_env_vars(config)
        return config
    
    def _expand_env_vars(self, obj):
        """Recursively expand environment variables in config."""
        if isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            var_name = obj[2:-1]
            return os.environ.get(var_name, obj)
        return obj
    
    def run(self, num_issues: Optional[int] = None):
        """Run the triage workflow."""
        print("BTC Map Triage Bot")
        print("=" * 50)
        
        # Get number of issues to process
        if num_issues is None:
            if self.config['operation_mode'] == 'ask':
                response = input(f"\nHow many issues would you like to process? [{self.config['default_batch_size']}]: ")
                num_issues = int(response) if response.strip() else self.config['default_batch_size']
            else:
                num_issues = self.config['default_batch_size']
        
        print(f"\nFetching {num_issues} open issues from btcmap-data...")
        
        # Fetch issues
        issues = self.gitea.fetch_issues(
            limit=num_issues,
            labels=self.config['issue_labels'],
            skip_assigned=self.config['advanced'].get('skip_assigned_issues', True)
        )
        
        if not issues:
            print("No issues found matching criteria.")
            return
        
        print(f"Found {len(issues)} issues to process.\n")
        
        # Process each issue
        results = []
        for i, issue in enumerate(issues, 1):
            print(f"\n[{i}/{len(issues)}] Processing issue #{issue['number']}: {issue['title']}")
            print("-" * 60)
            
            try:
                result = self._process_issue(issue)
                results.append(result)
            except Exception as e:
                print(f"Error processing issue #{issue['number']}: {e}")
                results.append({
                    'issue_number': issue['number'],
                    'error': str(e),
                    'status': 'error'
                })
            
            # Rate limiting
            if i < len(issues):
                delay = 60 / self.config['rate_limiting']['gitea_requests_per_minute']
                time.sleep(delay)
        
        # Print summary
        self._print_summary(results)
    
    def _process_issue(self, issue: Dict) -> Dict:
        """Process a single issue through both phases."""
        result = {
            'issue_number': issue['number'],
            'title': issue['title'],
            'phase1': None,
            'phase2': None,
            'final_score': 0,
            'recommendation': None,
            'comments_posted': []
        }
        
        # Phase 1: Automated Verification
        if self.config['enable_phase1']:
            print("\n[Phase 1] Running automated verification...")
            phase1_results = self.phase1.verify(issue)
            result['phase1'] = phase1_results
            
            phase1_score = phase1_results['score']
            print(f"Phase 1 Confidence: {phase1_score}%")
            
            # Post Phase 1 report
            if self.config['output']['post_phase1_immediately']:
                comment_id = self._post_phase1_report(issue, phase1_results)
                result['comments_posted'].append(('phase1', comment_id))
            
            # Check if Phase 2 is needed
            if phase1_score >= self.config['phase1_threshold']:
                print(f"Phase 1 score ({phase1_score}%) >= threshold ({self.config['phase1_threshold']}%) - skipping Phase 2")
                result['final_score'] = phase1_score
                result['recommendation'] = self.scorer.get_recommendation(phase1_score)
                
                # Post final report
                comment_id = self._post_final_report(issue, result)
                result['comments_posted'].append(('final', comment_id))
                
                return result
        
        # Phase 2: Outreach Verification
        if self.config['enable_phase2']:
            print("\n[Phase 2] Running outreach verification...")
            phase2_results = self.phase2.verify(issue, result['phase1'])
            result['phase2'] = phase2_results
            
            # Calculate final score
            final_score = self.scorer.calculate_final_score(
                result['phase1']['score'],
                phase2_results
            )
            result['final_score'] = final_score
            result['recommendation'] = self.scorer.get_recommendation(final_score)
            
            print(f"Final Confidence: {final_score}%")
            print(f"Recommendation: {result['recommendation']}")
            
            # Post final report
            comment_id = self._post_final_report(issue, result)
            result['comments_posted'].append(('final', comment_id))
        
        return result
    
    def _post_phase1_report(self, issue: Dict, phase1_results: Dict) -> int:
        """Post Phase 1 verification report to Gitea."""
        report = self._generate_phase1_report(issue, phase1_results)
        
        print("Posting Phase 1 report to Gitea...")
        comment_id = self.gitea.post_comment(issue['number'], report)
        print(f"Posted comment ID: {comment_id}")
        
        return comment_id
    
    def _post_final_report(self, issue: Dict, result: Dict) -> int:
        """Post final verification report to Gitea."""
        report = self._generate_final_report(issue, result)
        
        print("Posting final report to Gitea...")
        
        if self.config['output']['update_phase1_comment'] and len(result['comments_posted']) > 0:
            # Update existing comment
            comment_id = result['comments_posted'][0][1]
            self.gitea.update_comment(comment_id, report)
            print(f"Updated comment ID: {comment_id}")
        else:
            # Post new comment
            comment_id = self.gitea.post_comment(issue['number'], report)
            print(f"Posted comment ID: {comment_id}")
        
        return comment_id
    
    def _generate_phase1_report(self, issue: Dict, phase1_results: Dict) -> str:
        """Generate Phase 1 verification report."""
        template_path = Path("assets/templates/phase1_report.md")
        if template_path.exists():
            with open(template_path, 'r') as f:
                template = f.read()
        else:
            template = self._default_phase1_template()
        
        # Format template
        report = template.format(
            merchant_name=issue['title'],
            issue_number=issue['number'],
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            phase1_score=phase1_results['score'],
            osm_status=phase1_results['checks']['osm']['status'],
            osm_score=phase1_results['checks']['osm']['score'],
            website_status=phase1_results['checks']['website']['status'],
            website_score=phase1_results['checks']['website']['score'],
            social_status=phase1_results['checks']['social']['status'],
            social_score=phase1_results['checks']['social']['score'],
            crossref_status=phase1_results['checks']['cross_reference']['status'],
            crossref_score=phase1_results['checks']['cross_reference']['score'],
            consistency_status=phase1_results['checks']['consistency']['status'],
            consistency_score=phase1_results['checks']['consistency']['score'],
            details=phase1_results
        )
        
        return report
    
    def _generate_final_report(self, issue: Dict, result: Dict) -> str:
        """Generate final verification report."""
        template_path = Path("assets/templates/final_report.md")
        if template_path.exists():
            with open(template_path, 'r') as f:
                template = f.read()
        else:
            template = self._default_final_template()
        
        # Format template
        report = template.format(
            merchant_name=issue['title'],
            issue_number=issue['number'],
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            phase1_score=result['phase1']['score'],
            final_score=result['final_score'],
            recommendation=result['recommendation'],
            phase2_email_status=result.get('phase2', {}).get('email', {}).get('status', 'N/A'),
            phase2_dm_status=result.get('phase2', {}).get('social_dm', {}).get('status', 'N/A'),
            details=result
        )
        
        return report
    
    def _default_phase1_template(self) -> str:
        """Default Phase 1 report template."""
        return """## Phase 1 Verification Report

**Merchant**: {merchant_name}  
**Issue**: #{issue_number}  
**Generated**: {timestamp}

### Phase 1 Confidence Score: {phase1_score}%

#### Automated Checks:

| Check | Status | Score |
|-------|--------|-------|
| OSM Verification | {osm_status} | {osm_score}/30 |
| Website Check | {website_status} | {website_score}/25 |
| Social Media | {social_status} | {social_score}/20 |
| Cross-Reference | {crossref_status} | {crossref_score}/15 |
| Data Consistency | {consistency_status} | {consistency_score}/10 |

---

*This is an automated Phase 1 report. Phase 2 outreach may follow if needed.*
"""
    
    def _default_final_template(self) -> str:
        """Default final report template."""
        return """## Final Verification Report

**Merchant**: {merchant_name}  
**Issue**: #{issue_number}  
**Generated**: {timestamp}

### Final Confidence Score: {final_score}%
**Recommendation**: {recommendation}

### Phase 1 Score: {phase1_score}%

### Phase 2 Outreach:
- Email Verification: {phase2_email_status}
- Social DM: {phase2_dm_status}

---

*Verification complete. See Phase 1 report above for detailed breakdown.*
"""
    
    def _print_summary(self, results: List[Dict]):
        """Print processing summary."""
        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        
        total = len(results)
        errors = len([r for r in results if r.get('status') == 'error'])
        completed = total - errors
        
        # Count by recommendation
        recommendations = {}
        for r in results:
            if 'recommendation' in r:
                rec = r['recommendation']
                recommendations[rec] = recommendations.get(rec, 0) + 1
        
        print(f"\nTotal Issues Processed: {total}")
        print(f"Successful: {completed}")
        print(f"Errors: {errors}")
        
        if recommendations:
            print("\nRecommendations:")
            for rec, count in sorted(recommendations.items()):
                print(f"  - {rec}: {count}")
        
        print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='BTC Map Triage Bot')
    parser.add_argument('--config', '-c', default='config/config.yaml',
                        help='Path to configuration file')
    parser.add_argument('--issues', '-n', type=int, default=None,
                        help='Number of issues to process')
    
    args = parser.parse_args()
    
    try:
        orchestrator = TriageOrchestrator(args.config)
        orchestrator.run(args.issues)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    import os
    main()
