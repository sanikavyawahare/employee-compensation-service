import json
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import azure.functions as func
import pyodbc

import db

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

EMPLOYEE_SELECT = """
SELECT e.EmployeeID, e.FirstName, e.LastName, e.DepartmentID, d.DepartmentName,
       e.Salary, e.Bonus, e.HireDate
FROM dbo.Employee e
LEFT JOIN dbo.Department d ON d.DepartmentID = e.DepartmentID
"""


# 1
def _json_default(o):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(f"Not serializable: {type(o)}")


def _resp(body, status=200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body, default=_json_default),
                             status_code=status, mimetype="application/json")


def _error(status: int, message: str) -> func.HttpResponse:
    return _resp({"error": message}, status)


class ValidationError(Exception):
    pass


def _parse_id(raw: str) -> int:
    try:
        v = int(raw)
        if v <= 0:
            raise ValueError
        return v
    except (TypeError, ValueError):
        raise ValidationError("id must be a positive integer")


def _money(value, field, required=False):
    if value is None:
        if required:
            raise ValidationError(f"{field} is required")
        return None
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(f"{field} must be a number")
    if d < 0:
        raise ValidationError(f"{field} must be >= 0")
    if d.as_tuple().exponent < -2 or abs(d) >= Decimal("1e10"):
        raise ValidationError(f"{field} must fit DECIMAL(12,2)")
    return d


def _text(value, field, max_len, required=False):
    if value is None:
        if required:
            raise ValidationError(f"{field} is required")
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValidationError(f"{field} must be a non-empty string")
    if len(value) > max_len:
        raise ValidationError(f"{field} must be at most {max_len} characters")
    return value.strip()


def _hire_date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError("hireDate must be an ISO date (YYYY-MM-DD)")


def _department_id(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("departmentId must be an integer")
    return value


def _body(req: func.HttpRequest) -> dict:
    try:
        data = req.get_json()
    except ValueError:
        raise ValidationError("Request body must be valid JSON")
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def _safe(handler):
    """Maps exceptions to HTTP status codes; never leaks internals to the client."""
    def wrapper(req: func.HttpRequest) -> func.HttpResponse:
        try:
            return handler(req)
        except ValidationError as e:
            return _error(400, str(e))
        except pyodbc.IntegrityError as e:
            logging.warning("Integrity error: %s", e)
            return _error(409, "Constraint violation (e.g. unknown departmentId)")
        except (pyodbc.OperationalError, pyodbc.InterfaceError) as e:
            logging.exception("Database unavailable")
            return _error(503, "Database temporarily unavailable")
        except Exception:
            logging.exception("Unhandled error")
            return _error(500, "Internal server error")
    wrapper.__name__ = handler.__name__
    return wrapper


def _get_employee(emp_id: int):
    rows = db.query(EMPLOYEE_SELECT + " WHERE e.EmployeeID = ?", (emp_id,))
    return rows[0] if rows else None


#  Part A: CRUD
@app.route(route="employees", methods=["POST"])
@_safe
def create_employee(req: func.HttpRequest) -> func.HttpResponse:
    b = _body(req)
    first = _text(b.get("firstName"), "firstName", 50, required=True)
    last = _text(b.get("lastName"), "lastName", 50, required=True)
    salary = _money(b.get("salary"), "salary", required=True)
    bonus = _money(b.get("bonus"), "bonus")  
    dept = _department_id(b.get("departmentId"))
    hired = _hire_date(b.get("hireDate"))

    new_id = db.execute(
        """INSERT INTO dbo.Employee (FirstName, LastName, DepartmentID, Salary, Bonus, HireDate)
           OUTPUT INSERTED.EmployeeID
           VALUES (?, ?, ?, ?, ?, ?)""",
        (first, last, dept, salary, bonus, hired))[0]["EmployeeID"]
    return _resp(_get_employee(new_id), 201)


@app.route(route="employees/{id}", methods=["GET"])
@_safe
def get_employee(req: func.HttpRequest) -> func.HttpResponse:
    emp = _get_employee(_parse_id(req.route_params.get("id")))
    return _resp(emp) if emp else _error(404, "Employee not found")


@app.route(route="employees", methods=["GET"])
@_safe
def list_employees(req: func.HttpRequest) -> func.HttpResponse:
    dept = req.params.get("departmentId")
    if dept is not None:
        rows = db.query(EMPLOYEE_SELECT + " WHERE e.DepartmentID = ? ORDER BY e.EmployeeID",
                        (_parse_id(dept),))
    else:
        rows = db.query(EMPLOYEE_SELECT + " ORDER BY e.EmployeeID")
    return _resp(rows)


@app.route(route="employees/{id}", methods=["PUT", "PATCH"])
@_safe
def update_employee(req: func.HttpRequest) -> func.HttpResponse:
    """Partial update: only fields present in the body change. `"bonus": null` clears the bonus."""
    emp_id = _parse_id(req.route_params.get("id"))
    b = _body(req)

    sets, params = [], []
    if "firstName" in b:
        sets.append("FirstName = ?"); params.append(_text(b["firstName"], "firstName", 50, required=True))
    if "lastName" in b:
        sets.append("LastName = ?"); params.append(_text(b["lastName"], "lastName", 50, required=True))
    if "salary" in b:
        sets.append("Salary = ?"); params.append(_money(b["salary"], "salary", required=True))
    if "bonus" in b:
        sets.append("Bonus = ?"); params.append(_money(b["bonus"], "bonus"))
    if "departmentId" in b:
        sets.append("DepartmentID = ?"); params.append(_department_id(b["departmentId"]))
    if "hireDate" in b:
        sets.append("HireDate = ?"); params.append(_hire_date(b["hireDate"]))
    if not sets:
        raise ValidationError("No updatable fields supplied")

    updated = db.execute(
        f"UPDATE dbo.Employee SET {', '.join(sets)} OUTPUT INSERTED.EmployeeID WHERE EmployeeID = ?",
        (*params, emp_id))
    if "_rowcount" in updated[0]:
        return _error(404, "Employee not found")
    return _resp(_get_employee(emp_id))


@app.route(route="employees/{id}", methods=["DELETE"])
@_safe
def delete_employee(req: func.HttpRequest) -> func.HttpResponse:
    res = db.execute("DELETE FROM dbo.Employee OUTPUT DELETED.EmployeeID WHERE EmployeeID = ?",
                     (_parse_id(req.route_params.get("id")),))
    if "_rowcount" in res[0]:
        return _error(404, "Employee not found")
    return func.HttpResponse(status_code=204)


#  Part B: reports 
@app.route(route="reports/total-bonus", methods=["GET"])
@_safe
def total_bonus(req: func.HttpRequest) -> func.HttpResponse:
    rows = db.query("SELECT COALESCE(SUM(COALESCE(Bonus, 0)), 0) AS TotalBonus FROM dbo.Employee")
    return _resp(rows[0])


@app.route(route="reports/no-bonus", methods=["GET"])
@_safe
def employees_without_bonus(req: func.HttpRequest) -> func.HttpResponse:
    
    return _resp(db.query(
        """SELECT EmployeeID, FirstName, LastName, DepartmentID, Salary, HireDate
           FROM dbo.Employee WHERE Bonus IS NULL ORDER BY EmployeeID"""))


@app.route(route="reports/bonus-percentage", methods=["GET"])
@_safe
def bonus_percentage(req: func.HttpRequest) -> func.HttpResponse:
    return _resp(db.query(
        """SELECT EmployeeID, FirstName, LastName, Salary, Bonus,
                  CAST(ROUND(Bonus * 100.0 / NULLIF(Salary, 0), 2) AS DECIMAL(10,2)) AS BonusPercentOfSalary
           FROM dbo.Employee WHERE Bonus IS NOT NULL ORDER BY EmployeeID"""))


@app.route(route="reports/departments-bonus-exceeds-avg-salary", methods=["GET"])
@_safe
def departments_bonus_exceeds_avg_salary(req: func.HttpRequest) -> func.HttpResponse:
    return _resp(db.query(
        """SELECT d.DepartmentID, d.DepartmentName,
                  SUM(COALESCE(e.Bonus, 0)) AS TotalBonus,
                  AVG(e.Salary)             AS AverageSalary
           FROM dbo.Department d
           JOIN dbo.Employee e ON e.DepartmentID = d.DepartmentID
           GROUP BY d.DepartmentID, d.DepartmentName
           HAVING SUM(COALESCE(e.Bonus, 0)) > AVG(e.Salary)
           ORDER BY d.DepartmentID"""))


@app.route(route="reports/bonus-ranking", methods=["GET"])
@_safe
def bonus_ranking(req: func.HttpRequest) -> func.HttpResponse:
    
    return _resp(db.query(
        """SELECT RANK() OVER (ORDER BY CASE WHEN Bonus IS NULL THEN 1 ELSE 0 END, Bonus DESC) AS BonusRank,
                  EmployeeID, FirstName, LastName, Salary, Bonus
           FROM dbo.Employee
           ORDER BY BonusRank, EmployeeID"""))


@app.route(route="reports/top-earner", methods=["GET"])
@_safe
def top_earner(req: func.HttpRequest) -> func.HttpResponse:
    """Highest base salary (all ties returned) + whether each also has the highest total compensation."""
    rows = db.query(
        """WITH c AS (
               SELECT EmployeeID, FirstName, LastName, Salary, Bonus,
                      Salary + COALESCE(Bonus, 0) AS TotalCompensation
               FROM dbo.Employee)
           SELECT EmployeeID, FirstName, LastName, Salary, Bonus, TotalCompensation,
                  CASE WHEN TotalCompensation = (SELECT MAX(TotalCompensation) FROM c) THEN 1 ELSE 0 END
                      AS HasHighestTotalCompensation
           FROM c
           WHERE Salary = (SELECT MAX(Salary) FROM c)
           ORDER BY EmployeeID""")
    for r in rows:
        r["HasHighestTotalCompensation"] = bool(r["HasHighestTotalCompensation"])
    return _resp({"highestSalary": rows})
