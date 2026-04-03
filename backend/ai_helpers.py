"""Helper functions for AI generation"""
import base64
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
import os


async def generate_with_openai(api_key: str, prompt: str) -> str:
    """Generate image using OpenAI DALL-E"""
    image_gen = OpenAIImageGeneration(api_key=api_key)
    images = await image_gen.generate_images(
        prompt=prompt,
        model="gpt-image-1",
        number_of_images=1
    )
    
    if not images or len(images) == 0:
        raise ValueError("No image generated")
    
    return base64.b64encode(images[0]).decode('utf-8')


async def generate_with_gemini(api_key: str, prompt: str) -> str:
    """Generate image using Google Gemini"""
    chat = LlmChat(
        api_key=api_key,
        session_id=str(uuid.uuid4()),
        system_message="You are an AI image generator"
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"]
    )
    
    msg = UserMessage(text=prompt)
    text, images = await chat.send_message_multimodal_response(msg)
    
    if not images or len(images) == 0:
        raise ValueError("No image generated")
    
    return images[0]['data']


def create_product_data(product_type: str, prompt: str, content: str, price: float) -> dict:
    """Create product data dictionary for database"""
    name_prefix = "AI Art" if product_type == "image" else "AI Generated Content"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    return {
        "id": str(uuid.uuid4()),
        "name": f"{name_prefix} - {timestamp}",
        "description": prompt[:200],
        "product_type": product_type,
        "content": content,
        "price": price,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "listed_on": [],
        "status": "draft"
    }
