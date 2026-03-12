@echo off
cd /d C:\Users\nicho\repos\swarm
timeout /t 60 /nobreak >nul
docker compose up -d
