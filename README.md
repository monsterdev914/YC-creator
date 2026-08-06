# YC Account Creator — Signup

Automates the Startup School / Co-Founder Matching signup form at
[account.ycombinator.com](https://account.ycombinator.com/?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fsign_in).

## Setup

```powershell
cd C:\Users\Administrator\Documents\YC\account_creator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

Edit `.env`:

```env
PASSWORD=YourSecurePassword123!
HEADLESS=false
```

Edit `profile.json` for shared first/last name and LinkedIn URL.

Edit `emails.csv` (one email per line):

```csv
one@example.com
two@example.com
```

Or with a header column named `email`.

Shared first/last name and LinkedIn URL come from `profile.json`; password from `.env`.  
Username is generated randomly for each account.

After each run, credentials are appended to `credentials.csv`:

```csv
email,username,password,first_name,last_name,linkedin_url,status,created_at
```

## Run (use the venv python)

```powershell
.\run.ps1 signup
.\run.ps1 profile
```

Or manually:

```powershell
.\.venv\Scripts\Activate.ps1
python run_signup.py
python run_complete_profile.py
```

If you see `No module named 'playwright'`, you ran system Python — use `.venv\Scripts\python.exe` or `.\run.ps1`.

### Signup

```powershell
.\run.ps1 signup --limit 1
```

Writes/appends `credentials.csv`.

### Complete profile

After signup, log in with `credentials.csv` and fill
[edit_sign_up](https://www.startupschool.org/users/edit_sign_up) from `profile.json`:

```powershell
.\run.ps1 profile --limit 1
```

By default processes `status=submitted` or `profile_complete`. Flow:

1. Fill [edit_sign_up](https://www.startupschool.org/users/edit_sign_up) from `profile.json`
2. Click **Save** if enabled; if disabled, skip and refresh
3. Open [cofounder-matching](https://www.startupschool.org/cofounder-matching) and click **Create profile**
4. On Behavior Agreement: check all boxes, click **I agree**
5. Fill cofounder profile wizard from `profile.json`:
   - Basics (`profile.png` avatar + intro/education/etc.) → **Save & continue**
   - More About You (idea/timing/responsibilities/all interests) → **Save & continue**
   - Co-Founder Preferences → **Save & continue**

On success, status becomes `cofounder_profile_complete`.

**Note:** Login must run headed (`HEADLESS=false`) — headless is blocked with “Validation required”.

### Export cookies (for profile-web-scraper)

Log into accounts from `credentials.csv` and write `_sso.key` / `_sus_session` to a CSV you can import on the Cookies page (labels = emails):

```powershell
.\run.ps1 cookies
.\run.ps1 cookies --limit 1
```

Writes `cookies_export.csv`:

```csv
label,ssoKey,susSession,email,status,error
user@example.com,<_sso.key>,<_sus_session>,user@example.com,ok,
```

Default status filter: `cofounder_profile_complete`.

## Proxy

Set in `.env`:

```env
PROXY_ENABLED=true
PROXY_FILE=proxy.txt
```

`proxy.txt` format (one per line):

```text
host:port:username:password
```

When enabled, each account gets the next proxy from the pool (rotated).
