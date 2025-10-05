"""Automatic model detection for Claude Code integration."""

import os
import re
from typing import Dict, Any, Optional


def detect_current_model() -> Dict[str, str]:
    """
    Detect the current AI model being used by Claude Code.
    
    This function attempts to determine which model is active based on:
    1. Environment variables
    2. Claude Code session context
    3. API usage patterns
    """
    
    # Check for Claude Code environment indicators
    if os.getenv('CLAUDE_MODEL'):
        model_name = os.getenv('CLAUDE_MODEL')
        if 'claude' in model_name.lower():
            return {
                'provider': 'anthropic',
                'model': model_name,
                'version': extract_claude_version(model_name)
            }
    
    # Check for Anthropic API key presence (indicates Claude usage)
    if os.getenv('ANTHROPIC_API_KEY'):
        return {
            'provider': 'anthropic', 
            'model': 'claude-3-sonnet-20240229',  # Default Claude model
            'version': '3-sonnet'
        }
    
    # Check for OpenAI API key
    if os.getenv('OPENAI_API_KEY'):
        return {
            'provider': 'openai',
            'model': 'gpt-4',
            'version': '4'
        }
    
    # Default fallback
    return {
        'provider': 'unknown',
        'model': 'unknown',
        'version': 'unknown'
    }


def extract_claude_version(model_name: str) -> str:
    """Extract Claude version from model name."""
    # Handle various Claude model naming patterns
    patterns = [
        r'claude-(\d+(?:\.\d+)?)-?(sonnet|opus|haiku)?',
        r'sonnet-?(\d+(?:\.\d+)?)',
        r'claude-?(\d+(?:\.\d+)?)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, model_name.lower())
        if match:
            version = match.group(1)
            model_type = match.group(2) if len(match.groups()) > 1 else 'sonnet'
            return f"{version}-{model_type}" if model_type else version
    
    return 'unknown'


def detect_from_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Detect model from HTTP request headers."""
    
    # Check for Anthropic-specific headers
    if 'anthropic-version' in headers or 'x-api-key' in headers:
        # Look for model in headers
        model = headers.get('anthropic-model', 'claude-3-sonnet-20240229')
        return {
            'provider': 'anthropic',
            'model': model,
            'version': extract_claude_version(model)
        }
    
    # Check for OpenAI headers
    if 'authorization' in headers and 'bearer' in headers['authorization'].lower():
        model = headers.get('openai-model', 'gpt-4')
        return {
            'provider': 'openai', 
            'model': model,
            'version': model.replace('gpt-', '')
        }
    
    return detect_current_model()


def enhance_context_with_model_detection(context: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance context with automatic model detection."""
    
    # If model info already provided, use it
    if context.get('model_provider') and context.get('model_name'):
        return context
    
    # Detect current model
    model_info = detect_current_model()
    
    # For Claude Code, we know it's likely Anthropic Claude
    if not context.get('model_provider'):
        # Claude Code specific detection
        context['model_provider'] = 'anthropic'
        context['model_name'] = 'claude-3-sonnet-20240229'  # Current Claude Code model
        context['model_version'] = '3-sonnet'
        context['detected_automatically'] = True
        
        # Try to get more specific info if available
        if os.getenv('CLAUDE_MODEL'):
            context['model_name'] = os.getenv('CLAUDE_MODEL') 
            context['model_version'] = extract_claude_version(context['model_name'])
    
    return context


def get_claude_code_model_info() -> Dict[str, str]:
    """Get specific model info for Claude Code integration."""
    
    # Claude Code uses Claude Sonnet 4 (as mentioned by user)
    # Updated to reflect the actual model being used
    return {
        'provider': 'anthropic',
        'model': 'claude-sonnet-4-20250514',  # Actual Claude Sonnet 4 model
        'version': '4-sonnet',
        'source': 'claude-code',
        'display_name': 'Claude Sonnet 4 (Claude Code)'
    }


def format_model_info_for_commit(model_info: Dict[str, str]) -> str:
    """Format model information for commit messages."""
    
    provider = model_info.get('provider', 'unknown')
    model = model_info.get('model', 'unknown')
    
    # Create user-friendly display names
    if provider == 'anthropic':
        if 'sonnet' in model.lower():
            return f"anthropic/claude-sonnet"
        elif 'opus' in model.lower():
            return f"anthropic/claude-opus"
        elif 'haiku' in model.lower():
            return f"anthropic/claude-haiku"
        else:
            return f"anthropic/{model}"
    elif provider == 'openai':
        return f"openai/{model}"
    else:
        return f"{provider}/{model}"