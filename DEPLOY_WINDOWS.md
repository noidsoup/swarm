# Windows: After You Pull

**Run these commands in the swarm repo on Windows** to pick up new code and restart the worker:

```powershell
cd C:\Users\nicho\repos\swarm
git checkout main
git pull

.\scripts\cursor-worker.ps1 stop
.\scripts\cursor-worker.ps1 start -CursorAgent
```

That's it. The worker will use your Cursor subscription (no API key). Mac dispatches tasks; Windows runs them; results flow back via callback or outbox.
