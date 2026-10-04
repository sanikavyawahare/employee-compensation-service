# Employee Compensation Service

A REST API built using Python Azure Functions to manage employee compensation data.

Tech Stack

- Python 3.11
- Azure Functions
- SQL Server
- pyodbc
- Docker
- Azurite

Features

- Create employee
- Get all employees
- Get employee by ID
- Update employee
- Delete employee
- Compensation reports
- Parameterized SQL queries

Project Structure


Fusion Practice/
├── function_app.py       # API endpoints
├── db.py                 # Database connection and queries
├── host.json             # Azure Functions configuration
├── local.settings.json   # Local configuration
├── requirements.txt      # Python dependencies
├── README.md
└── sql/
    ├── 001_schema.sql    # Database schema
    └── 002_seed.sql      # Sample 
    

Database
The project uses a SQL Server database named HrDb.
Main tables:
- Department
- Employee
SQL Server runs locally using Docker.
Run Locally
1. Activate virtual environment
source .venv/bin/activate

2. Start SQL Server
docker start fusion-sql

3. Start Azurite
azurite

4. Start Azure Functions
func start

The API runs at:
http://localhost:7071

Example API
Get all employees:
curl http://localhost:7071/api/employees

Other endpoints:
GET    /api/employees
GET    /api/employees/{id}
POST   /api/employees
PUT    /api/employees/{id}
PATCH  /api/employees/{id}
DELETE /api/employees/{id}

GET    /api/reports/total-bonus
GET    /api/reports/no-bonus
GET    /api/reports/bonus-percentage
GET    /api/reports/bonus-ranking
GET    /api/reports/top-earner

Security
- SQL queries use parameters to help prevent SQL injection.
- Database credentials are stored in local configuration and should not be committed to GitHub.
