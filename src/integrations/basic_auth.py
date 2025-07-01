"""
Basic username/password authentication handler for aggregator site logins.
"""

import json
import os
import time
from typing import Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from ..utils.logger import setup_logging

logger = setup_logging()


class BasicAuthHandler:
    """
    Handles basic email/password authentication for aggregator websites.
    """
    
    def __init__(self, driver: webdriver.Chrome, config):
        """
        Initialize the Basic Auth handler.
        
        Args:
            driver: Selenium WebDriver instance
            config: Application configuration
        """
        self.driver = driver
        self.config = config
        
        # Load credentials from environment variables
        self.competition_cloud_username = os.getenv('COMPETITION_CLOUD_UNAME', '').strip('"')
        self.competition_cloud_password = os.getenv('COMPETITION_CLOUD_PWORD', '').strip('"')
        
        # Session storage paths
        self.session_dir = Path("data/sessions")
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def get_session_file(self, domain: str) -> Path:
        """Get session file path for a domain."""
        safe_domain = domain.replace('.', '_').replace('/', '_')
        return self.session_dir / f"{safe_domain}_basic_session.json"
    
    def save_session_cookies(self, domain: str) -> None:
        """Save current session cookies for a domain."""
        try:
            cookies = self.driver.get_cookies()
            session_file = self.get_session_file(domain)
            
            with open(session_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            
            logger.debug(f"Saved session cookies for {domain}")
            
        except Exception as e:
            logger.error(f"Error saving session cookies for {domain}: {e}")
    
    def load_session_cookies(self, domain: str) -> bool:
        """Load saved session cookies for a domain."""
        try:
            session_file = self.get_session_file(domain)
            
            if not session_file.exists():
                logger.debug(f"No saved session found for {domain}")
                return False
            
            with open(session_file, 'r') as f:
                cookies = json.load(f)
            
            # Add each cookie to the driver
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"Could not add cookie {cookie.get('name', '')}: {e}")
            
            logger.debug(f"Loaded {len(cookies)} session cookies for {domain}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading session cookies for {domain}: {e}")
            return False
    
    def check_if_logged_in(self, site_domain: str) -> bool:
        """
        Check if user is already logged in to the site.
        
        Args:
            site_domain: Domain of the site to check
            
        Returns:
            True if logged in, False otherwise
        """
        try:
            # Common indicators of being logged in
            login_indicators = [
                # User profile/account elements
                '[data-testid*="user"]', '[data-testid*="profile"]',
                '.user-menu', '.profile-menu', '.account-menu',
                'a[href*="logout"]', 'a[href*="profile"]', 'a[href*="account"]',
                # Text-based indicators
                '//*[contains(text(), "Logout")]',
                '//*[contains(text(), "Log Out")]',
                '//*[contains(text(), "My Account")]',
                '//*[contains(text(), "Profile")]',
                '//*[contains(text(), "Dashboard")]',
                # Site-specific indicators
                '.logged-in', '.authenticated', '.user-authenticated'
            ]
            
            for indicator in login_indicators:
                try:
                    if indicator.startswith('//'):
                        # XPath selector
                        element = self.driver.find_element(By.XPATH, indicator)
                    else:
                        # CSS selector
                        element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                    
                    if element.is_displayed():
                        logger.debug(f"Found login indicator: {indicator}")
                        return True
                        
                except:
                    continue
            
            # Check if we're redirected away from login page
            current_url = self.driver.current_url.lower()
            if 'login' not in current_url and 'signin' not in current_url and 'auth' not in current_url:
                logger.debug(f"Not on login page, assuming logged in")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking login status for {site_domain}: {e}")
            return False
    
    def login_to_competition_cloud(self, site_url: str) -> bool:
        """
        Login to Competition Cloud using email/password.
        
        Args:
            site_url: URL of the site to login to
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            if not self.competition_cloud_username or not self.competition_cloud_password:
                logger.error("Competition Cloud credentials not found in environment variables")
                return False
            
            logger.info("Attempting to login to Competition Cloud")
            
            # Navigate to the main site first
            self.driver.get(site_url)
            time.sleep(3)
            
            # Try to load saved session first
            if self.load_session_cookies('competitioncloud.com.au'):
                self.driver.refresh()
                time.sleep(3)
                
                if self.check_if_logged_in('competitioncloud.com.au'):
                    logger.info("Successfully restored session for Competition Cloud")
                    return True
            
            # Navigate to login page
            login_url = "https://competitioncloud.com.au/Identity/Account/Login"
            logger.debug(f"Navigating to login page: {login_url}")
            self.driver.get(login_url)
            time.sleep(3)
            
            # Find email field
            email_selectors = [
                'input[name="Email"]',
                'input[type="email"]',
                'input[id*="email"]',
                'input[name*="email"]',
                '#Email'
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if email_field.is_displayed():
                        logger.debug(f"Found email field: {selector}")
                        break
                except:
                    continue
            
            if not email_field:
                logger.error("Could not find email field on login page")
                return False
            
            # Find password field
            password_selectors = [
                'input[name="Password"]',
                'input[type="password"]',
                'input[id*="password"]',
                'input[name*="password"]',
                '#Password'
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if password_field.is_displayed():
                        logger.debug(f"Found password field: {selector}")
                        break
                except:
                    continue
            
            if not password_field:
                logger.error("Could not find password field on login page")
                return False
            
            # Fill in credentials
            logger.debug("Filling in credentials")
            email_field.clear()
            email_field.send_keys(self.competition_cloud_username)
            time.sleep(1)
            
            password_field.clear()
            password_field.send_keys(self.competition_cloud_password)
            time.sleep(1)
            
            # Find and click submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button[class*="btn"]',
                '.login-button',
                '.submit-button',
                '//button[contains(text(), "Login")]',
                '//button[contains(text(), "Sign In")]',
                '//input[@value="Login"]'
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    if selector.startswith('//'):
                        submit_button = self.driver.find_element(By.XPATH, selector)
                    else:
                        submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if submit_button.is_displayed() and submit_button.is_enabled():
                        logger.debug(f"Found submit button: {selector}")
                        break
                except:
                    continue
            
            if not submit_button:
                logger.error("Could not find submit button on login page")
                return False
            
            # Submit the form
            logger.debug("Submitting login form")
            submit_button.click()
            
            # Wait for redirect/response
            time.sleep(5)
            
            # Check if login was successful
            if self.check_if_logged_in('competitioncloud.com.au'):
                logger.info("Successfully logged into Competition Cloud")
                self.save_session_cookies('competitioncloud.com.au')
                return True
            else:
                logger.error("Login appears to have failed - no login indicators found")
                return False
                
        except Exception as e:
            logger.error(f"Error during Competition Cloud login: {e}")
            return False
    
    def login_to_site(self, site_url: str, site_domain: str) -> bool:
        """
        Attempt to login to a site using basic authentication.
        
        Args:
            site_url: URL of the site to login to
            site_domain: Domain of the site
            
        Returns:
            True if login successful, False otherwise
        """
        if 'competitioncloud.com.au' in site_domain:
            return self.login_to_competition_cloud(site_url)
        else:
            logger.warning(f"No basic auth handler configured for {site_domain}")
            return False
