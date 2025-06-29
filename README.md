# Competition Auto-Entry System

An automated system for discovering and entering free competitions from aggregation websites.

## Features

- **Web Scraping**: Crawls competition aggregation websites to discover new competitions
- **Smart Filtering**: Only enters free competitions based on terms and conditions analysis
- **Form Detection**: Automatically identifies and fills competition entry forms
- **Personal Data Management**: Securely stores personal information for form filling
- **Entry Tracking**: Maintains a database of entered competitions with status and deadlines
- **Social Media Integration**: Handles competitions requiring social media follows/shares

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install browser drivers for Selenium:
```bash
playwright install
```

3. Copy the example configuration file and fill in your details:
```bash
cp config/config.example.json config/config.json
```

4. Run the system:
```bash
python main.py
```

## Configuration

Edit `config/config.json` with your personal information:

- Personal details (name, email, address)
- Social media login credentials
- Competition website URLs to monitor
- Entry preferences and filters

## Project Structure

```
competition-auto-entry/
├── src/
│   ├── core/
│   │   ├── scraper.py          # Web scraping functionality
│   │   ├── form_detector.py    # Form identification and filling
│   │   ├── competition.py      # Competition data models
│   │   └── tracker.py          # Entry tracking system
│   ├── utils/
│   │   ├── config.py           # Configuration management
│   │   ├── logger.py           # Logging setup
│   │   └── helpers.py          # Utility functions
│   └── integrations/
│       ├── social_media.py     # Social media integrations
│       └── aggregators.py      # Competition aggregator specific logic
├── config/
│   ├── config.example.json     # Example configuration
│   └── aggregator_sites.json   # List of competition aggregator websites
├── data/
│   └── competitions.db         # SQLite database for tracking
├── logs/                       # Log files
├── requirements.txt
└── main.py                     # Main entry point
```

## Safety Features

- **Terms & Conditions Analysis**: Automatically checks if competitions are free to enter
- **Rate Limiting**: Implements delays to avoid being blocked by websites
- **Error Handling**: Comprehensive error handling and logging
- **Data Backup**: Regular backups of competition entry data

## Legal & Ethical Considerations

This tool is designed to automate legitimate competition entries. Please ensure you:
- Only enter competitions you're genuinely interested in
- Respect website terms of service
- Don't overwhelm websites with requests
- Verify competition legitimacy before entering

## License

This project is for personal use only.
