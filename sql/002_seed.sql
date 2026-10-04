INSERT INTO dbo.Department (DepartmentID, DepartmentName, Location) VALUES
 (1, 'Engineering', 'Bengaluru'),
 (2, 'Sales',       'Mumbai'),
 (3, 'HR',          'Pune'),
 (4, 'Finance',     NULL);

INSERT INTO dbo.Employee (FirstName, LastName, DepartmentID, Salary, Bonus, HireDate) VALUES
 ('Asha',   'Rao',    1, 150000.00, 10000.00, '2019-03-15'),
 ('Vikram', 'Singh',  1, 120000.00, NULL,     '2020-07-01'),
 ('Meera',  'Iyer',   1,  95000.00,  5000.00, '2021-01-10'),
 ('Rohan',  'Shah',   2,  60000.00, 80000.00, '2018-11-20'),  -- bonus > dept avg salary
 ('Priya',  'Nair',   2,  70000.00, NULL,     '2022-05-02'),
 ('Karan',  'Mehta',  3,  55000.00,  2750.00, '2023-02-14'),
 ('Neha',   'Joshi',  3,  58000.00, NULL,     '2017-09-09'),
 ('Arjun',  'Patel',  4, 150000.00, 25000.00, '2016-06-30'),  -- ties top salary with Asha
 ('Divya',  'Menon',  4,  90000.00,  0.00,    '2024-01-08');  -- explicit 0 bonus (still "has a bonus" row)
