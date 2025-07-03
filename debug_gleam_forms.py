#!/usr/bin/env python3
"""
Debug Gleam.io form structure to understand field classification issues
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_gleam_forms():
    """Debug Gleam.io form fields to understand classification issues"""
    
    # Direct Gleam.io URL from our test
    gleam_url = "https://gleam.io/zYPeK/win-your-dream-pergola-for-free"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to: {gleam_url}")
            await page.goto(gleam_url, timeout=30000)
            await page.wait_for_load_state('domcontentloaded')
            
            title = await page.title()
            logger.info(f"Page title: {title}")
            
            # Analyze all forms
            forms = await page.query_selector_all('form')
            logger.info(f"Found {len(forms)} forms")
            
            for i, form in enumerate(forms):
                logger.info(f"\n--- Form {i+1} ---")
                
                # Get form attributes
                action = await form.get_attribute('action')
                method = await form.get_attribute('method')
                form_id = await form.get_attribute('id')
                form_class = await form.get_attribute('class')
                
                logger.info(f"Form attributes: action={action}, method={method}, id={form_id}, class={form_class}")
                
                # Get all inputs in this form
                inputs = await form.query_selector_all('input, textarea, select')
                logger.info(f"Form {i+1} has {len(inputs)} input fields:")
                
                for j, input_elem in enumerate(inputs):
                    try:
                        visible = await input_elem.is_visible()
                        name = await input_elem.get_attribute('name') or ''
                        placeholder = await input_elem.get_attribute('placeholder') or ''
                        input_type = await input_elem.get_attribute('type') or 'text'
                        input_id = await input_elem.get_attribute('id') or ''
                        input_class = await input_elem.get_attribute('class') or ''
                        value = await input_elem.get_attribute('value') or ''
                        required = await input_elem.get_attribute('required')
                        
                        logger.info(f"  Input {j+1}: visible={visible}, type={input_type}, name='{name}', placeholder='{placeholder}'")
                        logger.info(f"    id='{input_id}', class='{input_class}', value='{value}', required={required}")
                        
                        # Check if it's a typical entry field
                        field_text = f"{name} {placeholder} {input_id} {input_class}".lower()
                        
                        if any(keyword in field_text for keyword in ['email', 'mail']):
                            logger.info(f"    -> Likely EMAIL field")
                        elif any(keyword in field_text for keyword in ['name', 'first', 'last']):
                            logger.info(f"    -> Likely NAME field")
                        elif any(keyword in field_text for keyword in ['phone', 'mobile', 'tel']):
                            logger.info(f"    -> Likely PHONE field")
                        elif input_type == 'checkbox':
                            logger.info(f"    -> CHECKBOX field")
                        elif input_type == 'submit' or input_type == 'button':
                            logger.info(f"    -> SUBMIT/BUTTON field")
                        else:
                            logger.info(f"    -> UNKNOWN field type")
                            
                    except Exception as e:
                        logger.error(f"Error analyzing input {j}: {e}")
            
            # Look for visible input fields across the whole page
            all_visible_inputs = await page.query_selector_all('input:visible, textarea:visible, select:visible')
            logger.info(f"\nTotal visible inputs on page: {len(all_visible_inputs)}")
            
            # Take a screenshot
            await page.screenshot(path='screenshots/gleam_form_debug.png')
            logger.info("Screenshot saved: screenshots/gleam_form_debug.png")
            
        except Exception as e:
            logger.error(f"Error: {e}")
        
        input("Press Enter to continue...")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(debug_gleam_forms())
