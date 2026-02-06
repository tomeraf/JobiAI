====================================
  JobiAI - LinkedIn Job Application Bot
====================================

JobiAI helps you apply for jobs by leveraging your LinkedIn connections.
Submit job URLs and the bot automatically finds and contacts relevant
people at the target company.


REQUIREMENTS
------------
- Windows 10/11
- Python 3.11 or later (https://python.org)
  IMPORTANT: During Python installation, check "Add Python to PATH"


INSTALLATION (One Time)
-----------------------
1. Extract this folder anywhere you like
2. Double-click: install.bat
3. Wait for installation to complete (takes a few minutes)


RUNNING
-------
1. Double-click: JobiAI.vbs
2. The app opens in your browser at http://localhost:9000
3. First time: Go to Settings and login to LinkedIn
4. Paste job URLs and let the bot work!


STOPPING
--------
- Just close the browser tab (auto-shutdown)
- Or run: exit-JobiAI.bat


DATA LOCATION
-------------
Your data is stored in: %LOCALAPPDATA%\JobiAI\
- jobiai.db - Your jobs, contacts, and settings
- Browser session data is in backend\linkedin_data\


TROUBLESHOOTING
---------------
Q: The app doesn't start
A: Run install.bat again, make sure Python is installed

Q: Browser shows "refused to connect"
A: Wait a few more seconds, or run exit-JobiAI.bat and try again

Q: LinkedIn login doesn't work
A: Use "Login with Browser" option in Settings for manual login


TIPS
----
- The bot sends ONE message per company, then waits for a reply
- Check the "Waiting for Reply" jobs and click "Check Replies" regularly
- VIPs (CEOs, CTOs, founders) are automatically skipped
- Known job sites are recognized automatically (Greenhouse, Lever, etc.)
