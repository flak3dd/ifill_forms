"""
AI Client abstraction with OpenAI primary and Ollama fallback.
Provides unified interface for text completion and vision analysis.
"""
import json
import base64
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging
import httpx
from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> str:
        """Generate text completion."""
        pass
    
    @abstractmethod
    async def analyze_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """Analyze an image with a prompt."""
        pass


class OpenAIProvider(AIProvider):
    """OpenAI GPT-4 provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=settings.OPENAI_BASE_URL
        )
        self.text_model = "gpt-4o-mini"
        self.vision_model = "gpt-4o"
    
    async def complete(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Generate text completion using OpenAI."""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        try:
            response = await self.client.chat.completions.create(
                model=model or self.text_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", 1000)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI completion error: {e}")
            raise
    
    async def analyze_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """Analyze image using GPT-4 Vision."""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        
        try:
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }],
                temperature=0.1,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw_response": content, "fields": []}
                
        except Exception as e:
            logger.error(f"OpenAI vision error: {e}")
            raise


class OllamaProvider(AIProvider):
    """Local Ollama provider for privacy/cost control."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.text_model = settings.OLLAMA_MODEL or "llama3.2"
        self.vision_model = settings.OLLAMA_VISION_MODEL or "llava"
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def complete(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Generate text completion using Ollama."""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model or self.text_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", 0.1)
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
            
        except Exception as e:
            logger.error(f"Ollama completion error: {e}")
            raise
    
    async def analyze_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """Analyze image using Ollama vision model (LLaVA)."""
        try:
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [base64_image],
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()
            
            content = result.get("response", "")
            
            # Try to parse as JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw_response": content, "fields": []}
                
        except Exception as e:
            logger.error(f"Ollama vision error: {e}")
            raise
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class AIClient:
    """
    Unified AI client with fallback chain:
    1. OpenAI (GPT-4o) for high-quality results
    2. Ollama (local) for privacy/cost control
    """
    
    def __init__(
        self,
        primary: Optional[AIProvider] = None,
        fallback: Optional[AIProvider] = None
    ):
        self.primary = primary
        self.fallback = fallback
        
        # Initialize providers if not provided
        if not self.primary and settings.OPENAI_API_KEY:
            self.primary = OpenAIProvider()
        
        if not self.fallback:
            self.fallback = OllamaProvider()
    
    async def complete(self, prompt: str, **kwargs) -> str:
        """Generate completion with fallback."""
        try:
            if self.primary:
                return await self.primary.complete(prompt, **kwargs)
        except Exception as e:
            logger.warning(f"Primary AI failed: {e}, trying fallback...")
        
        if self.fallback:
            return await self.fallback.complete(prompt, **kwargs)
        
        raise RuntimeError("No AI provider available")
    
    async def analyze_form(
        self,
        screenshot: bytes,
        fields_metadata: List[Dict[str, Any]],
        use_vision: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze form screenshot and field metadata.
        
        Args:
            screenshot: PNG image bytes
            fields_metadata: List of detected field metadata
            use_vision: Whether to use vision model or text-only
        
        Returns:
            Dict with "fields" list containing semantic tags and confidence
        """
        prompt = self._build_field_analysis_prompt(fields_metadata)
        
        try:
            if use_vision and self.primary:
                return await self.primary.analyze_image(screenshot, prompt)
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}, using text fallback...")
        
        # Text-only fallback
        text_prompt = f"""
        Analyze these form fields based on metadata only:
        
        {prompt}
        
        Return JSON format:
        {{
            "fields": [
                {{"index": 0, "semantic_tag": "given_name", "confidence": 0.95, "reasoning": "..."}}
            ]
        }}
        """
        
        result = await self.complete(text_prompt)
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"fields": [], "raw_response": result}
    
    def _build_field_analysis_prompt(self, fields: List[Dict[str, Any]]) -> str:
        """Build prompt for field analysis."""
        semantic_options = [
            "given_name (First name)",
            "family_name (Last name)",
            "full_name",
            "email",
            "phone",
            "address_line1",
            "city",
            "state",
            "postal_code",
            "country",
            "job_title",
            "company_name",
            "experience",
            "education",
            "skills",
            "salary",
            "cover_letter",
            "resume_file",
            "availability",
            "custom_field"
        ]
        
        field_descriptions = []
        for i, f in enumerate(fields):
            desc = f"""
Field {i}:
- HTML Type: {f.get('type', 'unknown')}
- Label: {f.get('label', 'N/A')}
- Placeholder: {f.get('placeholder', 'N/A')}
- Name attribute: {f.get('name', 'N/A')}
- Required: {f.get('required', False)}
"""
            field_descriptions.append(desc)
        
        return f"""Analyze these form fields and assign semantic tags for CSV data mapping.

Available semantic tags:
{chr(10).join([f"- {opt}" for opt in semantic_options])}

Fields to analyze:
{chr(10).join(field_descriptions)}

For each field, provide:
1. semantic_tag: Which category best fits (use "custom_field" if uncertain)
2. confidence: 0.0 to 1.0 based on clarity of the label/placeholder
3. reasoning: Brief explanation of your choice

Return JSON:
{{
    "fields": [
        {{"index": 0, "semantic_tag": "...", "confidence": 0.95, "reasoning": "..."}}
    ]
}}"""
    
    async def suggest_mappings(
        self,
        csv_columns: List[str],
        csv_samples: List[Dict[str, str]],
        profile_fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Suggest CSV column to field mappings.
        
        Returns:
            Dict with mapping suggestions
        """
        # Build sample data string
        sample_str = ""
        for i, row in enumerate(csv_samples[:3]):
            sample_str += f"Row {i+1}:\n"
            for col in csv_columns[:5]:  # Limit columns for brevity
                val = row.get(col, "")
                sample_str += f"  {col}: {val[:30]}...\n" if len(str(val)) > 30 else f"  {col}: {val}\n"
        
        field_str = ""
        for f in profile_fields:
            field_str += f"- {f.get('semantic_tag', 'unknown')}: {f.get('label', 'N/A')} (type: {f.get('field_type', 'text')})\n"
        
        prompt = f"""Match these CSV columns to the form fields.

CSV Columns: {', '.join(csv_columns)}

Sample Data:
{sample_str}

Target Form Fields:
{field_str}

Suggest the best mapping for each CSV column to a form field semantic tag.
Consider:
- Column names and their similarity to field labels
- Data types and formats
- Sample values

Return JSON:
{{
    "mappings": [
        {{"csv_column": "column_name", "semantic_tag": "field_tag", "confidence": 0.95, "reasoning": "..."}}
    ],
    "unmapped_csv_columns": ["column1", "column2"],
    "unmapped_fields": ["field_tag1"]
}}"""
        
        result = await self.complete(prompt)
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI mapping response: {result}")
            return {"mappings": [], "unmapped_csv_columns": csv_columns, "unmapped_fields": []}


# Global AI client instance
ai_client: Optional[AIClient] = None


def get_ai_client() -> AIClient:
    """Get or create global AI client instance."""
    global ai_client
    if ai_client is None:
        ai_client = AIClient()
    return ai_client
