"""
Utility helper functions for the competition auto-entry system.
"""

import re
import time
import random
import hashlib
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normalize and resolve relative URLs.
    
    Args:
        url: URL to normalize
        base_url: Base URL for resolving relative URLs
        
    Returns:
        Normalized absolute URL
    """
    if base_url and not is_valid_url(url):
        url = urljoin(base_url, url)
    
    # Remove fragments and normalize
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: URL to extract domain from
        
    Returns:
        Domain name
    """
    return urlparse(url).netloc.lower()


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove non-printable characters
    text = ''.join(char for char in text if char.isprintable() or char.isspace())
    
    return text


def extract_text_from_element(element) -> str:
    """
    Extract clean text from BeautifulSoup element.
    
    Args:
        element: BeautifulSoup element
        
    Returns:
        Cleaned text content
    """
    if not element:
        return ""
    
    return clean_text(element.get_text())


def is_free_competition(text: str, terms_text: str = "") -> bool:
    """
    Determine if a competition is free to enter based on text analysis.
    
    Args:
        text: Competition description text
        terms_text: Terms and conditions text
        
    Returns:
        True if competition appears to be free, False otherwise
    """
    combined_text = f"{text} {terms_text}".lower()
    
    # Keywords that indicate paid entry
    paid_keywords = [
        'purchase', 'buy', 'payment', 'fee', 'cost', 'price',
        'subscription', 'premium', 'paid', '$', '£', '€',
        'credit card', 'billing', 'charge'
    ]
    
    # Keywords that indicate free entry
    free_keywords = [
        'free', 'no purchase', 'no fee', 'no cost',
        'free to enter', 'free entry', 'no charge'
    ]
    
    # Check for paid indicators
    for keyword in paid_keywords:
        if keyword in combined_text:
            # Check if it's in context of "no purchase necessary" etc.
            context = combined_text[max(0, combined_text.find(keyword) - 50):
                                  combined_text.find(keyword) + 50]
            if not any(free_word in context for free_word in ['no ', 'free', 'without']):
                return False
    
    # Check for free indicators
    free_score = sum(1 for keyword in free_keywords if keyword in combined_text)
    
    return free_score > 0


def generate_delay(min_delay: float = 1.0, max_delay: float = 3.0) -> float:
    """
    Generate a random delay for rate limiting.
    
    Args:
        min_delay: Minimum delay in seconds
        max_delay: Maximum delay in seconds
        
    Returns:
        Random delay in seconds
    """
    return random.uniform(min_delay, max_delay)


def hash_text(text: str) -> str:
    """
    Generate a hash of text for deduplication.
    
    Args:
        text: Text to hash
        
    Returns:
        SHA-256 hash of the text
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def parse_deadline(date_str: str) -> Optional[datetime]:
    """
    Parse various date formats to extract competition deadline.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not date_str:
        return None
    
    # Common date formats
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%B %d, %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%d %b %Y"
    ]
    
    # Clean the date string
    date_str = clean_text(date_str)
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def is_competition_expired(deadline: Optional[datetime]) -> bool:
    """
    Check if competition deadline has passed.
    
    Args:
        deadline: Competition deadline
        
    Returns:
        True if expired, False otherwise
    """
    if not deadline:
        return False
    
    return datetime.now() > deadline


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_competition_summary(competition: Dict[str, Any]) -> str:
    """
    Format competition data for display.
    
    Args:
        competition: Competition data dictionary
        
    Returns:
        Formatted summary string
    """
    title = competition.get('title', 'Unknown')
    url = competition.get('url', 'Unknown')
    deadline = competition.get('deadline', 'Unknown')
    source = competition.get('source', 'Unknown')
    
    return f"""
Competition: {title}
URL: {url}
Deadline: {deadline}
Source: {source}
""".strip()
