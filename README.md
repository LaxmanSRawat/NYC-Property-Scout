# Zillow NYC Scraper

A Python web scraper for extracting rental and for-sale property listings from Zillow for New York City.

## Features

- 🔄 **Anti-detection**: User-agent rotation, random delays
- 🏠 **Dual listing types**: Rent and sale in a single run
- 🏢 **Multi-unit support**: Extracts individual units from apartment buildings
- 📊 **Comprehensive data**: Address, price, beds, baths, sqft, GPS coordinates
- 📄 **CSV/JSON export**: Configurable output format

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Scrape rentals (2 pages)
python zillow_scraper.py --type rent --pages 2

# Scrape for-sale listings (3 pages)
python zillow_scraper.py --type sale --pages 3

# Scrape both (5 pages each, JSON output)
python zillow_scraper.py --type both --pages 5 --format json

# Custom delay range (slower to avoid detection)
python zillow_scraper.py --type rent --pages 10 --delay-min 5 --delay-max 10
```

## Output Fields

| Field | Description |
|-------|-------------|
| `address` | Full street address |
| `building_name` | Building/complex name |
| `price` | Rent or sale price |
| `beds` | Number of bedrooms |
| `baths` | Number of bathrooms |
| `sqft` | Square footage |
| `property_type` | APARTMENT, HOUSE, MULTI_UNIT, etc. |
| `latitude`, `longitude` | GPS coordinates |
| `url` | Direct link to listing |

## Disclaimer

⚠️ Web scraping Zillow may violate their Terms of Service. Use responsibly for personal/educational purposes only.
