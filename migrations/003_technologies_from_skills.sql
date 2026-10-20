-- Technologies are now kept in sync with skills (see sync_skill_technology in routes/admin.py).
-- Backfill a technology for every skill that already exists.

INSERT IGNORE INTO technologies (name)
SELECT DISTINCT TRIM(name) FROM skills;
