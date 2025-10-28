# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from app.routes import coworker, ask  # Add ask import

# app = FastAPI()

# # Enable CORS for frontend
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Change later to only allow your domain
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Register routes
# app.include_router(ask.router, prefix="/api")      # Add this line
# app.include_router(coworker.router, prefix="/api") # Add prefix here too

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
import logging

# Import your existing routes
from app.routes.ask import router as ask_router
from app.routes.coworker import router as coworker_router

# Import new Microsoft Graph routes (you'll need to convert this to FastAPI too)
# from app.routes.microsoft import router as microsoft_router

# Import the enhanced AI service
from app.services.enhanced_ai_service import EnhancedAIService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Assistant with Microsoft Graph Integration",
    description="Enhanced AI assistant with Microsoft Teams and Outlook integration",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store session data (in production, use Redis or proper session management)
user_sessions = {}

# Include routers
app.include_router(ask_router, prefix="/api", tags=["AI Chat"])
app.include_router(coworker_router, prefix="/api", tags=["Coworker"])
# app.include_router(microsoft_router, prefix="/api/microsoft", tags=["Microsoft Graph"])

@app.get("/")
async def home():
    return {"message": "AI Assistant with Microsoft Graph Integration"}

@app.post("/api/chat")
async def enhanced_chat(request: Request):
    """Enhanced chat endpoint that can handle Microsoft Graph integration"""
    try:
        data = await request.json()
        user_message = data.get('message', '')
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Get user's access token if available (you'll need to implement session management)
        # For now, we'll use a simple in-memory store
        client_host = request.client.host if request.client else "unknown"
        access_token = user_sessions.get(client_host, {}).get('access_token')
        
        # Initialize enhanced AI service
        ai_service = EnhancedAIService(access_token)
        
        # Process the query
        result = ai_service.process_user_query(user_message)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in enhanced_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check if user is authenticated with Microsoft"""
    client_host = request.client.host if request.client else "unknown"
    token = user_sessions.get(client_host, {}).get('access_token')
    
    return {
        "authenticated": bool(token),
        "message": "Connected to Microsoft" if token else "Not connected to Microsoft"
    }

@app.post("/api/microsoft/auth")
async def microsoft_auth(request: Request):
    """Handle Microsoft authentication (store token)"""
    try:
        data = await request.json()
        access_token = data.get('access_token')
        
        if not access_token:
            raise HTTPException(status_code=400, detail="Access token is required")
        
        # Store token in session (implement proper session management in production)
        client_host = request.client.host if request.client else "unknown"
        if client_host not in user_sessions:
            user_sessions[client_host] = {}
        user_sessions[client_host]['access_token'] = access_token
        
        return {"message": "Authentication successful", "authenticated": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in microsoft_auth: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.post("/api/microsoft/logout")
async def microsoft_logout(request: Request):
    """Handle Microsoft logout"""
    client_host = request.client.host if request.client else "unknown"
    if client_host in user_sessions:
        user_sessions[client_host].pop('access_token', None)
    
    return {"message": "Logged out successfully", "authenticated": False}

@app.post("/api/microsoft/quick-actions")
async def microsoft_quick_actions(request: Request):
    """Handle quick actions for Microsoft Graph integration"""
    try:
        data = await request.json()
        action = data.get('action')
        
        client_host = request.client.host if request.client else "unknown"
        access_token = user_sessions.get(client_host, {}).get('access_token')
        
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated with Microsoft")
        
        ai_service = EnhancedAIService(access_token)
        
        if action == 'get_daily_summary':
            # Get both Teams and Outlook summary
            teams_result = ai_service._handle_teams_messages_today("teams messages today")
            emails_result = ai_service._handle_emails_today("emails today")
            
            summary_prompt = f"""
            Create a daily summary for the user:
            
            Teams Activity:
            {teams_result.get('response', 'No Teams activity')}
            
            Email Activity:
            {emails_result.get('response', 'No email activity')}
            
            Provide a brief, friendly daily overview and ask what they'd like to focus on.
            """
            
            daily_summary = ai_service.ai_service.generate_response(summary_prompt)
            
            return {
                "type": "daily_summary",
                "response": daily_summary,
                "data": {
                    "teams": teams_result.get('data', {}),
                    "emails": emails_result.get('data', {})
                }
            }
        
        elif action == 'quick_response_mode':
            # Enable quick response mode for Teams/Email
            return {
                "type": "quick_response_mode",
                "response": "Quick response mode activated! You can now say things like 'reply yes' or 'send thanks' and I'll help you respond to your messages.",
                "requires_action": True,
                "actions": ["show_recent_messages", "help"]
            }
        
        raise HTTPException(status_code=400, detail="Unknown action")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in microsoft_quick_actions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Quick action failed: {str(e)}")

# Microsoft Graph endpoints (you'll need to convert your microsoft.py to FastAPI format)
@app.get("/api/microsoft/teams/messages/today")
async def get_teams_messages_today(request: Request):
    """Get today's Teams messages"""
    try:
        client_host = request.client.host if request.client else "unknown"
        access_token = user_sessions.get(client_host, {}).get('access_token')
        
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated with Microsoft")
        
        ai_service = EnhancedAIService(access_token)
        result = ai_service._handle_teams_messages_today("Get today's Teams messages")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Teams messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Teams messages: {str(e)}")

@app.post("/api/microsoft/teams/send")
async def send_teams_message(request: Request):
    """Send a Teams message"""
    try:
        data = await request.json()
        recipient = data.get('recipient')
        message = data.get('message')
        
        if not recipient or not message:
            raise HTTPException(status_code=400, detail="Recipient and message are required")
        
        client_host = request.client.host if request.client else "unknown"
        access_token = user_sessions.get(client_host, {}).get('access_token')
        
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated with Microsoft")
        
        ai_service = EnhancedAIService(access_token)
        query = f"Send Teams message to {recipient}: {message}"
        result = ai_service._handle_teams_send_message(query)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Teams message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send Teams message: {str(e)}")

@app.get("/api/microsoft/outlook/emails/today")
async def get_emails_today(request: Request):
    """Get today's emails"""
    try:
        client_host = request.client.host if request.client else "unknown"
        access_token = user_sessions.get(client_host, {}).get('access_token')
        
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated with Microsoft")
        
        ai_service = EnhancedAIService(access_token)
        result = ai_service._handle_emails_today("Get today's emails")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting emails: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get emails: {str(e)}")

@app.post("/api/microsoft/outlook/send")
async def send_email(request: Request):
    """Send an email"""
    try:
        data = await request.json()
        to_email = data.get('to')
        subject = data.get('subject')
        message = data.get('message')
        cc = data.get('cc')
        
        if not to_email or not subject or not message:
            raise HTTPException(status_code=400, detail="To, subject, and message are required")
        
        client_host = request.client.host if request.client else "unknown"
        access_token = user_sessions.get(client_host, {}).get('access_token')
        
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated with Microsoft")
        
        ai_service = EnhancedAIService(access_token)
        
        # Build query for AI service
        query = f"Send email to {to_email} with subject '{subject}': {message}"
        if cc:
            query += f" (CC: {cc})"
            
        result = ai_service._handle_email_send(query)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=True if os.getenv('ENVIRONMENT') == 'development' else False
    )