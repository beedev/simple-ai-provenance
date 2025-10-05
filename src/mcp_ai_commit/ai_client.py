"""AI client for generating commit messages."""

import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

import openai
import anthropic

from .config import get_config
from .models import FileChange, CommitStrategy, ModelProvider


class AIClient:
    """Client for AI model interactions."""
    
    def __init__(self, provider: ModelProvider, model_name: str):
        self.provider = provider
        self.model_name = model_name
        self.config = get_config()
        
        # Initialize AI clients
        if provider == ModelProvider.OPENAI:
            if not self.config.ai_models.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self.openai_client = openai.AsyncOpenAI(
                api_key=self.config.ai_models.openai_api_key,
                base_url=self.config.ai_models.openai_base_url
            )
        elif provider == ModelProvider.ANTHROPIC:
            if not self.config.ai_models.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            self.anthropic_client = anthropic.AsyncAnthropic(
                api_key=self.config.ai_models.anthropic_api_key
            )
    
    async def generate_commit_message(
        self,
        file_changes: List[FileChange],
        repo_info: Dict[str, str],
        strategy: CommitStrategy,
        temperature: float = 0.3,
        max_tokens: int = 200,
        include_body: bool = True,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a commit message using AI."""
        
        # Build prompt
        prompt = self._build_prompt(
            file_changes=file_changes,
            repo_info=repo_info,
            strategy=strategy,
            include_body=include_body,
            custom_instructions=custom_instructions
        )
        
        start_time = time.time()
        
        try:
            if self.provider == ModelProvider.OPENAI:
                result = await self._call_openai(prompt, temperature, max_tokens)
            elif self.provider == ModelProvider.ANTHROPIC:
                result = await self._call_anthropic(prompt, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
            
            end_time = time.time()
            
            # Parse AI response
            parsed_response = self._parse_ai_response(result["content"], strategy, include_body)
            
            # Add metadata
            parsed_response.update({
                "prompt_text": prompt,
                "response_text": result["content"],
                "prompt_tokens": result.get("prompt_tokens", 0),
                "completion_tokens": result.get("completion_tokens", 0),
                "execution_time_ms": int((end_time - start_time) * 1000),
                "confidence_score": self._calculate_confidence_score(parsed_response, file_changes)
            })
            
            return parsed_response
            
        except Exception as e:
            # Return fallback response
            return self._create_fallback_response(file_changes, str(e))
    
    def _build_prompt(
        self,
        file_changes: List[FileChange],
        repo_info: Dict[str, str],
        strategy: CommitStrategy,
        include_body: bool,
        custom_instructions: Optional[str]
    ) -> str:
        """Build the prompt for AI commit generation."""
        
        # Base system instructions
        if strategy == CommitStrategy.CONVENTIONAL:
            system_prompt = """Generate a conventional commit message following the format:
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
Use lowercase. Keep description under 50 characters."""
        
        elif strategy == CommitStrategy.SEMANTIC:
            system_prompt = """Generate a semantic commit message that clearly describes what changed and why.
Focus on the business impact and user-facing changes.
Use imperative mood. Be specific but concise."""
        
        elif strategy == CommitStrategy.NATURAL:
            system_prompt = """Generate a natural language commit message that clearly describes the changes.
Write as if explaining to a colleague what you did.
Be descriptive but not verbose."""
        
        else:  # CUSTOM
            system_prompt = """Generate an appropriate commit message for the changes.
Follow good commit message practices: imperative mood, clear description, proper formatting."""
        
        # Add custom instructions
        if custom_instructions:
            system_prompt += f"\n\nAdditional instructions: {custom_instructions}"
        
        # Build context
        context_parts = [
            "Repository context:",
            f"- Repository: {repo_info.get('repo_path', 'unknown')}",
            f"- Branch: {repo_info.get('current_branch', 'unknown')}",
            f"- Current commit: {repo_info.get('current_commit', 'unknown')[:8]}",
            "",
            "Changes to commit:"
        ]
        
        # Add file changes
        for file_change in file_changes:
            status_desc = {
                'A': 'Added',
                'M': 'Modified', 
                'D': 'Deleted',
                'R': 'Renamed'
            }.get(file_change.status, file_change.status)
            
            context_parts.append(f"- {status_desc}: {file_change.path}")
            if file_change.additions > 0 or file_change.deletions > 0:
                context_parts.append(f"  (+{file_change.additions}, -{file_change.deletions} lines)")
        
        # Add statistics
        total_files = len(file_changes)
        total_additions = sum(f.additions for f in file_changes)
        total_deletions = sum(f.deletions for f in file_changes)
        
        context_parts.extend([
            "",
            f"Summary: {total_files} files changed, {total_additions} insertions(+), {total_deletions} deletions(-)"
        ])
        
        # Construct full prompt
        full_prompt = f"""{system_prompt}

{chr(10).join(context_parts)}

Please generate a commit message for these changes."""
        
        if include_body:
            full_prompt += " Include a detailed body if the changes are complex or significant."
        
        return full_prompt
    
    async def _call_openai(self, prompt: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        """Call OpenAI API."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                "content": response.choices[0].message.content,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            }
            
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def _call_anthropic(self, prompt: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        """Call Anthropic API."""
        try:
            response = await self.anthropic_client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return {
                "content": response.content[0].text,
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens
            }
            
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
    def _parse_ai_response(self, content: str, strategy: CommitStrategy, include_body: bool) -> Dict[str, Any]:
        """Parse AI response into structured format."""
        lines = content.strip().split('\n')
        
        # Extract commit message (first non-empty line)
        commit_message = ""
        commit_body = ""
        
        # Find first non-empty line as commit message
        for line in lines:
            if line.strip():
                commit_message = line.strip()
                break
        
        # Extract body if requested
        if include_body and len(lines) > 1:
            # Everything after the first line (and any blank lines) is the body
            body_lines = []
            found_message = False
            skip_next_empty = False
            
            for line in lines:
                if not found_message and line.strip():
                    found_message = True
                    skip_next_empty = True
                    continue
                elif found_message:
                    if skip_next_empty and not line.strip():
                        skip_next_empty = False
                        continue
                    body_lines.append(line)
            
            commit_body = '\n'.join(body_lines).strip()
        
        # Detect commit type for conventional commits
        detected_type = "unknown"
        if strategy == CommitStrategy.CONVENTIONAL:
            detected_type = self._detect_conventional_type(commit_message)
        else:
            detected_type = self._detect_change_type(commit_message, [])  # Pass file changes if available
        
        # Detect breaking changes
        breaking_changes = self._detect_breaking_changes(commit_message + "\n" + commit_body)
        
        return {
            "commit_message": commit_message,
            "commit_body": commit_body if commit_body else None,
            "detected_type": detected_type,
            "breaking_changes": breaking_changes
        }
    
    def _detect_conventional_type(self, message: str) -> str:
        """Detect conventional commit type."""
        conventional_types = [
            "feat", "fix", "docs", "style", "refactor", 
            "perf", "test", "build", "ci", "chore"
        ]
        
        message_lower = message.lower()
        for commit_type in conventional_types:
            if message_lower.startswith(f"{commit_type}:") or message_lower.startswith(f"{commit_type}("):
                return commit_type
        
        return "unknown"
    
    def _detect_change_type(self, message: str, file_changes: List[FileChange]) -> str:
        """Detect general change type."""
        message_lower = message.lower()
        
        # Check for keywords
        if any(word in message_lower for word in ["add", "new", "create", "implement"]):
            return "feature"
        elif any(word in message_lower for word in ["fix", "bug", "issue", "resolve"]):
            return "fix"
        elif any(word in message_lower for word in ["update", "change", "modify", "improve"]):
            return "improvement"
        elif any(word in message_lower for word in ["remove", "delete", "clean"]):
            return "removal"
        elif any(word in message_lower for word in ["refactor", "restructure", "reorganize"]):
            return "refactor"
        elif any(word in message_lower for word in ["doc", "readme", "comment"]):
            return "documentation"
        elif any(word in message_lower for word in ["test", "spec"]):
            return "test"
        
        return "unknown"
    
    def _detect_breaking_changes(self, full_message: str) -> List[str]:
        """Detect breaking changes indicators."""
        breaking_indicators = []
        message_lower = full_message.lower()
        
        # Common breaking change indicators
        if "breaking change" in message_lower or "breaking:" in message_lower:
            breaking_indicators.append("Explicit breaking change mentioned")
        
        if "!" in full_message and (":" in full_message):
            # Conventional commit breaking change indicator
            breaking_indicators.append("Conventional commit breaking change indicator (!)")
        
        # API changes
        if any(word in message_lower for word in ["remove api", "delete endpoint", "change interface"]):
            breaking_indicators.append("API change detected")
        
        return breaking_indicators
    
    def _calculate_confidence_score(self, response: Dict[str, Any], file_changes: List[FileChange]) -> float:
        """Calculate confidence score for the generated commit."""
        score = 0.8  # Base score
        
        # Check if message follows expected format
        commit_message = response.get("commit_message", "")
        if len(commit_message) > 10 and len(commit_message) < 80:
            score += 0.1
        
        # Check if type was detected
        if response.get("detected_type") != "unknown":
            score += 0.1
        
        # Reduce score for very short or very long messages
        if len(commit_message) < 5:
            score -= 0.3
        elif len(commit_message) > 100:
            score -= 0.1
        
        return min(1.0, max(0.0, score))
    
    def _create_fallback_response(self, file_changes: List[FileChange], error: str) -> Dict[str, Any]:
        """Create fallback response when AI fails."""
        # Generate simple commit message based on file changes
        if len(file_changes) == 1:
            file_change = file_changes[0]
            if file_change.status == 'A':
                message = f"Add {file_change.path}"
            elif file_change.status == 'M':
                message = f"Update {file_change.path}"
            elif file_change.status == 'D':
                message = f"Remove {file_change.path}"
            else:
                message = f"Change {file_change.path}"
        else:
            total_files = len(file_changes)
            message = f"Update {total_files} files"
        
        return {
            "commit_message": message,
            "commit_body": None,
            "detected_type": "unknown",
            "breaking_changes": [],
            "confidence_score": 0.3,
            "error": f"AI generation failed: {error}",
            "fallback": True
        }