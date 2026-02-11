# Git Commit Message Conventions

## 📋 Overview

This document outlines the commit message conventions for our project. Following these guidelines ensures a clean, readable Git history and enables automatic changelog generation.

## 🎯 The 7 Rules

1. **Separate subject from body** with a blank line
2. **Limit subject line** to 50 characters
3. **Capitalize** the subject line
4. **Do not end** subject line with a period
5. **Use imperative mood** ("add feature" not "added feature")
6. **Wrap body** at 72 characters
7. **Explain WHY** in body, not just what

## 📝 Commit Structure

```
<type>(<scope>): <subject>

<body>

<footer>
```

### **Types** (Required)

| Type       | Description                                                                 |
|------------|-----------------------------------------------------------------------------|
| `feat`     | A new feature                                                               |
| `fix`      | A bug fix                                                                   |
| `docs`     | Documentation only changes                                                  |
| `style`    | Changes that do not affect meaning (white-space, formatting, missing semi-colons, etc) |
| `refactor` | A code change that neither fixes a bug nor adds a feature                   |
| `perf`     | A code change that improves performance                                     |
| `test`     | Adding missing tests or correcting existing tests                           |
| `build`    | Changes that affect the build system or external dependencies               |
| `ci`       | Changes to our CI configuration files and scripts                           |
| `chore`    | Other changes that don't modify src or test files                          |
| `revert`   | Reverts a previous commit                                                   |

### **Scope** (Optional)

The scope should be the name of the module, component, or area affected:
- `auth` (authentication module)
- `api` (API endpoints)
- `ui` (user interface)
- `db` (database)
- `config` (configuration)
- `deps` (dependencies)

### **Subject** (Required)

- Use imperative, present tense: "change" not "changed" nor "changes"
- Don't capitalize first letter
- No period (.) at the end

### **Body** (Optional)

- Use the body to explain **what** and **why** vs. how
- Wrap at 72 characters
- Use bullet points when appropriate
- Reference issues and tickets

### **Footer** (Optional)

- Breaking changes
- Issues closed: `Fixes #123`, `Closes #456`
- References: `Refs: #789`

## ✅ Examples

### **Feature with scope:**
```
feat(auth): add two-factor authentication support

- Implement TOTP-based 2FA
- Add QR code generation for setup
- Create backup code system
- Add unit tests for 2FA flow

Closes #45
```

### **Bug fix:**
```
fix(api): prevent SQL injection in user search

Sanitize user input in search endpoint to prevent
SQL injection attacks. Added parameterized queries
and input validation.

Fixes #128
Security: MEDIUM
```

### **Documentation:**
```
docs(readme): update installation instructions

Add Docker Compose setup instructions and
troubleshooting section for common issues.

See also: docs/INSTALL.md
```

### **Refactoring:**
```
refactor(payments): extract Stripe service to separate module

- Move Stripe-related logic to services/stripe/
- Update all imports
- Add interface for payment providers
- No functional changes

Improves maintainability and prepares for
additional payment providers.
```

### **Breaking Change:**
```
feat(api)!: migrate from REST to GraphQL

BREAKING CHANGE: All REST endpoints removed.
Use GraphQL queries instead. Update your
clients to use the new GraphQL API.

Migration guide: docs/MIGRATION.md
```

## 🚀 Best Practices

### **1. Commit Atomic Changes**
```bash
# Good: Small, focused commits
git commit -m "feat(login): add password strength meter"
git commit -m "test(login): add password validation tests"

# Bad: Multiple unrelated changes
git commit -m "feat: add login and fix search and update styles"
```

### **2. Use Imperative Mood**
```bash
# Good (imperative):
"add user authentication"
"fix null pointer exception"
"update dependencies"

# Bad:
"added user authentication"
"fixed null pointer exception"
"updated dependencies"
```

### **3. Reference Issues**
```bash
# In footer:
Fixes #123
Closes #456
Related to #789
See also: #101
```

### **4. Breaking Changes**
Always indicate breaking changes with `!` after type and `BREAKING CHANGE:` in body:
```
feat(api)!: remove deprecated endpoints

BREAKING CHANGE: The /v1/users endpoint is removed.
Migrate to /v2/users instead.
```

## 🛠️ Tooling

### **Commitizen (Interactive Commits)**
```bash
# Install
npm install -g commitizen

# Use instead of git commit
git cz
```

### **Commitlint (Validation)**
Add to `package.json`:
```json
{
  "commitlint": {
    "extends": ["@commitlint/config-conventional"]
  }
}
```

### **Husky (Git Hooks)**
```json
{
  "husky": {
    "hooks": {
      "commit-msg": "commitlint -E HUSKY_GIT_PARAMS"
    }
  }
}
```

### **VS Code Snippets**
Create `.vscode/commit-message.code-snippets`:
```json
{
  "Commit Message": {
    "prefix": "commit",
    "body": [
      "${1|feat,fix,docs,style,refactor,test,chore,build,ci,perf|}(${2:scope}): ${3:description}",
      "",
      "${4:body}",
      "",
      "${5|Fixes,Closes,Refs|} #${6:issue}"
    ],
    "description": "Conventional commit message"
  }
}
```

## 📊 Branch Naming

Follow this pattern: `type/description-in-kebab-case`

| Branch Type | Format                     | Example                          |
|-------------|----------------------------|----------------------------------|
| Feature     | `feature/description`      | `feature/add-payment`            |
| Bug fix     | `fix/description`          | `fix/login-error`                |
| Hotfix      | `hotfix/description`       | `hotfix/critical-security-patch` |
| Release     | `release/version`          | `release/v1.2.0`                 |
| Docs        | `docs/description`         | `docs/update-api`                |

## 🔄 Workflow

### **1. Create Branch**
```bash
git checkout -b feat/add-search-filter
```

### **2. Make Changes & Commit**
```bash
# Add changes
git add .

# Commit with proper message
git commit -m "feat(search): add price range filter"
```

### **3. Keep History Clean**
```bash
# Interactive rebase to squash/fixup
git rebase -i main

# Format: pick, reword, edit, squash, fixup, drop
```

### **4. Before Merging**
```bash
# Update with latest main
git pull --rebase origin main

# Run tests
npm test

# Push
git push origin feat/add-search-filter
```

## 📈 Benefits

1. **Automatic changelogs** - tools can parse commit history
2. **Semantic versioning** - determine version bumps from commit types
3. **Better code reviews** - understand changes quickly
4. **Easier debugging** - trace changes through history
5. **Automated workflows** - trigger deployments based on commit types

## 🚨 Common Pitfalls to Avoid

### **❌ Don't:**
- Write vague messages ("fix bug", "update", "changes")
- Include multiple concerns in one commit
- Forget to reference issues
- Use past tense ("added", "fixed")
- End subject with period

### **✅ Do:**
- Write clear, descriptive messages
- Keep commits focused and atomic
- Reference related issues
- Use imperative mood
- Explain why in body

## 📚 Additional Resources

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)
- [Semantic Versioning](https://semver.org/)

---

**Remember:** Good commit messages are like good comments in code - they help your future self and teammates understand why changes were made.

*Last updated: $(date)*