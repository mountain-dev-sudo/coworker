import os
from dotenv import load_dotenv
from transformers import pipeline
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize the pipeline with GPT-Neo (you can change this to other models)
# pipe = pipeline("text-generation", model="EleutherAI/gpt-neo-2.7B")
# pipe = pipeline("text-generation", model="EleutherAI/gpt-neo-1.3B")
# pipe = pipeline("text-generation", model="pszemraj/led-large-book-summary")
pipe = pipeline("text-generation", model="microsoft/Phi-3-mini-4k-instruct")


def clean_response(text: str) -> str:
    """Clean up the generated response"""
    # Remove common forum/Q&A artifacts
    text = re.sub(r'^A:\s*', '', text)
    text = re.sub(r'^\n+', '', text)
    text = re.sub(r'\n+$', '', text)
    
    # Remove incomplete sentences at the end
    sentences = text.split('.')
    if len(sentences) > 1 and sentences[-1].strip() and len(sentences[-1]) < 20:
        text = '.'.join(sentences[:-1]) + '.'
    
    # Remove repetitive patterns
    lines = text.split('\n')
    cleaned_lines = []
    prev_line = ""
    
    for line in lines:
        line = line.strip()
        if line and line != prev_line:
            cleaned_lines.append(line)
            prev_line = line
    
    return '\n'.join(cleaned_lines).strip()

def generate_text(prompt: str) -> str:
    """Generate text using the transformers pipeline"""
    logger.info(f"Generating text for prompt: {prompt[:50]}...")
    
    try:
        # Format prompt for better conversational response
        formatted_prompt = f"Question: {prompt}\nAnswer:"
        
        result = pipe(
            formatted_prompt, 
            max_new_tokens=100,
            temperature=0.7,
            do_sample=True,
            return_full_text=False,
            pad_token_id=pipe.tokenizer.eos_token_id,
            repetition_penalty=1.1,
            no_repeat_ngram_size=2,
            top_p=0.9
        )
        
        logger.info(f"Raw result: {result}")
        
        if result and len(result) > 0:
            generated_text = result[0]['generated_text'].strip()
            
            # Clean up the response
            cleaned_text = clean_response(generated_text)
            
            logger.info(f"Generated text: {cleaned_text}")
            return cleaned_text if cleaned_text else "I'm thinking..."
        
        return "Let me think about that..."
        
    except Exception as e:
        logger.error(f"Error generating text: {str(e)}")
        return f"Sorry, I encountered an error: {str(e)}"

def generate_chat_response(prompt: str) -> str:
    """Generate a conversational response"""
    logger.info(f"Generating chat response for: {prompt[:50]}...")
    
    try:
        # Different formatting for chat
        chat_prompt = f"Human: {prompt}\nAssistant: I'll help you with that."
        
        result = pipe(
            chat_prompt,
            max_new_tokens=120,
            temperature=0.8,
            do_sample=True,
            return_full_text=False,
            pad_token_id=pipe.tokenizer.eos_token_id,
            repetition_penalty=1.1,
            no_repeat_ngram_size=2,
            top_p=0.9,
            stop_sequences=["Human:", "Assistant:"]
        )
        
        if result and len(result) > 0:
            response = result[0]['generated_text'].strip()
            
            # Remove the "I'll help you with that." prefix if it appears
            response = re.sub(r'^I\'ll help you with that\.?\s*', '', response)
            
            # Clean up the response
            cleaned_response = clean_response(response)
            
            # If response is too short or empty, fall back to basic generation
            if not cleaned_response or len(cleaned_response.split()) < 3:
                return generate_text(prompt)
            
            logger.info(f"Chat response: {cleaned_response}")
            return cleaned_response
        
        # Fallback to basic generation
        return generate_text(prompt)
        
    except Exception as e:
        logger.error(f"Error in chat response: {str(e)}")
        return generate_text(prompt)

def generate_code_response(prompt: str) -> str:
    """Generate code-specific responses with better formatting"""
    logger.info(f"Generating code response for: {prompt[:50]}...")
    
    try:
        # Much cleaner prompt for code
        if "hello world" in prompt.lower() and "python" in prompt.lower():
            # Direct response for hello world
            return 'print("Hello, World!")'
        
        # General code prompt
        code_prompt = f'Write {prompt.lower()}:\n\n```python\n'
        
        result = pipe(
            code_prompt,
            max_new_tokens=80,
            temperature=0.2,  # Very low for clean code
            do_sample=True,
            return_full_text=False,
            pad_token_id=pipe.tokenizer.eos_token_id,
            repetition_penalty=1.0
        )
        
        if result and len(result) > 0:
            code_response = result[0]['generated_text'].strip()
            
            # Clean up code response
            code_response = re.sub(r'```.*', '', code_response)  # Remove markdown
            code_response = re.sub(r'#.*\n', '', code_response)  # Remove comments
            code_response = re.sub(r'>>>.*', '', code_response)  # Remove interpreter prompts
            
            # Extract just the actual code
            lines = code_response.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('A:') and not line.startswith('So,'):
                    clean_lines.append(line)
                    if len(clean_lines) >= 3:  # Limit to 3 lines max
                        break
            
            final_code = '\n'.join(clean_lines).strip()
            
            if final_code:
                logger.info(f"Code response: {final_code}")
                return final_code
        
        # Hardcoded responses for common requests
        if "hello world" in prompt.lower():
            return 'print("Hello, World!")'
        elif "add two numbers" in prompt.lower():
            return 'a = 5\nb = 3\nprint(a + b)'
        
        return "I'm having trouble generating that code right now."
        
    except Exception as e:
        logger.error(f"Error in code generation: {str(e)}")
        return f"Sorry, I encountered an error generating code: {str(e)}"

def get_smart_response(prompt: str) -> str:
    """Smart router that chooses the best response method"""
    prompt_lower = prompt.lower()
    
    # Check if it's a code-related request
    code_keywords = ['code', 'python', 'function', 'class', 'import', 'def', 'print', 'variable', 'loop', 'if', 'else', 'javascript', 'html', 'css']
    
    if any(keyword in prompt_lower for keyword in code_keywords):
        return generate_code_response(prompt)
    else:
        return generate_chat_response(prompt)