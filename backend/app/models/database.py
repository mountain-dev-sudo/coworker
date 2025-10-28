import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "coworker_chats.db"):
        """Initialize database connection and create tables"""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create database and tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create chats table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chats (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create messages table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        type TEXT NOT NULL CHECK (type IN ('user', 'ai')),
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
                    )
                ''')
                
                # Create user_memory table for persistent user info
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
                    ON messages(chat_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_messages_timestamp 
                    ON messages(timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_chats_updated_at 
                    ON chats(updated_at)
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def create_chat(self, chat_id: str, title: str = "New Conversation") -> bool:
        """Create a new chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if chat already exists
                cursor.execute('SELECT id FROM chats WHERE id = ?', (chat_id,))
                if cursor.fetchone():
                    # Chat exists, just update the title
                    cursor.execute('''
                        UPDATE chats SET title = ?, updated_at = ?
                        WHERE id = ?
                    ''', (title, datetime.now(), chat_id))
                else:
                    # Create new chat
                    cursor.execute('''
                        INSERT INTO chats (id, title, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (chat_id, title, datetime.now(), datetime.now()))
                
                conn.commit()
                logger.info(f"Chat created/updated: {chat_id}")
                return True
        except Exception as e:
            logger.error(f"Error creating chat: {e}")
            return False
    
    def add_message(self, chat_id: str, message_type: str, content: str) -> bool:
        """Add a message to a chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ensure chat exists
                cursor.execute('SELECT id FROM chats WHERE id = ?', (chat_id,))
                if not cursor.fetchone():
                    # Create chat if it doesn't exist
                    self.create_chat(chat_id)
                
                # Add the message
                cursor.execute('''
                    INSERT INTO messages (chat_id, type, content, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (chat_id, message_type, content, datetime.now()))
                
                # Update chat's updated_at timestamp
                cursor.execute('''
                    UPDATE chats SET updated_at = ? WHERE id = ?
                ''', (datetime.now(), chat_id))
                
                conn.commit()
                logger.info(f"Message added to chat {chat_id}: {message_type}")
                return True
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False
    
    def get_chat_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        """Get all messages for a specific chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT type, content, timestamp FROM messages 
                    WHERE chat_id = ? ORDER BY timestamp ASC
                '''
                params = [chat_id]
                
                if limit:
                    query += ' LIMIT ?'
                    params.append(limit)
                
                cursor.execute(query, params)
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'role': row[0],  # 'user' or 'ai'
                        'content': row[1],
                        'timestamp': row[2]
                    })
                
                logger.info(f"Retrieved {len(messages)} messages for chat {chat_id}")
                return messages
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []
    
    def get_all_chats(self) -> List[Dict]:
        """Get all chats with their latest message"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.id, c.title, c.created_at, c.updated_at,
                           m.content as last_message, m.timestamp as last_message_time
                    FROM chats c
                    LEFT JOIN (
                        SELECT chat_id, content, timestamp,
                               ROW_NUMBER() OVER (PARTITION BY chat_id ORDER BY timestamp DESC) as rn
                        FROM messages
                    ) m ON c.id = m.chat_id AND m.rn = 1
                    ORDER BY c.updated_at DESC
                ''')
                
                chats = []
                for row in cursor.fetchall():
                    chats.append({
                        'id': row[0],
                        'title': row[1],
                        'created_at': row[2],
                        'updated_at': row[3],
                        'last_message': row[4] or "Start a conversation...",
                        'last_message_time': row[5]
                    })
                
                logger.info(f"Retrieved {len(chats)} chats")
                return chats
        except Exception as e:
            logger.error(f"Error getting all chats: {e}")
            return []
    
    def get_user_memory(self, key: str) -> Optional[str]:
        """Get stored user information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM user_memory WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting user memory: {e}")
            return None
    
    def set_user_memory(self, key: str, value: str) -> bool:
        """Store user information that persists across chats"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO user_memory (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (key, value, datetime.now()))
                conn.commit()
                logger.info(f"User memory updated: {key} = {value}")
                return True
        except Exception as e:
            logger.error(f"Error setting user memory: {e}")
            return False
    
    def get_all_user_memory(self) -> Dict[str, str]:
        """Get all stored user information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT key, value FROM user_memory ORDER BY key')
                return dict(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error getting all user memory: {e}")
            return {}
    
    def delete_user_memory(self, key: str) -> bool:
        """Delete specific user memory"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM user_memory WHERE key = ?', (key,))
                deleted = cursor.rowcount > 0
                conn.commit()
                
                if deleted:
                    logger.info(f"User memory deleted: {key}")
                
                return deleted
        except Exception as e:
            logger.error(f"Error deleting user memory: {e}")
            return False
    
    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and all its messages"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if chat exists
                cursor.execute('SELECT id FROM chats WHERE id = ?', (chat_id,))
                if not cursor.fetchone():
                    return False
                
                # Delete chat (messages will be deleted due to CASCADE)
                cursor.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
                conn.commit()
                
                logger.info(f"Chat deleted: {chat_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting chat: {e}")
            return False
    
    def clear_all_chats(self) -> bool:
        """Clear all chats and messages"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM messages')
                cursor.execute('DELETE FROM chats')
                conn.commit()
                logger.info("All chats cleared")
                return True
        except Exception as e:
            logger.error(f"Error clearing all chats: {e}")
            return False
    
    def clear_all_user_memory(self) -> bool:
        """Clear all user memory"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM user_memory')
                conn.commit()
                logger.info("All user memory cleared")
                return True
        except Exception as e:
            logger.error(f"Error clearing user memory: {e}")
            return False
    
    def get_chat_info(self, chat_id: str) -> Optional[Dict]:
        """Get basic chat information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, created_at, updated_at
                    FROM chats WHERE id = ?
                ''', (chat_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'title': row[1],
                        'created_at': row[2],
                        'updated_at': row[3]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            return None
    
    def update_chat_title(self, chat_id: str, title: str) -> bool:
        """Update chat title"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE chats SET title = ?, updated_at = ?
                    WHERE id = ?
                ''', (title, datetime.now(), chat_id))
                
                updated = cursor.rowcount > 0
                conn.commit()
                
                if updated:
                    logger.info(f"Chat title updated: {chat_id} -> {title}")
                
                return updated
        except Exception as e:
            logger.error(f"Error updating chat title: {e}")
            return False
    
    def search_messages(self, search_term: str, limit: int = 50) -> List[Dict]:
        """Search for messages containing the search term"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT m.chat_id, m.type, m.content, m.timestamp, c.title
                    FROM messages m
                    JOIN chats c ON m.chat_id = c.id
                    WHERE m.content LIKE ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                ''', (f'%{search_term}%', limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'chat_id': row[0],
                        'type': row[1],
                        'content': row[2],
                        'timestamp': row[3],
                        'chat_title': row[4]
                    })
                
                logger.info(f"Found {len(results)} messages matching '{search_term}'")
                return results
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []
    
    def get_recent_messages(self, limit: int = 20) -> List[Dict]:
        """Get recent messages across all chats"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT m.chat_id, m.type, m.content, m.timestamp, c.title
                    FROM messages m
                    JOIN chats c ON m.chat_id = c.id
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'chat_id': row[0],
                        'type': row[1],
                        'content': row[2],
                        'timestamp': row[3],
                        'chat_title': row[4]
                    })
                
                return messages
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []
    
    def get_chat_count(self) -> int:
        """Get total number of chats"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM chats')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting chat count: {e}")
            return 0
    
    def get_message_count(self, chat_id: str = None) -> int:
        """Get total number of messages, optionally for a specific chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if chat_id:
                    cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ?', (chat_id,))
                else:
                    cursor.execute('SELECT COUNT(*) FROM messages')
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0
    
    def backup_database(self, backup_path: str = None) -> bool:
        """Create a backup of the database"""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"coworker_chats_backup_{timestamp}.db"
            
            # Create backup using sqlite3 backup API
            with sqlite3.connect(self.db_path) as source:
                with sqlite3.connect(backup_path) as backup:
                    source.backup(backup)
            
            logger.info(f"Database backed up to: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
    
    def get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.now().isoformat()
    
    def cleanup_old_chats(self, days_old: int = 30) -> int:
        """Remove chats older than specified days with no messages"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find chats older than X days with no messages
                cursor.execute('''
                    SELECT c.id FROM chats c
                    LEFT JOIN messages m ON c.id = m.chat_id
                    WHERE c.created_at < datetime('now', '-{} days')
                    AND m.id IS NULL
                '''.format(days_old))
                
                old_chat_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete these chats
                for chat_id in old_chat_ids:
                    cursor.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
                
                conn.commit()
                logger.info(f"Cleaned up {len(old_chat_ids)} old empty chats")
                return len(old_chat_ids)
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0
    
    def export_chat_data(self, chat_id: str) -> Optional[Dict]:
        """Export all data for a specific chat"""
        try:
            chat_info = self.get_chat_info(chat_id)
            if not chat_info:
                return None
            
            messages = self.get_chat_history(chat_id)
            
            return {
                'chat_info': chat_info,
                'messages': messages,
                'message_count': len(messages),
                'exported_at': self.get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error exporting chat data: {e}")
            return None
    
    def import_chat_data(self, chat_data: Dict) -> bool:
        """Import chat data from exported format"""
        try:
            chat_info = chat_data.get('chat_info', {})
            messages = chat_data.get('messages', [])
            
            # Create the chat
            success = self.create_chat(
                chat_info['id'], 
                chat_info.get('title', 'Imported Chat')
            )
            
            if not success:
                return False
            
            # Add all messages
            for message in messages:
                self.add_message(
                    chat_info['id'],
                    message['role'],
                    message['content']
                )
            
            logger.info(f"Imported chat: {chat_info['id']} with {len(messages)} messages")
            return True
            
        except Exception as e:
            logger.error(f"Error importing chat data: {e}")
            return False

# Create global database instance
db_manager = DatabaseManager()