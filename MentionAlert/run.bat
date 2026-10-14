@echo off
rem Starts MentionAlert (console stays open so you can see it is running).
cd /d %~dp0
.venv\Scripts\python -m mentionalert gui
