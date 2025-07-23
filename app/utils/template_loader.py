import os
from typing import Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class EmailTemplateLoader:
    """Simple template loader for email templates"""
    
    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "templates"
        self._template_cache = {}
    
    def load_template(self, template_name: str) -> str:
        """Load template content from file"""
        if template_name in self._template_cache:
            return self._template_cache[template_name]
        
        template_path = self.template_dir / f"{template_name}.html"
        
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            raise FileNotFoundError(f"Template {template_name}.html not found")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._template_cache[template_name] = content
                return content
        except Exception as e:
            logger.error(f"Error loading template {template_name}: {str(e)}")
            raise
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render template with context variables"""
        template_content = self.load_template(template_name)
        
        # Simple template rendering using string formatting
        # For more complex templating, consider using Jinja2
        try:
            # Handle conditional blocks for Jinja2-like syntax
            rendered = self._render_conditionals(template_content, context)
            
            # Replace variables
            for key, value in context.items():
                placeholder = f"{{{{ {key} }}}}"
                rendered = rendered.replace(placeholder, str(value or ""))
            
            return rendered
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise
    
    def _render_conditionals(self, content: str, context: Dict[str, Any]) -> str:
        """Handle simple conditional blocks like {% if variable %}"""
        import re
        
        # Handle {% if variable %} blocks
        def replace_if_block(match):
            variable = match.group(1).strip()
            block_content = match.group(2)
            
            # Check if variable exists and is truthy
            if variable in context and context[variable]:
                return block_content
            else:
                return ""
        
        # Pattern to match {% if variable %}...{% endif %}
        if_pattern = r'{%\s*if\s+(\w+)\s*%}(.*?){%\s*endif\s*%}'
        content = re.sub(if_pattern, replace_if_block, content, flags=re.DOTALL)
        
        return content
    
    def get_text_version(self, html_content: str) -> str:
        """Convert HTML to plain text for email text version"""
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Replace HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

# Global template loader instance
template_loader = EmailTemplateLoader()