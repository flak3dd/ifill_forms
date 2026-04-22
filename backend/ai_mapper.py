import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Tuple
import logging
from playwright.async_api import async_playwright, Page
from .config import settings
from .schemas import SiteAnalysis, FieldInfo, MappingSuggestion, FieldMapping

logger = logging.getLogger(__name__)

class AIMapper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        
    async def initialize(self):
        """Initialize Playwright for site analysis"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
    
    async def analyze_website(self, url: str) -> SiteAnalysis:
        """Analyze a website to detect forms and create a profile"""
        await self.initialize()
        
        try:
            page = await self.browser.new_page()
            response = await page.goto(url, wait_until="networkidle")
            
            if response.status >= 400:
                raise Exception(f"Failed to load page: {response.status}")
            
            # Get page title
            title = await page.title()
            
            # Detect forms using multiple methods
            forms = await self._detect_forms(page)
            
            # Check for multi-step flows
            multi_step = await self._detect_multi_step(page)
            
            # Estimate success rate and confidence
            success_rate = self._estimate_success_rate(forms, multi_step)
            confidence = self._calculate_confidence(forms)
            
            return SiteAnalysis(
                url=url,
                title=title,
                forms=forms,
                multi_step=multi_step,
                estimated_success_rate=success_rate,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Site analysis error: {str(e)}")
            raise
        finally:
            if 'page' in locals():
                await page.close()
    
    async def _detect_forms(self, page: Page) -> List[FieldInfo]:
        """Detect form fields using multiple strategies"""
        forms = []
        
        # Strategy 1: DOM analysis
        dom_fields = await self._detect_dom_fields(page)
        forms.extend(dom_fields)
        
        # Strategy 2: AI vision analysis (if OpenAI API is available)
        if settings.OPENAI_API_KEY:
            try:
                vision_fields = await self._detect_vision_fields(page)
                # Merge with DOM fields, preferring AI-detected ones
                forms = self._merge_field_detections(forms, vision_fields)
            except Exception as e:
                logger.warning(f"Vision analysis failed: {str(e)}")
        
        # Strategy 3: Semantic field inference
        semantic_fields = await self._infer_semantic_fields(page)
        forms = self._merge_field_detections(forms, semantic_fields)
        
        return forms
    
    async def _detect_dom_fields(self, page: Page) -> List[FieldInfo]:
        """Detect fields using DOM analysis"""
        fields = []
        
        # Find all input elements
        inputs = await page.query_selector_all("input, select, textarea")
        
        for input_element in inputs:
            try:
                field_info = await self._extract_field_info(input_element)
                if field_info:
                    fields.append(field_info)
            except Exception as e:
                logger.warning(f"Failed to extract field info: {str(e)}")
        
        return fields
    
    async def _extract_field_info(self, element) -> Optional[FieldInfo]:
        """Extract field information from a DOM element"""
        try:
            # Get basic attributes
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            field_type = await element.get_attribute("type") or tag_name
            
            # Get label text
            label_text = await self._get_label_text(element)
            
            # Get placeholder text
            placeholder = await element.get_attribute("placeholder") or ""
            
            # Check if required
            is_required = await element.get_attribute("required") is not None
            
            # Build locator
            locator = self._build_dom_locator(element, tag_name, field_type)
            
            # Determine semantic tag
            semantic_tag = self._infer_semantic_tag(label_text, placeholder, field_type)
            
            # Get options for select elements
            options = None
            if tag_name == "select":
                options = await self._get_select_options(element)
            
            return FieldInfo(
                semantic_tag=semantic_tag,
                label=label_text or placeholder or f"Field {len(locator)}",
                field_type=field_type,
                locator=locator,
                required=is_required,
                options=options
            )
            
        except Exception as e:
            logger.warning(f"Field extraction error: {str(e)}")
            return None
    
    async def _get_label_text(self, element) -> str:
        """Get the label text for a form element"""
        try:
            # Try to find associated label
            label_id = await element.get_attribute("id")
            if label_id:
                label = await element.query_selector(f"label[for='{label_id}']")
                if label:
                    return await label.inner_text()
            
            # Try to find parent label
            parent_label = await element.query_selector("xpath=./ancestor::label")
            if parent_label:
                return await parent_label.inner_text()
            
            # Try to find preceding text
            preceding_text = await element.evaluate("""
                el => {
                    const text = el.previousSibling?.textContent?.trim() || 
                               el.parentElement?.previousElementSibling?.textContent?.trim();
                    return text || '';
                }
            """)
            
            return preceding_text.strip()
            
        except Exception:
            return ""
    
    def _build_dom_locator(self, element, tag_name: str, field_type: str) -> Dict[str, Any]:
        """Build a reliable DOM locator"""
        locator = {}
        
        # Try ID first
        element_id = getattr(element, 'id', None)
        if element_id:
            locator["selector"] = f"#{element_id}"
            return locator
        
        # Try name attribute
        element_name = getattr(element, 'name', None)
        if element_name:
            locator["selector"] = f"[name='{element_name}']"
            return locator
        
        # Try type + placeholder/name combination
        placeholder = getattr(element, 'placeholder', None)
        if placeholder:
            locator["placeholder"] = placeholder
        else:
            locator["type"] = field_type
        
        return locator
    
    def _infer_semantic_tag(self, label: str, placeholder: str, field_type: str) -> str:
        """Infer semantic field type from label and attributes"""
        text = (label + " " + placeholder).lower()
        
        # Name fields
        if any(word in text for word in ["first name", "given name", "fname"]):
            return "given_name"
        elif any(word in text for word in ["last name", "surname", "lname", "family name"]):
            return "family_name"
        elif any(word in text for word in ["name", "full name"]):
            return "full_name"
        
        # Contact fields
        elif any(word in text for word in ["email", "e-mail"]):
            return "email"
        elif any(word in text for word in ["phone", "telephone", "mobile"]):
            return "phone"
        
        # Address fields
        elif any(word in text for word in ["address", "street"]):
            return "address"
        elif "city" in text:
            return "city"
        elif any(word in text for word in ["state", "province"]):
            return "state"
        elif any(word in text for word in ["zip", "postal", "postcode"]):
            return "postal_code"
        elif "country" in text:
            return "country"
        
        # Professional fields
        elif any(word in text for word in ["job title", "position", "role"]):
            return "job_title"
        elif any(word in text for word in ["company", "employer"]):
            return "company"
        elif any(word in text for word in ["experience", "years"]):
            return "experience"
        elif any(word in text for word in ["education", "degree"]):
            return "education"
        elif any(word in text for word in ["skills", "qualifications"]):
            return "skills"
        elif any(word in text for word in ["salary", "compensation", "pay"]):
            return "salary"
        
        # Application fields
        elif any(word in text for word in ["cover letter", "letter", "message"]):
            return "cover_letter"
        elif any(word in text for word in ["resume", "cv"]):
            return "resume"
        elif any(word in text for word in ["availability", "start date"]):
            return "availability"
        
        # Default to field type
        else:
            return f"field_{field_type}"
    
    async def _get_select_options(self, element) -> List[str]:
        """Get options for a select element"""
        try:
            options = await element.query_selector_all("option")
            option_texts = []
            
            for option in options:
                text = await option.inner_text()
                if text.strip():
                    option_texts.append(text.strip())
            
            return option_texts
            
        except Exception:
            return []
    
    async def _detect_vision_fields(self, page: Page) -> List[FieldInfo]:
        """Use AI vision to detect form fields"""
        if not settings.OPENAI_API_KEY:
            return []
        
        try:
            # Take screenshot
            screenshot = await page.screenshot()
            
            # Use vision model to analyze
            # This would integrate with OpenAI Vision API
            # For now, return empty list as placeholder
            
            return []
            
        except Exception as e:
            logger.warning(f"Vision detection failed: {str(e)}")
            return []
    
    async def _infer_semantic_fields(self, page: Page) -> List[FieldInfo]:
        """Infer additional semantic fields using page context"""
        fields = []
        
        # Look for common patterns
        patterns = [
            {"selector": "input[type='file']", "semantic": "file_upload", "type": "file"},
            {"selector": "input[type='checkbox']", "semantic": "agreement", "type": "checkbox"},
            {"selector": "textarea", "semantic": "long_text", "type": "textarea"},
        ]
        
        for pattern in patterns:
            elements = await page.query_selector_all(pattern["selector"])
            for element in elements:
                try:
                    label_text = await self._get_label_text(element)
                    
                    field_info = FieldInfo(
                        semantic_tag=pattern["semantic"],
                        label=label_text or f"Field {len(fields)}",
                        field_type=pattern["type"],
                        locator={"selector": pattern["selector"]},
                        required=False
                    )
                    fields.append(field_info)
                    
                except Exception as e:
                    logger.warning(f"Semantic field inference error: {str(e)}")
        
        return fields
    
    def _merge_field_detections(self, primary: List[FieldInfo], secondary: List[FieldInfo]) -> List[FieldInfo]:
        """Merge field detection results, preferring primary"""
        # Simple merge - in production would be more sophisticated
        seen_labels = set(field.label for field in primary)
        
        for field in secondary:
            if field.label not in seen_labels:
                primary.append(field)
        
        return primary
    
    async def _detect_multi_step(self, page: Page) -> bool:
        """Detect if this is a multi-step form"""
        try:
            # Look for step indicators
            step_indicators = await page.query_selector_all(
                "[class*='step'], [class*='progress'], [class*='wizard'], [class*='tab']"
            )
            
            if len(step_indicators) > 1:
                return True
            
            # Look for next/previous buttons
            nav_buttons = await page.query_selector_all(
                "[class*='next'], [class*='previous'], [class*='continue'], [class*='back']"
            )
            
            if len(nav_buttons) > 1:
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Multi-step detection error: {str(e)}")
            return False
    
    def _estimate_success_rate(self, forms: List[FieldInfo], multi_step: bool) -> float:
        """Estimate automation success rate"""
        base_rate = 0.8
        
        # Adjust based on form complexity
        if len(forms) > 20:
            base_rate -= 0.1
        elif len(forms) < 5:
            base_rate += 0.1
        
        # Adjust for multi-step
        if multi_step:
            base_rate -= 0.1
        
        # Adjust for field types
        complex_fields = sum(1 for field in forms if field.field_type in ['file', 'captcha'])
        if complex_fields > 0:
            base_rate -= 0.2 * complex_fields
        
        return max(0.1, min(0.95, base_rate))
    
    def _calculate_confidence(self, forms: List[FieldInfo]) -> float:
        """Calculate confidence in field detection"""
        if not forms:
            return 0.0
        
        # High confidence if we have good labels and semantic tags
        labeled_fields = sum(1 for field in forms if field.label and not field.label.startswith("Field"))
        semantic_fields = sum(1 for field in forms if not field.semantic_tag.startswith("field_"))
        
        confidence = (labeled_fields + semantic_fields) / (2 * len(forms))
        return max(0.1, min(0.95, confidence))
    
    async def map_fields(self, profile_data: Dict[str, Any], csv_preview: List[Dict[str, Any]]) -> MappingSuggestion:
        """AI-powered field mapping from CSV to profile"""
        try:
            # Extract fields from profile
            profile_fields = profile_data.get("forms", [])
            
            # Extract CSV columns
            csv_columns = list(csv_preview[0].keys()) if csv_preview else []
            
            mappings = []
            unmapped_columns = []
            unmapped_fields = []
            
            # Map each profile field to CSV column
            for field in profile_fields:
                semantic_tag = field.semantic_tag
                best_match = self._find_best_column_match(semantic_tag, csv_columns, field.label)
                
                if best_match:
                    confidence = self._calculate_mapping_confidence(semantic_tag, best_match, field.label)
                    mappings.append(FieldMapping(
                        csv_column=best_match,
                        field_semantic=semantic_tag,
                        confidence=confidence,
                        transformation=self._suggest_transformation(semantic_tag, best_match, csv_preview)
                    ))
                    csv_columns.remove(best_match)  # Remove to avoid duplicate mappings
                else:
                    unmapped_fields.append(semantic_tag)
            
            unmapped_columns = csv_columns  # Remaining columns
            
            # Calculate overall confidence
            overall_confidence = sum(m.confidence for m in mappings) / len(mappings) if mappings else 0.0
            
            return MappingSuggestion(
                mappings=mappings,
                unmapped_columns=unmapped_columns,
                unmapped_fields=unmapped_fields,
                overall_confidence=overall_confidence
            )
            
        except Exception as e:
            logger.error(f"Field mapping error: {str(e)}")
            raise
    
    def _find_best_column_match(self, semantic_tag: str, csv_columns: List[str], field_label: str) -> Optional[str]:
        """Find the best CSV column match for a semantic field"""
        # Semantic to column name mappings
        semantic_mappings = {
            "given_name": ["first", "fname", "given"],
            "family_name": ["last", "lname", "surname", "family"],
            "full_name": ["name", "full"],
            "email": ["email", "e-mail", "mail"],
            "phone": ["phone", "telephone", "mobile", "tel"],
            "address": ["address", "street"],
            "city": ["city"],
            "state": ["state", "province"],
            "postal_code": ["zip", "postal", "postcode"],
            "country": ["country"],
            "job_title": ["title", "position", "role"],
            "company": ["company", "employer"],
            "experience": ["experience", "years"],
            "education": ["education", "degree"],
            "skills": ["skills", "qualifications"],
            "salary": ["salary", "pay", "compensation"],
            "cover_letter": ["cover", "letter", "message"],
            "resume": ["resume", "cv"],
            "availability": ["availability", "start", "date"]
        }
        
        # Get search terms for this semantic tag
        search_terms = semantic_mappings.get(semantic_tag, [semantic_tag.replace("_", " ")])
        
        # Add field label to search terms
        search_terms.extend(field_label.lower().split())
        
        # Score each column
        best_column = None
        best_score = 0
        
        for column in csv_columns:
            column_lower = column.lower()
            score = 0
            
            # Exact matches
            for term in search_terms:
                if term in column_lower:
                    score += 10
                    if column_lower.startswith(term):
                        score += 5
                    if column_lower == term:
                        score += 10
            
            # Partial matches
            for term in search_terms:
                if any(word in column_lower for word in term.split()):
                    score += 3
            
            if score > best_score:
                best_score = score
                best_column = column
        
        return best_column if best_score >= 5 else None
    
    def _calculate_mapping_confidence(self, semantic_tag: str, csv_column: str, field_label: str) -> float:
        """Calculate confidence score for a field mapping"""
        confidence = 0.5  # Base confidence
        
        column_lower = csv_column.lower()
        semantic_lower = semantic_tag.lower()
        label_lower = field_label.lower()
        
        # Exact semantic match
        if semantic_lower in column_lower:
            confidence += 0.3
        
        # Label match
        if any(word in column_lower for word in label_lower.split()):
            confidence += 0.2
        
        # Common field patterns
        if semantic_tag == "email" and "email" in column_lower:
            confidence = 0.95
        elif semantic_tag == "phone" and "phone" in column_lower:
            confidence = 0.95
        
        return min(0.95, confidence)
    
    def _suggest_transformation(self, semantic_tag: str, csv_column: str, csv_preview: List[Dict[str, Any]]) -> Optional[str]:
        """Suggest data transformation for a mapping"""
        if not csv_preview:
            return None
        
        # Sample values from CSV
        sample_values = [str(row.get(csv_column, "")) for row in csv_preview[:5]]
        sample_values = [val for val in sample_values if val.strip()]
        
        if not sample_values:
            return None
        
        # Check for transformation needs
        if semantic_tag == "email":
            return "email_clean"
        elif semantic_tag == "phone":
            return "phone_format"
        elif semantic_tag in ["given_name", "family_name", "city", "state"]:
            # Check if values need title case
            if any(val.isupper() or val.islower() for val in sample_values if val):
                return "title_case"
        elif semantic_tag == "job_title":
            return "title_case"
        
        return None
    
    async def cleanup(self):
        """Clean up resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
