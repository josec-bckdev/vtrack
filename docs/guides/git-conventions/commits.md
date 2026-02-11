# How to Commit

## Quick Start
Instead of `git commit`, use:
```bash
npm run commit
```

This launches an interactive prompt that ensures your commit follows our conventions.

## First Time Setup
```bash
npm install
npx husky install
```

## The Prompt Will Ask:
1. **Type** - What kind of change? (feat, fix, etc.)
2. **Scope** - What part of the codebase? (auth, api, etc.)
3. **Subject** - Short description (max 50 chars)
4. **Body** - Detailed explanation (optional)
5. **Breaking Changes** - Any breaking changes? (optional)
6. **Issues** - Close any issues? (optional)

## Examples
See [commit_conventions](./commit_conventions.md) for detailed examples.

## Troubleshooting
**"commitlint failed"** - Your commit message doesn't follow conventions. Read the error and try again.
**"npm run commit not working"** - Run `npm install` first.