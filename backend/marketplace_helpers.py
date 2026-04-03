"""Helper functions for marketplace listing"""
import logging

logger = logging.getLogger(__name__)


async def list_on_platform(platform: str, product: dict) -> bool:
    """List product on a specific platform"""
    if platform == "etsy":
        return await list_on_etsy(product)
    elif platform == "shopify":
        return await list_on_shopify(product)
    elif platform == "gumroad":
        return await list_on_gumroad(product)
    else:
        logger.warning(f"Unknown platform: {platform}")
        return False


async def list_on_etsy(product: dict) -> bool:
    """List product on Etsy marketplace"""
    # Etsy listing logic would go here
    logger.info(f"Listed on Etsy: {product['name']}")
    return True


async def list_on_shopify(product: dict) -> bool:
    """List product on Shopify store"""
    # Shopify listing logic would go here
    logger.info(f"Listed on Shopify: {product['name']}")
    return True


async def list_on_gumroad(product: dict) -> bool:
    """List product on Gumroad"""
    # Gumroad listing logic would go here
    logger.info(f"Listed on Gumroad: {product['name']}")
    return True


async def list_on_multiple_platforms(platforms: list, product: dict) -> list:
    """List product on multiple platforms and return successful ones"""
    listed_platforms = []
    
    for platform in platforms:
        success = await list_on_platform(platform, product)
        if success:
            listed_platforms.append(platform)
    
    return listed_platforms
