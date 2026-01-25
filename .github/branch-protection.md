# Branch Protection Rules

To enforce CI/CD validation before merging, apply these branch protection rules in GitHub:

## For `main` branch:
1. **Require status checks to pass before merging**
   - Require branches to be up to date before merging: ✓ ON
   - Required status checks:
     - `test` (CI/CD Pipeline)
     - `build` (CI/CD Pipeline)

2. **Require code reviews**
   - Required approving reviews: 1
   - Dismiss stale pull request approvals: ✓ ON

3. **Additional settings**
   - Include administrators: ✓ ON (recommended)

## For `develop` branch:
Same as `main` but with:
   - Required approving reviews: 1 (can be more lenient than main)

## To Apply via GitHub UI:
1. Go to Settings → Branches
2. Click "Add rule"
3. Enter branch name pattern: `main` (or `develop`)
4. Configure as above
5. Click "Create"

## Alternative: GitHub CLI
```bash
# Install GitHub CLI if not already installed
# brew install gh

# Authenticate
gh auth login

# Create protection rules
gh api repos/{owner}/{repo}/branches/main/protection \
  -f required_status_checks='{"strict":true,"contexts":["test","build"]}' \
  -f require_code_reviews='{"required_reviewing_count":1}' \
  -f enforce_admins=true
```

## Verify Rules
```bash
gh api repos/{owner}/{repo}/branches/main/protection
```
