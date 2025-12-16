"""Immobiliare.it scraper with all filters"""

from urllib.parse import urlencode
from playwright.async_api import async_playwright, Page
from typing import Dict, List, Optional
import asyncio
from apify import Actor


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"
    
    def __init__(self, filters: Dict):
        self.filters = filters
        
    def build_url(self) -> str:
        """Build URL with all filters"""
        # Base path
        municipality = self.filters.get('municipality', 'roma').lower()
        operation = self.filters.get('operation', 'vendita').lower()
        
        # Map 'buy' to 'vendita' and 'rent' to 'affitto'
        if operation == 'buy':
            operation = 'vendita'
        elif operation == 'rent':
            operation = 'affitto'
            
        base_path = f"/{operation}-case/{municipality}/"
        
        # Query parameters
        params = {}
        
        # Price filters
        if self.filters.get('min_price'):
            params['prezzoMinimo'] = self.filters['min_price']
        if self.filters.get('max_price'):
            params['prezzoMassimo'] = self.filters['max_price']
            
        # Size filters
        if self.filters.get('min_size'):
            params['superficieMinima'] = self.filters['min_size']
        if self.filters.get('max_size'):
            params['superficieMassima'] = self.filters['max_size']
            
        # Rooms filters
        if self.filters.get('min_rooms'):
            params['localiMinimo'] = self.filters['min_rooms']
        if self.filters.get('max_rooms'):
            params['localiMassimo'] = self.filters['max_rooms']
            
        # Bathrooms
        if self.filters.get('bathrooms'):
            params['bagni'] = self.filters['bathrooms']
            
        # Property condition
        if self.filters.get('property_condition'):
            params['stato'] = self.filters['property_condition']
            
        # Floor
        if self.filters.get('floor'):
            params['piano'] = self.filters['floor']
            
        # Garage
        if self.filters.get('garage'):
            params['garage'] = self.filters['garage']
            
        # Heating
        if self.filters.get('heating'):
            params['riscaldamento'] = self.filters['heating']
            
        # Garden
        if self.filters.get('garden'):
            params['giardino'] = self.filters['garden']
            
        # Boolean filters
        if self.filters.get('terrace'):
            params['terrazzo'] = 'terrazzo'
        if self.filters.get('balcony'):
            params['balcone'] = 'balcone'
        if self.filters.get('lift'):
            params['ascensore'] = '1'
        if self.filters.get('furnished'):
            params['arredato'] = 'on'
        if self.filters.get('cellar'):
            params['cantina'] = '1'
        if self.filters.get('pool'):
            params['piscina'] = '1'
        if self.filters.get('exclude_auctions'):
            params['noAste'] = 'on'
        if self.filters.get('virtual_tour'):
            params['virtualTour'] = '1'
            
        # Keywords
        if self.filters.get('keywords'):
            params['q'] = self.filters['keywords']
            
        # Build full URL
        url = f"{self.BASE_URL}{base_path}"
        if params:
            url += f"?{urlencode(params)}"
            
        return url
    
    async def extract_listings(self, page: Page) -> List[Dict]:
        """Extract listings from current page"""
        await page.wait_for_selector('.in-card', timeout=15000)
        
        listings = await page.evaluate('''() => {
            const cards = document.querySelectorAll('.in-card');
            return Array.from(cards).map(card => {
                // Extract basic info
                const titleEl = card.querySelector('.in-card__title');
                const priceEl = card.querySelector('.in-card__price');
                const locationEl = card.querySelector('.in-card__location');
                const featuresEl = card.querySelector('.in-card__features');
                const linkEl = card.querySelector('a.in-card__title');
                const imageEl = card.querySelector('img');
                
                // Extract features text
                const features = featuresEl?.textContent?.trim() || '';
                
                // Try to parse rooms, bathrooms, sqm from features
                const roomsMatch = features.match(/(\\d+)\\s*local/i);
                const bathsMatch = features.match(/(\\d+)\\s*bagn/i);
                const sqmMatch = features.match(/(\\d+)\\s*m/i);
                
                return {
                    title: titleEl?.textContent?.trim() || '',
                    price: priceEl?.textContent?.trim() || '',
                    location: locationEl?.textContent?.trim() || '',
                    features: features,
                    rooms: roomsMatch ? parseInt(roomsMatch[1]) : null,
                    bathrooms: bathsMatch ? parseInt(bathsMatch[1]) : null,
                    surface_sqm: sqmMatch ? parseInt(sqmMatch[1]) : null,
                    url: linkEl?.href || '',
                    image_url: imageEl?.src || '',
                    listing_id: card.getAttribute('data-id') || '',
                    scraped_at: new Date().toISOString()
                };
            });
        }''')
        
        return listings
    
    async def has_next_page(self, page: Page) -> bool:
        """Check if there's a next page"""
        return await page.evaluate('''() => {
            const nextBtn = document.querySelector('a.pagination__next:not(.disabled)');
            return nextBtn !== null;
        }''')
    
    async def scrape(self, max_pages: int = 10) -> List[Dict]:
        """Main scraping method"""
        url = self.build_url()
        Actor.log.info(f"Starting scrape from: {url}")
        
        all_listings = []
        pages_scraped = 0
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                while pages_scraped < max_pages:
                    Actor.log.info(f"Scraping page {pages_scraped + 1}...")
                    
                    # Extract listings from current page
                    listings = await self.extract_listings(page)
                    all_listings.extend(listings)
                    
                    Actor.log.info(f"Extracted {len(listings)} listings from page {pages_scraped + 1}")
                    
                    # Save to dataset incrementally
                    for listing in listings:
                        await Actor.push_data(listing)
                    
                    pages_scraped += 1
                    
                    # Check for next page
                    if pages_scraped < max_pages and await self.has_next_page(page):
                        # Click next page
                        await page.click('a.pagination__next:not(.disabled)')
                        await asyncio.sleep(2)  # Wait for page load
                    else:
                        break
                        
            except Exception as e:
                Actor.log.error(f"Error during scraping: {str(e)}")
                
            finally:
                await browser.close()
        
        Actor.log.info(f"Scraping completed! Total listings: {len(all_listings)}")
        return all_listings