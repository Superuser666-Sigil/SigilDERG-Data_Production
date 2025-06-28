#!/usr/bin/env python3
"""
Data Accuracy Verification Script

This script verifies the factual accuracy of our Rust crate data by cross-referencing
with online sources like crates.io and GitHub.
"""

import json
import requests
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataAccuracyVerifier:
    def __init__(self):
        # User-Agent and contact info for API compliance
        self.user_agent = (
            "SigilDERG-Data-Production (Superuser666-Sigil; miragemodularframework@gmail.com; "
            "https://github.com/Superuser666-Sigil/SigilDERG-Data_Production)"
        )
        self.crates_io_base = "https://crates.io/api/v1"
        self.github_api_base = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent
        })
        
    def get_crate_info_from_crates_io(self, crate_name: str) -> Optional[Dict[str, Any]]:
        """Fetch crate information from crates.io API, with rate limit handling."""
        url = f"{self.crates_io_base}/crates/{crate_name}"
        retries = 0
        while retries < 5:
            try:
                response = self.session.get(url)
                if response.status_code == 429:
                    # Too Many Requests: exponential backoff
                    wait = 2 ** retries
                    logger.warning(f"Rate limited by crates.io, sleeping {wait}s...")
                    time.sleep(wait)
                    retries += 1
                    continue
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.warning(f"Failed to fetch {crate_name} from crates.io: {e}")
                return None
        logger.error(f"Exceeded retry limit for {crate_name} on crates.io API.")
        return None
    
    def get_github_repo_info(self, repo_url: str) -> Optional[Dict[str, Any]]:
        """Fetch GitHub repository information, with rate limit handling."""
        try:
            if "github.com" in repo_url:
                parts = repo_url.split("github.com/")[-1].split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                    url = f"{self.github_api_base}/repos/{owner}/{repo}"
                    retries = 0
                    while retries < 5:
                        response = self.session.get(url)
                        if response.status_code == 429:
                            wait = 2 ** retries
                            logger.warning(f"Rate limited by GitHub, sleeping {wait}s...")
                            time.sleep(wait)
                            retries += 1
                            continue
                        response.raise_for_status()
                        return response.json()
        except (requests.RequestException, IndexError) as e:
            logger.warning(f"Failed to fetch GitHub info for {repo_url}: {e}")
        return None
    
    def verify_crate_data(self, crate_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a single crate's data against online sources"""
        crate_name = crate_data.get('name')
        if not crate_name:
            return {'name': 'unknown', 'verified': False, 'errors': ['No crate name found']}
        
        logger.info(f"Verifying {crate_name}...")
        
        verification_result = {
            'name': crate_name,
            'verified': True,
            'discrepancies': [],
            'warnings': [],
            'verified_fields': []
        }
        
        # Get data from crates.io
        crates_io_data = self.get_crate_info_from_crates_io(crate_name)
        
        if crates_io_data:
            crate_info = crates_io_data.get('crate', {})
            
            # Verify downloads
            our_downloads = crate_data.get('downloads', 0)
            their_downloads = crate_info.get('downloads', 0)
            if our_downloads != their_downloads:
                verification_result['discrepancies'].append({
                    'field': 'downloads',
                    'our_value': our_downloads,
                    'their_value': their_downloads,
                    'difference': abs(our_downloads - their_downloads)
                })
            else:
                verification_result['verified_fields'].append('downloads')
            
            # Verify description
            our_desc = crate_data.get('description', '').strip()
            their_desc = crate_info.get('description', '').strip()
            if our_desc and their_desc and our_desc != their_desc:
                verification_result['warnings'].append({
                    'field': 'description',
                    'note': 'Descriptions differ but both may be valid'
                })
            elif our_desc:
                verification_result['verified_fields'].append('description')
            
            # Verify repository
            our_repo = crate_data.get('repository', '')
            their_repo = crate_info.get('repository', '')
            if our_repo and their_repo and our_repo != their_repo:
                verification_result['discrepancies'].append({
                    'field': 'repository',
                    'our_value': our_repo,
                    'their_value': their_repo
                })
            elif our_repo:
                verification_result['verified_fields'].append('repository')
            
            # Verify categories
            our_categories = set(crate_data.get('categories', []))
            # Handle different possible structures for categories in crates.io API
            their_categories = set()
            categories_data = crate_info.get('categories', [])
            for cat in categories_data:
                if isinstance(cat, dict):
                    their_categories.add(cat.get('category', ''))
                elif isinstance(cat, str):
                    their_categories.add(cat)
            
            if our_categories and their_categories and our_categories != their_categories:
                verification_result['warnings'].append({
                    'field': 'categories',
                    'our_value': list(our_categories),
                    'their_value': list(their_categories)
                })
            elif our_categories:
                verification_result['verified_fields'].append('categories')
        
        # Verify GitHub stars if we have a repository
        repo_url = crate_data.get('repository', '')
        if repo_url and 'github.com' in repo_url:
            github_data = self.get_github_repo_info(repo_url)
            if github_data:
                our_stars = crate_data.get('github_stars', 0)
                their_stars = github_data.get('stargazers_count', 0)
                if our_stars != their_stars:
                    verification_result['discrepancies'].append({
                        'field': 'github_stars',
                        'our_value': our_stars,
                        'their_value': their_stars,
                        'difference': abs(our_stars - their_stars)
                    })
                else:
                    verification_result['verified_fields'].append('github_stars')
        
        # Check if we have any major discrepancies
        if verification_result['discrepancies']:
            verification_result['verified'] = False
        
        return verification_result
    
    def verify_dataset(self, data_file_path: str, sample_size: int = 50) -> Dict[str, Any]:
        """Verify a sample of crates from the dataset"""
        logger.info(f"Loading data from {data_file_path}")
        
        crates = []
        with open(data_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    crate_data = json.loads(line.strip())
                    crates.append(crate_data)
                except json.JSONDecodeError:
                    continue
        
        logger.info(f"Loaded {len(crates)} crates")
        
        # Take a sample for verification
        import random
        random.seed(42)  # For reproducible results
        sample_crates = random.sample(crates, min(sample_size, len(crates)))
        
        logger.info(f"Verifying {len(sample_crates)} crates...")
        
        verification_results = []
        for i, crate_data in enumerate(sample_crates, 1):
            logger.info(f"Progress: {i}/{len(sample_crates)}")
            result = self.verify_crate_data(crate_data)
            verification_results.append(result)
            
            # Rate limiting
            time.sleep(0.1)
        
        # Compile summary
        summary = {
            'total_verified': len(verification_results),
            'successfully_verified': sum(1 for r in verification_results if r['verified']),
            'failed_verifications': sum(1 for r in verification_results if not r['verified']),
            'total_discrepancies': sum(len(r['discrepancies']) for r in verification_results),
            'total_warnings': sum(len(r['warnings']) for r in verification_results),
            'most_common_discrepancies': self._analyze_discrepancies(verification_results),
            'verification_results': verification_results
        }
        
        return summary
    
    def _analyze_discrepancies(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze the most common types of discrepancies"""
        discrepancy_counts = {}
        for result in results:
            for discrepancy in result.get('discrepancies', []):
                field = discrepancy['field']
                discrepancy_counts[field] = discrepancy_counts.get(field, 0) + 1
        return dict(sorted(discrepancy_counts.items(), key=lambda x: x[1], reverse=True))

def main():
    verifier = DataAccuracyVerifier()
    
    # Find the most recent data file
    output_dir = Path("output")
    if not output_dir.exists():
        logger.error("Output directory not found")
        return
    
    data_files = list(output_dir.glob("**/enriched_crate_metadata_*.jsonl"))
    if not data_files:
        logger.error("No data files found")
        return
    
    # Use the most recent file
    latest_file = max(data_files, key=lambda f: f.stat().st_mtime)
    logger.info(f"Using data file: {latest_file}")
    
    # Verify the data
    summary = verifier.verify_dataset(str(latest_file), sample_size=20)
    
    # Print results
    print("\n" + "="*60)
    print("DATA ACCURACY VERIFICATION RESULTS")
    print("="*60)
    print(f"Total crates verified: {summary['total_verified']}")
    print(f"Successfully verified: {summary['successfully_verified']}")
    print(f"Failed verifications: {summary['failed_verifications']}")
    print(f"Total discrepancies: {summary['total_discrepancies']}")
    print(f"Total warnings: {summary['total_warnings']}")
    
    if summary['most_common_discrepancies']:
        print("\nMost common discrepancies:")
        for field, count in summary['most_common_discrepancies'].items():
            print(f"  {field}: {count}")
    
    # Show specific examples of discrepancies
    print("\nSpecific discrepancies found:")
    for result in summary['verification_results']:
        if result['discrepancies']:
            print(f"\n{result['name']}:")
            for disc in result['discrepancies']:
                print(f"  {disc['field']}: {disc['our_value']} vs {disc['their_value']}")
    
    # Save detailed results
    output_file = f"verification_results_{int(time.time())}.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main() 