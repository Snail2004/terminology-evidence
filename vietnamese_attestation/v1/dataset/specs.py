from __future__ import annotations

from dataclasses import dataclass


V3_SCHEMA_ID = "D2LContextSupportSetValidationReadyV3"
V3_SCHEMA_VERSION = "3.0.0"
V3_DATASET_VERSION = "d2l_context_support_set_validation_ready_v3"
V3_ZIP_SHA256 = (
    "2f8e6ad0519854b161eda8cce61b13cdfc2f5ee54d205d18c27f279493c4fe52"
)
V3_MANIFEST_SHA256 = (
    "258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce"
)
V3_MANIFEST_FILE_SHA256 = (
    "b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8"
)

PILOT_SCHEMA_ID = "D2LCSTDevelopmentOnlyPilotV1_1"
PILOT_SCHEMA_VERSION = "1.1.0"
PILOT_ZIP_SHA256 = (
    "664cd5bf9e3006ebd77cffa6665a3cd86690dff0201fc518cae407a121aa4f15"
)
PILOT_MANIFEST_SHA256 = (
    "599692d33f9cc162698bc0e8fc0bf60cce1715cb0f34214fec499f14c1364eb5"
)
PILOT_MANIFEST_FILE_SHA256 = (
    "e45205adfe22b6b6c67680e159c64bb3c69c3a9849a3109a962134dc8cb3dd76"
)


@dataclass(frozen=True)
class DatasetArtifactSpec:
    schema_id: str
    schema_version: str
    zip_sha256: str
    manifest_sha256: str
    manifest_file_sha256: str
    dataset_version: str
    term_sense_count: int
    candidate_count: int
    context_count: int
    context_role_counts: tuple[tuple[str, int], ...]
    split_counts: tuple[tuple[str, int], ...]
    mode: str
    requires_parent_v3: bool


V3_SPEC = DatasetArtifactSpec(
    schema_id=V3_SCHEMA_ID,
    schema_version=V3_SCHEMA_VERSION,
    zip_sha256=V3_ZIP_SHA256,
    manifest_sha256=V3_MANIFEST_SHA256,
    manifest_file_sha256=V3_MANIFEST_FILE_SHA256,
    dataset_version=V3_DATASET_VERSION,
    term_sense_count=150,
    candidate_count=450,
    context_count=1340,
    context_role_counts=(
        ("BACKUP", 408),
        ("CONTRASTIVE", 150),
        ("PRIMARY", 740),
        ("UNSELECTED", 42),
    ),
    split_counts=(
        ("development", 100),
        ("test", 25),
        ("validation", 25),
    ),
    mode="VALIDATION_READY_ZERO_API",
    requires_parent_v3=False,
)

PILOT_SPEC = DatasetArtifactSpec(
    schema_id=PILOT_SCHEMA_ID,
    schema_version=PILOT_SCHEMA_VERSION,
    zip_sha256=PILOT_ZIP_SHA256,
    manifest_sha256=PILOT_MANIFEST_SHA256,
    manifest_file_sha256=PILOT_MANIFEST_FILE_SHA256,
    dataset_version=V3_DATASET_VERSION,
    term_sense_count=5,
    candidate_count=15,
    context_count=38,
    context_role_counts=(
        ("BACKUP", 8),
        ("CONTRASTIVE", 5),
        ("PRIMARY", 25),
    ),
    split_counts=(("development", 5),),
    mode="DEVELOPMENT_ZERO_API",
    requires_parent_v3=True,
)

SUPPORTED_BY_ZIP_SHA256 = {
    V3_SPEC.zip_sha256: V3_SPEC,
    PILOT_SPEC.zip_sha256: PILOT_SPEC,
}


__all__ = [
    "DatasetArtifactSpec",
    "PILOT_MANIFEST_SHA256",
    "PILOT_SCHEMA_ID",
    "PILOT_SCHEMA_VERSION",
    "PILOT_SPEC",
    "PILOT_ZIP_SHA256",
    "SUPPORTED_BY_ZIP_SHA256",
    "V3_DATASET_VERSION",
    "V3_MANIFEST_SHA256",
    "V3_SCHEMA_ID",
    "V3_SCHEMA_VERSION",
    "V3_SPEC",
    "V3_ZIP_SHA256",
]
