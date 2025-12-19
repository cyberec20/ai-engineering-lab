# Changelog — Session5

## Unreleased

### Fixed
- LangSmith traces: spans/root no longer end with empty outputs (previously shown as `Raw Output: null`); each step now records minimal structured outputs (counts/status) and the root run records a final status summary.
- Tracing end is now idempotent to avoid double-close overwriting outputs.

