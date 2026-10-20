-- Multiple images per project, plus a certificates table.
-- The first image of a project (lowest sort_order) is used as its cover.

CREATE TABLE IF NOT EXISTS project_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Carry over images uploaded with the old single-image field
INSERT INTO project_images (project_id, filename, sort_order)
SELECT id, image, 0 FROM projects WHERE image IS NOT NULL AND image <> '';

ALTER TABLE projects DROP COLUMN image;

CREATE TABLE IF NOT EXISTS certificates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    issuer VARCHAR(150) NOT NULL,
    issue_date DATE NULL,
    credential_url VARCHAR(255) NULL,
    description TEXT NULL,
    file VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
