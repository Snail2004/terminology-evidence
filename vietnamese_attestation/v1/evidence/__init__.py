"""Evidence construction, source profiling, and deduplication."""

from .dedup import cluster_evidence_documents
from .sources import SourceProfile, profile_source
from .spans import CandidateSnippet, build_candidate_snippet

__all__ = [
    "CandidateSnippet",
    "SourceProfile",
    "build_candidate_snippet",
    "cluster_evidence_documents",
    "profile_source",
]
