# Publishing This Action

This guide explains how to publish and maintain this GitHub composite action.

## Repository Structure

```
ulogger_upload/
├── action.yml           # Action definition with inputs/outputs
├── postbuild.py         # Main Python script
├── requirements.txt     # Python dependencies
├── README.md           # User documentation
├── LICENSE             # MIT License
├── .gitignore          # Git ignore patterns
└── PUBLISHING.md       # This file
```

## Initial Setup

1. **Create the GitHub Repository**
   ```bash
   cd C:\Work\ulogger\public_github\ulogger_upload
   git init
   git add .
   git commit -m "Initial commit: uLogger AXF Upload Action"
   ```

2. **Push to GitHub**
   ```bash
   git remote add origin https://github.com/ulogger-ai/ulogger_upload.git
   git branch -M main
   git push -u origin main
   ```

## Creating a Release

Users reference your action by version tag (e.g., `@v1`, `@v1.0.0`). To create a release:

1. **Tag the release**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. **Create a major version tag** (for easier user reference)
   ```bash
   git tag -a v1 -m "Release v1"
   git push origin v1 --force
   ```

3. **Create GitHub Release**
   - Go to: https://github.com/ulogger-ai/ulogger_upload/releases/new
   - Select the tag you just created
   - Add release notes describing features/fixes
   - Publish the release

## Updating the Action

When you make changes:

1. **Update the code**
   ```bash
   # Make your changes
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

2. **Tag a new version**
   ```bash
   # Patch version for bug fixes
   git tag -a v1.0.1 -m "Fix: description"
   
   # Minor version for new features
   git tag -a v1.1.0 -m "Feature: description"
   
   # Major version for breaking changes
   git tag -a v2.0.0 -m "Breaking: description"
   
   git push origin v1.0.1  # or whatever version
   ```

3. **Update major version tag** (so users on `@v1` get the update)
   ```bash
   git tag -f v1 -m "Update v1 to v1.0.1"
   git push origin v1 --force
   ```

## Publishing to GitHub Marketplace (Optional)

To make your action discoverable in the GitHub Marketplace:

1. Ensure your repository is public
2. Add topics to your repository (e.g., "github-actions", "firmware", "iot")
3. Go to repository settings
4. Check "Publish this Action to the GitHub Marketplace"
5. Fill in the required information
6. Create a release (as described above)

## Testing Changes

Before releasing, test the action in a workflow:

```yaml
# .github/workflows/test.yml
name: Test Action

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Test the action
        uses: ./  # References local action
        with:
          customer_id: ${{ secrets.ULOGGER_CUSTOMER_ID }}
          # ... other required inputs
```

## Versioning Strategy

Follow semantic versioning (SemVer):

- **v1.0.0** → v1.0.1: Patch (bug fixes, no new features)
- **v1.0.0** → v1.1.0: Minor (new features, backward compatible)
- **v1.0.0** → v2.0.0: Major (breaking changes)

## User Migration

When releasing breaking changes, provide migration guides:

1. Create a new major version (e.g., v2)
2. Keep the old version available
3. Document changes in the release notes
4. Provide examples of how to upgrade

## Common Updates

### Updating Dependencies

```bash
# Edit requirements.txt
# Test locally
# Commit and release a new patch version
```

### Fixing Bugs

```bash
# Fix the bug in postbuild.py or action.yml
git commit -m "Fix: describe the bug fix"
git tag -a v1.0.X -m "Fix: describe the bug fix"
git push origin main
git push origin v1.0.X
git tag -f v1
git push origin v1 --force
```

### Adding Features

```bash
# Add feature to postbuild.py or action.yml
git commit -m "Feature: describe the feature"
git tag -a v1.X.0 -m "Feature: describe the feature"
git push origin main
git push origin v1.X.0
git tag -f v1
git push origin v1 --force
```

## Support

For questions about publishing or maintaining this action, contact the uLogger development team at [ulogger.ai](https://ulogger.ai).
