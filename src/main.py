"""Main entry point for Apify Actor"""

from apify import Actor
from src.scraper import ImmobiliareScraper


async def main():
    async with Actor:
        # Get input from Apify
        actor_input = await Actor.get_input() or {}
        
        # Extract filters
        filters = {
            'municipality': actor_input.get('municipality', 'roma'),
            'operation': actor_input.get('operation', 'vendita'),
            'min_price': actor_input.get('min_price'),
            'max_price': actor_input.get('max_price'),
            'min_size': actor_input.get('min_size'),
            'max_size': actor_input.get('max_size'),
            'min_rooms': actor_input.get('min_rooms'),
            'max_rooms': actor_input.get('max_rooms'),
            'bathrooms': actor_input.get('bathrooms'),
            'property_condition': actor_input.get('property_condition'),
            'floor': actor_input.get('floor'),
            'garage': actor_input.get('garage'),
            'heating': actor_input.get('heating'),
            'garden': actor_input.get('garden'),
            'terrace': actor_input.get('terrace', False),
            'balcony': actor_input.get('balcony', False),
            'lift': actor_input.get('lift', False),
            'furnished': actor_input.get('furnished', False),
            'cellar': actor_input.get('cellar', False),
            'pool': actor_input.get('pool', False),
            'exclude_auctions': actor_input.get('exclude_auctions', False),
            'virtual_tour': actor_input.get('virtual_tour', False),
            'keywords': actor_input.get('keywords'),
        }
        
        max_pages = actor_input.get('max_items', 10)
        
        Actor.log.info(f"Starting scraper with filters: {filters}")
        
        # Create scraper and run
        scraper = ImmobiliareScraper(filters)
        await scraper.scrape(max_pages=max_pages)
        
        Actor.log.info("Actor finished successfully!")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
