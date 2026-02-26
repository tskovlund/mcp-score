# Code Conventions

Shared conventions for all tskovlund repositories. Each repo includes the
relevant subset in its own AGENTS.md / CLAUDE.md / CONTRIBUTING.md.

## Code Quality

- **Explicit types whenever possible** — full type annotations in Python, no
  `var` in C#, no `auto` where the type isn't obvious. The reader should never
  have to guess a type
- **Proper fixes over workarounds.** Solve at the root cause. If a hack is
  unavoidable (something outside our control), track it so it can be replaced
  when a proper solution is available
- **No magic constants** — named constants for ports, protocol versions, error
  codes. Every literal value must be self-documenting
- **No DRY violations** — extract shared logic into a single source of truth.
  Prefer a base class or utility over copy-paste
- **Single responsibility** — each file and class has one clear purpose
- **Clean APIs / interface abstractions** — decouple code when valuable and
  appropriate
- **Full variable names** — `measure_index` not `m`, `connection` not `conn`.
  Intent should be readable, not inferred from abbreviations
- **No shorthand** — `exception` not `exc`, `message` not `msg`, `response`
  not `resp`
- **Idempotency** — scripts, migrations, and deployments must be safe to run
  twice

## Configuration

- **Externalize values that vary by environment or that users may need to
  change.** Hardcode what is truly constant
- **Choose the right configuration mechanism for the situation** — env vars for
  secrets and deployment, config files for complex settings, CI variables for
  build-time values

## Error Handling & Resilience

- **Surface problems, don't swallow them** — errors should be visible, not
  silently ignored
- **Validate data** — at system boundaries, API inputs, external data. Trust
  internal code
- **Proper retry patterns** — use battle-tested libraries (Polly/.NET,
  tenacity/Python, EF Core built-in retries) instead of homebrew retry loops
- **Structured logging** — use proper logging frameworks (`logging` in Python,
  Serilog/.NET, etc.) with consistent log levels (DEBUG/INFO/WARN/ERROR). No
  print debugging in production code
- **Fail CI on warnings** — warnings that persist become invisible. Either fix
  them or explicitly suppress with justification

## API Design

- **Predictable and consistent** — consistent naming, consistent error shapes,
  consistent return types. If one endpoint returns `{"error": "..."}`, all
  endpoints do
- **Version APIs deliberately** — whether versioning adds value depends on the
  technology and situation. Make it a conscious decision, not a default or an
  afterthought

## Library Usage

- **Battle-tested libraries for complex problems** — don't reinvent auth, retry
  logic, serialization, or anything with known edge cases
- **Skip trivial dependencies** — if a few lines of our own code solve the same
  problem, the dependency isn't worth it
- **Vet before adding** — check maintenance activity, security track record,
  and transitive dependency count
- **Discuss with the maintainer if unsure** — the right call isn't always
  obvious

## Dependencies & Security

- **Lockfiles always committed** — `uv.lock`, `package-lock.json`,
  `flake.lock`, etc. Reproducible builds
- **Pin direct dependencies to compatible ranges** — not exact (too noisy), not
  fully open (too risky)
- **CodeQL scanning in CI** when available
- **Dependabot/Renovate** for automated dependency updates when available
- **No secrets in code** — env vars or secret managers. `.env` files gitignored

## Testing

- **Naming:** `test_<action>_<expected_outcome>`
- **Structure:** Arrange / Act / Assert comments in every test
- **Lean:** every test must earn its place. No trivial tests, no tests of
  library/built-in functionality
- **No duplication:** shared logic tested once in the base, not per subclass
- **Complete coverage:** every error path, edge case, and branching condition
  that could fail in production
- **Integration tests alongside unit tests** — unit tests verify components in
  isolation, integration tests verify outcomes end-to-end. Both complement each
  other

## Git & Workflow

- **Conventional commits** — `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `chore:`
- **Direct to main** for small changes, **branch + PR** for structural work
- **PR review loop** before merge on structural changes

## Documentation

- **Diataxis framework** — tutorials, how-to guides, reference, explanation
- **README in every repo** — what the project does, how to set it up, how to
  run it. A repo without a README is incomplete

## Project Structure

- **Follow established conventions per language/framework** — `src/` layout in
  Python, standard framework structures elsewhere
- **AGENTS.md in every repo** with a CLAUDE.md symlink — the canonical file for
  AI agent instructions
- **Shared CI via `tskovlund/.github`** — reusable workflows for common
  patterns. Repos reference shared workflows instead of duplicating CI
  configuration
- **Automate enforcement** — CI checks, pre-commit/pre-push hooks, linting,
  and type checking should enforce every rule that can be checked automatically
- **Conventions belong in the repo** — each repo includes the relevant subset
  of these conventions in its own docs. Redundancy across repos is intentional
  so that every contributor picks them up

## Python-Specific

- **src layout** — all package code under `src/<package>/`
- **Pyright strict mode** — all function signatures fully typed
- **Ruff** for linting and formatting (line length 88)
- **`__all__` in every module** — explicitly declare the public API
