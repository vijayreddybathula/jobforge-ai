"""
Bullet library — approved resume statements seeded from Vijay's actual resume.
These are the ONLY bullets the resume tailor can use as a base.
The LLM may rephrase/reorder but cannot invent new claims.

Each bullet has:
  - id: unique stable identifier
  - text: the approved statement
  - tags: skill/domain tags for retrieval
  - metrics: quantified claims (must be preserved exactly)
"""

from typing import List, Dict, Any, Optional

BULLET_LIBRARY: List[Dict[str, Any]] = [
    # --- Azure OpenAI / GenAI Systems ---
    {
        "id": "VR-001",
        "text": "Architected and deployed production-grade Azure OpenAI (Assistants API + Responses API) pipelines handling multi-agent workflows with RAG, tool & function calling, and structured JSON outputs.",
        "tags": ["azure_openai", "assistants_api", "responses_api", "rag", "multi_agent", "genai"],
        "metrics": [],
    },
    {
        "id": "VR-002",
        "text": "Built metadata-aware chunking and hybrid semantic + filter-based retrieval systems using PGVector and Azure Blob Storage, reducing retrieval latency and improving answer relevance.",
        "tags": ["pgvector", "rag", "azure_blob", "embeddings", "retrieval"],
        "metrics": [],
    },
    {
        "id": "VR-003",
        "text": "Implemented LLM evaluation datasets and behavioral drift detection pipelines to monitor GenAI system quality in production, enabling proactive prompt/version control.",
        "tags": ["llm_evaluation", "monitoring", "prompt_versioning", "genai"],
        "metrics": [],
    },
    {
        "id": "VR-004",
        "text": "Designed token usage and latency monitoring dashboards for Azure OpenAI deployments, enabling cost and latency optimization across multiple LLM-powered services.",
        "tags": ["azure_openai", "monitoring", "cost_optimization", "latency"],
        "metrics": [],
    },
    # --- Backend / FastAPI / Python ---
    {
        "id": "VR-005",
        "text": "Developed schema-first RESTful APIs using FastAPI and Pydantic with AsyncIO, supporting high-throughput document ingestion pipelines and streaming responses.",
        "tags": ["fastapi", "python", "pydantic", "asyncio", "rest_api"],
        "metrics": [],
    },
    {
        "id": "VR-006",
        "text": "Built event-driven microservices using Kafka and Redis for real-time job orchestration, achieving reliable task deduplication and ordered processing at scale.",
        "tags": ["kafka", "redis", "microservices", "event_driven", "python"],
        "metrics": [],
    },
    {
        "id": "VR-007",
        "text": "Implemented TDD practices with regression testing suites for GenAI services, maintaining code quality standards through CI/CD pipelines with SonarQube and GitHub Actions.",
        "tags": ["tdd", "testing", "ci_cd", "sonarqube", "github_actions", "devsecops"],
        "metrics": [],
    },
    # --- Cloud / Infrastructure ---
    {
        "id": "VR-008",
        "text": "Led cloud migration of enterprise workloads to Azure (AKS, APIM, Blob Storage, CosmosDB), establishing DevSecOps pipelines and observability frameworks for production deployments.",
        "tags": ["azure", "aks", "kubernetes", "cloud_migration", "devsecops", "apim"],
        "metrics": [],
    },
    {
        "id": "VR-009",
        "text": "Containerized and deployed distributed AI services using Docker and Kubernetes (AKS), enabling zero-downtime deployments and horizontal scaling for LLM inference workloads.",
        "tags": ["docker", "kubernetes", "aks", "azure", "deployment"],
        "metrics": [],
    },
    # --- Data / Databases ---
    {
        "id": "VR-010",
        "text": "Designed and optimized PostgreSQL schemas with pgvector extensions for hybrid semantic search, implementing query optimization strategies that reduced p95 latency.",
        "tags": ["postgresql", "pgvector", "data_modeling", "query_optimization", "databases"],
        "metrics": [],
    },
    {
        "id": "VR-011",
        "text": "Integrated Elasticsearch for full-text search across document ingestion pipelines, supporting metadata-aware indexing strategies for large-scale enterprise knowledge bases.",
        "tags": ["elasticsearch", "search", "indexing", "data"],
        "metrics": [],
    },
    # --- Java / SpringBoot ---
    {
        "id": "VR-012",
        "text": "Built enterprise-grade SpringBoot microservices in Java with RESTful APIs, integrating with Azure APIM and downstream systems for supply chain intelligence platforms.",
        "tags": ["java", "springboot", "microservices", "rest_api", "enterprise"],
        "metrics": [],
    },
    # --- Cross-functional ---
    {
        "id": "VR-013",
        "text": "Collaborated with cross-functional Agile/Scrum teams across product, design, and data science to deliver GenAI features from ideation to production, adhering to structured release cycles.",
        "tags": ["agile", "scrum", "collaboration", "cross_functional"],
        "metrics": [],
    },
    {
        "id": "VR-014",
        "text": "Mentored junior engineers on GenAI architecture patterns, prompt engineering best practices, and production debugging of LLM-powered systems.",
        "tags": ["mentoring", "leadership", "genai", "prompt_engineering"],
        "metrics": [],
    },
]


def get_bullets_by_tags(tags: List[str], min_match: int = 1) -> List[Dict[str, Any]]:
    """Retrieve bullets matching any of the given tags."""
    results = []
    tags_lower = [t.lower() for t in tags]
    for bullet in BULLET_LIBRARY:
        bullet_tags_lower = [t.lower() for t in bullet["tags"]]
        matches = sum(1 for t in tags_lower if any(t in bt or bt in t for bt in bullet_tags_lower))
        if matches >= min_match:
            results.append({**bullet, "match_score": matches})
    return sorted(results, key=lambda x: x["match_score"], reverse=True)


def get_all_bullets() -> List[Dict[str, Any]]:
    return list(BULLET_LIBRARY)


def get_bullet_by_id(bullet_id: str) -> Optional[Dict[str, Any]]:
    for b in BULLET_LIBRARY:
        if b["id"] == bullet_id:
            return b
    return None


def get_bullet_ids_text_map() -> Dict[str, str]:
    """Return {id: text} map for prompt injection."""
    return {b["id"]: b["text"] for b in BULLET_LIBRARY}
