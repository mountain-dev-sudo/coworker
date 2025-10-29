import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class GeminiService:
    def __init__(self):
        """Initialize Gemini service with API key from environment"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Initialize the model (using Gemini 2.5 Flash - best price-performance)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        logger.info("Gemini service initialized successfully")

    def _handle_response(self, response) -> str:
        """Handle Gemini response and check for safety blocks or other issues"""
        try:
            # Check if response was blocked
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # Check finish reason
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    
                    if finish_reason == 2:  # SAFETY
                        logger.warning("Response blocked by safety filters")
                        return "I apologize, but I can't provide a response to that request due to safety guidelines. Please try rephrasing your question."
                    if finish_reason == 3:  # RECITATION
                        logger.warning("Response blocked due to recitation")
                        return "I can't provide that response as it may contain copyrighted content. Please try asking in a different way."
                    elif finish_reason == 4:  # OTHER
                        logger.warning("Response blocked for other reasons")
                        return "I'm unable to provide a response to that request. Please try rephrasing your question."
                
                # Check if there's actual content
                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts'):
                    if candidate.content.parts:
                        return candidate.content.parts[0].text.strip()
            
            # Fallback: try the .text accessor with error handling
            if hasattr(response, 'text'):
                return response.text.strip()
            
            # If we get here, there's no valid content
            logger.warning("No valid content in response")
            return "I wasn't able to generate a proper response. Please try rephrasing your question."
            
        except Exception as e:
            logger.error(f"Error handling response: {str(e)}")
            return f"Sorry, I encountered an error processing the response: {str(e)}"

    def generate_text(self, prompt: str, max_tokens: int = 150) -> str:
        """Generate text using Gemini API"""
        logger.info(f"Generating text for prompt: {prompt[:50]}...")
        
        try:
            # Configure generation settings
            generation_config = genai.types.GenerationConfig(
                # max_output_tokens=max_tokens,
                temperature=0.7,
                top_p=1,
                top_k=40
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            generated_text = self._handle_response(response)
            logger.info(f"Generated text: {generated_text[:100]}...")
            return generated_text
            
        except Exception as e:
            error_message = str(e).lower()
            
            if "quota" in error_message or "limit" in error_message:
                logger.error("Rate limit or quota exceeded")
                return "Sorry, I'm currently experiencing high demand. Please try again in a moment."
            elif "api" in error_message and "key" in error_message:
                logger.error("Authentication failed - check your API key")
                return "Authentication error. Please check the API configuration."
            elif "invalid" in error_message:
                logger.error(f"Invalid request: {str(e)}")
                return "Invalid request. Please try rephrasing your question."
            else:
                logger.error(f"Unexpected error: {str(e)}")
                return f"Sorry, I encountered an error: {str(e)}"

    # Replace the generate_chat_response method in your GeminiService class with this:

    def generate_chat_response(self, prompt: str, conversation_history: list = None) -> str:
        """Generate conversational response with context"""
        logger.info(f"Generating chat response for: {prompt[:50]}...")
        
        try:
            # First try without conversation history to avoid safety filter issues
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=200,
                temperature=0.8,
                top_p=1,
                top_k=40
            )
            
            # More permissive safety settings
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH", 
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                }
            ]
            
            # Try with conversation history first, but with better formatting
            if conversation_history and len(conversation_history) > 0:
                try:
                    # Limit to last 6 messages and format more naturally
                    recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
                    
                    # Build a cleaner context
                    context_parts = []
                    for msg in recent_history:
                        role = "User" if msg.get('role') == 'user' else "Assistant"
                        content = msg.get('content', '').strip()
                        if content and len(content) < 500:  # Skip very long messages
                            context_parts.append(f"{role}: {content}")
                    
                    if context_parts:
                        # Add current prompt
                        context_parts.append(f"User: {prompt}")
                        full_prompt = "\n\n".join(context_parts)
                        
                        response = self.model.generate_content(
                            full_prompt
                            # ,
                            # generation_config=generation_config,
                            # safety_settings=safety_settings
                        )
                        
                        chat_response = self._handle_response(response)
                        
                        # If response looks good, return it
                        if not ("safety" in chat_response.lower() or "can't provide" in chat_response.lower()):
                            logger.info(f"Chat response with history: {chat_response[:100]}...")
                            return chat_response
                            
                except Exception as e:
                    logger.warning(f"Failed to generate with history context: {str(e)}")
            
            # Fallback: Try without conversation history
            logger.info("Trying without conversation history...")
            response = self.model.generate_content(
                prompt
                # ,
                # generation_config=generation_config,
                # safety_settings=safety_settings
            )
            
            chat_response = self._handle_response(response)
            logger.info(f"Chat response without history: {chat_response[:100]}...")
            return chat_response
            
        except Exception as e:
            logger.error(f"Error in chat response: {str(e)}")
            return f"I encountered an error processing your request: {str(e)}"

    def summarize_document(self, text: str, summary_length: str = "medium") -> str:
        """Summarize a document"""
        logger.info(f"Summarizing document of length: {len(text)} characters")
        
        # Determine max tokens based on summary length
        token_limits = {
            "short": 100,
            "medium": 200,
            "long": 400
        }
        max_tokens = token_limits.get(summary_length, 200)
        
        try:
            prompt = f"""Please provide a {summary_length} summary of the following text:

{text}

Summary:"""
            
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,  # Lower temperature for more focused summaries
                top_p=1,
                top_k=20
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            summary = self._handle_response(response)
            logger.info(f"Summary generated: {len(summary)} characters")
            return summary
            
        except Exception as e:
            logger.error(f"Error in document summarization: {str(e)}")
            return f"Sorry, I couldn't summarize the document: {str(e)}"

    def generate_code(self, prompt: str) -> str:
        """Generate code based on prompt"""
        logger.info(f"Generating code for: {prompt[:50]}...")
        
        try:
            code_prompt = f"""Generate clean, well-commented code for the following request:

{prompt}

Please provide only the code with brief comments:"""
            
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=300,
                temperature=0.2,  # Low temperature for more deterministic code
                top_p=1,
                top_k=20
            )
            
            response = self.model.generate_content(
                code_prompt,
                generation_config=generation_config
            )
            
            code = self._handle_response(response)
            logger.info(f"Code generated successfully")
            return code
            
        except Exception as e:
            logger.error(f"Error in code generation: {str(e)}")
            return f"Sorry, I couldn't generate the code: {str(e)}"

    def get_smart_response(self, prompt: str, conversation_history: list = None) -> str:
        """Smart router that chooses the best response method"""
        prompt_lower = prompt.lower()
        
        # Check for code-related requests
        code_keywords = ['code', 'python', 'function', 'class', 'import', 'def', 'print', 'variable', 'javascript', 'html', 'css']
        
        # Check for summarization requests
        summary_keywords = ['summarize', 'summary', 'summarise', 'brief', 'overview', 'key points']
        
        if any(keyword in prompt_lower for keyword in summary_keywords):
            return self.generate_chat_response(f"Please provide a summary: {prompt}", conversation_history)
        elif any(keyword in prompt_lower for keyword in code_keywords):
            return self.generate_code(prompt)
        else:
            return self.generate_chat_response(prompt, conversation_history)

    def get_answer(self, query: str) -> str:
        """Main method that your routes should call"""
        return self.get_smart_response(query)

    def generate_with_safety_settings(self, prompt: str, max_tokens: int = 150) -> str:
        """Generate text with custom safety settings (more permissive)"""
        logger.info(f"Generating with custom safety settings for: {prompt[:50]}...")
        
        try:
            # Configure more permissive safety settings
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                }
            ]
            
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.7,
                top_p=1,
                top_k=40
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            generated_text = self._handle_response(response)
            # generated_text = response
            logger.info(f"Generated text with custom safety: {generated_text[:100]}...")
            return generated_text
            
        except Exception as e:
            logger.error(f"Error with custom safety settings: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"

    def retry_with_modified_prompt(self, original_prompt: str) -> str:
        """Retry with a modified prompt if original was blocked"""
        logger.info("Retrying with modified prompt...")
        
        # Add a neutral, academic framing to the prompt
        modified_prompt = f"""Please provide an informative and educational response to the following question in a neutral, academic tone:

{original_prompt}

Please focus on factual information and helpful insights."""
        
        return self.generate_with_safety_settings(modified_prompt)


# Initialize the service
try:
    ai_service = GeminiService()
    
    # Main functions for backwards compatibility with your existing code
    def generate_text(prompt: str) -> str:
        return ai_service.generate_text(prompt)
    
    def generate_chat_response(prompt: str) -> str:
        return ai_service.generate_chat_response(prompt)
    
    def summarize_document(text: str) -> str:
        return ai_service.summarize_document(text)
    
    def generate_code(prompt: str) -> str:
        return ai_service.generate_code(prompt)
    
    def get_answer(query: str) -> str:
        return ai_service.get_answer(query)
        
except Exception as e:
    logger.error(f"Failed to initialize Gemini service: {str(e)}")
    
    # Fallback functions if Gemini fails
    def generate_text(prompt: str) -> str:
        return "Gemini service unavailable. Please check your API key."
    
    def generate_chat_response(prompt: str) -> str:
        return "Gemini service unavailable. Please check your API key."
    
    def summarize_document(text: str) -> str:
        return "Gemini service unavailable. Please check your API key."
    
    def generate_code(prompt: str) -> str:
        return "Gemini service unavailable. Please check your API key."
    
    def get_answer(query: str) -> str:
        return "Gemini service unavailable. Please check your API key."