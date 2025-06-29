#!/usr/bin/env python3
"""
Rejection Log Analyzer - View and analyze competition rejections for manual review.
"""

import sys
from pathlib import Path
import click
import json
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config import load_config
from src.utils.rejection_logger import RejectionLogger


@click.group()
def cli():
    """Competition Rejection Log Analyzer"""
    pass


@cli.command()
@click.option('--config', '-c', default='config/config.json', help='Configuration file')
def stats(config):
    """Show rejection statistics."""
    try:
        config_obj = load_config(config)
        rejection_log_path = getattr(config_obj, 'rejection_log_path', 'data/rejection_log.json')
        
        logger = RejectionLogger(rejection_log_path)
        stats_data = logger.get_rejection_stats()
        
        print("\n=== REJECTION STATISTICS ===")
        print(f"Total rejections: {stats_data.get('total_rejections', 0)}")
        print(f"Reviewed: {stats_data.get('reviewed_count', 0)} ({stats_data.get('review_percentage', 0):.1f}%)")
        print(f"With feedback: {stats_data.get('feedback_count', 0)}")
        
        print("\nRejection types:")
        for reason_type, count in stats_data.get('reason_types', {}).items():
            print(f"  {reason_type}: {count}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.option('--config', '-c', default='config/config.json', help='Configuration file')
@click.option('--limit', '-l', default=10, help='Number of entries to show')
@click.option('--all', 'show_all', is_flag=True, help='Show all rejections, not just unreviewed')
def list(config, limit, show_all):
    """List recent rejections for review."""
    try:
        config_obj = load_config(config)
        rejection_log_path = getattr(config_obj, 'rejection_log_path', 'data/rejection_log.json')
        
        logger = RejectionLogger(rejection_log_path)
        
        if show_all:
            with open(rejection_log_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
            rejections = all_data[-limit:]
        else:
            rejections = logger.get_unreviewed_rejections(limit)
        
        if not rejections:
            print("No rejections found.")
            return
        
        print(f"\n=== {'ALL' if show_all else 'UNREVIEWED'} REJECTIONS ===")
        
        for i, rejection in enumerate(rejections, 1):
            print(f"\n{i}. {rejection['title']}")
            print(f"   URL: {rejection['url']}")
            print(f"   Date: {rejection['timestamp']}")
            print(f"   Reason: {rejection['reason']}")
            print(f"   Type: {rejection['reason_type']}")
            print(f"   Source: {rejection.get('source', 'Unknown')}")
            
            if rejection.get('page_text_sample'):
                print(f"   Sample: {rejection['page_text_sample'][:100]}...")
            
            if rejection.get('reviewed'):
                print(f"   ✓ Reviewed: {rejection.get('review_timestamp', 'Unknown time')}")
                if rejection.get('feedback'):
                    print(f"   Feedback: {rejection['feedback']}")
            
        if not show_all and rejections:
            print(f"\nUse 'python review_rejections.py review --url <URL>' to mark as reviewed")
            print(f"Use 'python review_rejections.py list --all' to see all rejections")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.option('--config', '-c', default='config/config.json', help='Configuration file')
@click.option('--url', required=True, help='URL to mark as reviewed')
@click.option('--feedback', help='Feedback about the rejection (correct/incorrect/needs_improvement)')
def review(config, url, feedback):
    """Mark a rejection as reviewed with optional feedback."""
    try:
        config_obj = load_config(config)
        rejection_log_path = getattr(config_obj, 'rejection_log_path', 'data/rejection_log.json')
        
        logger = RejectionLogger(rejection_log_path)
        
        success = logger.mark_reviewed(url, feedback)
        
        if success:
            print(f"✓ Marked {url} as reviewed")
            if feedback:
                print(f"  Feedback: {feedback}")
        else:
            print(f"✗ Could not find rejection for {url}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.option('--config', '-c', default='config/config.json', help='Configuration file')
@click.option('--reason-type', help='Filter by reason type')
@click.option('--feedback', help='Filter by feedback (correct/incorrect/needs_improvement)')
def analyze(config, reason_type, feedback):
    """Analyze rejection patterns to improve detection."""
    try:
        config_obj = load_config(config)
        rejection_log_path = getattr(config_obj, 'rejection_log_path', 'data/rejection_log.json')
        
        with open(rejection_log_path, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        
        # Filter data
        filtered_data = all_data
        
        if reason_type:
            filtered_data = [r for r in filtered_data if r.get('reason_type') == reason_type]
        
        if feedback:
            filtered_data = [r for r in filtered_data if r.get('feedback') == feedback]
        
        print(f"\n=== ANALYSIS ===")
        print(f"Total matching entries: {len(filtered_data)}")
        
        if not filtered_data:
            return
        
        # Analyze patterns
        reasons = {}
        sources = {}
        
        for entry in filtered_data:
            reason = entry.get('reason', 'Unknown')
            source = entry.get('source', 'Unknown')
            
            reasons[reason] = reasons.get(reason, 0) + 1
            sources[source] = sources.get(source, 0) + 1
        
        print("\nMost common rejection reasons:")
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {count:3d}: {reason}")
        
        print("\nRejections by source:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"  {count:3d}: {source}")
        
        # Show examples of incorrect rejections
        incorrect = [r for r in filtered_data if r.get('feedback') == 'incorrect']
        if incorrect:
            print(f"\n=== INCORRECTLY REJECTED ({len(incorrect)} entries) ===")
            for entry in incorrect[:5]:  # Show first 5
                print(f"  {entry['title']}")
                print(f"    Reason: {entry['reason']}")
                print(f"    URL: {entry['url']}")
                print()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.option('--config', '-c', default='config/config.json', help='Configuration file')
def export(config):
    """Export rejections to CSV for further analysis."""
    try:
        import csv
        
        config_obj = load_config(config)
        rejection_log_path = getattr(config_obj, 'rejection_log_path', 'data/rejection_log.json')
        
        with open(rejection_log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        csv_path = rejection_log_path.replace('.json', '.csv')
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if not data:
                print("No data to export.")
                return
            
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        print(f"✓ Exported {len(data)} rejections to {csv_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


if __name__ == "__main__":
    cli()
