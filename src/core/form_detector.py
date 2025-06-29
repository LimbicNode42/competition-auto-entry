"""
Form detection and analysis for competition entry automation.
"""

import re
from typing import List, Optional, Dict, Any
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from .competition import CompetitionForm, FormField

logger = logging.getLogger("competition_auto_entry.form_detector")


class FormDetector:
    """Detects and analyzes forms on competition pages."""
    
    def __init__(self):
        """Initialize the form detector."""
        self.common_field_patterns = {
            'first_name': [
                'first', 'fname', 'given', 'forename', 'christian'
            ],
            'last_name': [
                'last', 'lname', 'surname', 'family', 'lastname'
            ],
            'email': [
                'email', 'e-mail', 'mail', 'email_address'
            ],
            'phone': [
                'phone', 'tel', 'mobile', 'cell', 'telephone'
            ],
            'address': [
                'address', 'street', 'addr', 'address1', 'address_line1'
            ],
            'city': [
                'city', 'town', 'locality'
            ],
            'state': [
                'state', 'province', 'region', 'county'
            ],
            'postal_code': [
                'zip', 'postal', 'postcode', 'zipcode', 'post_code'
            ],
            'country': [
                'country', 'nation'
            ],
            'date_of_birth': [
                'birth', 'dob', 'birthday', 'birthdate', 'date_of_birth'
            ]
        }
    
    def detect_form(self, soup: BeautifulSoup, page_url: str) -> Optional[CompetitionForm]:
        """
        Detect and analyze the main entry form on a page.
        
        Args:
            soup: BeautifulSoup object of the page
            page_url: URL of the page containing the form
            
        Returns:
            CompetitionForm object or None if no suitable form found
        """
        # Find all forms on the page
        forms = soup.find_all('form')
        
        if not forms:
            logger.debug("No forms found on page")
            return None
        
        # Score forms to find the most likely entry form
        best_form = None
        best_score = 0
        
        for form in forms:
            score = self._score_form(form)
            if score > best_score:
                best_score = score
                best_form = form
        
        if not best_form or best_score < 1:
            logger.debug("No suitable entry form found")
            return None
        
        return self._analyze_form(best_form, page_url)
    
    def _score_form(self, form: Tag) -> int:
        """
        Score a form to determine if it's likely an entry form.
        
        Args:
            form: BeautifulSoup form element
            
        Returns:
            Score indicating likelihood of being an entry form
        """
        score = 0
        
        # Get all text in and around the form
        form_text = form.get_text().lower()
        
        # Look for entry-related keywords
        entry_keywords = [
            'enter', 'entry', 'submit', 'competition', 'contest',
            'giveaway', 'win', 'prize', 'register', 'sign up'
        ]
        
        for keyword in entry_keywords:
            if keyword in form_text:
                score += 2
        
        # Check form fields
        inputs = form.find_all(['input', 'select', 'textarea'])
        
        # Bonus for having name/email fields
        field_names = [inp.get('name', '').lower() for inp in inputs]
        field_names.extend([inp.get('id', '').lower() for inp in inputs])
        field_names = [name for name in field_names if name]
        
        for field_name in field_names:
            if any(pattern in field_name for pattern in ['name', 'email']):
                score += 3
            if any(pattern in field_name for pattern in ['phone', 'address']):
                score += 1
        
        # Bonus for submit buttons with relevant text
        submit_buttons = form.find_all(['input', 'button'], {'type': 'submit'})
        submit_buttons.extend(form.find_all('button'))
        
        for button in submit_buttons:
            button_text = (button.get_text() or button.get('value', '')).lower()
            if any(keyword in button_text for keyword in entry_keywords):
                score += 2
        
        # Penalty for login/auth forms
        auth_keywords = ['password', 'login', 'signin', 'sign in']
        for keyword in auth_keywords:
            if keyword in form_text:
                score -= 3
        
        return max(0, score)
    
    def _analyze_form(self, form: Tag, page_url: str) -> CompetitionForm:
        """
        Analyze a form and extract field information.
        
        Args:
            form: BeautifulSoup form element
            page_url: URL of the page containing the form
            
        Returns:
            CompetitionForm object with analyzed form data
        """
        fields = []
        
        # Analyze form attributes
        form_method = form.get('method', 'POST').upper()
        form_action = form.get('action', '')
        if form_action:
            form_action = urljoin(page_url, form_action)
        
        # Find all input fields
        inputs = form.find_all(['input', 'select', 'textarea'])
        
        for inp in inputs:
            field = self._analyze_field(inp, form)
            if field:
                fields.append(field)
        
        # Find submit button
        submit_selector = self._find_submit_button_selector(form)
        
        # Find terms checkbox
        terms_selector = self._find_terms_checkbox_selector(form)
        
        # Check for CAPTCHA
        captcha_present = self._check_for_captcha(form)
        
        # Check for social media requirements
        social_media_required = self._check_social_media_requirements(form)
        
        return CompetitionForm(
            url=page_url,
            fields=fields,
            submit_button_selector=submit_selector,
            terms_checkbox_selector=terms_selector,
            captcha_present=captcha_present,
            requires_social_media=social_media_required,
            form_method=form_method,
            form_action=form_action
        )
    
    def _analyze_field(self, inp: Tag, form: Tag) -> Optional[FormField]:
        """
        Analyze a single form field.
        
        Args:
            inp: BeautifulSoup input element
            form: Parent form element
            
        Returns:
            FormField object or None if field should be ignored
        """
        field_type = inp.get('type', 'text').lower()
        field_name = inp.get('name', '')
        field_id = inp.get('id', '')
        
        # Skip certain input types
        skip_types = ['hidden', 'submit', 'button', 'reset', 'image']
        if field_type in skip_types:
            return None
        
        # Skip if no name or id
        if not field_name and not field_id:
            return None
        
        # Get field label
        label = self._find_field_label(inp, form)
        
        # Determine if field is required
        required = (
            inp.get('required') is not None or
            'required' in inp.get('class', []) or
            '*' in label
        )
        
        # Get placeholder text
        placeholder = inp.get('placeholder', '')
        
        # Get select options if applicable
        options = []
        if inp.name == 'select':
            option_elements = inp.find_all('option')
            options = [opt.get_text().strip() for opt in option_elements if opt.get_text().strip()]
        
        # Generate selectors
        css_selector = self._generate_css_selector(inp)
        xpath = self._generate_xpath(inp)
        
        return FormField(
            name=field_name or field_id,
            field_type=field_type,
            label=label,
            required=required,
            placeholder=placeholder,
            options=options,
            css_selector=css_selector,
            xpath=xpath
        )
    
    def _find_field_label(self, inp: Tag, form: Tag) -> str:
        """
        Find the label text for a form field.
        
        Args:
            inp: Input element
            form: Parent form element
            
        Returns:
            Label text
        """
        # Try explicit label element
        field_id = inp.get('id')
        if field_id:
            label_elem = form.find('label', {'for': field_id})
            if label_elem:
                return label_elem.get_text().strip()
        
        # Try parent label
        parent_label = inp.find_parent('label')
        if parent_label:
            return parent_label.get_text().strip()
        
        # Try previous sibling
        prev_sibling = inp.find_previous_sibling()
        if prev_sibling and prev_sibling.name in ['label', 'span', 'div']:
            text = prev_sibling.get_text().strip()
            if len(text) < 100:  # Reasonable label length
                return text
        
        # Try placeholder or name as fallback
        return inp.get('placeholder', inp.get('name', ''))
    
    def _generate_css_selector(self, inp: Tag) -> str:
        """
        Generate a CSS selector for an input element.
        
        Args:
            inp: Input element
            
        Returns:
            CSS selector string
        """
        selectors = []
        
        # ID selector (most specific)
        if inp.get('id'):
            selectors.append(f"#{inp.get('id')}")
        
        # Name selector
        if inp.get('name'):
            selectors.append(f"[name='{inp.get('name')}']")
        
        # Class selector
        if inp.get('class'):
            classes = ' '.join(inp.get('class'))
            selectors.append(f".{classes.replace(' ', '.')}")
        
        # Type selector
        if inp.get('type'):
            selectors.append(f"input[type='{inp.get('type')}']")
        
        return selectors[0] if selectors else inp.name
    
    def _generate_xpath(self, inp: Tag) -> str:
        """
        Generate an XPath for an input element.
        
        Args:
            inp: Input element
            
        Returns:
            XPath string
        """
        if inp.get('id'):
            return f"//*[@id='{inp.get('id')}']"
        elif inp.get('name'):
            return f"//*[@name='{inp.get('name')}']"
        else:
            return f"//{inp.name}"
    
    def _find_submit_button_selector(self, form: Tag) -> str:
        """
        Find the CSS selector for the form's submit button.
        
        Args:
            form: Form element
            
        Returns:
            CSS selector for submit button
        """
        # Look for submit input
        submit_input = form.find('input', {'type': 'submit'})
        if submit_input:
            if submit_input.get('id'):
                return f"#{submit_input.get('id')}"
            elif submit_input.get('class'):
                classes = ' '.join(submit_input.get('class'))
                return f".{classes.replace(' ', '.')}"
            else:
                return "input[type='submit']"
        
        # Look for submit button
        buttons = form.find_all('button')
        for button in buttons:
            button_type = button.get('type', 'submit').lower()
            button_text = button.get_text().lower()
            
            if (button_type == 'submit' or 
                any(keyword in button_text for keyword in ['submit', 'enter', 'send'])):
                if button.get('id'):
                    return f"#{button.get('id')}"
                elif button.get('class'):
                    classes = ' '.join(button.get('class'))
                    return f".{classes.replace(' ', '.')}"
                else:
                    return "button[type='submit']"
        
        return "input[type='submit'], button[type='submit']"
    
    def _find_terms_checkbox_selector(self, form: Tag) -> str:
        """
        Find the CSS selector for terms and conditions checkbox.
        
        Args:
            form: Form element
            
        Returns:
            CSS selector for terms checkbox or empty string
        """
        checkboxes = form.find_all('input', {'type': 'checkbox'})
        
        for checkbox in checkboxes:
            # Check associated label text
            label_text = self._find_field_label(checkbox, form).lower()
            
            if any(keyword in label_text for keyword in [
                'terms', 'condition', 'agree', 'accept', 'privacy', 'policy'
            ]):
                if checkbox.get('id'):
                    return f"#{checkbox.get('id')}"
                elif checkbox.get('name'):
                    return f"[name='{checkbox.get('name')}']"
                elif checkbox.get('class'):
                    classes = ' '.join(checkbox.get('class'))
                    return f".{classes.replace(' ', '.')}"
        
        return ""
    
    def _check_for_captcha(self, form: Tag) -> bool:
        """
        Check if the form contains a CAPTCHA.
        
        Args:
            form: Form element
            
        Returns:
            True if CAPTCHA is present, False otherwise
        """
        form_html = str(form).lower()
        captcha_indicators = [
            'captcha', 'recaptcha', 'g-recaptcha', 'hcaptcha',
            'cf-turnstile', 'security check'
        ]
        
        return any(indicator in form_html for indicator in captcha_indicators)
    
    def _check_social_media_requirements(self, form: Tag) -> List[str]:
        """
        Check if the form requires social media actions.
        
        Args:
            form: Form element
            
        Returns:
            List of required social media platforms
        """
        form_text = form.get_text().lower()
        required_platforms = []
        
        social_platforms = {
            'instagram': ['instagram', 'insta'],
            'twitter': ['twitter', 'tweet'],
            'facebook': ['facebook', 'fb'],
            'youtube': ['youtube', 'subscribe'],
            'tiktok': ['tiktok'],
            'bluesky': ['bluesky']
        }
        
        for platform, keywords in social_platforms.items():
            if any(keyword in form_text for keyword in keywords):
                if any(action in form_text for action in ['follow', 'like', 'share', 'subscribe']):
                    required_platforms.append(platform)
        
        return required_platforms
