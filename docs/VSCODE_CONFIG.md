# Pylance Type Checking Configuration

To enable Pylance's type checking in VS Code, add this to your `.vscode/settings.json`:

```json
{
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.include": ["${workspaceFolder}"],
  "python.analysis.exclude": ["**/node_modules", "**/__pycache__"],
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "[python]": {
    "editor.formatOnSave": true
  }
}
```

## Type Checking Modes

- **off**: No type checking
- **basic**: Standard type checking (recommended for most projects)
- **strict**: Strict type checking (requires type hints everywhere)

The **basic** mode will catch common type errors while allowing the CI/CD pipeline to pass without requiring complete type annotations.
