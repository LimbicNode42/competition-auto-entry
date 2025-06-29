<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Competition Auto-Entry System - Copilot Instructions

This is a Python project for automatically entering free competitions from aggregation websites.

## Project Context

- **Main Purpose**: Web scraping and automation for competition entry
- **Key Technologies**: Python, Selenium, BeautifulSoup, Playwright
- **Data Storage**: SQLite database for tracking entries
- **Configuration**: JSON-based configuration management

## Code Style Guidelines

- Follow PEP 8 Python style guidelines
- Use type hints for all function parameters and return values
- Implement comprehensive error handling and logging
- Use async/await for I/O operations where possible
- Write docstrings for all classes and functions

## Security Considerations

- Never hardcode credentials or personal information
- Use environment variables or secure configuration files
- Implement rate limiting to avoid overwhelming target websites
- Validate all user inputs and scraped data
- Log security-relevant events

## Web Scraping Best Practices

- Always check robots.txt before scraping
- Implement respectful delays between requests
- Use rotating user agents to avoid detection
- Handle dynamic content with Playwright/Selenium when needed
- Parse HTML carefully with BeautifulSoup for static content

## Competition Entry Logic

- Only enter competitions that are confirmed to be free
- Verify terms and conditions automatically
- Track entry status and competition deadlines
- Implement retry logic for failed entries
- Store evidence of successful entries

## Database Schema

- Competitions table: id, url, title, deadline, status, terms_accepted
- Entries table: id, competition_id, entry_date, status, confirmation_data
- Personal_data table: encrypted storage of user information

## Error Handling

- Catch and log all exceptions with appropriate detail
- Implement graceful degradation for network issues
- Retry mechanisms for transient failures
- User-friendly error messages in CLI output
