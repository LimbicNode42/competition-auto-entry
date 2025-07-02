#!/usr/bin/env python3
"""
Simple competition form entry tester
Bypasses the authentication issues with CompetitionCloud
"""

import asyncio
import logging
import os
import sys
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv

from playwright.async_api import async_playwright, Page, Browser

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/direct_entry_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Fix Unicode issues on Windows
if sys.platform == "win32":
    import codecs
    if hasattr(sys.stdout, 'detach'):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    if hasattr(sys.stderr, 'detach'):
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

async def enter_direct_competition(url: str, headless: bool = False):
    """
    Enter a competition form directly without authentication
    """
    logger.info(f"Starting direct competition entry for URL: {url}")
    
    # Load personal info from .env
    load_dotenv()
    personal_info = {
        'first_name': os.getenv('FIRST_NAME', 'John'),
        'last_name': os.getenv('LAST_NAME', 'Doe'),
        'email': os.getenv('EMAIL', 'example@example.com'),
        'phone': os.getenv('PHONE', '+61400000000'),
        'address': os.getenv('ADDRESS_LINE1', '123 Sample St'),
        'city': os.getenv('CITY', 'Sydney'),
        'state': os.getenv('STATE', 'NSW'),
        'postal_code': os.getenv('POSTAL_CODE', '2000'),
        'country': os.getenv('COUNTRY', 'Australia'),
        'comments': 'Thank you for the opportunity to participate!',
        'terms': True  # Always accept terms
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        
        try:
            # Open competition page
            page = await context.new_page()
            logger.info(f"Opening URL: {url}")
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Take initial screenshot
            os.makedirs("screenshots", exist_ok=True)
            await page.screenshot(path=f"screenshots/direct_entry_start.png")
            
            # Detect form fields
            fields = await detect_form_fields(page)
            
            if not fields:
                logger.warning("No form fields detected on the page")
                await page.close()
                await context.close()
                await browser.close()
                return False
            
            logger.info(f"Detected {len(fields)} form fields")
            
            # Fill form fields
            filled_count = 0
            for field in fields:
                field_type = field['type']
                if field_type in personal_info:
                    value = personal_info[field_type]
                    success = await fill_field(page, field, value)
                    if success:
                        filled_count += 1
            
            logger.info(f"Filled {filled_count} fields out of {len(fields)}")
            
            # Take screenshot after filling
            await page.screenshot(path=f"screenshots/direct_entry_filled.png")
            
            # Find and click submit button
            submit_selectors = [
                'input[type="submit"]',
                'button[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Enter")',
                'button:has-text("Send")',
                'input[value="Submit"]',
                'input[value="Enter"]',
                '.submit-button',
                '#submit',
                'button.btn-primary',
                'button.primary'
            ]
            
            submit_clicked = False
            for selector in submit_selectors:
                submit_button = await page.query_selector(selector)
                if submit_button:
                    await page.screenshot(path=f"screenshots/before_submit.png")
                    await submit_button.click()
                    logger.info(f"Clicked submit button: {selector}")
                    submit_clicked = True
                    
                    # Wait for navigation
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass
                    
                    break
            
            if not submit_clicked:
                logger.warning("Could not find and click submit button")
                await page.screenshot(path=f"screenshots/no_submit_button.png")
                await page.close()
                await context.close()
                await browser.close()
                return False
            
            # Check for success indicators
            success_indicators = [
                'thank you',
                'thanks for entering',
                'entry received',
                'entry confirmed',
                'entry successful',
                'thank you for your entry',
                'success',
                'confirmation',
                'completed',
                'congratulations'
            ]
            
            # Wait a moment for any redirect
            await asyncio.sleep(2)
            
            # Take final screenshot
            await page.screenshot(path=f"screenshots/after_submit.png")
            
            # Check page content
            content = await page.content()
            content_lower = content.lower()
            
            success = False
            for indicator in success_indicators:
                if indicator in content_lower:
                    logger.info(f"Found success indicator: {indicator}")
                    success = True
                    break
            
            if success:
                logger.info("✓ Competition entry successful!")
            else:
                logger.warning("✗ Competition entry could not be confirmed")
            
            await page.close()
            await context.close()
            await browser.close()
            return success
            
        except Exception as e:
            logger.error(f"Error during competition entry: {e}")
            await context.close()
            await browser.close()
            return False

async def detect_form_fields(page: Page) -> List[Dict]:
    """Detect form fields using DOM inspection"""
    try:
        form_fields = []
        
        # Find all input elements and textareas
        inputs = await page.query_selector_all('input[type="text"], input[type="email"], input[name], textarea, input[type="checkbox"], select')
        
        for input_elem in inputs:
            try:
                # Get element properties
                name = await input_elem.get_attribute('name') or ''
                placeholder = await input_elem.get_attribute('placeholder') or ''
                input_type = await input_elem.get_attribute('type') or 'text'
                tag_name = await input_elem.evaluate('el => el.tagName.toLowerCase()')
                
                # Get element position
                box = await input_elem.bounding_box()
                if not box:
                    continue
                
                # Try to find associated label
                label_text = ''
                try:
                    # Look for label by 'for' attribute
                    input_id = await input_elem.get_attribute('id')
                    if input_id:
                        label = await page.query_selector(f'label[for="{input_id}"]')
                        if label:
                            label_text = await label.inner_text()
                    
                    # If no label found, look for nearby labels
                    if not label_text:
                        nearby_labels = await page.query_selector_all('label')
                        for label in nearby_labels:
                            label_box = await label.bounding_box()
                            if label_box:
                                # Check if label is near the input
                                if (abs(label_box['x'] - box['x']) < 150 and 
                                    abs(label_box['y'] - box['y']) < 50):
                                    label_text = await label.inner_text()
                                    break
                except Exception as e:
                    logger.debug(f"Error finding label: {e}")
                
                # Determine field type
                field_type = 'unknown'
                field_identifier = f"{name} {placeholder} {label_text}".lower()
                
                if input_type == 'checkbox':
                    field_type = 'checkbox'
                    if any(term in field_identifier for term in ['terms', 'conditions', 'agree', 'accept']):
                        field_type = 'terms'
                elif tag_name == 'select':
                    field_type = 'select'
                    # Try to determine more specific type
                    if any(keyword in field_identifier for keyword in ['state', 'province']):
                        field_type = 'state'
                    elif any(keyword in field_identifier for keyword in ['country']):
                        field_type = 'country'
                else:
                    # Classify based on name/label
                    if any(keyword in field_identifier for keyword in ['email', 'e-mail']):
                        field_type = 'email'
                    elif any(keyword in field_identifier for keyword in ['first', 'given', 'fname']):
                        field_type = 'first_name'
                    elif any(keyword in field_identifier for keyword in ['last', 'surname', 'lname']):
                        field_type = 'last_name'
                    elif 'name' in field_identifier and not any(word in field_identifier for word in ['first', 'last']):
                        field_type = 'first_name'  # Assume generic name field is first name
                    elif any(keyword in field_identifier for keyword in ['phone', 'mobile', 'tel']):
                        field_type = 'phone'
                    elif any(keyword in field_identifier for keyword in ['address', 'street']):
                        field_type = 'address'
                    elif any(keyword in field_identifier for keyword in ['city', 'town']):
                        field_type = 'city'
                    elif any(keyword in field_identifier for keyword in ['zip', 'postal', 'postcode']):
                        field_type = 'postal_code'
                    elif any(keyword in field_identifier for keyword in ['country']):
                        field_type = 'country'
                    elif any(keyword in field_identifier for keyword in ['comment', 'message']):
                        field_type = 'comments'
                
                form_fields.append({
                    'x': int(box['x']),
                    'y': int(box['y']),
                    'width': int(box['width']),
                    'height': int(box['height']),
                    'center_x': int(box['x'] + box['width'] / 2),
                    'center_y': int(box['y'] + box['height'] / 2),
                    'name': name,
                    'placeholder': placeholder,
                    'label': label_text,
                    'type': field_type,
                    'input_type': input_type,
                    'tag_name': tag_name,
                    'element': input_elem
                })
                
                logger.info(f"Detected field: {field_type} (name: {name}, label: {label_text})")
                
            except Exception as e:
                logger.warning(f"Error processing input element: {e}")
                continue
        
        return form_fields
        
    except Exception as e:
        logger.error(f"Error detecting form fields: {e}")
        return []

async def fill_field(page: Page, field: Dict, value: Any) -> bool:
    """Fill a single form field"""
    try:
        field_type = field['type']
        tag_name = field.get('tag_name', '').lower()
        input_type = field.get('input_type', '').lower()
        
        # For terms checkbox fields, always check them
        if field_type in ['terms', 'terms_checkbox']:
            value = True
        
        if input_type == 'checkbox':
            # Handle checkboxes
            current_checked = await field['element'].is_checked()
            should_check = value if isinstance(value, bool) else value.lower() in ['true', 'yes', '1']
            
            if current_checked != should_check:
                await field['element'].click()
            
            logger.info(f"Set checkbox {field_type} to: {should_check}")
            return True
            
        elif tag_name == 'select':
            # Handle dropdowns
            if isinstance(value, (list, tuple)) and len(value) > 0:
                # If value is a list, use the first item
                value = value[0]
            
            # Try to select by value, text, or index
            try:
                await field['element'].select_option(value=str(value))
            except:
                try:
                    await field['element'].select_option(label=str(value))
                except:
                    try:
                        await field['element'].select_option(index=0)  # Select first option as fallback
                    except Exception as e:
                        logger.warning(f"Failed to select option in dropdown: {e}")
                        return False
            
            logger.info(f"Selected option in {field_type} dropdown")
            return True
            
        else:
            # Standard text/email fields
            await field['element'].fill(str(value))
            logger.info(f"Filled field {field_type} with value: {value}")
            return True
                
    except Exception as e:
        logger.error(f"Failed to fill field {field_type}: {e}")
        return False

async def main():
    # Create a direct test URL from the local test form
    test_form_path = os.path.abspath("test_form.html")
    test_url = f"file://{test_form_path}"
    
    # Test with a known form
    success = await enter_direct_competition(test_url, headless=False)
    
    # Try a real competition form (uncomment to test with a real form)
    # real_url = "https://gleam.io/competitions/NZPJh-win-a-5-night-maldives-holiday-inc-flights-accommodation-1000-quicksilver-500-sun-bum"
    # success = await enter_direct_competition(real_url, headless=False)
    
    if success:
        logger.info("Test completed successfully!")
    else:
        logger.warning("Test completed with errors.")

if __name__ == "__main__":
    asyncio.run(main())
