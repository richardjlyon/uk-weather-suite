## ADDED Requirements

### Requirement: Listing parser under test
The CEDA JSON listing parser SHALL have tests driven by captured
listing fixtures (directory, station, qc-level, malformed/empty
responses), each fixture recording its capture date and source URL
in-file, asserting item extraction, dir/file discrimination and
retry-on-error behaviour without any network access.

#### Scenario: malformed listing does not panic
- **WHEN** the fixture is truncated JSON or an HTML error page
- **THEN** the parser returns an error naming the URL context, and the retry path is exercised

### Requirement: Token chain under test
The token source SHALL have tests covering: stored `ceda-token` found
(used verbatim), stored token absent with `ceda-credentials` present
(mint path invoked), and neither present (actionable error naming the
Keychain services) — with keychain and HTTP calls mocked; no test
touches a real secret or the network.

#### Scenario: fallback order is fixed
- **WHEN** both a stored token and credentials exist
- **THEN** the stored token wins and no mint call is made

### Requirement: Resumable-fetch logic under test
The skip/refetch decision SHALL have tests: size-match skips,
size-mismatch refetches, missing file fetches, and the dap-host URL
construction (the data-host redirect drops the Authorization header —
the reason the fetcher targets dap directly SHALL be asserted in a test
so a future refactor cannot silently regress it).

#### Scenario: the redirect regression is guarded
- **WHEN** a test inspects the fetch URL construction
- **THEN** it asserts the dap host is used directly, with a comment citing the header-dropping redirect
