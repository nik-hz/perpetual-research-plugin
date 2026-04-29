# Contributing to Sigil

Thanks for your interest. Issues and pull requests are welcome.

By submitting a contribution to this repository, you agree that your contribution is licensed under the [MIT License](LICENSE), the same license the project itself ships under (`inbound = outbound`). No separate signoff or CLA is required.

## What's a good PR

- **Bug fixes** with a small reproducer (a manual smoke-test script under `tests/` is fine for v0.1; a real test runner is on the roadmap).
- **Language adapters** following the libcst pattern in `bin/sig`. See [SPEC.md](SPEC.md) for the format contract any new language must satisfy.
- **Spec clarifications** in `SPEC.md`. The on-disk sigil grammar is the contract — bumping it requires a version bump.
- **Documentation** improvements.

## What's probably out of scope

- Major architectural rewrites without a prior discussion in an issue.
- Hard dependencies on services or daemons. Design constraint: library + CLI, no daemon.
- Changes that break wire-format compatibility with existing sidecars without a version bump path.

## Local development

```sh
git clone https://github.com/nik-hz/sigil
cd sigil
chmod +x bin/sig
./bin/sig --help          # uv resolves deps on first run
```

To test your local changes inside Claude Code, use the per-session install:

```sh
claude --plugin-dir /path/to/sigil
```

Or register your local clone as a marketplace source:

```text
/plugin marketplace add ~/code/sigil
/plugin install sigil@nik-hz
```

Changes are picked up on the next Claude Code session (or after `/reload-plugins`).

For a smoke test, see the recipe at the bottom of the [README](README.md).

## Versioning

Version numbers live in two places:

- `.claude-plugin/plugin.json` — the version Claude Code sees
- `.claude-plugin/marketplace.json` — the marketplace version

Bump both when cutting a release. The sidecar format version (`"version"` in `.sigil/index.json`) is governed by [SPEC.md](SPEC.md) and should only be bumped for breaking schema changes with a documented migration path.

## Reporting security issues

Don't open a public issue for security bugs. Use GitHub's private security advisory feature on the repository, or contact the maintainer directly.
