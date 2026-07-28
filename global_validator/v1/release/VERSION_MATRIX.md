# Global Validator V1.1 Version Matrix

| Surface | Adopted authority |
|---|---|
| Global Validator engine | `global-validator-v1.1.0` |
| Global input / decision / certificate schemas | `1.1.0` |
| Contracts authority tag | `contracts-v1.1.0` |
| Contracts authority commit | `38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed` |
| Contracts manifest self SHA-256 | `e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b` |
| Gate registry | `1.1.0` |
| Sealed GatePolicyArtifact | `1.0.0` / `9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2` |
| Global gate-action selection policy | `1.0.0` / `4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5` |
| Feature contract | `1.1.0` |
| Frozen calibration | Contract fixture only; no production authority |

The published authority receipt is accepted in
`PINNED_PHYSICAL_FALLBACK` mode because its declared canonical self hash is
invalid. The exact physical receipt SHA-256 is pinned; see
`IMPLEMENTATION_FINDINGS_V1_1.md` (`GV-F005`).
