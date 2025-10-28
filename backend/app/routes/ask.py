from fastapi import APIRouter, Request, HTTPException
from app.services.gemini_service import ai_service
from app.models.database import db_manager
import re
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/ask")  
async def ask_ai(request: Request):
    try:
        body = await request.json()
        query = body.get("query", "")
        chat_id = body.get("chat_id", None)
        
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        # If no chat_id provided, create a new one
        if not chat_id:
            chat_id = f"chat_{uuid.uuid4().hex[:8]}"
            success = db_manager.create_chat(chat_id, "New Conversation")
            if not success:
                raise HTTPException(status_code=500, detail="Failed to create chat")
        
        # Get conversation history from database (limit to last 10 messages to avoid token limits)
        conversation_history = db_manager.get_chat_history(chat_id, limit=10)
        
        # Check if user is sharing new personal info to remember
        await extract_and_store_user_info(query)
        
        # Build context more intelligently
        memory_context = ""
        user_memory = db_manager.get_all_user_memory()
        
        # Only add memory context if it's relevant to the query or if it's a greeting
        query_lower = query.lower()
        greeting_keywords = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
        memory_keywords = ['remember', 'know about me', 'who am i', 'my name', 'about me']
        
        should_include_memory = (
            any(keyword in query_lower for keyword in greeting_keywords) or
            any(keyword in query_lower for keyword in memory_keywords) or
            len(conversation_history) == 0  # First message in conversation
        )
        
        if user_memory and should_include_memory:
            # Filter memory to only include safe, relevant information
            safe_memory = {}
            for key, value in user_memory.items():
                # Only include basic, non-sensitive information
                if key in ['name', 'interests', 'profession'] and value:
                    # Clean the value to ensure it's safe
                    clean_value = str(value).strip()
                    if clean_value and len(clean_value) < 100:  # Reasonable length limit
                        safe_memory[key] = clean_value
            
            if safe_memory:
                memory_context = "Context: "
                memory_parts = []
                for key, value in safe_memory.items():
                    memory_parts.append(f"User's {key} is {value}")
                memory_context += ", ".join(memory_parts) + ". "
        
        # Build full prompt with safer context
        # For queries asking about user info, use a different approach to avoid safety blocks
        if memory_context and any(keyword in query_lower for keyword in memory_keywords):
            # Instead of adding context directly to the query, let the AI naturally reference the conversation
            # This avoids triggering safety filters
            full_query = f"Based on our previous conversations, {query}"
        elif memory_context:
            full_query = f"{memory_context}{query}"
        else:
            full_query = query
        
        # Log for debugging (remove in production)
        logger.info(f"Query: {query}")
        logger.info(f"Conversation history length: {len(conversation_history)}")
        
        # Use AI service for all questions - it now handles safety issues internally
        try:
            answer = ai_service.generate_chat_response(full_query, conversation_history)
        except Exception as e:
            logger.error(f"AI service failed: {e}")
            answer = f"I encountered an error: {str(e)}"
        
        # If still blocked, try the retry method (without history to avoid context issues)
        if "safety" in answer.lower() or "can't provide" in answer.lower():
            logger.warning("Response was blocked, trying modified prompt without history")
            answer = ai_service.retry_with_modified_prompt(query)
        
        # Store user message in database
        success = db_manager.add_message(chat_id, "user", query)
        if not success:
            logger.warning(f"Failed to store user message for chat {chat_id}")
        
        # Store AI response in database  
        success = db_manager.add_message(chat_id, "ai", answer)
        if not success:
            logger.warning(f"Failed to store AI response for chat {chat_id}")
        
        return {
            "response": answer,
            "chat_id": chat_id,
            "memory_updated": bool(user_memory)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ask_ai: {str(e)}")
        return {
            "response": f"Sorry, I encountered an error: {str(e)}",
            "error": str(e)
        }
async def extract_and_store_user_info(query: str):
    """Extract and store user information from messages"""
    query_lower = query.lower()
    
    # Extract name
    name_patterns = [
        r"my name is (\w+)",
        r"i'm (\w+)",
        r"i am (\w+)",
        r"call me (\w+)",
        r"name's (\w+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, query_lower)
        if match:
            name = match.group(1).title()
            db_manager.set_user_memory("name", name)
            logger.info(f"Stored user name: {name}")
            break
    
    # Extract workplace
    workplace_patterns = [
        r"i work at (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i work for (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i'm employed at (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"my job is at (.+?)(?:\.|,|$|\s+and|\s+but)"
    ]
    
    for pattern in workplace_patterns:
        match = re.search(pattern, query_lower)
        if match:
            workplace = match.group(1).strip()
            db_manager.set_user_memory("workplace", workplace)
            logger.info(f"Stored workplace: {workplace}")
            break
    
    # Extract location
    location_patterns = [
        r"i live in (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i'm from (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i'm in (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"my location is (.+?)(?:\.|,|$|\s+and|\s+but)"
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, query_lower)
        if match:
            location = match.group(1).strip()
            db_manager.set_user_memory("location", location)
            logger.info(f"Stored location: {location}")
            break
    
    # Extract interests/hobbies
    interest_patterns = [
        r"i like (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i love (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i enjoy (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i'm interested in (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"my hobby is (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i'm passionate about (.+?)(?:\.|,|$|\s+and|\s+but)"
    ]
    
    for pattern in interest_patterns:
        match = re.search(pattern, query_lower)
        if match:
            interest = match.group(1).strip()
            existing_interests = db_manager.get_user_memory("interests") or ""
            if interest not in existing_interests.lower():
                new_interests = f"{existing_interests}, {interest}" if existing_interests else interest
                db_manager.set_user_memory("interests", new_interests)
                logger.info(f"Added interest: {interest}")
            break
    
    # Extract profession/job title
    job_patterns = [
        r"i'm a (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i am a (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i work as a (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"my job is (.+?)(?:\.|,|$|\s+and|\s+but)",
        r"i'm an? (.+?)(?:\.|,|$|\s+and|\s+but)"
    ]
    
    for pattern in job_patterns:
        match = re.search(pattern, query_lower)
        if match:
            job = match.group(1).strip()
            # Filter out common words that aren't job titles
            excluded_words = ['person', 'individual', 'human', 'user', 'student studying']
            if not any(excluded in job.lower() for excluded in excluded_words):
                db_manager.set_user_memory("profession", job)
                logger.info(f"Stored profession: {job}")
            break
    
    # Extract age
    age_patterns = [
        r"i'm (\d+) years old",
        r"i am (\d+) years old",
        r"my age is (\d+)",
        r"i'm (\d+)"
    ]
    
    for pattern in age_patterns:
        match = re.search(pattern, query_lower)
        if match:
            age = match.group(1)
            if 13 <= int(age) <= 120:  # Reasonable age range
                db_manager.set_user_memory("age", age)
                logger.info(f"Stored age: {age}")
            break

@router.get("/chat-history/{chat_id}")
async def get_chat_history(chat_id: str):
    """Get chat history for a specific chat"""
    try:
        history = db_manager.get_chat_history(chat_id)
        
        # FIX: Ensure each message has required fields
        formatted_history = []
        for msg in history:
            formatted_msg = {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp") or msg.get("created_at") or "2024-01-01T00:00:00"
            }
            formatted_history.append(formatted_msg)
        
        return {"history": formatted_history, "chat_id": chat_id}
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")

@router.get("/chats")
async def get_all_chats():
    """Get all chats"""
    try:
        chats = db_manager.get_all_chats()
        return {"chats": chats}
    except Exception as e:
        logger.error(f"Error getting all chats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chats")

@router.post("/chat")
async def create_chat(request: Request):
    """Create a new chat"""
    try:
        body = await request.json()
        chat_id = body.get("chat_id")
        title = body.get("title", "New Conversation")
        
        if not chat_id:
            chat_id = f"chat_{uuid.uuid4().hex[:8]}"
        
        success = db_manager.create_chat(chat_id, title)
        
        if success:
            return {"success": True, "chat_id": chat_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to create chat")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create chat")

@router.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a specific chat"""
    try:
        success = db_manager.delete_chat(chat_id)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Chat not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete chat")

@router.get("/user-memory")
async def get_user_memory():
    """Get all stored user information"""
    try:
        memory = db_manager.get_all_user_memory()
        return {"memory": memory}
    except Exception as e:
        logger.error(f"Error getting user memory: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user memory")

@router.post("/user-memory")
async def set_user_memory(request: Request):
    """Manually set user memory"""
    try:
        body = await request.json()
        key = body.get("key")
        value = body.get("value")
        
        if not key or not value:
            raise HTTPException(status_code=400, detail="Key and value are required")
        
        success = db_manager.set_user_memory(key, value)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to store user memory")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user memory: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to store user memory")

@router.delete("/user-memory/{key}")
async def delete_user_memory(key: str):
    """Delete specific user memory"""
    try:
        # Add this method to your DatabaseManager class
        success = db_manager.delete_user_memory(key)
        
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Memory key not found")
            
    except Exception as e:
        logger.error(f"Error deleting user memory: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete user memory")

@router.get("/chat/{chat_id}/export")
async def export_chat(chat_id: str):
    """Export a chat as JSON"""
    try:
        # Get chat info
        chats = db_manager.get_all_chats()
        chat_info = next((chat for chat in chats if chat['id'] == chat_id), None)
        
        if not chat_info:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Get chat history
        history = db_manager.get_chat_history(chat_id)
        
        export_data = {
            "chat_id": chat_id,
            "title": chat_info['title'],
            "created_at": chat_info['created_at'],
            "messages": history,
            "exported_at": db_manager.get_current_timestamp()
        }
        
        return {"export_data": export_data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export chat")

@router.get("/stats")
async def get_stats():
    """Get usage statistics"""
    try:
        chats = db_manager.get_all_chats()
        total_chats = len(chats)
        
        # Count total messages
        total_messages = 0
        for chat in chats:
            history = db_manager.get_chat_history(chat['id'])
            total_messages += len(history)
        
        user_memory = db_manager.get_all_user_memory()
        
        return {
            "total_chats": total_chats,
            "total_messages": total_messages,
            "user_memory_items": len(user_memory),
            "user_memory": user_memory
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")