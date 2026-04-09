CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(150),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID,
    full_name VARCHAR(150),
    email VARCHAR(150) UNIQUE,
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID,
    allocated_amount NUMERIC(15,2),
    spent_amount NUMERIC(15,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_employees_company
ON employees(company_id);

CREATE INDEX idx_employees_email
ON employees(email);

CREATE INDEX idx_employees_role
ON employees(role);

CREATE INDEX idx_budgets_project
ON budgets(project_id);