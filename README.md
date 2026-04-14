# CloudCart — MongoDB E-Commerce Web Application

CloudCart is a full-stack e-commerce demo built with Flask and MongoDB. It has a cloud-inspired UI, user authentication, product catalog, shopping cart, checkout flow, order history, and a simple admin panel for product management.

## What is included

- User registration, login, and logout
- Product catalog with category filter and search
- Product detail pages
- Session-based cart
- Checkout flow with order storage in MongoDB
- User dashboard and order history
- Admin dashboard for product CRUD
- Starter product seeding
- Render deployment files
- Docker support
- Automated tests with `mongomock`

## Technology stack

- **Backend:** Flask, Flask-Login
- **Database:** MongoDB via PyMongo
- **Frontend:** Jinja templates, Bootstrap 5, custom cloud-style CSS
- **Testing:** pytest, mongomock
- **Deployment:** Render + Gunicorn

## Project structure

```text
cloudcart_mongodb/
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── routes.py
│   ├── static/css/styles.css
│   └── templates/
├── scripts/
│   ├── seed_admin.py
│   └── reset_demo_data.py
├── tests/
│   └── test_app.py
├── .env.example
├── Dockerfile
├── render.yaml
├── requirements.txt
└── run.py
```

## Local setup

### 1. Create and activate a virtual environment

On Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

On macOS/Linux:

```bash
python -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and update values.

```env
SECRET_KEY=change-me
MONGO_URI=mongodb://localhost:27017/cloudcart
MONGO_DB_NAME=cloudcart
ADMIN_EMAIL=admin@cloudcart.local
ADMIN_PASSWORD=Admin@123
```

### 4. Start MongoDB

Make sure a local MongoDB server is running, or use a MongoDB Atlas connection string in `MONGO_URI`.

### 5. Run the application

```bash
python run.py
```

Open:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/products`
- `http://127.0.0.1:5000/login`

## Default admin login

The application automatically creates an admin user if it does not already exist.

Use the values from `.env`:

- **Email:** `ADMIN_EMAIL`
- **Password:** `ADMIN_PASSWORD`

If you keep the default sample values:

- Email: `admin@cloudcart.local`
- Password: `Admin@123`

## Useful scripts

### Ensure admin and starter products exist

```bash
python scripts/seed_admin.py
```

### Reset demo data

This removes non-admin users and orders, clears products, then re-seeds the default catalog.

```bash
python scripts/reset_demo_data.py
```

## Run tests

```bash
pytest
```

## Docker run

```bash
docker build -t cloudcart .
docker run -p 5000:5000 --env-file .env cloudcart
```

## Render deployment

### Recommended setup

1. Push the code to GitHub.
2. Create a Render web service.
3. Connect the GitHub repo.
4. Add environment variables:
   - `SECRET_KEY`
   - `MONGO_URI`
   - `MONGO_DB_NAME`
   - `ADMIN_EMAIL`
   - `ADMIN_PASSWORD`
5. Use the included `render.yaml`, or configure manually:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn run:app`

### Important note about MongoDB

For Render deployment, use **MongoDB Atlas** or another hosted MongoDB instance. A local MongoDB server will not work on Render.

## What to build next

Once the e-commerce application is stable, the next layer can be added on top of this real app:

- GitHub Actions CI/CD
- Build/test/deploy monitoring
- Pipeline log storage
- Failure prediction dashboard
- Auto-remediation simulation

That makes this app a strong foundation for an AI-driven CI/CD dissertation project.
