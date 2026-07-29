# Global Validator V1.1 Version Matrix

| Surface | Adopted authority |
|---|---|
| Global Validator engine | `global-validator-v1.1.0` |
| Global input / decision / certificate schemas | `1.1.0` |
| Contracts authority tag | `contracts-v1.1.0` |
| Contracts authority commit | `38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed` |
| Contracts manifest self SHA-256 | `e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b` |
| Active authority receipt | `release/v1.1.0-final/contracts_v1_1_0_authority_receipt_r2.json` / revision `2` |
| Authority receipt canonical self SHA-256 | `a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618` |
| Authority receipt physical SHA-256 | `acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79` |
| Reviewed R2 publication commit | `282409c470049760904fa16de4c67d711b5fcd00` |
| Reviewed R2 contracts tree | `938bca1f9c60596ef9403a43f0355476ad42afef` |
| Gate registry | `1.1.0` |
| Sealed GatePolicyArtifact | `1.0.0` / `9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2` |
| Global gate-action selection policy | `1.0.0` / `4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5` |
| Global gate-action policy authority | `1.0.0` / `1fca452c0604b7f41e9ffab72de0c134b108c52cafed279153bd7e98a0e8994a` |
| Portable replay spec | `GlobalValidatorReplaySpecV1` / `1.1.0` |
| Feature contract | `1.1.0` |
| Frozen calibration | Contract fixture only; no production authority |

The resealed published authority receipt is accepted only when both its
canonical self hash and physical SHA-256 match the published values. Successful
verification reports `CANONICAL_SELF_HASH` with zero warnings; see
`IMPLEMENTATION_FINDINGS_V1_1.md` (`GV-F010`).
