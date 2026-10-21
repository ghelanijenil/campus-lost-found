# Smart Campus Lost & Found — BCA Final Year Project

## Features included
- Student registration/login with hashed passwords
- Admin login and admin dashboard
- Lost and Found item reports with category, campus location, date, description and optional photo upload
- Search, filters, and item details
- Smart rule-based matching by category, keywords, location and date
- Claim requests with approve/reject workflow
- Notifications for possible matches and claim updates
- Mark items resolved
- Admin can update item status and student/admin roles
- CSV export for all item reports
- SQLite database auto-created on first run
- Responsive modern Bootstrap interface

## Run on Windows
1. Extract this ZIP.
2. Open PowerShell in the folder containing `app.py`.
3. Create virtual environment:
   `py -m venv .venv`
4. Install dependencies:
   `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
5. Start app:
   `.\.venv\Scripts\python.exe app.py`
6. Open `http://127.0.0.1:5000`

## Demo Admin
Email: `admin@campus.local`
Password: `Admin@123`

Register a student account through Join Campus.

## Database
SQLite database file `lost_found.db` is created automatically. Tables: `users`, `items`, `claims`, `notifications`.

## Demo flow
Register two student accounts; create a Lost post from one account and a matching Found post from another. Open item details to see matching suggestions, send a claim request, then approve/reject from Claims as the item owner. Admin panel can update statuses and export CSV.

## Important
Smart matching is explainable rule-based matching, not a trained AI model. Present it honestly in viva. This is an educational starter project, not production-ready. For deployment, set a strong SECRET_KEY, disable debug mode, add CSRF protection, rate limits and secure hosting. Bootstrap styling uses CDN.
