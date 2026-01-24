"""Bullet library schema for approved resume bullets."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class Bullet(BaseModel):
    """Approved resume bullet point."""
    id: str
    text: str
    tags: List[str] = []
    metrics: Optional[Dict[str, Any]] = {}
    context: Optional[str] = None  # When to use this bullet


class BulletLibrary(BaseModel):
    """Bullet library collection."""
    bullets: List[Bullet] = []
    
    def get_bullets_by_tags(self, tags: List[str]) -> List[Bullet]:
        """Get bullets matching any of the given tags."""
        matching = []
        for bullet in self.bullets:
            if any(tag in bullet.tags for tag in tags):
                matching.append(bullet)
        return matching
    
    def get_bullet_by_id(self, bullet_id: str) -> Optional[Bullet]:
        """Get bullet by ID."""
        for bullet in self.bullets:
            if bullet.id == bullet_id:
                return bullet
        return None
