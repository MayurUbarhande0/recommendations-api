from pydantic import BaseModel
from typing import Dict, List, Optional


class Product(BaseModel):
    product_id: int
    name: str
    price: Optional[float] = None
    category: Optional[str] = None
    unit: Optional[int] = None
    is_available: bool = True


class User(BaseModel):
    id: int
    name: Optional[str] = None
    is_active: Optional[bool] = True


# ── Recommendation response models ───────────────────────────────────────────

class CategoryScore(BaseModel):
    """A category with its time-decayed combined score."""
    category: str
    score: float


class ArchetypeInfo(BaseModel):
    """Result of the ML archetype classifier."""
    archetype: str
    confidence: float
    all_scores: Dict[str, float]


class UserProfile(BaseModel):
    """Behavioural profile of the user derived from their interaction history."""
    engagement_level: str
    purchase_intent: str
    user_segment: str
    archetype: str
    archetype_confidence: float
    features: Dict[str, float]


class RecommendationResult(BaseModel):
    """The recommendation payload embedded inside ``RecommendationResponse``."""
    weightage: float
    search_weight: float
    purchase_weight: float
    recommended_categories: List[str]
    explore_categories: List[str]
    top_categories: List[CategoryScore]
    user_profile: UserProfile
    purchase_probabilities: Dict[str, float]


class RecommendationResponse(BaseModel):
    """Full response schema for ``GET /recommend/{user_id}``."""
    user_id: int
    recommendations: RecommendationResult
    metadata: Dict[str, int]

