from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import uuid
import json
import httpx

from openai import AsyncOpenAI
from supabase import create_client, Client

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://edvqnosgxxrfckonnixt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FastAPI app
app = FastAPI(title="AI Empire - Autonomous Product Generator & Seller")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class ProductGenerate(BaseModel):
    product_type: str
    prompt: str
    ai_model: str = "openai"

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

class AutoRunRequest(BaseModel):
    budget_products: int = 5
    auto_list: bool = True


# ==================== SUPABASE HELPERS ====================

def sb_insert(table: str, data: dict) -> dict:
    data.pop("_id", None)
    res = supabase.table(table).insert(data).execute()
    return res.data[0] if res.data else {}

def sb_select(table: str, filters: dict = None, limit: int = 1000) -> list:
    q = supabase.table(table).select("*").limit(limit)
    if filters:
        for k, v in filters.items():
            q = q.eq(k, v)
    return q.execute().data or []

def sb_update(table: str, match: dict, data: dict):
    q = supabase.table(table).update(data)
    for k, v in match.items():
        q = q.eq(k, v)
    q.execute()

def sb_delete(table: str, match: dict):
    q = supabase.table(table).delete()
    for k, v in match.items():
        q = q.eq(k, v)
    q.execute()

def sb_increment(table: str, id_val: str, field: str, amount):
    rows = sb_select(table, {"id": id_val})
    if rows:
        current = rows[0].get(field, 0) or 0
        supabase.table(table).update({field: current + amount}).eq("id", id_val).execute()


# ==================== AI HELPERS ====================

async def call_gpt(system: str, user: str, json_mode: bool = False) -> str:
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
        "name": name or f"{product_type.replace('_', ' ').title()} - {timestamp}",
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
        "prompt_template": "Create a pack of 10 detailed AI music generation prompts for the genre/style: {prompt}. Each should be detailed and ready to use in Suno or Udio."
    },
    "course": {
        "system": "You are an expert online course creator and instructional designer.",
        "price": 49.99,
        "prompt_template": "Design a complete online course outline on: {prompt}. Include: title, target audience, learning outcomes, 5+ modules with lessons, assignments, and a final project."
    },
    "prompt_pack": {
        "system": "You are an AI prompt engineering expert who creates high-value prompt packs.",
        "price": 12.99,
        "prompt_template": "Create a pack of 20 premium AI prompts for: {prompt}. Each prompt should be detailed and immediately usable. Organize by use case."
    },
    "notion_template": {
        "system": "You are a Notion expert and productivity consultant.",
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


# ==================== ORIGINAL ENDPOINTS ====================

@api_router.post("/generate/text")
async def generate_text_content(request: ProductGenerate):
    try:
        content = await call_gpt(
            system="You are a professional content creator. Create high-quality, sellable digital products.",
            user=request.prompt
        )
        product_data = make_product_record("text", request.prompt, content, 9.99)
        sb_insert("products", product_data)
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
    try:
        image_base64 = await generate_image_openai(request.prompt)
        product_data = make_product_record("image", request.prompt, image_base64, 19.99)
        sb_insert("products", product_data)
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
        filters = {}
        if status: filters["status"] = status
        if product_type: filters["product_type"] = product_type
        if niche: filters["niche"] = niche
        if agent_team: filters["agent_team"] = agent_team
        products = sb_select("products", filters)
        return {"products": products, "count": len(products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    try:
        rows = sb_select("products", {"id": product_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Product not found")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    try:
        sb_delete("products", {"id": product_id})
        return {"success": True, "message": "Product deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/list-product")
async def list_product(request: ListingRequest, background_tasks: BackgroundTasks):
    try:
        rows = sb_select("products", {"id": request.product_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Product not found")
        product = rows[0]
        listed_platforms = await list_on_multiple_platforms(request.platforms, product, request.price)
        sb_update("products", {"id": request.product_id}, {
            "listed_on": listed_platforms, "status": "listed", "price": request.price
        })
        return {"success": True, "product_id": request.product_id, "listed_on": listed_platforms}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/sales")
async def get_sales():
    try:
        sales = sb_select("sales")
        total_revenue = sum(s.get("amount", 0) for s in sales)
        return {"sales": sales, "count": len(sales), "total_revenue": total_revenue}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/sales")
async def record_sale(sale: SaleRecord):
    try:
        sale_data = sale.model_dump()
        sale_data["sold_at"] = sale_data["sold_at"].isoformat()
        sb_insert("sales", sale_data)
        sb_update("products", {"id": sale.product_id}, {"status": "sold"})
        rows = sb_select("products", {"id": sale.product_id})
        if rows and rows[0].get("agent_team"):
            sb_increment("agent_teams", rows[0]["agent_team"], "total_revenue", sale.amount)
        return {"success": True, "sale_id": sale.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/analytics")
async def get_analytics():
    try:
        products = sb_select("products")
        sales = sb_select("sales")
        agent_teams = sb_select("agent_teams")
        revenue_streams = sb_select("revenue_streams")
        total_revenue = sum(s.get("amount", 0) for s in sales)
        platform_sales = {}
        for sale in sales:
            p = sale.get("platform", "unknown")
            platform_sales[p] = platform_sales.get(p, 0) + sale.get("amount", 0)
        return {
            "total_products": len(products),
            "draft_products": sum(1 for p in products if p.get("status") == "draft"),
            "listed_products": sum(1 for p in products if p.get("status") == "listed"),
            "sold_products": sum(1 for p in products if p.get("status") == "sold"),
            "total_sales": len(sales),
            "total_revenue": round(total_revenue, 2),
            "platform_revenue": platform_sales,
            "active_agent_teams": sum(1 for t in agent_teams if t.get("status") == "active"),
            "revenue_streams_discovered": len(revenue_streams),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: SCOUTING ====================

@api_router.post("/empire/scout")
async def scout_revenue_streams():
    try:
        raw = await call_gpt(
            system="You are a digital product market analyst. Identify profitable niches for AI-generated digital products. Respond ONLY with valid JSON.",
            user="""Return top 5 niches as JSON:
{
  "streams": [
    {
      "niche": "string",
      "opportunity": "string",
      "product_types": ["ebook"],
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
        saved = []
        for s in data.get("streams", []):
            doc = {
                "id": str(uuid.uuid4()),
                **s,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "status": "discovered"
            }
            sb_insert("revenue_streams", doc)
            saved.append(doc)
        return {"success": True, "streams_discovered": len(saved), "streams": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/empire/streams")
async def get_revenue_streams(status: Optional[str] = None):
    try:
        streams = sb_select("revenue_streams", {"status": status} if status else None)
        return {"streams": streams, "count": len(streams)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: AGENT TEAMS ====================

@api_router.post("/empire/teams/spawn")
async def spawn_agent_team(stream_id: str):
    try:
        rows = sb_select("revenue_streams", {"id": stream_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Revenue stream not found")
        stream = rows[0]
        raw = await call_gpt(
            system="You are an AI business strategist. Design a focused agent team to dominate a digital product niche. Respond ONLY with valid JSON.",
            user=f"""Design an agent team for:
Niche: {stream['niche']}
Opportunity: {stream['opportunity']}
Product types: {stream['product_types']}
Platforms: {stream['platforms']}

Return JSON:
{{
  "name": "team name",
  "strategy": "2-3 sentence strategy",
  "product_types": ["list"],
  "target_platforms": ["list"],
  "pricing_strategy": "description"
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
        sb_insert("agent_teams", team_doc)
        sb_update("revenue_streams", {"id": stream_id}, {"status": "assigned", "team_id": team_doc["id"]})
        return {"success": True, "team": team_doc}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/empire/teams")
async def get_agent_teams(status: Optional[str] = None):
    try:
        teams = sb_select("agent_teams", {"status": status} if status else None)
        return {"teams": teams, "count": len(teams)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.patch("/empire/teams/{team_id}/status")
async def update_team_status(team_id: str, status: str):
    try:
        if status not in ["active", "paused", "retired"]:
            raise HTTPException(status_code=400, detail="Status must be active, paused, or retired")
        sb_update("agent_teams", {"id": team_id}, {"status": status})
        return {"success": True, "team_id": team_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: GENERATE ====================

@api_router.post("/empire/generate")
async def empire_generate(request: ProductGenerate, agent_team_id: Optional[str] = None):
    try:
        product_type = request.product_type
        config = PRODUCT_GENERATORS.get(product_type, PRODUCT_GENERATORS["text"])
        niche, team_name = None, None
        if agent_team_id:
            rows = sb_select("agent_teams", {"id": agent_team_id})
            if rows:
                niche = rows[0].get("niche")
                team_name = rows[0].get("name")

        content = await generate_image_openai(request.prompt) if product_type == "image" \
            else await call_gpt(system=config["system"], user=config["prompt_template"].format(prompt=request.prompt))

        name_raw = await call_gpt(
            system="Return ONLY a product name, max 8 words.",
            user=f"Type: {product_type}\nIdea: {request.prompt[:200]}"
        )
        product_data = make_product_record(
            product_type=product_type, prompt=request.prompt, content=content,
            price=config["price"], name=name_raw.strip().strip('"'),
            niche=niche, agent_team=agent_team_id
        )
        sb_insert("products", product_data)
        if agent_team_id:
            sb_increment("agent_teams", agent_team_id, "products_generated", 1)

        return {
            "success": True,
            "product_id": product_data["id"],
            "name": product_data["name"],
            "product_type": product_type,
            "price": config["price"],
            "niche": niche,
            "agent_team": team_name,
            "preview": content[:400] + "..." if len(content) > 400 else content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMPIRE: AUTO-RUN ====================

@api_router.post("/empire/auto-run")
async def auto_run(request: AutoRunRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_auto_run_task, request)
    return {"success": True, "message": f"Auto-run started. Generating {request.budget_products} products.", "auto_list": request.auto_list}


async def _auto_run_task(request: AutoRunRequest):
    try:
        raw = await call_gpt(
            system="You are a digital product market analyst. Respond ONLY with valid JSON.",
            user="""Return top 3 niches as JSON:
{
  "streams": [
    {"niche": "string", "opportunity": "string", "product_types": ["ebook"],
     "platforms": ["gumroad"], "estimated_monthly_revenue": 500.0,
     "competition_level": "low", "ai_confidence": 0.85}
  ]
}""",
            json_mode=True
        )
        streams = json.loads(raw).get("streams", [])[:3]
        stream_ids = []
        for s in streams:
            doc = {"id": str(uuid.uuid4()), **s, "discovered_at": datetime.now(timezone.utc).isoformat(), "status": "discovered"}
            sb_insert("revenue_streams", doc)
            stream_ids.append(doc["id"])

        team_ids = []
        for sid in stream_ids:
            rows = sb_select("revenue_streams", {"id": sid})
            if not rows:
                continue
            stream = rows[0]
            team_doc = {
                "id": str(uuid.uuid4()), "name": f"Team {stream['niche']}",
                "niche": stream["niche"], "product_types": stream.get("product_types", ["ebook"]),
                "target_platforms": stream.get("platforms", ["gumroad"]),
                "strategy": stream.get("opportunity", ""), "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "products_generated": 0, "total_revenue": 0.0, "stream_id": sid
            }
            sb_insert("agent_teams", team_doc)
            sb_update("revenue_streams", {"id": sid}, {"status": "assigned", "team_id": team_doc["id"]})
            team_ids.append(team_doc["id"])

        products_per_team = max(1, request.budget_products // len(team_ids)) if team_ids else 1

        for team_id in team_ids:
            rows = sb_select("agent_teams", {"id": team_id})
            if not rows:
                continue
            team = rows[0]
            for pt in team.get("product_types", ["ebook"])[:products_per_team]:
                if pt not in PRODUCT_GENERATORS:
                    pt = "ebook"
                config = PRODUCT_GENERATORS[pt]
                prompt = (await call_gpt(
                    system="Suggest ONE specific digital product idea. Return ONLY the idea, max 2 sentences.",
                    user=f"Niche: {team['niche']}\nType: {pt}"
                )).strip()
                try:
                    content = await generate_image_openai(prompt) if pt == "image" \
                        else await call_gpt(system=config["system"], user=config["prompt_template"].format(prompt=prompt))
                    name = (await call_gpt(system="Return ONLY a product name, max 8 words.", user=f"Type: {pt}\nIdea: {prompt}")).strip().strip('"')
                    product_data = make_product_record(pt, prompt, content, config["price"], name, team["niche"], team_id)
                    sb_insert("products", product_data)
                    sb_increment("agent_teams", team_id, "products_generated", 1)
                    if request.auto_list and os.getenv("GUMROAD_ACCESS_TOKEN") and pt != "image":
                        await gumroad_list(product_data)
                except Exception as e:
                    logger.error(f"AUTO-RUN product error: {e}")
        logger.info("AUTO-RUN complete.")
    except Exception as e:
        logger.error(f"AUTO-RUN failed: {e}")


# ==================== GUMROAD ====================

async def gumroad_list(product: dict) -> bool:
    try:
        token = os.getenv("GUMROAD_ACCESS_TOKEN")
        if not token:
            return False
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.gumroad.com/v2/products",
                data={"access_token": token, "name": product.get("name", "AI Product"),
                      "description": product.get("description", ""),
                      "price": int(product.get("price", 9.99) * 100)},
                timeout=15
            )
        if r.status_code == 200:
            gumroad_id = r.json().get("product", {}).get("id")
            sb_update("products", {"id": product["id"]}, {"status": "listed", "listed_on": ["gumroad"], "gumroad_id": gumroad_id})
            return True
        return False
    except Exception as e:
        logger.error(f"Gumroad error: {e}")
        return False


async def list_on_multiple_platforms(platforms: list, product: dict, price: float) -> list:
    listed = []
    for platform in platforms:
        if platform == "gumroad":
            product["price"] = price
            if await gumroad_list(product):
                listed.append("gumroad")
    return listed


# ==================== EMPIRE DASHBOARD ====================

@api_router.get("/empire/dashboard")
async def empire_dashboard():
    try:
        teams = sb_select("agent_teams")
        streams = sb_select("revenue_streams")
        sales = sb_select("sales")
        products = sb_select("products")
        total_revenue = sum(s.get("amount", 0) for s in sales)
        by_niche = {}
        for p in products:
            n = p.get("niche") or "unassigned"
            by_niche[n] = by_niche.get(n, 0) + 1
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


# ==================== HEALTH ====================

@api_router.get("/")
async def root():
    return {"message": "AI Empire API", "status": "running", "version": "2.0"}

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "gumroad_configured": bool(os.getenv("GUMROAD_ACCESS_TOKEN")),
        "supabase_configured": bool(SUPABASE_KEY),
        "product_types_supported": list(PRODUCT_GENERATORS.keys()),
    }


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
