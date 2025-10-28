import os
import requests
from datetime import datetime, timedelta
import msal
from typing import Dict, List, Optional, Any
import json

class MicrosoftGraphService:
    def __init__(self):
        self.client_id = os.getenv('MICROSOFT_CLIENT_ID')
        self.client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
        self.tenant_id = os.getenv('MICROSOFT_TENANT_ID')
        self.redirect_uri = os.getenv('MICROSOFT_REDIRECT_URI')
        
        # Microsoft Graph API endpoints
        self.graph_endpoint = 'https://graph.microsoft.com/v1.0'
        
        # Required scopes for Teams and Outlook
        self.scopes = [
            'https://graph.microsoft.com/Chat.Read',
            'https://graph.microsoft.com/Chat.ReadWrite',
            'https://graph.microsoft.com/ChatMessage.Read',
            'https://graph.microsoft.com/ChatMessage.Send',
            'https://graph.microsoft.com/Mail.Read',
            'https://graph.microsoft.com/Mail.ReadWrite',
            'https://graph.microsoft.com/Mail.Send',
            'https://graph.microsoft.com/User.Read',
            'https://graph.microsoft.com/offline_access'
        ]
        
        # Initialize MSAL app
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
        
        self.access_token = None

    def get_auth_url(self) -> str:
        """Get the authorization URL for OAuth flow"""
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        return auth_url

    def get_token_from_code(self, code: str) -> Dict:
        """Exchange authorization code for access token"""
        result = self.app.acquire_token_by_authorization_code(
            code,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        if "access_token" in result:
            self.access_token = result["access_token"]
            return {"success": True, "token": result}
        else:
            return {"success": False, "error": result.get("error_description", "Unknown error")}

    def set_access_token(self, token: str):
        """Set the access token manually"""
        self.access_token = token

    def _make_graph_request(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Dict:
        """Make a request to Microsoft Graph API"""
        if not self.access_token:
            return {"error": "No access token available"}

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        url = f"{self.graph_endpoint}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=headers, json=data)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    # Teams-related methods
    def get_my_chats(self) -> List[Dict]:
        """Get user's Teams chats"""
        result = self._make_graph_request('me/chats')
        return result.get('value', [])

    def get_chat_messages(self, chat_id: str, limit: int = 50) -> List[Dict]:
        """Get messages from a specific chat"""
        endpoint = f'me/chats/{chat_id}/messages?$top={limit}&$orderby=createdDateTime desc'
        result = self._make_graph_request(endpoint)
        return result.get('value', [])

    def get_todays_teams_messages(self) -> List[Dict]:
        """Get all Teams messages from today"""
        today = datetime.now().date()
        all_messages = []
        
        chats = self.get_my_chats()
        
        for chat in chats:
            chat_id = chat.get('id')
            messages = self.get_chat_messages(chat_id, 20)  # Get recent messages
            
            # Filter messages from today
            todays_messages = []
            for msg in messages:
                msg_date = datetime.fromisoformat(msg['createdDateTime'].replace('Z', '+00:00')).date()
                if msg_date == today:
                    msg['chat_info'] = {
                        'chat_id': chat_id,
                        'topic': chat.get('topic', 'No topic'),
                        'chat_type': chat.get('chatType', 'unknown')
                    }
                    todays_messages.append(msg)
            
            all_messages.extend(todays_messages)
        
        return sorted(all_messages, key=lambda x: x['createdDateTime'], reverse=True)

    def send_teams_message(self, chat_id: str, message: str) -> Dict:
        """Send a message to a Teams chat"""
        data = {
            "body": {
                "contentType": "text",
                "content": message
            }
        }
        
        endpoint = f'me/chats/{chat_id}/messages'
        return self._make_graph_request(endpoint, 'POST', data)

    # Outlook-related methods
    def get_emails(self, folder: str = 'inbox', limit: int = 20) -> List[Dict]:
        """Get emails from specified folder"""
        endpoint = f'me/mailFolders/{folder}/messages?$top={limit}&$orderby=receivedDateTime desc'
        result = self._make_graph_request(endpoint)
        return result.get('value', [])

    def get_todays_emails(self) -> List[Dict]:
        """Get emails received today"""
        today = datetime.now().strftime('%Y-%m-%d')
        endpoint = f"me/messages?$filter=receivedDateTime ge {today}T00:00:00Z&$orderby=receivedDateTime desc"
        result = self._make_graph_request(endpoint)
        return result.get('value', [])

    def get_email_content(self, email_id: str) -> Dict:
        """Get full email content including body"""
        endpoint = f'me/messages/{email_id}'
        return self._make_graph_request(endpoint)

    def send_email(self, to_emails: List[str], subject: str, body: str, 
                   cc_emails: List[str] = None, attachments: List[Dict] = None) -> Dict:
        """Send an email"""
        
        recipients = [{"emailAddress": {"address": email}} for email in to_emails]
        cc_recipients = [{"emailAddress": {"address": email}} for email in (cc_emails or [])]
        
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": recipients,
                "ccRecipients": cc_recipients if cc_recipients else []
            }
        }
        
        # Add attachments if provided
        if attachments:
            email_data["message"]["attachments"] = attachments
        
        endpoint = 'me/sendMail'
        return self._make_graph_request(endpoint, 'POST', email_data)

    def create_draft_email(self, to_emails: List[str], subject: str, body: str,
                          cc_emails: List[str] = None) -> Dict:
        """Create a draft email"""
        recipients = [{"emailAddress": {"address": email}} for email in to_emails]
        cc_recipients = [{"emailAddress": {"address": email}} for email in (cc_emails or [])]
        
        draft_data = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body
            },
            "toRecipients": recipients,
            "ccRecipients": cc_recipients if cc_recipients else []
        }
        
        endpoint = 'me/messages'
        return self._make_graph_request(endpoint, 'POST', draft_data)

    def search_emails(self, query: str, limit: int = 10) -> List[Dict]:
        """Search emails with a query"""
        endpoint = f"me/messages?$search=\"{query}\"&$top={limit}"
        result = self._make_graph_request(endpoint)
        return result.get('value', [])

    def get_user_info(self) -> Dict:
        """Get current user information"""
        return self._make_graph_request('me')

    # Utility methods for AI integration
    def summarize_chat_messages(self, messages: List[Dict]) -> str:
        """Format chat messages for AI summarization"""
        formatted_messages = []
        
        for msg in messages:
            sender = msg.get('from', {}).get('user', {}).get('displayName', 'Unknown')
            content = msg.get('body', {}).get('content', '')
            timestamp = msg.get('createdDateTime', '')
            
            formatted_messages.append(f"[{timestamp}] {sender}: {content}")
        
        return "\n".join(formatted_messages)

    def format_emails_for_ai(self, emails: List[Dict]) -> str:
        """Format emails for AI processing"""
        formatted_emails = []
        
        for email in emails:
            sender = email.get('sender', {}).get('emailAddress', {}).get('name', 'Unknown')
            subject = email.get('subject', 'No subject')
            received = email.get('receivedDateTime', '')
            preview = email.get('bodyPreview', '')
            
            formatted_emails.append(f"From: {sender}\nSubject: {subject}\nReceived: {received}\nPreview: {preview}\n---")
        
        return "\n".join(formatted_emails)