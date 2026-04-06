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
import json
import httpx

# OpenAI SDK (replaces emergentintegrations)
from openai import AsyncOpenAI

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', os.environ.get('MONGO_URI', ''))
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', os.environ.get('MONGO_DB_NAME', 'ai_empire'))]

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FastAPI app
app = FastAPI(title="AI Empire - Autonomous Product Generator & Seller")
api_router = APIRouter(prefix="/api")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class ProductGenerate(BaseModel):
    product_type: str  # 'image', 'text', 'ebook', 'template', 'code', 'video_script', 'music_prompt', 'course'
    prompt: str
    ai_model: str = "openai"

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    product_type: str
    content: str
    price: float = 9.99
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    listed_on: List[str] = []
    status: str = "draft"
    niche: Optional[str] = None
    agent_team: Optional[str] = None
    estimated_monthly_revenue: Optional[float] = None

class ListingRequest(BaseModel):
    product_id: str
    platforms: List[str]
    price: float

class SaleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    platform: str
    amount: float
    customer_email: Optional[str] = None
    sold_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AgentTeam(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    niche: str
    product_types: List[str]
    target_platforms: List[str]
    strategy: str
    status: str = "active"  # active, paused, retired
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    products_generated: int = 0
    total_revenue: float = 0.0

class RevenueStream(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    niche: str
    opportunity: str
    product_types: List[str]
    platforms: List[str]
    estimated_monthly_revenue: float
    competition_level: str  # low, medium, high
    ai_confidence: float  # 0-1
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "discovered"  # discovered, assigned, active, retired

class AutoRunRequest(BaseModel):
    budget_products: int = 5  # how many products to auto-generate
    auto_list: bool = True    # auto-list on Gumroad


# ==================== AI HELPERS ====================

async def call_gpt(system: str, user: str, json_mode: bool = False) -> str:
    """Core GPT-4o call used by all agents"""
    kwargs = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": 4000,
        "temperature": 0.7,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    
    response = await openai_client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


async def generate_image_openai(prompt: str) -> str:
    """Generate image via DALL-E 3, return base64"""
    response = await openai_client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        response_format="b64_json",
        n=1
    )
    return response.data[0].b64_json


def make_product_record(product_type: str, prompt: str, content: str,
                        price: float, name: str = None, niche: str = None,
                        agent_team: str = None) -> dict:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return {
        "id": str(uuid.uuid4()),
        "name": name or f"{product_type.replace('_',' ').title()} - {timestamp}",
        "description": prompt[:300],
        "product_type": product_type,
        "content": content,
        "price": price,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "listed_on": [],
        "status": "draft",
        "niche": niche,
        "agent_team": agent_team,
    }


# ==================== EXISTING ENDPOINTS (preserved) ====================

@api_router.post("/generate/text")
async def generate_text_content(request: ProductGenerate):
    """Generate text content using AI (original endpoint, now uses openai SDK)"""
    try:
        content = await call_gpt(
            system="You are a professional content creator. Create high-quality, sellable digital products. Be thorough and detailed.",
            user=request.prompt
        )
        product_data = make_product_record("text", request.prompt, content, 9.99)
        await db.products.insert_one(product_data)
        return {
            "success": True,
            "product_id": product_data["id"],
            "content": content[:500] + "..." if len(content) > 500 else content,
            "full_length": len(content)
        }
    except Exception as e:
        logger.error(f"Text generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/generate/image")
async def generate_image_content(request: ProductGenerate):
    """Generate image using DALL-E 3 (original endpoint)"""
    try:
        image_base64 = await generate_image_openai(request.prompt)
        product_data = make_product_record("image", request.prompt, image_base64, 19.99)
        await db.products.insert_one(product_data)
        return {
            "success": True,
            "product_id": product_data["id"],
            "image_preview": f"data:image/png;base64,{image_base64[:100]}...",
            "message": "Image generated successfully"
        }
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products")
async def get_all_products(status: Optional[str] = None, product_type: Optional[str] = None,
                           niche: Optional[str] = None, agent_team: Optional[str] = None):
    try:
        query = {}
        if status:
            query["status"] = status
        if product_type:
            query["product_type"] = product_type
        if niche:
            query["niche"] = niche
        if agent_team:
            query["agent_team"] = agent_team
        products = await db.products.find(query, {"_id": 0}).to_list(1000)
        return {"products": products, "count": len(products)}
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    try:
        product = await db.products.find_one({"id": product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    try:
        result = await db.products.delete_one({"id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"success": True, "message": "Product deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/list-product")
async def list_product(request: ListingRequest, background_tasks: BackgroundTasks):
    try:
        product = await db.products.find_one({"id": request.product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        listed_platforms = await list_on_multiple_platforms(request.platforms, product, request.price)
        await db.products.update_one(
            {"id": request.product_id},
            {"$set": {"listed_on": listed_platforms, "status": "listed", "price": request.price}}
        )
        return {"success": True, "product_id": request.product_id, "listed_on": listed_platforms}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sales")
async def get_sales():
    try:
        sales = await db.sales.find({}, {"_id": 0}).to_list(1000)
        total_revenue = sum(sale.get("amount", 0) for sale in sales)
        return {"sales": sales, "count": len(sales), "total_revenue": total_revenue}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/sales")
async def record_sale(sale: SaleRecord):
    try:
        sale_data = sale.model_dump()
        sale_data["sold_at"] = sale_data["sold_at"].isoformat()
        await db.sales.insert_one(sale_data)
        await db.products.update_one({"id": sale.product_id}, {"$set": {"status": "sold"}})
        # Update agent team revenue if applicable
        product = await db.products.find_one({"id": sale.product_id}, {"_id": 0})
        if product and product.get("agent_team"):
            await db.agent_teams.update_one(
                {"id": product["agent_team"]},
                {"$inc": {"total_revenue": sale.amount}}
            )
        return {"success": True, "sale_id": sale.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/analytics")
async def get_analytics():
    try:
        total_products = await db.products.count_documents({})
        draft_products = await db.products.count_documents({"status": "draft"})
        listed_products = await db.products.count_documents({"status": "listed"})
        sold_products = await db.products.count_documents({"status": "sold"})
        sales = await db.sales.find({}, {"_id": 0}).to_list(1000)
        total_revenue = sum(sale.get("amount", 0) for sale in sales)
        platform_sales = {}
        for sale in sales:
            platform = sale.get("platform", "unknown")
            platform_sales[platform] = platform_sales.get(platform, 0) + sale.get("amount", 0)
        # Empire stats
        active_teams = await db.agent_teams.count_documents({"status": "active"})
        revenue_streams = await db.revenue_streams.count_documents({})
        return {
            "total_products": total_products,
            "draft_products": draft_products,
            "listed_products": listed_products,
            "sold_products": sold_products,
            "total_sales": len(sales),
            "total_revenue": round(total_revenue, 2),
            "platform_revenue": platform_sales,
            # Empire stats
            "active_agent_teams": active_teams,
            "revenue_streams_discovered": revenue_streams,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: REVENUE STREAM SCOUTING ====================

@api_router.post("/empire/scout")
async def scout_revenue_streams(background_tasks: BackgroundTasks):
    """AI scouts the market and identifies the most profitable niches and product types right now."""
    try:
        raw = await call_gpt(
            system="""You are a digital product market analyst and AI monetization expert.
Your job is to identify the MOST profitable niches for AI-generated digital products right now.
Focus only on products that AI can fully create: images, ebooks, templates, code tools,
video scripts, music prompts, courses, Notion dashboards, Canva templates, prompt packs, etc.
Respond ONLY with valid JSON.""",
            user="""Identify the top 5 most profitable revenue stream opportunities for AI-generated digital products.
For each, return JSON with this exact structure:
{
  "streams": [
    {
      "niche": "string",
      "opportunity": "string (1-2 sentences explaining the opportunity)",
      "product_types": ["list", "of", "product", "types"],
      "platforms": ["gumroad", "etsy", "etc"],
      "estimated_monthly_revenue": 500.0,
      "competition_level": "low|medium|high",
      "ai_confidence": 0.85
    }
  ]
}""",
            json_mode=True
        )

        data = json.loads(raw)
        streams = data.get("streams", [])
        saved = []

        for s in streams:
            stream_doc = {
                "id": str(uuid.uuid4()),
                "niche": s.get("niche"),
                "opportunity": s.get("opportunity"),
                "product_types": s.get("product_types", []),
                "platforms": s.get("platforms", []),
                "estimated_monthly_revenue": s.get("estimated_monthly_revenue", 0),
                "competition_level": s.get("competition_level", "medium"),
                "ai_confidence": s.get("ai_confidence", 0.5),
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "status": "discovered"
            }
            await db.revenue_streams.insert_one(stream_doc)
            saved.append(stream_doc)

        return {
            "success": True,
            "streams_discovered": len(saved),
            "streams": [{k: v for k, v in s.items() if k != "_id"} for s in saved]
        }

    except Exception as e:
        logger.error(f"Scout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/empire/streams")
async def get_revenue_streams(status: Optional[str] = None):
    """Get all discovered revenue streams"""
    try:
        query = {}
        if status:
            query["status"] = status
        streams = await db.revenue_streams.find(query, {"_id": 0}).to_list(500)
        return {"streams": streams, "count": len(streams)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: AGENT TEAMS ====================

@api_router.post("/empire/teams/spawn")
async def spawn_agent_team(stream_id: str):
    """Spawn an agent team to exploit a discovered revenue stream."""
    try:
        stream = await db.revenue_streams.find_one({"id": stream_id}, {"_id": 0})
        if not stream:
            raise HTTPException(status_code=404, detail="Revenue stream not found")

        raw = await call_gpt(
            system="""You are an AI business strategist. Design a focused agent team
to dominate a specific digital product niche. Respond ONLY with valid JSON.""",
            user=f"""Design an agent team for this niche:
Niche: {stream['niche']}
Opportunity: {stream['opportunity']}
Product types: {stream['product_types']}
Platforms: {stream['platforms']}
Estimated monthly revenue: ${stream['estimated_monthly_revenue']}

Return JSON:
{{
  "name": "team name",
  "strategy": "2-3 sentence strategy description",
  "product_types": ["list"],
  "target_platforms": ["list"],
  "pricing_strategy": "description of pricing"
}}""",
            json_mode=True
        )

        plan = json.loads(raw)
        team_doc = {
            "id": str(uuid.uuid4()),
            "name": plan.get("name", f"Team {stream['niche']}"),
            "niche": stream["niche"],
            "product_types": plan.get("product_types", stream["product_types"]),
            "target_platforms": plan.get("target_platforms", stream["platforms"]),
            "strategy": plan.get("strategy", ""),
            "pricing_strategy": plan.get("pricing_strategy", ""),
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "products_generated": 0,
            "total_revenue": 0.0,
            "stream_id": stream_id
        }

        await db.agent_teams.insert_one(team_doc)
        await db.revenue_streams.update_one(
            {"id": stream_id},
            {"$set": {"status": "assigned", "team_id": team_doc["id"]}}
        )

        return {"success": True, "team": {k: v for k, v in team_doc.items() if k != "_id"}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Spawn team error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/empire/teams")
async def get_agent_teams(status: Optional[str] = None):
    """Get all agent teams"""
    try:
        query = {}
        if status:
            query["status"] = status
        teams = await db.agent_teams.find(query, {"_id": 0}).to_list(500)
        return {"teams": teams, "count": len(teams)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.patch("/empire/teams/{team_id}/status")
async def update_team_status(team_id: str, status: str):
    """Pause, activate, or retire a team"""
    try:
        if status not in ["active", "paused", "retired"]:
            raise HTTPException(status_code=400, detail="Status must be active, paused, or retired")
        result = await db.agent_teams.update_one({"id": team_id}, {"$set": {"status": status}})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Team not found")
        return {"success": True, "team_id": team_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: MULTI-PRODUCT GENERATION ====================

PRODUCT_GENERATORS = {
    "ebook": {
        "system": "You are a professional ebook author. Write complete, valuable, sellable ebooks with chapters, subheadings, and actionable content.",
        "price": 14.99,
        "prompt_template": "Write a complete ebook on: {prompt}. Include: title, introduction, 5+ chapters with subheadings, actionable tips, and conclusion."
    },
    "template": {
        "system": "You are a professional template designer. Create detailed, ready-to-use templates with clear instructions.",
        "price": 7.99,
        "prompt_template": "Create a complete, professional template for: {prompt}. Include structure, placeholders, usage instructions, and examples."
    },
    "code": {
        "system": "You are a senior software developer. Create complete, documented, production-ready code tools and scripts.",
        "price": 24.99,
        "prompt_template": "Create a complete, well-documented code solution for: {prompt}. Include setup instructions, comments, and example usage."
    },
    "video_script": {
        "system": "You are a professional YouTube scriptwriter and content strategist.",
        "price": 9.99,
        "prompt_template": "Write a complete YouTube video script about: {prompt}. Include hook, intro, main sections with b-roll notes, CTA, and outro."
    },
    "music_prompt": {
        "system": "You are an expert AI music prompt engineer for tools like Suno and Udio.",
        "price": 4.99,
        "prompt_template": "Create a pack of 10 detailed AI music generation prompts for the genre/style: {prompt}. Each prompt should be detailed, creative, and ready to use in Suno or Udio."
    },
    "course": {
        "system": "You are an expert online course creator and instructional designer.",
        "price": 49.99,
        "prompt_template": "Design a complete online course outline on: {prompt}. Include: course title, target audience, learning outcomes, 5+ modules with lessons, assignments, and a final project."
    },
    "prompt_pack": {
        "system": "You are an AI prompt engineering expert who creates high-value prompt packs for creative professionals.",
        "price": 12.99,
        "prompt_template": "Create a pack of 20 premium AI prompts for: {prompt}. Each prompt should be detailed, creative, and immediately usable. Organize by use case."
    },
    "notion_template": {
        "system": "You are a Notion expert and productivity consultant. Design detailed Notion workspace templates.",
        "price": 19.99,
        "prompt_template": "Design a complete Notion template for: {prompt}. Include: database structures, views, properties, formulas, and a setup guide."
    },
    "text": {
        "system": "You are a professional content creator. Create high-quality, sellable digital content.",
        "price": 9.99,
        "prompt_template": "{prompt}"
    },
    "image": {
        "system": "",
        "price": 19.99,
        "prompt_template": "{prompt}"
    }
}


@api_router.post("/empire/generate")
async def empire_generate(request: ProductGenerate, agent_team_id: Optional[str] = None):
    """
    Generate any product type the empire supports.
    product_type: image | text | ebook | template | code | video_script |
                  music_prompt | course | prompt_pack | notion_template
    """
    try:
        product_type = request.product_type
        config = PRODUCT_GENERATORS.get(product_type, PRODUCT_GENERATORS["text"])
        niche = None
        team_name = None

        if agent_team_id:
            team = await db.agent_teams.find_one({"id": agent_team_id}, {"_id": 0})
            if team:
                niche = team.get("niche")
                team_name = team.get("name")

        if product_type == "image":
            content = await generate_image_openai(request.prompt)
        else:
            formatted_prompt = config["prompt_template"].format(prompt=request.prompt)
            content = await call_gpt(system=config["system"], user=formatted_prompt)

        # Let GPT pick a good product name
        name_raw = await call_gpt(
            system="You are a digital product naming expert. Return ONLY the product name, nothing else. Max 8 words.",
            user=f"Product type: {product_type}\nDescription: {request.prompt[:200]}\nCreate a compelling, sellable product name:"
        )
        product_name = name_raw.strip().strip('"')

        product_data = make_product_record(
            product_type=product_type,
            prompt=request.prompt,
            content=content,
            price=config["price"],
            name=product_name,
            niche=niche,
            agent_team=agent_team_id
        )

        await db.products.insert_one(product_data)

        if agent_team_id:
            await db.agent_teams.update_one(
                {"id": agent_team_id},
                {"$inc": {"products_generated": 1}}
            )

        return {
            "success": True,
            "product_id": product_data["id"],
            "name": product_name,
            "product_type": product_type,
            "price": config["price"],
            "niche": niche,
            "agent_team": team_name,
            "preview": content[:400] + "..." if len(content) > 400 else content
        }

    except Exception as e:
        logger.error(f"Empire generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: AUTO-RUN (full autonomous loop) ====================

@api_router.post("/empire/auto-run")
async def auto_run(request: AutoRunRequest, background_tasks: BackgroundTasks):
    """
    Full autonomous loop:
    1. Scout top revenue streams
    2. Spawn agent teams for best opportunities
    3. Generate products for each team
    4. Auto-list on Gumroad if enabled
    """
    background_tasks.add_task(_auto_run_task, request)
    return {
        "success": True,
        "message": f"Auto-run started. Generating {request.budget_products} products across top niches.",
        "auto_list": request.auto_list
    }


async def _auto_run_task(request: AutoRunRequest):
    """Background task that runs the full autonomous empire loop"""
    try:
        logger.info("AUTO-RUN: Scouting revenue streams...")

        # Step 1: Scout
        raw = await call_gpt(
            system="""You are a digital product market analyst. Identify the top 3 most profitable
niches for AI-generated digital products right now. Respond ONLY with valid JSON.""",
            user="""Return the top 3 niches as JSON:
{
  "streams": [
    {
      "niche": "string",
      "opportunity": "string",
      "product_types": ["ebook", "template", etc],
      "platforms": ["gumroad"],
      "estimated_monthly_revenue": 500.0,
      "competition_level": "low|medium|high",
      "ai_confidence": 0.85
    }
  ]
}""",
            json_mode=True
        )

        data = json.loads(raw)
        streams = data.get("streams", [])[:3]

        stream_ids = []
        for s in streams:
            doc = {
                "id": str(uuid.uuid4()),
                **s,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "status": "discovered"
            }
            await db.revenue_streams.insert_one(doc)
            stream_ids.append(doc["id"])
            logger.info(f"AUTO-RUN: Found stream: {s['niche']}")

        # Step 2: Spawn teams for each stream
        team_ids = []
        for sid in stream_ids:
            stream = await db.revenue_streams.find_one({"id": sid}, {"_id": 0})
            if not stream:
                continue

            team_doc = {
                "id": str(uuid.uuid4()),
                "name": f"Team {stream['niche']}",
                "niche": stream["niche"],
                "product_types": stream.get("product_types", ["ebook"]),
                "target_platforms": stream.get("platforms", ["gumroad"]),
                "strategy": stream.get("opportunity", ""),
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "products_generated": 0,
                "total_revenue": 0.0,
                "stream_id": sid
            }
            await db.agent_teams.insert_one(team_doc)
            await db.revenue_streams.update_one({"id": sid}, {"$set": {"status": "assigned", "team_id": team_doc["id"]}})
            team_ids.append(team_doc["id"])
            logger.info(f"AUTO-RUN: Spawned team for {stream['niche']}")

        # Step 3: Generate products across teams
        products_per_team = max(1, request.budget_products // len(team_ids)) if team_ids else 1

        for team_id in team_ids:
            team = await db.agent_teams.find_one({"id": team_id}, {"_id": 0})
            if not team:
                continue

            product_types = team.get("product_types", ["ebook"])[:products_per_team]

            for pt in product_types:
                if pt not in PRODUCT_GENERATORS:
                    pt = "ebook"

                config = PRODUCT_GENERATORS[pt]

                # Let AI decide what to make
                prompt_raw = await call_gpt(
                    system="You are a digital product strategist. Suggest ONE specific product idea. Return ONLY the product idea description, max 2 sentences.",
                    user=f"Niche: {team['niche']}\nProduct type: {pt}\nSuggest a specific, high-demand product:"
                )
                prompt = prompt_raw.strip()

                try:
                    if pt == "image":
                        content = await generate_image_openai(prompt)
                    else:
                        formatted = config["prompt_template"].format(prompt=prompt)
                        content = await call_gpt(system=config["system"], user=formatted)

                    name_raw = await call_gpt(
                        system="Return ONLY a product name, max 8 words.",
                        user=f"Type: {pt}\nIdea: {prompt}"
                    )

                    product_data = make_product_record(
                        product_type=pt,
                        prompt=prompt,
                        content=content,
                        price=config["price"],
                        name=name_raw.strip().strip('"'),
                        niche=team["niche"],
                        agent_team=team_id
                    )

                    await db.products.insert_one(product_data)
                    await db.agent_teams.update_one({"id": team_id}, {"$inc": {"products_generated": 1}})
                    logger.info(f"AUTO-RUN: Generated {pt} for {team['niche']}")

                    # Step 4: Auto-list on Gumroad
                    if request.auto_list and os.getenv("GUMROAD_ACCESS_TOKEN") and pt != "image":
                        await gumroad_list(product_data)

                except Exception as gen_err:
                    logger.error(f"AUTO-RUN: Product gen failed: {gen_err}")
                    continue

        logger.info("AUTO-RUN: Complete.")

    except Exception as e:
        logger.error(f"AUTO-RUN task failed: {e}")


# ==================== MARKETPLACE: GUMROAD ====================

async def gumroad_list(product: dict) -> bool:
    """List a product on Gumroad via their API"""
    try:
        token = os.getenv("GUMROAD_ACCESS_TOKEN")
        if not token:
            return False

        # Gumroad API: create a product
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.gumroad.com/v2/products",
                data={
                    "access_token": token,
                    "name": product.get("name", "AI Digital Product"),
                    "description": product.get("description", ""),
                    "price": int(product.get("price", 9.99) * 100),  # cents
                    "url": "",
                },
                timeout=15
            )

        if response.status_code == 200:
            result = response.json()
            gumroad_id = result.get("product", {}).get("id")
            await db.products.update_one(
                {"id": product["id"]},
                {"$set": {
                    "status": "listed",
                    "listed_on": ["gumroad"],
                    "gumroad_id": gumroad_id
                }}
            )
            logger.info(f"Listed on Gumroad: {product['name']}")
            return True
        else:
            logger.warning(f"Gumroad listing failed: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Gumroad error: {e}")
        return False


async def list_on_multiple_platforms(platforms: list, product: dict, price: float) -> list:
    listed = []
    for platform in platforms:
        if platform == "gumroad":
            product["price"] = price
            ok = await gumroad_list(product)
            if ok:
                listed.append("gumroad")
        else:
            logger.info(f"Platform {platform} not yet integrated — skipping")
    return listed


# ==================== EMPIRE: DASHBOARD SUMMARY ====================

@api_router.get("/empire/dashboard")
async def empire_dashboard():
    """Full empire overview"""
    try:
        teams = await db.agent_teams.find({}, {"_id": 0}).to_list(500)
        streams = await db.revenue_streams.find({}, {"_id": 0}).to_list(500)
        sales = await db.sales.find({}, {"_id": 0}).to_list(1000)
        products = await db.products.find({}, {"_id": 0}).to_list(1000)

        total_revenue = sum(s.get("amount", 0) for s in sales)
        by_niche = {}
        for p in products:
            niche = p.get("niche", "unassigned")
            by_niche[niche] = by_niche.get(niche, 0) + 1

        by_type = {}
        for p in products:
            pt = p.get("product_type", "unknown")
            by_type[pt] = by_type.get(pt, 0) + 1

        return {
            "empire": {
                "total_revenue": round(total_revenue, 2),
                "total_products": len(products),
                "active_teams": sum(1 for t in teams if t.get("status") == "active"),
                "revenue_streams": len(streams),
                "products_listed": sum(1 for p in products if p.get("status") == "listed"),
                "products_sold": sum(1 for p in products if p.get("status") == "sold"),
            },
            "by_niche": by_niche,
            "by_product_type": by_type,
            "teams": teams,
            "top_streams": sorted(streams, key=lambda x: x.get("estimated_monthly_revenue", 0), reverse=True)[:5]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HEALTH & ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "AI Empire API", "status": "running", "version": "2.0"}


@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "gumroad_configured": bool(os.getenv("GUMROAD_ACCESS_TOKEN")),
        "mailchimp_configured": bool(os.getenv("MAILCHIMP_API_KEY")),
        "product_types_supported": list(PRODUCT_GENERATORS.keys()),
    }


# ==================== APP SETUP ====================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
