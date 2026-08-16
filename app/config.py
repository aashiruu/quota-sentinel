from typing import Dict
from pydantic import BaseModel


class TierConfig(BaseModel):
    name: str
    rate_limit: int  # Requests per minute window
    burst_limit: int


TIER_DEFINITIONS: Dict[str, TierConfig] = {
    "free": TierConfig(name="free", rate_limit=5, burst_limit=5),
    "standard": TierConfig(name="standard", rate_limit=20, burst_limit=20),
    "premium": TierConfig(name="premium", rate_limit=60, burst_limit=60),
}

TENANT_TIER_MAP: Dict[str, str] = {
    "tenant-free": "free",
    "tenant-alpha": "free",
    "tenant-standard": "standard",
    "tenant-beta": "standard",
    "tenant-premium": "premium",
}


def get_tenant_tier(tenant_id: str) -> TierConfig:
    tier_name = TENANT_TIER_MAP.get(tenant_id, "free")
    return TIER_DEFINITIONS.get(tier_name, TIER_DEFINITIONS["free"])
