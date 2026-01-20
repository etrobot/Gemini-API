"""
FastAPI server for Gemini WebAPI
Provides REST API endpoints compatible with the curl request format.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, List
import tempfile
import aiofiles
import httpx

from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from .client import GeminiClient
from .constants import Model
from .utils import set_log_level

# Set log level to INFO to hide DEBUG messages like cookie refresh
set_log_level("INFO")


class GenerateRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.5-flash"


class ChatRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.5-flash"
    chat_id: Optional[str] = None
    reply_id: Optional[str] = None
    reply_candidate_id: Optional[str] = None


class GenerateResponse(BaseModel):
    text: str
    thoughts: Optional[str] = None
    images: list = []
    chat_metadata: Optional[dict] = None


class ChatResponse(BaseModel):
    text: str
    thoughts: Optional[str] = None
    images: list = []
    chat_id: str
    reply_id: str
    reply_candidate_id: str


class ImageGenerateRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.5-flash"


class ImageEditRequest(BaseModel):
    prompt: str
    model: str = "gemini-2.5-flash"


app = FastAPI(
    title="Gemini WebAPI Server",
    description="REST API server for Gemini WebAPI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global client cache for different users
client_cache = {}


async def get_client_for_cookies(secure_1psid: str, secure_1psidts: Optional[str] = None) -> GeminiClient:
    """Get or create Gemini client instance for specific cookies"""
    cache_key = f"{secure_1psid}:{secure_1psidts or ''}"
    
    if cache_key in client_cache:
        client = client_cache[cache_key]
        if client._running:
            return client
        else:
            # Remove dead client from cache
            del client_cache[cache_key]
    
    # Create new client
    client = GeminiClient(
        secure_1psid=secure_1psid,
        secure_1psidts=secure_1psidts
    )
    
    try:
        await client.init(timeout=30, auto_close=False, auto_refresh=False)
        client_cache[cache_key] = client
        return client
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Failed to initialize Gemini client with provided cookies: {str(e)}"
        )


def extract_cookies_from_request(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract Gemini cookies from request headers"""
    cookie_header = request.headers.get("cookie", "")
    
    secure_1psid = None
    secure_1psidts = None
    
    # Parse cookies from header
    for cookie in cookie_header.split(";"):
        cookie = cookie.strip()
        if cookie.startswith("__Secure-1PSID="):
            secure_1psid = cookie.split("=", 1)[1]
        elif cookie.startswith("__Secure-1PSIDTS="):
            secure_1psidts = cookie.split("=", 1)[1]
    
    return secure_1psid, secure_1psidts


@app.post("/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest, http_request: Request):
    """
    Generate content using Gemini API
    
    Compatible with curl requests like:
    curl -X POST "https://g.subx.fun/generate" \
         -H "Content-Type: application/json" \
         -H "Cookie: __Secure-1PSID=your_psid; __Secure-1PSIDTS=your_psidts" \
         -d '{"prompt":"写一段简短的自我介绍","model":"gemini-2.0-flash-exp"}'
    """
    
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID. Please provide Gemini cookies in the Cookie header."
        )
    
    # Get client for these specific cookies
    current_client = await get_client_for_cookies(req_psid, req_psidts)
    
    # Map model name to Model enum
    model_mapping = {
        "gemini-3.0-pro": Model.G_3_0_PRO,
        "gemini-2.5-pro": Model.G_2_5_PRO,
        "gemini-2.5-flash": Model.G_2_5_FLASH,
        "unspecified": Model.UNSPECIFIED,
    }
    
    model = model_mapping.get(request.model, Model.G_2_5_FLASH)
    
    try:
        # Generate content
        response = await current_client.generate_content(
            prompt=request.prompt,
            model=model
        )
        
        # Extract images information
        images = []
        for img in response.images:
            images.append({
                "url": img.url,
                "title": img.title,
                "alt": img.alt,
                "type": "web" if hasattr(img, "proxy") else "generated"
            })
        
        return GenerateResponse(
            text=response.text,
            thoughts=response.thoughts,
            images=images,
            chat_metadata={
                "chat_id": response.metadata[0] if len(response.metadata) > 0 else None,
                "reply_id": response.metadata[1] if len(response.metadata) > 1 else None,
                "reply_candidate_id": response.rcid
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate content: {str(e)}"
        )


@app.post("/chat", response_model=ChatResponse)
async def chat_with_history(request: ChatRequest, http_request: Request):
    """
    Chat with conversation history support
    
    Example:
    curl -X POST "https://g.subx.fun/chat" \
         -H "Content-Type: application/json" \
         -H "Cookie: __Secure-1PSID=your_psid; __Secure-1PSIDTS=your_psidts" \
         -d '{"prompt":"你好","model":"gemini-2.5-flash"}'
    """
    
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID. Please provide Gemini cookies in the Cookie header."
        )
    
    # Get client for these specific cookies
    current_client = await get_client_for_cookies(req_psid, req_psidts)
    
    # Map model name to Model enum
    model_mapping = {
        "gemini-3.0-pro": Model.G_3_0_PRO,
        "gemini-2.5-pro": Model.G_2_5_PRO,
        "gemini-2.5-flash": Model.G_2_5_FLASH,
        "unspecified": Model.UNSPECIFIED,
    }
    
    model = model_mapping.get(request.model, Model.G_2_5_FLASH)
    
    try:
        # Create chat session with metadata if provided
        metadata = []
        if request.chat_id:
            metadata.append(request.chat_id)
        if request.reply_id:
            metadata.append(request.reply_id)
        if request.reply_candidate_id:
            metadata.append(request.reply_candidate_id)
        
        chat = current_client.start_chat(
            metadata=metadata if metadata else None,
            model=model
        )
        
        # Send message
        response = await chat.send_message(request.prompt)
        
        # Extract images information
        images = []
        for img in response.images:
            images.append({
                "url": img.url,
                "title": img.title,
                "alt": img.alt,
                "type": "web" if hasattr(img, "proxy") else "generated"
            })
        
        return ChatResponse(
            text=response.text,
            thoughts=response.thoughts,
            images=images,
            chat_id=response.metadata[0] if len(response.metadata) > 0 else "",
            reply_id=response.metadata[1] if len(response.metadata) > 1 else "",
            reply_candidate_id=response.rcid
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to chat: {str(e)}"
        )


@app.post("/generate-image", response_model=GenerateResponse)
async def generate_image(request: ImageGenerateRequest, http_request: Request):
    """
    Generate images using Gemini
    
    Example:
    curl -X POST "https://g.subx.fun/generate-image" \
         -H "Content-Type: application/json" \
         -H "Cookie: __Secure-1PSID=your_psid; __Secure-1PSIDTS=your_psidts" \
         -d '{"prompt":"Generate a cute cat image","model":"gemini-2.5-flash"}'
    """
    
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID. Please provide Gemini cookies in the Cookie header."
        )
    
    # Get client for these specific cookies
    current_client = await get_client_for_cookies(req_psid, req_psidts)
    
    # Map model name to Model enum
    model_mapping = {
        "gemini-3.0-pro": Model.G_3_0_PRO,
        "gemini-2.5-pro": Model.G_2_5_PRO,
        "gemini-2.5-flash": Model.G_2_5_FLASH,
        "unspecified": Model.UNSPECIFIED,
    }
    
    model = model_mapping.get(request.model, Model.G_2_5_FLASH)
    
    try:
        # Try different prompt variations for image generation
        prompts_to_try = [
            f"Create an image of {request.prompt}",
            f"Generate a picture showing {request.prompt}",
            f"Draw {request.prompt}",
            f"Make an image: {request.prompt}"
        ]
        
        last_error = None
        
        for prompt_variation in prompts_to_try:
            try:
                # Generate content
                response = await current_client.generate_content(
                    prompt=prompt_variation,
                    model=model
                )
                
                # Extract images information
                images = []
                
                # Check for generated images first
                for img in response.images:
                    if hasattr(img, 'url') and img.url:
                        images.append({
                            "url": img.url,
                            "title": getattr(img, 'title', 'Generated Image'),
                            "alt": getattr(img, 'alt', ''),
                            "type": "generated" if 'googleusercontent.com/image_generation_content' in img.url else "web"
                        })
                
                # If we got images, return success
                if images:
                    return GenerateResponse(
                        text=response.text,
                        thoughts=response.thoughts,
                        images=images,
                        chat_metadata={
                            "chat_id": response.metadata[0] if len(response.metadata) > 0 else None,
                            "reply_id": response.metadata[1] if len(response.metadata) > 1 else None,
                            "reply_candidate_id": response.rcid
                        }
                    )
                
                # If no images but got text response, continue to next prompt
                last_error = f"No images generated with prompt: {prompt_variation}"
                
            except Exception as e:
                last_error = str(e)
                continue
        
        # If all prompts failed, raise the last error
        raise Exception(last_error or "Failed to generate image with all prompt variations")
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate image: {str(e)}"
        )


@app.post("/test-image-gen")
async def test_image_generation(http_request: Request):
    """
    Simple test endpoint for image generation debugging
    """
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID"
        )
    
    # Get client for these specific cookies
    current_client = await get_client_for_cookies(req_psid, req_psidts)
    
    try:
        # Simple test prompt
        response = await current_client.generate_content(
            prompt="Create a simple drawing of a red apple",
            model=Model.G_2_5_FLASH
        )
        
        return {
            "success": True,
            "text": response.text,
            "images_count": len(response.images),
            "images": [{"url": img.url, "title": getattr(img, 'title', 'Image')} for img in response.images],
            "thoughts": response.thoughts
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.post("/edit-image", response_model=GenerateResponse)
async def edit_image(
    prompt: str = Form(...),
    model: str = Form("gemini-2.5-flash"),
    image: UploadFile = File(...),
    http_request: Request = None
):
    """
    Edit images using Gemini
    
    Example:
    curl -X POST "https://g.subx.fun/edit-image" \
         -H "Cookie: __Secure-1PSID=your_psid; __Secure-1PSIDTS=your_psidts" \
         -F "prompt=Make this image more colorful" \
         -F "model=gemini-2.5-flash" \
         -F "image=@/path/to/image.jpg"
    """
    
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID. Please provide Gemini cookies in the Cookie header."
        )
    
    # Get client for these specific cookies
    current_client = await get_client_for_cookies(req_psid, req_psidts)
    
    # Map model name to Model enum
    model_mapping = {
        "gemini-3.0-pro": Model.G_3_0_PRO,
        "gemini-2.5-pro": Model.G_2_5_PRO,
        "gemini-2.5-flash": Model.G_2_5_FLASH,
        "unspecified": Model.UNSPECIFIED,
    }
    
    model_enum = model_mapping.get(model, Model.G_2_5_FLASH)
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(image.filename).suffix) as temp_file:
            content = await image.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Generate content with image
            response = await current_client.generate_content(
                prompt=f"Edit this image: {prompt}",
                files=[temp_file_path],
                model=model_enum
            )
            
            # Extract images information
            images = []
            for img in response.images:
                images.append({
                    "url": img.url,
                    "title": img.title,
                    "alt": img.alt,
                    "type": "web" if hasattr(img, "proxy") else "generated"
                })
            
            return GenerateResponse(
                text=response.text,
                thoughts=response.thoughts,
                images=images,
                chat_metadata={
                    "chat_id": response.metadata[0] if len(response.metadata) > 0 else None,
                    "reply_id": response.metadata[1] if len(response.metadata) > 1 else None,
                    "reply_candidate_id": response.rcid
                }
            )
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to edit image: {str(e)}"
        )


@app.post("/generate-with-files", response_model=GenerateResponse)
async def generate_with_files(
    prompt: str = Form(...),
    model: str = Form("gemini-2.5-flash"),
    files: List[UploadFile] = File(...),
    http_request: Request = None
):
    """
    Generate content with file attachments
    
    Example:
    curl -X POST "https://g.subx.fun/generate-with-files" \
         -H "Cookie: __Secure-1PSID=your_psid; __Secure-1PSIDTS=your_psidts" \
         -F "prompt=Analyze these files" \
         -F "model=gemini-2.5-flash" \
         -F "files=@/path/to/file1.pdf" \
         -F "files=@/path/to/file2.jpg"
    """
    
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID. Please provide Gemini cookies in the Cookie header."
        )
    
    # Get client for these specific cookies
    current_client = await get_client_for_cookies(req_psid, req_psidts)
    
    # Map model name to Model enum
    model_mapping = {
        "gemini-3.0-pro": Model.G_3_0_PRO,
        "gemini-2.5-pro": Model.G_2_5_PRO,
        "gemini-2.5-flash": Model.G_2_5_FLASH,
        "unspecified": Model.UNSPECIFIED,
    }
    
    model_enum = model_mapping.get(model, Model.G_2_5_FLASH)
    
    temp_files = []
    try:
        # Save uploaded files temporarily
        for file in files:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix)
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            temp_files.append(temp_file.name)
        
        # Generate content with files
        response = await current_client.generate_content(
            prompt=prompt,
            files=temp_files,
            model=model_enum
        )
        
        # Extract images information
        images = []
        for img in response.images:
            images.append({
                "url": img.url,
                "title": img.title,
                "alt": img.alt,
                "type": "web" if hasattr(img, "proxy") else "generated"
            })
        
        return GenerateResponse(
            text=response.text,
            thoughts=response.thoughts,
            images=images,
            chat_metadata={
                "chat_id": response.metadata[0] if len(response.metadata) > 0 else None,
                "reply_id": response.metadata[1] if len(response.metadata) > 1 else None,
                "reply_candidate_id": response.rcid
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate content with files: {str(e)}"
        )
    finally:
        # Clean up temporary files
        for temp_file_path in temp_files:
            try:
                os.unlink(temp_file_path)
            except:
                pass


@app.get("/download-image")
async def download_image(url: str, http_request: Request):
    """
    Proxy download for generated images using GeneratedImage.save()
    """
    
    # Extract cookies from request header
    req_psid, req_psidts = extract_cookies_from_request(http_request)
    
    if not req_psid:
        raise HTTPException(
            status_code=400,
            detail="Missing required cookie: __Secure-1PSID"
        )
    
    try:
        from .types import GeneratedImage
        import tempfile
        import os
        
        # Get the initialized client which has all the necessary cookies
        current_client = await get_client_for_cookies(req_psid, req_psidts)
        
        # Use the client's cookies (which include all necessary cookies from initialization)
        cookies = current_client.cookies
            
        # Create GeneratedImage instance with the complete cookies
        generated_image = GeneratedImage(
            url=url,
            title="Downloaded Image",
            cookies=cookies
        )
        
        # Use temporary directory to save the image
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save the image using the built-in method
            saved_path = await generated_image.save(
                path=temp_dir,
                filename="temp_image.png",
                verbose=False
            )
            
            if saved_path and os.path.exists(saved_path):
                # Read the saved file and return its content
                with open(saved_path, "rb") as f:
                    image_content = f.read()
                
                return Response(
                    content=image_content,
                    media_type="image/png",
                    headers={
                        "Content-Disposition": "inline",
                        "Cache-Control": "public, max-age=3600"
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to save image"
                )
                
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading image: {str(e)}"
        )


@app.get("/")
async def root():
    """API information and available endpoints"""
    return {
        "service": "Gemini WebAPI Server",
        "version": "1.0.0",
        "endpoints": {
            "/generate": {
                "method": "POST",
                "description": "Generate text content",
                "example": 'curl -X POST "https://g.subx.fun/generate" -H "Content-Type: application/json" -H "Cookie: __Secure-1PSID=xxx; __Secure-1PSIDTS=xxx" -d \'{"prompt":"Hello","model":"gemini-2.5-flash"}\''
            },
            "/chat": {
                "method": "POST", 
                "description": "Chat with conversation history",
                "example": 'curl -X POST "https://g.subx.fun/chat" -H "Content-Type: application/json" -H "Cookie: __Secure-1PSID=xxx; __Secure-1PSIDTS=xxx" -d \'{"prompt":"Hello","model":"gemini-2.5-flash"}\''
            },
            "/generate-image": {
                "method": "POST",
                "description": "Generate images",
                "example": 'curl -X POST "https://g.subx.fun/generate-image" -H "Content-Type: application/json" -H "Cookie: __Secure-1PSID=xxx; __Secure-1PSIDTS=xxx" -d \'{"prompt":"A cute cat","model":"gemini-2.5-flash"}\''
            },
            "/edit-image": {
                "method": "POST",
                "description": "Edit images with multipart form",
                "example": 'curl -X POST "https://g.subx.fun/edit-image" -H "Cookie: __Secure-1PSID=xxx; __Secure-1PSIDTS=xxx" -F "prompt=Make colorful" -F "image=@image.jpg"'
            },
            "/generate-with-files": {
                "method": "POST",
                "description": "Generate content with file attachments",
                "example": 'curl -X POST "https://g.subx.fun/generate-with-files" -H "Cookie: __Secure-1PSID=xxx; __Secure-1PSIDTS=xxx" -F "prompt=Analyze" -F "files=@file.pdf"'
            },
            "/models": {
                "method": "GET",
                "description": "List available models"
            },
            "/health": {
                "method": "GET", 
                "description": "Health check"
            }
        },
        "authentication": "Provide __Secure-1PSID and __Secure-1PSIDTS cookies in Cookie header"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "gemini-webapi"}


@app.get("/models")
async def list_models():
    """List available models"""
    return {
        "models": [
            {
                "name": "gemini-3.0-pro",
                "description": "Gemini 3.0 Pro"
            },
            {
                "name": "gemini-2.5-pro", 
                "description": "Gemini 2.5 Pro"
            },
            {
                "name": "gemini-2.5-flash",
                "description": "Gemini 2.5 Flash (Default)"
            },
            {
                "name": "unspecified",
                "description": "Unspecified model"
            }
        ]
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    for client in client_cache.values():
        if client._running:
            await client.close()
    client_cache.clear()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)