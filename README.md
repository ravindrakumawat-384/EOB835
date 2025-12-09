# EOB-835: Explanation of Benefits to ANSI X12 835 Converter

A modern SaaS platform for converting EOB (Explanation of Benefits) files to ANSI X12 835 format. Built with FastAPI, MongoDB, and async Python, this application provides secure authentication, role-based access control, and comprehensive user management for healthcare billing workflows.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation Steps](#installation-steps)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [Running the Project](#running-the-project)
- [Contribution Guidelines](#contribution-guidelines)
- [Contact & Support](#contact--support)

---

## Project Overview

EOB-835 is a comprehensive platform designed to:

- **Convert EOB Files**: Transform Explanation of Benefits files into standardized ANSI X12 835 format
- **User Authentication**: Secure JWT-based authentication with refresh token rotation
- **Role-Based Access Control**: Support for Admin, Reviewer, and Viewer roles with granular permissions
- **Organization Management**: Multi-tenant architecture with organization and team member management
- **User Profiles**: Manage user settings, preferences, and profile information
- **Password Management**: Secure password reset and change password functionality
- **Settings Management**: Organization-wide settings including retention policies and general configurations
- **Team Collaboration**: Invite users, manage team members, and track activity

---

## Tech Stack

### Backend Framework
- **FastAPI** – Modern, fast web framework for building APIs with Python
- **Uvicorn** – ASGI web server for running FastAPI applications
- **Pydantic** – Data validation and settings management using Python type annotations

### Database
- **MongoDB** – NoSQL document database for flexible data storage
- **Motor** – Async MongoDB driver for Python
- **PyMongo** – MongoDB Python driver (used by Motor)

### Authentication & Security
- **python-jose** – JWT (JSON Web Token) implementation
- **passlib** – Password hashing and verification
- **bcrypt** – Secure password hashing algorithm

### Async & Concurrency
- **AsyncIO** – Python's built-in async/await framework
- **httpx** – Async HTTP client (optional, for external API calls)

### Email & Utilities
- **smtplib** – SMTP email sending (built-in)
- **python-multipart** – Multipart form data support
- **python-dotenv** – Environment variable management

### Development Tools
- **black** – Code formatter
- **flake8** – Linter
- **isort** – Import sorting
- **pytest** – Testing framework (recommended)

---

## Project Structure

```
eob/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app initialization & lifespan management
│   ├── config.py                    # Configuration & settings
│   │
│   ├── common/
│   │   ├── config.py                # Centralized configuration
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── db.py                # MongoDB connection & initialization
│   │   │   └── models.py            # Pydantic models for database documents
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py                  # Authentication endpoints (login, register, password reset, logout, change password)
│   │   ├── orgs.py                  # Organization management endpoints
│   │   ├── settings_general.py       # General organization settings
│   │   ├── settings_profile.py       # User profile management
│   │   ├── settings_users.py         # Team member management
│   │   ├── settings_notifications.py # Notification preferences
│   │   └── settings_audit_logs.py    # Audit log endpoints
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_deps.py              # Authentication dependencies & role checks
│   │   ├── auth_utils.py             # Password hashing, token creation/decoding
│   │   ├── crud.py                   # Database CRUD operations
│   │   ├── email_service.py          # Email sending functionality
│   │   └── auth_deps.py              # Authorization & dependency injection
│   │
│   └── utils/
│       ├── __init__.py
│       ├── auth_utils.py             # JWT & password utilities
│       └── logger.py                 # Centralized logging configuration
│
├── requirements.txt                 # Python dependencies
├── seed_db.py                       # Database seeding script
├── README.md                        # This file
└── .env                             # Environment variables (not in repo)
```

### Key Directories Explained

| Directory | Purpose |
|-----------|---------|
| `app/common/` | Shared configuration, database setup, and core models |
| `app/routes/` | API endpoint handlers organized by domain (auth, settings, orgs) |
| `app/services/` | Business logic, CRUD operations, authentication helpers |
| `app/utils/` | Utility functions (logging, token handling, password hashing) |

---

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/ravindrakumawat-384/EOB835.git
cd EOB835/eob
```

### 2. Create Virtual Environment

```bash
# Using venv (Python 3.10+)
python3 -m venv env

# Activate the virtual environment
# On Linux/macOS:
source env/bin/activate

# On Windows:
env\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
# Edit .env with your configuration
```

See [Environment Variables](#environment-variables) section for details.

### 5. Seed the Database (Optional)

```bash
python seed_db.py
```

This will populate the database with sample data for development/testing.

### 6. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Database Configuration
MONGO_URI=mongodb://localhost:27017
MONGO_DB=eob_database

# JWT Configuration
JWT_SECRET=your_super_secret_jwt_key_change_this_in_production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
RESET_TOKEN_EXPIRE_MINUTES=15

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_specific_password

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Application Configuration
DEBUG=True
LOG_LEVEL=INFO
```

### Required Environment Variables Explained

| Variable | Description | Default/Example |
|----------|-------------|-----------------|
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGO_DB` | Database name | `eob_database` |
| `JWT_SECRET` | Secret key for JWT signing | Generate a secure random string |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration time | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiration time | `7` |
| `RESET_TOKEN_EXPIRE_MINUTES` | Password reset token expiration | `15` |
| `SMTP_HOST` | Email SMTP server | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | Email sender address | Your email |
| `SMTP_PASS` | Email password/app password | Your app-specific password |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000` |
| `DEBUG` | Debug mode | `False` (for production) |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## API Documentation

FastAPI automatically generates interactive API documentation. Once the server is running, access:

### Swagger UI (Interactive Documentation)
```
http://localhost:8000/docs
```

### ReDoc (Alternative Documentation)
```
http://localhost:8000/redoc
```

### OpenAPI Schema (JSON)
```
http://localhost:8000/openapi.json
```

All endpoints are documented with:
- Request/response models
- Parameter descriptions
- Authentication requirements
- Example requests and responses

---

## Running the Project

### Development Mode (with auto-reload)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using a Process Manager (Gunicorn + Uvicorn)

```bash
pip install gunicorn
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Running with Docker (Optional)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY .env .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t eob-835 .
docker run -p 8000:8000 --env-file .env eob-835
```

---

## Contribution Guidelines

### Code Quality Standards

We maintain high code quality standards using:

#### 1. Black (Code Formatter)

```bash
# Format all Python files
black app/

# Check formatting without modifying
black --check app/
```

#### 2. Flake8 (Linter)

```bash
# Check code for style issues
flake8 app/

# Exclude certain files/dirs
flake8 app/ --exclude=migrations
```

#### 3. isort (Import Sorter)

```bash
# Sort imports alphabetically
isort app/

# Check without modifying
isort --check-only app/
```

### Before Submitting a PR

1. **Format your code**:
   ```bash
   black app/
   isort app/
   ```

2. **Check for linting issues**:
   ```bash
   flake8 app/
   ```

3. **Run tests** (if available):
   ```bash
   pytest
   ```

4. **Commit with clear messages**:
   ```bash
   git commit -m "feat: add user authentication endpoint"
   ```

### Commit Message Format

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Formatting (no code logic change)
- `refactor:` Code reorganization
- `test:` Test additions/changes
- `chore:` Dependency updates, config changes

Example:
```
feat: implement password reset email functionality
fix: resolve MongoDB connection timeout issue
docs: update API endpoint documentation
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and ensure code quality
4. Commit with clear messages
5. Push to your fork
6. Submit a pull request with detailed description

---

## Contact & Support

### Project Maintainers

- **Lead Developer**: Ravindra Kumawat
  - GitHub: [@ravindrakumawat-384](https://github.com/ravindrakumawat-384)
  - Email: kumawat.ravindra@example.com

### Support Channels

- **GitHub Issues**: [Report bugs or request features](https://github.com/ravindrakumawat-384/EOB835/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/ravindrakumawat-384/EOB835/discussions)
- **Email**: For critical issues, contact maintainers directly

### License

This project is licensed under the MIT License. See LICENSE file for details.

### Acknowledgments

- FastAPI community for excellent documentation
- MongoDB for robust database solution
- Open source contributors

---

## Quick Reference

### Useful Commands

```bash
# Activate virtual environment
source env/bin/activate

# Run server
uvicorn app.main:app --reload

# Format code
black app/

# Check linting
flake8 app/

# Sort imports
isort app/

# Seed database
python seed_db.py

# Run tests
pytest

# View logs
tail -f logs/app.log
```

### API Endpoints Overview

| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|----------------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | User login | No |
| POST | `/auth/refresh` | Refresh access token | Yes |
| POST | `/auth/request-password-reset` | Request password reset | No |
| POST | `/auth/reset-password` | Reset password | No |
| POST | `/auth/change-password` | Change password | Yes |
| POST | `/auth/logout` | User logout | Yes |
| GET | `/settings/profile/` | Get user profile | Yes |
| PATCH | `/settings/profile/` | Update user profile | Yes |
| GET | `/settings/users/` | List team members | Yes |
| POST | `/settings/users/` | Invite user | Yes (Admin) |
| PATCH | `/settings/users/` | Update team member | Yes (Admin) |
| DELETE | `/settings/users/{member_id}` | Delete team member | Yes (Admin) |
| GET | `/settings/general/` | Get org settings | Yes |
| PATCH | `/settings/general/` | Update org settings | Yes (Admin) |
| GET | `/orgs/` | List organizations | Yes |

---

**Last Updated**: December 10, 2025  
**Version**: 1.0.0
