from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from app.services.enhanced_ai_service import EnhancedAIService
from app.services.microsoft_graph_service import MicrosoftGraphService

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request validation
class AuthRequest(BaseModel):
    access_token: str

class TeamsMessageRequest(BaseModel):
    recipient: str
    message: str
    chat_id: Optional[str] = None

class EmailRequest(BaseModel):
    to: str
    subject: str
    message: str
    cc: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None

class QuickActionRequest(BaseModel):
    action: str
    data: Optional[Dict[str, Any]] = None

# Store sessions (use Redis or proper session management in production)
user_sessions = {}

def get_access_token(request: Request) -> Optional[str]:
    """Get access token from session"""
    client_host = request.client.host if request.client else "unknown"
    return user_sessions.get(client_host, {}).get('access_token')

def require_auth(request: Request) -> str:
    """Require authentication and return access token"""
    token = get_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated with Microsoft")
    return token

@router.post("/auth")
async def authenticate(request: AuthRequest, req: Request):
    """Store Microsoft Graph access token"""
    try:
        client_host = req.client.host if req.client else "unknown"
        if client_host not in user_sessions:
            user_sessions[client_host] = {}
        user_sessions[client_host]['access_token'] = request.access_token
        
        # Test the token by making a simple Graph API call
        graph_service = MicrosoftGraphService(request.access_token)
        user_info = graph_service.get_user_profile()
        
        if user_info:
            return {
                "success": True,
                "message": "Authentication successful",
                "user": user_info
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid access token")
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.post("/logout")
async def logout(request: Request):
    """Remove access token from session"""
    client_host = request.client.host if request.client else "unknown"
    if client_host in user_sessions:
        user_sessions[client_host].pop('access_token', None)
    
    return {"success": True, "message": "Logged out successfully"}

@router.get("/auth/status")
async def auth_status(request: Request):
    """Check authentication status"""
    token = get_access_token(request)
    return {
        "authenticated": bool(token),
        "message": "Connected to Microsoft" if token else "Not connected to Microsoft"
    }

# Teams endpoints
@router.get("/teams/messages/today")
async def get_teams_messages_today(request: Request):
    """Get today's Teams messages"""
    try:
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        result = ai_service._handle_teams_messages_today("Get today's Teams messages")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Teams messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/teams/send")
async def send_teams_message(data: TeamsMessageRequest, request: Request):
    """Send a Teams message"""
    try:
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        
        query = f"Send Teams message to {data.recipient}: {data.message}"
        result = ai_service._handle_teams_send_message(query)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Teams message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/teams/chats")
async def get_teams_chats(request: Request):
    """Get Teams chats"""
    try:
        access_token = require_auth(request)
        graph_service = MicrosoftGraphService(access_token)
        chats = graph_service.get_teams_chats()
        return {"chats": chats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Teams chats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/teams/summarize")
async def summarize_teams_chat(request: Request):
    """Summarize a Teams chat"""
    try:
        data = await request.json()
        chat_id = data.get('chat_id')
        
        if not chat_id:
            raise HTTPException(status_code=400, detail="chat_id is required")
        
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        
        query = f"Summarize Teams chat {chat_id}"
        result = ai_service._handle_teams_summarize(query)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing Teams chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Outlook endpoints
@router.get("/outlook/emails/today")
async def get_emails_today(request: Request):
    """Get today's emails"""
    try:
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        result = ai_service._handle_emails_today("Get today's emails")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/outlook/send")
async def send_email(data: EmailRequest, request: Request):
    """Send an email"""
    try:
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        
        query = f"Send email to {data.to} with subject '{data.subject}': {data.message}"
        if data.cc:
            query += f" (CC: {data.cc})"
        
        result = ai_service._handle_email_send(query)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/outlook/draft")
async def draft_email(request: Request):
    """Draft an email with AI assistance"""
    try:
        data = await request.json()
        recipient = data.get('recipient')
        topic = data.get('topic')
        context = data.get('context', '')
        
        if not recipient or not topic:
            raise HTTPException(status_code=400, detail="recipient and topic are required")
        
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        
        query = f"Draft email to {recipient} about {topic}. Context: {context}"
        result = ai_service._handle_email_draft(query)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error drafting email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/outlook/folders")
async def get_email_folders(request: Request):
    """Get email folders"""
    try:
        access_token = require_auth(request)
        graph_service = MicrosoftGraphService(access_token)
        folders = graph_service.get_email_folders()
        return {"folders": folders}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email folders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Quick actions and utilities
@router.post("/quick-actions")
async def quick_actions(data: QuickActionRequest, request: Request):
    """Handle quick actions"""
    try:
        access_token = require_auth(request)
        ai_service = EnhancedAIService(access_token)
        
        if data.action == 'daily_summary':
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
        
        elif data.action == 'quick_response_mode':
            return {
                "type": "quick_response_mode",
                "response": "Quick response mode activated! You can now say things like 'reply yes' or 'send thanks' and I'll help you respond to your messages.",
                "requires_action": True,
                "actions": ["show_recent_messages", "help"]
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {data.action}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in quick actions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/profile")
async def get_user_profile(request: Request):
    """Get user profile from Microsoft Graph"""
    try:
        access_token = require_auth(request)
        graph_service = MicrosoftGraphService(access_token)
        profile = graph_service.get_user_profile()
        return {"profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))