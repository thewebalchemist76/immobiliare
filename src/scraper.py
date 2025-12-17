"""Immobiliare.it scraper with hybrid approach"""

from urllib.parse import urlencode, urlparse
from playwright.async_api import async_playwright, Page
from typing import Dict, List, Optional
import asyncio
import requests
from bs4 import BeautifulSoup
from apify import Actor
import time


class ImmobiliareScraper:
    BASE_URL = "https://www.immobiliare.it"
    
    def __init__(self, filters: Dict):
        self.filters = filters
        
    def build_url(self) -> str:
        """Build URL with all filters"""
        municipality = self.filters.get('municipality', 'roma').lower()
        operation = self.filters.get('operation', 'vendita').lower()
        
        if operation == 'buy':
            operation = 'vendita'
        elif operation == 'rent':
            operation = 'affitto'
            
        base_path = f"/{operation}-case/{municipality}/"
        
        params = {}
        
        if self.filters.get('min_price'):
            params['prezzoMinimo'] = self.filters['min_price']
        if self.filters.get('max_price'):
            params['prezzoMassimo'] = self.filters['max_price']
        if self.filters.get('min_size'):
            params['superficieMinima'] = self.filters['min_size']
        if self.filters.get('max_size'):
            params['superficieMassima'] = self.filters['max_size']
        if self.filters.get('min_rooms'):
            params['localiMinimo'] = self.filters['min_rooms']
        if self.filters.get('max_rooms'):
            params['localiMassimo'] = self.filters['max_rooms']
        if self.filters.get('bathrooms'):
            params['bagni'] = self.filters['bathrooms']
        if self.filters.get('property_condition'):
            params['stato'] = self.filters['property_condition']
        if self.filters.get('floor'):
            params['piano'] = self.filters['floor']
        if self.filters.get('garage'):
            params['garage'] = self.filters['garage']
        if self.filters.get('heating'):
            params['riscaldamento'] = self.filters['heating']
        if self.filters.get('garden'):
            params['giardino'] = self.filters['garden']
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
        if self.filters.get('keywords'):
            params['q'] = self.filters['keywords']
            
        url = f"{self.BASE_URL}{base_path}"
        if params:
            url += f"?{urlencode(params)}"
            
        return url
    
    async def extract_listing_urls(self, page: Page) -> List[str]:
        """Extract only URLs from listing page"""
        selectors = [
            '.in-card',
            '.nd-list__item.in-realEstateResults__item',
            'article[class*="card"]'
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
            return []
        
        urls = await page.evaluate(f'''() => {{
            const cards = document.querySelectorAll('{working_selector}');
            const urls = [];
            cards.forEach(card => {{
                const link = card.querySelector('a[href*="/annunci/"]');
                if (link && link.href) {{
                    urls.push(link.href);
                }}
            }});
            return urls;
        }}''')
        
        return urls
    
    def scrape_listing_details(self, url: str) -> Optional[Dict]:
        """Scrape details from a single listing page using requests"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                Actor.log.warning(f"Failed to fetch {url}: status {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract data (based on GitHub code)
            data = {
                'url': url,
                'scraped_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Title
            try:
                title_elem = soup.find("h1", class_="in-titleBlock__title")
                data['title'] = title_elem.text.strip() if title_elem else ""
            except:
                data['title'] = ""
            
            # Price
            try:
                price_elem = soup.find("li", class_="in-detail__mainFeaturesPrice")
                if price_elem:
                    price_text = price_elem.text.strip()
                    data['price'] = price_text.replace("€", "").replace(".", "").strip()
                else:
                    data['price'] = ""
            except:
                data['price'] = ""
            
            # Rooms
            try:
                rooms_li = soup.find("li", {"aria-label": "locali"})
                if rooms_li:
                    rooms_div = rooms_li.find("div", class_="in-feat__data")
                    data['rooms'] = rooms_div.text.strip() if rooms_div else ""
                else:
                    data['rooms'] = ""
            except:
                data['rooms'] = ""
            
            # Size
            try:
                size_li = soup.find("li", {"aria-label": "superficie"})
                if size_li:
                    size_div = size_li.find("div", class_="in-feat__data")
                    data['surface_sqm'] = size_div.text.strip() if size_div else ""
                else:
                    data['surface_sqm'] = ""
            except:
                data['surface_sqm'] = ""
            
            # Bathrooms
            try:
                bath_li = soup.find("li", {"aria-label": "bagni"})
                if bath_li:
                    bath_div = bath_li.find("div", class_="in-feat__data")
                    data['bathrooms'] = bath_div.text.strip() if bath_div else ""
                else:
                    data['bathrooms'] = ""
            except:
                data['bathrooms'] = ""
            
            # Property type
            try:
                type_dt = soup.find("dt", text="tipologia")
                if type_dt:
                    type_dd = type_dt.find_next_sibling("dd")
                    data['property_type'] = type_dd.text.strip() if type_dd else ""
                else:
                    data['property_type'] = ""
            except:
                data['property_type'] = ""
            
            # Location
            try:
                location_elem = soup.find("span", class_="in-titleBlock__zone")
                data['location'] = location_elem.text.strip() if location_elem else ""
            except:
                data['location'] = ""
            
            # Agent
            try:
                agent_div = soup.find("div", class_="in-referent")
                if agent_div:
                    agent_a = agent_div.find("a")
                    data['agent'] = agent_a.text.strip() if agent_a else "Privato"
                else:
                    data['agent'] = "Privato"
            except:
                data['agent'] = ""
            
            # Description
            try:
                desc_div = soup.find("div", class_="in-readAll")
                data['description'] = desc_div.text.strip() if desc_div else ""
            except:
                data['description'] = ""
            
            # Images
            try:
                images = []
                img_gallery = soup.find_all("img", class_="in-carousel__item")
                for img in img_gallery[:5]:  # Max 5 images
                    if img.get('src'):
                        images.append(img['src'])
                data['images'] = images
            except:
                data['images'] = []
            
            # Energy class
            try:
                energy_dt = soup.find("dt", text="classe energetica")
                if energy_dt:
                    energy_dd = energy_dt.find_next_sibling("dd")
                    data['energy_class'] = energy_dd.text.strip() if energy_dd else ""
                else:
                    data['energy_class'] = ""
            except:
                data['energy_class'] = ""
            
            # Floor
            try:
                floor_dt = soup.find("dt", text="piano")
                if floor_dt:
                    floor_dd = floor_dt.find_next_sibling("dd")
                    data['floor'] = floor_dd.text.strip() if floor_dd else ""
                else:
                    data['floor'] = ""
            except:
                data['floor'] = ""
            
            return data
            
        except Exception as e:
            Actor.log.error(f"Error scraping details from {url}: {str(e)}")
            return None
    
    async def collect_listing_urls(self, max_pages: int = 10) -> List[str]:
        """Collect listing URLs from search pages using Playwright"""
        url = self.build_url()
        Actor.log.info(f"📋 Collecting listing URLs from: {url}")
        
        all_urls = []
        pages_scraped = 0
        
        async with async_playwright() as p:
            # Use proxy for URL collection
            proxy_config = await Actor.create_proxy_configuration(
                groups=['RESIDENTIAL']
            )
            proxy_url = await proxy_config.new_url()
            parsed_proxy = urlparse(proxy_url)
            
            browser = await p.chromium.launch(
                headless=True,
                proxy={
                    'server': f"{parsed_proxy.scheme}://{parsed_proxy.hostname}:{parsed_proxy.port}",
                    'username': parsed_proxy.username,
                    'password': parsed_proxy.password
                },
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(3)
                
                # Check for CAPTCHA
                page_content = await page.content()
                if 'captcha' in page_content.lower():
                    Actor.log.error("❌ CAPTCHA on search page. Try again.")
                    return []
                
                while pages_scraped < max_pages:
                    Actor.log.info(f"📄 Collecting URLs from page {pages_scraped + 1}...")
                    
                    urls = await self.extract_listing_urls(page)
                    
                    if not urls:
                        Actor.log.warning(f"No URLs found on page {pages_scraped + 1}")
                        break
                    
                    all_urls.extend(urls)
                    Actor.log.info(f"✅ Found {len(urls)} URLs on page {pages_scraped + 1}")
                    
                    pages_scraped += 1
                    
                    # Check for next page
                    has_next = await page.evaluate('''() => {
                        const btn = document.querySelector('a.pagination__next:not(.disabled)');
                        return btn !== null;
                    }''')
                    
                    if pages_scraped < max_pages and has_next:
                        try:
                            await page.click('a.pagination__next:not(.disabled)', timeout=5000)
                            await asyncio.sleep(3)
                        except:
                            break
                    else:
                        break
                        
            except Exception as e:
                Actor.log.error(f"Error collecting URLs: {str(e)}")
                
            finally:
                await browser.close()
        
        Actor.log.info(f"📊 Total URLs collected: {len(all_urls)}")
        return all_urls
    
    async def scrape(self, max_pages: int = 10) -> List[Dict]:
        """Main scraping method - hybrid approach"""
        Actor.log.info("🚀 Starting hybrid scraping approach")
        
        # PHASE 1: Collect URLs with Playwright
        Actor.log.info("📋 PHASE 1: Collecting listing URLs...")
        listing_urls = await self.collect_listing_urls(max_pages)
        
        if not listing_urls:
            Actor.log.error("❌ No URLs collected")
            return []
        
        # Remove duplicates
        listing_urls = list(set(listing_urls))
        Actor.log.info(f"📊 Unique URLs to scrape: {len(listing_urls)}")
        
        # PHASE 2: Scrape details with requests
        Actor.log.info("🔍 PHASE 2: Scraping listing details...")
        all_listings = []
        
        for i, url in enumerate(listing_urls, 1):
            Actor.log.info(f"📄 [{i}/{len(listing_urls)}] Scraping: {url}")
            
            listing_data = self.scrape_listing_details(url)
            
            if listing_data:
                all_listings.append(listing_data)
                await Actor.push_data(listing_data)
                Actor.log.info(f"✅ Scraped: {listing_data.get('title', 'N/A')}")
            else:
                Actor.log.warning(f"⚠️ Failed to scrape {url}")
            
            # Rate limiting - important!
            time.sleep(2)  # Wait 2 seconds between requests
        
        Actor.log.info(f"🎉 Scraping completed! Total listings: {len(all_listings)}")
        return all_listings