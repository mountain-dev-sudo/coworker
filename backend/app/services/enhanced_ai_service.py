from app.services.microsoft_graph_service import MicrosoftGraphService
from app.services.gemini_service import GeminiService
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class EnhancedAIService:
    """Enhanced AI service that integrates with Microsoft Graph for Teams and Outlook"""
    
    def __init__(self, access_token: str = None):
        self.ai_service = GeminiService()
        self.graph_service = MicrosoftGraphService()
        if access_token:
            self.graph_service.set_access_token(access_token)

    def process_user_query(self, query: str, user_context: Dict = None) -> Dict:
        """Process user query and determine if it needs Microsoft Graph integration"""
        
        query_lower = query.lower()
        
        # Intent detection patterns
        intent_patterns = {
            'teams_messages_today': ['teams messages today', 'teams today', 'new messages teams', 'what\'s new in teams'],
            'outlook_emails_today': ['emails today', 'new emails', 'outlook today', 'mail today'],
            'send_teams_message': ['send teams message', 'message someone teams', 'teams send'],
            'send_email': ['send email', 'email someone', 'compose email'],
            'summarize_teams_chat': ['summarize teams', 'summarize chat', 'teams summary'],
            'summarize_emails': ['summarize emails', 'email summary', 'summarize mail']
        }
        
        detected_intent = None
        for intent, patterns in intent_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                detected_intent = intent
                break
        
        if not detected_intent:
            # Regular AI query
            response = self.ai_service.generate_response(query)
            return {
                "type": "regular_ai_response",
                "response": response,
                "requires_action": False
            }
        
        # Handle Microsoft Graph intents
        return self._handle_microsoft_intent(detected_intent, query, user_context)

    def _handle_microsoft_intent(self, intent: str, query: str, user_context: Dict = None) -> Dict:
        """Handle intents that require Microsoft Graph integration"""
        
        try:
            if intent == 'teams_messages_today':
                return self._handle_teams_messages_today(query)
            
            elif intent == 'outlook_emails_today':
                return self._handle_emails_today(query)
            
            elif intent == 'send_teams_message':
                return self._handle_send_teams_message(query)
            
            elif intent == 'send_email':
                return self._handle_send_email(query)
            
            elif intent == 'summarize_teams_chat':
                return self._handle_summarize_teams_chat(query)
            
            elif intent == 'summarize_emails':
                return self._handle_summarize_emails(query)
            
        except Exception as e:
            return {
                "type": "error",
                "response": f"I encountered an error while trying to help you: {str(e)}",
                "requires_action": False
            }

    def _handle_teams_messages_today(self, query: str) -> Dict:
        """Handle request for today's Teams messages"""
        messages = self.graph_service.get_todays_teams_messages()
        
        if not messages:
            return {
                "type": "teams_messages",
                "response": "You don't have any new Teams messages today.",
                "requires_action": False,
                "data": {"messages": []}
            }
        
        # Use AI to create a friendly summary
        formatted_messages = self.graph_service.summarize_chat_messages(messages[:10])  # Limit to 10 recent
        
        prompt = f"""
        Here are the user's Teams messages from today. Create a friendly, conversational summary:
        
        {formatted_messages}
        
        Make it sound like you're a helpful assistant telling them about their day's messages.
        Mention the most important ones and ask if they want to respond to any.
        """
        
        ai_summary = self.ai_service.generate_response(prompt)
        
        return {
            "type": "teams_messages",
            "response": ai_summary,
            "requires_action": True,
            "actions": ["respond_to_message", "mark_as_read", "get_more_details"],
            "data": {
                "messages": messages[:10],
                "total_count": len(messages)
            }
        }

    def _handle_emails_today(self, query: str) -> Dict:
        """Handle request for today's emails"""
        emails = self.graph_service.get_todays_emails()
        
        if not emails:
            return {
                "type": "outlook_emails",
                "response": "You don't have any new emails today.",
                "requires_action": False,
                "data": {"emails": []}
            }
        
        # Use AI to create a summary
        formatted_emails = self.graph_service.format_emails_for_ai(emails[:10])
        
        prompt = f"""
        Here are the user's emails from today. Create a helpful summary:
        
        {formatted_emails}
        
        Highlight the most important ones, mention any that need urgent attention,
        and ask if they want to respond to any.
        """
        
        ai_summary = self.ai_service.generate_response(prompt)
        
        return {
            "type": "outlook_emails",
            "response": ai_summary,
            "requires_action": True,
            "actions": ["reply_to_email", "compose_email", "mark_as_read"],
            "data": {
                "emails": emails[:10],
                "total_count": len(emails)
            }
        }

    def _handle_send_teams_message(self, query: str) -> Dict:
        """Handle request to send a Teams message"""
        # Extract message content and recipient info from query
        message_info = self._extract_message_info(query, "teams")
        
        if not message_info.get('content'):
            return {
                "type": "teams_send",
                "response": "I'd be happy to help you send a Teams message! What would you like to say and to whom?",
                "requires_action": True,
                "actions": ["specify_recipient", "compose_message"],
                "data": {}
            }
        
        # Get user's chats to find the right recipient
        chats = self.graph_service.get_my_chats()
        
        # Use AI to help craft the message
        prompt = f"""
        The user wants to send this Teams message: "{message_info['content']}"
        
        Please help them by:
        1. Reviewing if the message is clear and professional
        2. Suggesting any improvements
        3. Asking if they want to add any context
        4. Confirming they want to send it
        
        Be conversational and helpful, like a personal assistant.
        """
        
        ai_response = self.ai_service.generate_response(prompt)
        
        return {
            "type": "teams_send",
            "response": ai_response,
            "requires_action": True,
            "actions": ["confirm_send", "edit_message", "cancel"],
            "data": {
                "message": message_info['content'],
                "chats": chats[:10],  # Show recent chats for selection
                "recipient": message_info.get('recipient')
            }
        }

    def _handle_send_email(self, query: str) -> Dict:
        """Handle request to send an email"""
        email_info = self._extract_email_info(query)
        
        if not email_info.get('content') or not email_info.get('subject'):
            return {
                "type": "email_send",
                "response": "I'll help you compose an email! Please provide the recipient, subject, and message content.",
                "requires_action": True,
                "actions": ["specify_recipient", "add_subject", "compose_body"],
                "data": {}
            }
        
        # Use AI to review the email
        prompt = f"""
        The user wants to send this email:
        To: {email_info.get('recipient', 'Not specified')}
        Subject: {email_info.get('subject', '')}
        Body: {email_info.get('content', '')}
        
        Please review and provide suggestions:
        1. Is the tone appropriate?
        2. Should they add CC recipients?
        3. Any improvements to subject or content?
        4. Do they need attachments?
        5. Ask if they're ready to send
        
        Be helpful and conversational.
        """
        
        ai_response = self.ai_service.generate_response(prompt)
        
        return {
            "type": "email_send",
            "response": ai_response,
            "requires_action": True,
            "actions": ["confirm_send", "add_cc", "add_attachment", "edit_email"],
            "data": {
                "email": email_info
            }
        }

    def _handle_summarize_teams_chat(self, query: str) -> Dict:
        """Handle request to summarize Teams chat"""
        # Get recent Teams messages
        messages = self.graph_service.get_todays_teams_messages()
        
        if not messages:
            return {
                "type": "teams_summary",
                "response": "You don't have any Teams messages to summarize today.",
                "requires_action": False,
                "data": {}
            }
        
        # Group messages by chat
        chats_summary = {}
        for msg in messages:
            chat_id = msg.get('chat_info', {}).get('chat_id')
            topic = msg.get('chat_info', {}).get('topic', 'Unknown Chat')
            
            if chat_id not in chats_summary:
                chats_summary[chat_id] = {
                    'topic': topic,
                    'messages': []
                }
            chats_summary[chat_id]['messages'].append(msg)
        
        # Summarize each chat
        summaries = []
        for chat_id, chat_data in chats_summary.items():
            formatted_messages = self.graph_service.summarize_chat_messages(chat_data['messages'])
            
            prompt = f"""
            Summarize this Teams chat conversation:
            Chat: {chat_data['topic']}
            
            {formatted_messages}
            
            Provide a brief summary of:
            1. Main topics discussed
            2. Any decisions made
            3. Action items
            """
            
            summary = self.ai_service.generate_response(prompt)
            summaries.append({
                'chat_topic': chat_data['topic'],
                'summary': summary,
                'message_count': len(chat_data['messages'])
            })
        
        # Create overall summary
        overall_prompt = f"""
        Here are summaries of the user's Teams chats today:
        
        {chr(10).join([f"Chat: {s['chat_topic']}\n{s['summary']}" for s in summaries])}
        
        Create a friendly overview of their Teams activity today.
        """
        
        overall_summary = self.ai_service.generate_response(overall_prompt)
        
        return {
            "type": "teams_summary",
            "response": overall_summary,
            "requires_action": True,
            "actions": ["get_chat_details", "respond_to_chat"],
            "data": {
                "chat_summaries": summaries,
                "total_messages": len(messages)
            }
        }

    def _handle_summarize_emails(self, query: str) -> Dict:
        """Handle request to summarize emails"""
        emails = self.graph_service.get_todays_emails()
        
        if not emails:
            return {
                "type": "email_summary",
                "response": "You don't have any emails to summarize today.",
                "requires_action": False,
                "data": {}
            }
        
        formatted_emails = self.graph_service.format_emails_for_ai(emails[:15])
        
        prompt = f"""
        Summarize these emails for the user:
        
        {formatted_emails}
        
        Organize by:
        1. Most urgent/important emails
        2. Emails requiring response
        3. FYI/informational emails
        4. Overall themes/topics
        
        Be conversational and helpful.
        """
        
        summary = self.ai_service.generate_response(prompt)
        
        return {
            "type": "email_summary",
            "response": summary,
            "requires_action": True,
            "actions": ["reply_to_email", "mark_important", "schedule_response"],
            "data": {
                "emails": emails[:15],
                "total_count": len(emails)
            }
        }

    def _extract_message_info(self, query: str, platform: str) -> Dict:
        """Extract message information from user query"""
        info = {}
        
        # Simple regex patterns to extract content
        message_patterns = [
            r'send\s+(?:him|her|them)?\s*["\']([^"\']+)["\']',
            r'message\s+(?:him|her|them)?\s*["\']([^"\']+)["\']',
            r'tell\s+(?:him|her|them)?\s*["\']([^"\']+)["\']',
            r'say\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in message_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info['content'] = match.group(1)
                break
        
        # Extract recipient info
        recipient_patterns = [
            r'(?:to|message)\s+([A-Za-z\s]+)(?:\s+that|\s+to|\s+about)',
            r'(?:send|tell)\s+([A-Za-z\s]+)\s+that'
        ]
        
        for pattern in recipient_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info['recipient'] = match.group(1).strip()
                break
        
        return info

    def _extract_email_info(self, query: str) -> Dict:
        """Extract email information from user query"""
        info = {}
        
        # Extract email content
        content_patterns = [
            r'email\s+(?:him|her|them)?\s*["\']([^"\']+)["\']',
            r'send\s+(?:an\s+)?email\s+["\']([^"\']+)["\']',
            r'compose\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info['content'] = match.group(1)
                break
        
        # Extract subject
        subject_patterns = [
            r'subject\s+["\']([^"\']+)["\']',
            r'about\s+["\']([^"\']+)["\']'
        ]
        
        for pattern in subject_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info['subject'] = match.group(1)
                break
        
        # Extract recipient
        recipient_patterns = [
            r'(?:to|email)\s+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'(?:to|email)\s+([A-Za-z\s]+)(?:\s+that|\s+to|\s+about)'
        ]
        
        for pattern in recipient_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info['recipient'] = match.group(1).strip()
                break
        
        return info

    def generate_contextual_response(self, query: str, context_type: str, context_data: Dict) -> str:
        """Generate contextual AI responses based on Microsoft Graph data"""
        
        if context_type == "teams_message_response":
            prompt = f"""
            The user wants to respond to this Teams message:
            From: {context_data.get('sender', 'Unknown')}
            Message: {context_data.get('content', '')}
            
            User's intended response: {query}
            
            Help them craft a professional and appropriate response.
            """
        
        elif context_type == "email_response":
            prompt = f"""
            The user wants to respond to this email:
            From: {context_data.get('sender', 'Unknown')}
            Subject: {context_data.get('subject', '')}
            Content: {context_data.get('content', '')}
            
            User's intended response: {query}
            
            Help them write a professional email response.
            """
        
        elif context_type == "meeting_preparation":
            prompt = f"""
            The user has an upcoming meeting:
            Title: {context_data.get('title', '')}
            Attendees: {', '.join(context_data.get('attendees', []))}
            Time: {context_data.get('time', '')}
            
            User query: {query}
            
            Help them prepare for this meeting.
            """
        
        else:
            prompt = query
        
        return self.ai_service.generate_response(prompt)

    def set_access_token(self, token: str):
        """Set Microsoft Graph access token"""
        self.graph_service.set_access_token(token)