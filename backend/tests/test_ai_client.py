"""
Tests for AI Client.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ..services.ai_client import AIClient, OpenAIProvider, OllamaProvider


@pytest.mark.asyncio
async def test_ollama_provider_complete():
    """Test Ollama text completion."""
    provider = OllamaProvider(base_url="http://localhost:11434")
    
    mock_response = MagicMock()
    mock_response.json = AsyncMock(return_value={"response": "Test response"})
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await provider.complete("Test prompt")
        assert result == "Test response"


@pytest.mark.asyncio
async def test_ai_client_with_fallback():
    """Test AI client with fallback to Ollama when OpenAI fails."""
    # Create mock providers
    primary = AsyncMock()
    primary.complete.side_effect = Exception("OpenAI failed")
    
    fallback = AsyncMock()
    fallback.complete.return_value = "Fallback response"
    
    client = AIClient(primary=primary, fallback=fallback)
    
    result = await client.complete("Test prompt")
    
    assert result == "Fallback response"
    primary.complete.assert_called_once()
    fallback.complete.assert_called_once()


@pytest.mark.asyncio
async def test_ai_client_fallback_disabled():
    """Test AI client when fallback is disabled/fails."""
    primary = AsyncMock()
    primary.complete.side_effect = Exception("OpenAI failed")
    
    fallback = AsyncMock()
    fallback.complete.side_effect = Exception("Ollama also failed")
    
    client = AIClient(primary=primary, fallback=fallback)
    
    with pytest.raises(RuntimeError):
        await client.complete("Test prompt")


def test_build_field_analysis_prompt():
    """Test building field analysis prompt."""
    client = AIClient()
    
    fields = [
        {
            "type": "text",
            "label": "First Name",
            "placeholder": "Enter your first name",
            "name": "firstName",
            "required": True
        },
        {
            "type": "email",
            "label": "Email Address",
            "placeholder": "your@email.com",
            "name": "email",
            "required": True
        }
    ]
    
    prompt = client._build_field_analysis_prompt(fields)
    
    assert "First Name" in prompt
    assert "Email Address" in prompt
    assert "given_name" in prompt
    assert "email" in prompt
    assert "semantic_tag" in prompt


@pytest.mark.asyncio
async def test_suggest_mappings():
    """Test AI mapping suggestions."""
    client = AIClient()
    
    # Mock the complete method
    mock_response = '''
    {
        "mappings": [
            {"csv_column": "first_name", "semantic_tag": "given_name", "confidence": "high", "reasoning": "Direct match"},
            {"csv_column": "email", "semantic_tag": "email", "confidence": "high", "reasoning": "Direct match"}
        ],
        "unmapped_csv_columns": ["phone"],
        "unmapped_fields": []
    }
    '''
    
    with patch.object(client, 'complete', return_value=mock_response):
        result = await client.suggest_mappings(
            csv_columns=["first_name", "email", "phone"],
            csv_samples=[{"first_name": "John", "email": "john@example.com", "phone": "555-1234"}],
            profile_fields=[
                {"semantic_tag": "given_name", "label": "First Name", "field_type": "text"},
                {"semantic_tag": "email", "label": "Email", "field_type": "email"}
            ]
        )
        
        assert "mappings" in result
        assert len(result["mappings"]) == 2
        assert "phone" in result["unmapped_csv_columns"]
