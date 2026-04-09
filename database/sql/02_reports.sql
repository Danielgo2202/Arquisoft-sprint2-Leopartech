
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID,
    report_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE report_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID,
    worker_name VARCHAR(50),
    status VARCHAR(20) DEFAULT 'QUEUED',
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (report_id) REFERENCES reports(id)
);

CREATE TABLE report_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID,
    event_type VARCHAR(50),
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reports_status
ON reports(status);

CREATE INDEX idx_report_jobs_status
ON report_jobs(status);

CREATE INDEX idx_report_jobs_worker
ON report_jobs(worker_name);

CREATE INDEX idx_report_events_type
ON report_events(event_type);

CREATE INDEX idx_report_events_created
ON report_events(created_at);