# Using Swarm in Other Repos

The AI Dev Swarm is designed to be portable — you can run it against any repository.

## Option 1: CLI with `--repo` flag (recommended for quick use)

From the swarm repo:

```bash
python run.py --repo /path/to/my-nextjs-app "Add dark mode toggle"
python run.py --repo ../my-wordpress-plugin "Add REST endpoint for products"
```

The swarm will:
- Read your repo files
- Run agents
- Make changes
- Commit (or `--no-commit` to preview)

## Option 2: Install as a package (recommended for regular use)

### Install from GitHub

```bash
pip install git+https://github.com/noidsoup/swarm.git
```

Then in **any** repo:

```bash
swarm-run "Add filtering to products page"
swarm-run --repo /path/to/other/repo "Optimize images"
swarm-daemon /path/to/repo  # Continuous improvement
```

### Local development install

```bash
cd /path/to/swarm
pip install -e .
```

Then use `swarm-run` anywhere.

## Option 3: Point MCP at swarm (for Cursor)

In Cursor settings, MCP config points to the swarm repo:

```json
{
  "mcpServers": {
    "swarm": {
      "command": "python",
      "args": ["/path/to/swarm/swarm/mcp_server.py"]
    }
  }
}
```

Then from any Cursor chat, call `run_swarm(plan, repo_path="/path/to/other/repo")`.

## Option 4: Copy/symlink swarm into your project

```bash
# Copy the swarm
cp -r /path/to/swarm /path/to/my-project/.ai-swarm

# Or symlink
ln -s /path/to/swarm /path/to/my-project/.ai-swarm

# Then run
cd /path/to/my-project
python .ai-swarm/run.py "Add feature"
```

## Example Workflows

### Improving an existing React app

```bash
python run.py --repo ~/projects/my-react-app "Optimize Core Web Vitals"
```

The swarm will:
- Analyze the React codebase
- Run lighthouse checks
- Optimize images, lazy load, etc.
- Suggest performance improvements
- Create a commit

### Adding a feature to a WordPress plugin

```bash
python run.py --repo ~/projects/my-plugin --builder wordpress_dev "Add REST endpoint for filtering products"
```

### Continuous improvement on a Next.js project

```bash
python daemon.py ~/projects/my-nextjs-app
```

The daemon will:
- Watch for file changes
- Automatically review new code
- Run quality gates
- Open PRs for improvements
- Run 24/7

## Configuration Per Repo

Each repo can have its own `.env.swarm`:

```
WORKER_MODEL=ollama/qwen2.5-coder
MAX_REVIEWS=3
AUTO_COMMIT=true
BRANCH_PREFIX=ai/
```

The swarm will read this if it exists in the target repo root.

## Combining with Your Cursor Workflow

**Recommended setup:**

1. **Install swarm globally:**
   ```bash
   pip install -e /path/to/swarm
   ```

2. **Enable MCP in Cursor** to point at swarm

3. **From Cursor chat in any repo:**
   ```
   "Add dark mode to the settings page"
   ```
   Cursor calls → swarm MCP → `run_swarm(plan, repo_path=<current-repo>)`

4. **Or use CLI:**
   ```bash
   swarm-run --repo . "Add feature"
   ```

## Tips

- **`--no-commit`** to preview changes before committing
- **`--dry-run`** to see config without running
- **`--max-reviews N`** to limit review iterations
- **`--builder react_dev|wordpress_dev|shopify_dev`** to force a builder
- **`--quiet`** to reduce output noise

## Multi-Repo Example

```bash
# Improve all your projects at once
for repo in ~/projects/*; do
  echo "Improving $repo..."
  python run.py --repo "$repo" "Refactor and optimize"
done
```

The swarm becomes your AI development team across all repositories.
