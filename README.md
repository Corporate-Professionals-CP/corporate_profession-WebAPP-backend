# Corporate Professionals WebApp Backend

This is the backend API for the Corporate Professionals WebApp, a platform for connecting corporate professionals and recruiters.

## Features

- User authentication and authorization
- Profile management
- Professional networking
- Post creation and interaction
- Admin dashboard
- Analytics
- And more...

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL
- Google Cloud Storage (for file storage)

### Installation

1. Clone the repository

```bash
git clone <repository-url>
cd corporate_profession-WebAPP-backend
```

2. Create a virtual environment and activate it

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`

```bash
cp .env.example .env
```

5. Update the `.env` file with your configuration

6. Run the application

```bash
uvicorn app.main:app --reload
```

## Automatic Admin Creation

The application automatically creates an admin user during database initialization if one doesn't already exist. To configure this feature:

1. Set the following environment variables in your `.env` file:

```
ADMIN_EMAIL=your_admin_email@example.com
ADMIN_PASSWORD=your_secure_password
```

2. When the application starts, it will:
   - Check if a user with the specified email exists
   - If the user exists but is not an admin, it will upgrade them to admin
   - If the user doesn't exist, it will create a new admin user

This ensures that an admin user is always available in the system, especially useful for new deployments or testing environments.

## API Documentation

Once the application is running, you can access the API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Running Tests

```bash
pytest
```

### Database Migrations with Alembic

The application uses Alembic for database migrations. Alembic is now fully configured to work with SQLModel and our async PostgreSQL database.

#### Creating a New Migration

To create a new migration after changing models:

```bash
python -m alembic revision --autogenerate -m "Description of changes"
```

This will automatically detect changes in your models and generate a migration script.

#### Applying Migrations

To apply all pending migrations:

```bash
python -m alembic upgrade head
```

To apply migrations up to a specific revision:

```bash
python -m alembic upgrade <revision_id>
```

#### Rolling Back Migrations

To roll back the most recent migration:

```bash
python -m alembic downgrade -1
```

To roll back to a specific revision:

```bash
python -m alembic downgrade <revision_id>
```

#### Viewing Migration History

To see the current migration status:

```bash
python -m alembic current
```

To see the migration history:

```bash
python -m alembic history
```

## Deployment

The application can be deployed using Docker:

```bash
docker-compose up -d
```

## License

This project is licensed under the terms of the license provided with the project.