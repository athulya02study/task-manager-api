# Task Manager API

A REST API for managing tasks with user authentication and role-based access (admin/user), built with Flask, postgresql, and JWT.

## Features
- User registration & login (JWT auth)
- Create, list, update tasks — scoped to the logged-in user
- Admins can view/delete all tasks across all users
- Password hashing (never stored in plain text)

## Stack
Flask · postgresql · PyJWT · Werkzeug security

## Run it
```bash
pip install flask pyjwt werkzeug
python app.py
```
Server runs at `http://localhost:5001`

## Example usage
```bash
# Register
curl -X POST http://localhost:5001/api/register -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

# Login (returns a token)
curl -X POST http://localhost:5001/api/login -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

# Create a task (use the token from login)
curl -X POST http://localhost:5001/api/tasks -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" -d '{"title":"Finish portfolio", "description":"Ship it"}'

# List tasks
curl http://localhost:5001/api/tasks -H "Authorization: Bearer <TOKEN>"
```

## Porting to Django
The same model maps directly to Django: `users`/`tasks` become models, JWT auth becomes `djangorestframework-simplejwt`, and each route becomes a DRF `ViewSet`. The auth/permission logic (owner-only vs admin-all) is identical — it just moves into DRF permission classes.

## Portfolio notes
Good talking points: password hashing, JWT expiry handling, role-based access control at the query level (not just the route level — note how `list_tasks` filters differently for admin vs user).
