# Contributing to Sigil

Thanks for your interest. Issues and pull requests are welcome.

## Before you submit a PR

You'll need to sign the [Contributor License Agreement](CLA.md) before any pull request can be merged. The signing flow is automated via [cla-assistant.io](https://cla-assistant.io/) — it will post a comment on your PR with a sign-in link the first time you contribute. Sign once and all your future PRs are covered.

The CLA grants the project the right to relicense contributions later (e.g. to maintain dual-license commercial offerings). It does not prevent you from using your own work elsewhere — you retain all rights to your contributions.

## What's a good PR

- **Bug fixes** with a reproducer in `tests/` (no test runner yet — manual smoke-test scripts are fine for v0.1)
- **Language adapters** following the pattern in `bin/sig`'s libcst path (see [SPEC.md](SPEC.md) for the format contract any new language must satisfy)
- **Documentation** improvements, including SPEC clarifications

## What's probably out of scope

- Major architectural rewrites without a prior discussion in an issue
- Changes that break the format spec (the on-disk sigil comment grammar is the contract; bumping it requires a version bump)
- Hard dependencies on services or daemons (the design constraint is "library + CLI, no daemon")

## Local development

```sh
git clone https://github.com/nik-hz/sigil
cd sigil
chmod +x bin/sig
# uv resolves deps on first run
./bin/sig --help
```

For a smoke test, see the recipe at the bottom of the [README](README.md).

## Reporting security issues

Don't open a public issue for security bugs. Email the maintainer or use GitHub's private security advisory feature on the repository.
