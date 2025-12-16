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
        # Try multiple selectors
        selectors = [
            '.in-card',
            '.nd-list__item.in-realEstateResults__item',
            'article[class*="card"]',
            '[data-id][class*="card"]'
        ]
        
        working_selector = None
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                working_selector = selector
                Actor.log.info(f"Using selector: {selector}")
                break
            except:
                continue
        
        if not working_selector:
            Actor.log.error("No valid selector found for listings")
            return []
        
        listings = await page.evaluate(f'''() => {{
            const cards = document.querySelectorAll('{working_selector}');
            return Array.from(cards).map(card => {{
                // Try multiple selectors for each field
                const titleEl = card.querySelector('.in-card__title, [class*="title"]');
                const priceEl = card.querySelector('.in-card__price, [class*="price"]');
                const locationEl = card.querySelector('.in-card__location, [class*="location"]');
                const featuresEl = card.querySelector('.in-card__features, [class*="features"]');
                const linkEl = card.querySelector('a.in-card__title, a[class*="title"], a');
                const imageEl = card.querySelector('img');
                
                // Extract features text
                const features = featuresEl?.textContent?.trim() || '';
                
                // Try to parse rooms, bathrooms, sqm from features
                const roomsMatch = features.match(/(\\d+)\\s*local/i);
                const bathsMatch = features.match(/(\\d+)\\s*bagn/i);
                const sqmMatch = features.match(/(\\d+)\\s*m/i);
                
                return {{
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
                }};
            }});
        }}''')
        
        # Filter out empty listings
        listings = [l for l in listings if l.get('title') or l.get('url')]
        
        return listings
    
    async def has_next_page(self, page: Page) -> bool:
        """Check if there's a next page"""
        return await page.evaluate('''() => {
            const nextBtn = document.querySelector('a.pagination__next:not(.disabled), [class*="pagination"] a[rel="next"]');
            return nextBtn !== null;
        }''')
    
    async def scrape(self, max_pages: int = 10) -> List[Dict]:
        """Main scraping method"""
        url = self.build_url()
        Actor.log.info(f"Starting scrape from: {url}")
        
        all_listings = []
        pages_scraped = 0
        
        async with async_playwright() as p:
            # Get Apify proxy configuration with RESIDENTIAL proxies
            proxy_config = await Actor.create_proxy_configuration(
                groups=['RESIDENTIAL']
            )
            proxy_url = await proxy_config.new_url()
            
            Actor.log.info(f"🔒 Using Apify residential proxy")
            
            # Parse proxy URL to extract components
            from urllib.parse import urlparse
            parsed_proxy = urlparse(proxy_url)
            
            browser = await p.chromium.launch(
                headless=True,
                proxy={
                    'server': f"{parsed_proxy.scheme}://{parsed_proxy.hostname}:{parsed_proxy.port}",
                    'username': parsed_proxy.username,
                    'password': parsed_proxy.password
                }
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='it-IT',
                timezone_id='Europe/Rome'
            )
            
            page = await context.new_page()
            
            try:
                # Go to URL and wait for network to be idle
                await page.goto(url, wait_until='networkidle', timeout=30000)
                Actor.log.info(f"Page loaded. Title: {await page.title()}")
                
                # Wait a bit for dynamic content
                await asyncio.sleep(3)
                
                # Check for CAPTCHA
                page_content = await page.content()
                if 'captcha' in page_content.lower():
                    Actor.log.error("❌ CAPTCHA detected! The site is blocking automated access.")
                    Actor.log.info("Try running again - residential proxies rotate automatically")
                    return []
                
                # Debug: check page content
                if 'Nessun risultato' in page_content or 'Non ci sono annunci' in page_content:
                    Actor.log.warning("⚠️ La ricerca non ha prodotto risultati sul sito Immobiliare.it")
                    Actor.log.warning(f"URL cercato: {url}")
                    return []
                
                # Debug: try to find any card-like elements
                selectors_to_check = [
                    '.in-card',
                    '.nd-list__item',
                    'article',
                    '[data-id]',
                    '[class*="card"]',
                    '[class*="RealEstate"]'
                ]
                
                found_elements = []
                for selector in selectors_to_check:
                    count = await page.locator(selector).count()
                    if count > 0:
                        found_elements.append(f"{selector}: {count} elements")
                
                if found_elements:
                    Actor.log.info(f"✅ Found elements: {', '.join(found_elements)}")
                else:
                    Actor.log.error("❌ No card elements found on page")
                    Actor.log.info(f"Page HTML length: {len(page_content)} characters")
                    # Log first 3000 chars of HTML for debugging
                    Actor.log.info(f"HTML preview:\n{page_content[:3000]}")
                    return []
                
                while pages_scraped < max_pages:
                    Actor.log.info(f"Scraping page {pages_scraped + 1}...")
                    
                    # Extract listings from current page
                    listings = await self.extract_listings(page)
                    
                    if not listings:
                        Actor.log.warning(f"No listings extracted from page {pages_scraped + 1}")
                        break
                    
                    all_listings.extend(listings)
                    
                    Actor.log.info(f"✅ Extracted {len(listings)} listings from page {pages_scraped + 1}")
                    
                    # Save to dataset incrementally
                    for listing in listings:
                        await Actor.push_data(listing)
                    
                    pages_scraped += 1
                    
                    # Check for next page
                    if pages_scraped < max_pages and await self.has_next_page(page):
                        # Click next page
                        try:
                            await page.click('a.pagination__next:not(.disabled)', timeout=5000)
                            await asyncio.sleep(3)  # Wait for page load
                        except:
                            Actor.log.warning("Could not click next page button")
                            break
                    else:
                        break
                        
            except Exception as e:
                Actor.log.error(f"❌ Error during scraping: {str(e)}")
                import traceback
                Actor.log.error(f"Traceback: {traceback.format_exc()}")
                
            finally:
                await browser.close()
        
        Actor.log.info(f"🎉 Scraping completed! Total listings: {len(all_listings)}")
        return all_listings