from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import uuid
import base64
import asyncio

# AI Generation Imports
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# FastAPI app
app = FastAPI(title="AI Product Generator & Multi-Platform Seller")
api_router = APIRouter(prefix="/api")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class ProductGenerate(BaseModel):
    product_type: str  # 'image', 'text', 'design'
    prompt: str
    ai_model: str = "openai"  # 'openai' or 'gemini'

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    product_type: str
    content: str  # base64 for images, text content for text products
    price: float = 9.99
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    listed_on: List[str] = []  # platforms where it's listed
    status: str = "draft"  # draft, listed, sold

class ListingRequest(BaseModel):
    product_id: str
    platforms: List[str]  # ['etsy', 'shopify', 'gumroad']
    price: float

class SaleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    platform: str
    amount: float
    customer_email: Optional[str] = None
    sold_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== AI GENERATION ====================

@api_router.post("/generate/text")
async def generate_text_content(request: ProductGenerate):
    """Generate text content using AI"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message="You are a professional content creator. Create high-quality, sellable digital products."
        )
        
        if request.ai_model == "openai":
            chat.with_model("openai", "gpt-5.2")
        else:
            api_key = os.getenv("GENAI_API_KEY")
            chat = LlmChat(api_key=api_key, session_id=str(uuid.uuid4()), system_message="You are a professional content creator.")
            chat.with_model("gemini", "gemini-3-flash-preview")
        
        message = UserMessage(text=request.prompt)
        response = await chat.send_message(message)
        
        # Save to database
        product_data = {
            "id": str(uuid.uuid4()),
            "name": f"AI Generated Content - {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "description": request.prompt[:200],
            "product_type": "text",
            "content": response,
            "price": 9.99,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "listed_on": [],
            "status": "draft"
        }
        
        await db.products.insert_one(product_data)
        
        return {
            "success": True,
            "product_id": product_data["id"],
            "content": response[:500] + "..." if len(response) > 500 else response,
            "full_length": len(response)
        }
        
    except Exception as e:
        logger.error(f"Text generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/generate/image")
async def generate_image_content(request: ProductGenerate):
    """Generate image using AI"""
    from ai_helpers import generate_with_openai, generate_with_gemini, create_product_data
    
    try:
        # Generate image based on AI model
        if request.ai_model == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            image_base64 = await generate_with_openai(api_key, request.prompt)
        else:
            api_key = os.getenv("GENAI_API_KEY")
            image_base64 = await generate_with_gemini(api_key, request.prompt)
        
        # Create and save product
        product_data = create_product_data("image", request.prompt, image_base64, 19.99)
        await db.products.insert_one(product_data)
        
        return {
            "success": True,
            "product_id": product_data["id"],
            "image_preview": f"data:image/png;base64,{image_base64[:100]}...",
            "message": "Image generated successfully"
        }
        
    except ValueError as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PRODUCT MANAGEMENT ====================

@api_router.get("/products")
async def get_all_products(status: Optional[str] = None):
    """Get all products"""
    try:
        query = {}
        if status:
            query["status"] = status
            
        products = await db.products.find(query, {"_id": 0}).to_list(1000)
        return {"products": products, "count": len(products)}
        
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get single product"""
    try:
        product = await db.products.find_one({"id": product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    """Delete a product"""
    try:
        result = await db.products.delete_one({"id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"success": True, "message": "Product deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MARKETPLACE LISTING ====================

@api_router.post("/list-product")
async def list_product(request: ListingRequest, background_tasks: BackgroundTasks):
    """List product on selected platforms"""
    from marketplace_helpers import list_on_multiple_platforms
    
    try:
        # Fetch product
        product = await db.products.find_one({"id": request.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # List on platforms
        listed_platforms = await list_on_multiple_platforms(request.platforms, product)
        
        # Update product status
        await db.products.update_one(
            {"id": request.product_id},
            {"$set": {
                "listed_on": listed_platforms,
                "status": "listed",
                "price": request.price
            }}
        )
        
        return {
            "success": True,
            "product_id": request.product_id,
            "listed_on": listed_platforms
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SALES TRACKING ====================

@api_router.get("/sales")
async def get_sales():
    """Get all sales records"""
    try:
        sales = await db.sales.find({}, {"_id": 0}).to_list(1000)
        total_revenue = sum(sale.get("amount", 0) for sale in sales)
        
        return {
            "sales": sales,
            "count": len(sales),
            "total_revenue": total_revenue
        }
        
    except Exception as e:
        logger.error(f"Error fetching sales: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/sales")
async def record_sale(sale: SaleRecord):
    """Record a new sale"""
    try:
        sale_data = sale.model_dump()
        sale_data["sold_at"] = sale_data["sold_at"].isoformat()
        
        await db.sales.insert_one(sale_data)
        
        # Update product status
        await db.products.update_one(
            {"id": sale.product_id},
            {"$set": {"status": "sold"}}
        )
        
        return {"success": True, "sale_id": sale.id}
        
    except Exception as e:
        logger.error(f"Error recording sale: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANALYTICS ====================

@api_router.get("/analytics")
async def get_analytics():
    """Get business analytics"""
    try:
        total_products = await db.products.count_documents({})
        draft_products = await db.products.count_documents({"status": "draft"})
        listed_products = await db.products.count_documents({"status": "listed"})
        sold_products = await db.products.count_documents({"status": "sold"})
        
        sales = await db.sales.find({}, {"_id": 0}).to_list(1000)
        total_revenue = sum(sale.get("amount", 0) for sale in sales)
        
        # Platform breakdown
        platform_sales = {}
        for sale in sales:
            platform = sale.get("platform", "unknown")
            platform_sales[platform] = platform_sales.get(platform, 0) + sale.get("amount", 0)
        
        return {
            "total_products": total_products,
            "draft_products": draft_products,
            "listed_products": listed_products,
            "sold_products": sold_products,
            "total_sales": len(sales),
            "total_revenue": round(total_revenue, 2),
            "platform_revenue": platform_sales
        }
        
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== HEALTH & ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "AI Product Generator & Multi-Platform Seller API", "status": "running"}

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "gemini_configured": bool(os.getenv("GENAI_API_KEY")),
        "etsy_configured": bool(os.getenv("ETSY_API_KEY")),
        "shopify_configured": bool(os.getenv("SHOPIFY_API_KEY")),
        "gumroad_configured": bool(os.getenv("GUMROAD_ACCESS_TOKEN")),
        "mailchimp_configured": bool(os.getenv("MAILCHIMP_API_KEY"))
    }

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shutdown handler
@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
