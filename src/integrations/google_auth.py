"""
Google OAuth authentication handler for aggregator site logins.
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


class GoogleAuthHandler:
    """
    Handles Google OAuth authentication for aggregator websites.
    """
    
    def __init__(self, config, driver: webdriver.Chrome):
        """
        Initialize the Google Auth handler.
        
        Args:
            config: Application configuration
            driver: Selenium WebDriver instance
        """
        self.config = config
        self.driver = driver
        self.google_email = getattr(config, 'google_auth', {}).get('email', '')
        self.auto_login = getattr(config, 'google_auth', {}).get('auto_login', True)
        self.save_session = getattr(config, 'google_auth', {}).get('save_session', True)
        
        # Session storage paths
        self.session_dir = Path("data/sessions")
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def get_session_file(self, domain: str) -> Path:
        """Get session file path for a domain."""
        safe_domain = domain.replace('.', '_').replace('/', '_')
        return self.session_dir / f"{safe_domain}_session.json"
    
    def save_session_cookies(self, domain: str) -> None:
        """Save current session cookies for a domain."""
        if not self.save_session:
            return
        
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
        if not self.save_session:
            return False
        
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
                '//*[contains(text(), "My Account")]',
                '//*[contains(text(), "Profile")]',
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
            
            # Check for Google account email in page source
            if self.google_email and self.google_email in self.driver.page_source:
                logger.debug(f"Found Google email {self.google_email} in page source")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking login status for {site_domain}: {e}")
            return False
    
    def login_to_site(self, site_url: str, site_domain: str) -> bool:
        """
        Attempt to login to a site using Google OAuth.
        
        Args:
            site_url: URL of the site to login to
            site_domain: Domain of the site
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info(f"Attempting to login to {site_domain}")
            
            # Navigate to the site
            self.driver.get(site_url)
            time.sleep(3)
            
            # Try to load saved session first
            if self.load_session_cookies(site_domain):
                self.driver.refresh()
                time.sleep(3)
                
                if self.check_if_logged_in(site_domain):
                    logger.info(f"Successfully restored session for {site_domain}")
                    return True
            
            # Look for Google login button
            google_login_selectors = [
                # Common Google login button patterns
                'button[class*="google"]', 'a[class*="google"]',
                'button[class*="Google"]', 'a[class*="Google"]',
                '[data-provider="google"]', '[data-auth="google"]',
                'button[title*="Google"]', 'a[title*="Google"]',
                # Text-based selectors
                '//button[contains(text(), "Google")]',
                '//a[contains(text(), "Google")]',
                '//button[contains(text(), "Sign in with Google")]',
                '//a[contains(text(), "Sign in with Google")]',
                # Generic login buttons that might lead to Google
                '.login-button', '.signin-button', '.auth-button',
                'button[type="submit"]', 'input[type="submit"][value*="Login"]'
            ]
            
            google_button = None
            for selector in google_login_selectors:
                try:
                    if selector.startswith('//'):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            # Check if this looks like a Google login button
                            element_text = element.text.lower()
                            element_html = element.get_attribute('outerHTML').lower()
                            
                            if any(term in element_text or term in element_html for term in [
                                'google', 'sign in with google', 'login with google'
                            ]):
                                google_button = element
                                logger.debug(f"Found Google login button: {selector}")
                                break
                    
                    if google_button:
                        break
                        
                except Exception:
                    continue
            
            if not google_button:
                # Try to find general login/signin links first
                login_selectors = [
                    'a[href*="login"]', 'a[href*="signin"]', 'a[href*="auth"]',
                    '//a[contains(text(), "Login")]', '//a[contains(text(), "Sign In")]',
                    '//a[contains(text(), "Log In")]', '.login-link', '.signin-link'
                ]
                
                for selector in login_selectors:
                    try:
                        if selector.startswith('//'):
                            element = self.driver.find_element(By.XPATH, selector)
                        else:
                            element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if element.is_displayed():
                            logger.debug(f"Clicking general login link: {selector}")
                            element.click()
                            time.sleep(3)
                            
                            # Now try to find Google login on the login page
                            for google_selector in google_login_selectors[:5]:  # Try first 5
                                try:
                                    if google_selector.startswith('//'):
                                        google_button = self.driver.find_element(By.XPATH, google_selector)
                                    else:
                                        google_button = self.driver.find_element(By.CSS_SELECTOR, google_selector)
                                    
                                    if google_button.is_displayed():
                                        logger.debug(f"Found Google login after clicking general login")
                                        break
                                except:
                                    continue
                            
                            if google_button:
                                break
                                
                    except Exception:
                        continue
            
            if not google_button:
                logger.warning(f"Could not find Google login button on {site_domain}")
                return False
            
            # Click the Google login button
            logger.debug("Clicking Google login button")
            original_window = self.driver.current_window_handle
            google_button.click()
            
            # Wait for potential popup or redirect
            time.sleep(3)
            
            # Check if a popup window opened
            all_windows = self.driver.window_handles
            if len(all_windows) > 1:
                # Switch to the popup window
                for window in all_windows:
                    if window != original_window:
                        self.driver.switch_to.window(window)
                        break
            
            # Handle Google OAuth flow
            return self._handle_google_oauth(site_domain, original_window)
            
        except Exception as e:
            logger.error(f"Error during login to {site_domain}: {e}")
            return False
    
    def _handle_google_oauth(self, site_domain: str, original_window: str) -> bool:
        """
        Handle the Google OAuth authentication flow.
        
        Args:
            site_domain: Domain of the site being logged into
            original_window: Handle of the original window
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Wait for Google login page to load
            WebDriverWait(self.driver, 10).until(
                lambda d: "accounts.google.com" in d.current_url or 
                         any(text in d.page_source.lower() for text in ["sign in", "email", "google"])
            )
            
            # If we have the email configured and auto_login is enabled
            if self.google_email and self.auto_login:
                logger.info(f"Attempting automatic Google login with {self.google_email}")
                
                # Try to find and fill email field
                email_selectors = [
                    'input[type="email"]', 'input[name="email"]', 
                    'input[id="email"]', 'input[id="identifierId"]',
                    'input[autocomplete="username"]'
                ]
                
                email_field = None
                for selector in email_selectors:
                    try:
                        email_field = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        break
                    except TimeoutException:
                        continue
                
                if email_field:
                    email_field.clear()
                    email_field.send_keys(self.google_email)
                    
                    # Click Next/Continue button
                    next_selectors = [
                        'button[type="submit"]', 'input[type="submit"]',
                        'button[jsname="LgbsSe"]', '#identifierNext',
                        '//button[contains(text(), "Next")]',
                        '//input[contains(@value, "Next")]'
                    ]
                    
                    for selector in next_selectors:
                        try:
                            if selector.startswith('//'):
                                next_button = self.driver.find_element(By.XPATH, selector)
                            else:
                                next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            
                            if next_button.is_displayed() and next_button.is_enabled():
                                next_button.click()
                                break
                        except:
                            continue
                    
                    logger.info("Email entered, waiting for user to complete authentication...")
                else:
                    logger.info("Could not find email field, waiting for manual authentication...")
            else:
                logger.info("Waiting for manual Google authentication...")
            
            # Wait for authentication to complete (user will handle password/2FA manually)
            # We'll wait for either:
            # 1. Return to original site (successful auth)
            # 2. Popup closes
            # 3. Timeout
            
            max_wait_time = 120  # 2 minutes for user to complete auth
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                current_url = self.driver.current_url
                
                # Check if we're back on the original site
                if site_domain in current_url:
                    logger.info("Successfully returned to original site")
                    self.save_session_cookies(site_domain)
                    return True
                
                # Check if popup closed (for popup-based auth)
                if len(self.driver.window_handles) == 1:
                    # Popup closed, switch back to original window
                    self.driver.switch_to.window(original_window)
                    time.sleep(3)
                    
                    if self.check_if_logged_in(site_domain):
                        logger.info("Authentication successful (popup closed)")
                        self.save_session_cookies(site_domain)
                        return True
                
                time.sleep(2)
            
            logger.warning("Authentication timeout - user may need to complete manually")
            
            # Switch back to original window if we're still in popup
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(original_window)
            
            # Final check if logged in
            if self.check_if_logged_in(site_domain):
                logger.info("Authentication appears successful")
                self.save_session_cookies(site_domain)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling Google OAuth for {site_domain}: {e}")
            
            # Try to switch back to original window
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(original_window)
            except:
                pass
            
            return False
