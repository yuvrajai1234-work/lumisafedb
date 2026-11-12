-- ====================================================================
-- LUMISAFE DATABASE SCHEMA & INITIALIZATION SCRIPT
-- Intelligent Street Light Management & Urban Safety System
-- Compatible with MySQL Server 8.0+ and MySQL Workbench
-- ====================================================================

-- 1. Create and select Database
CREATE DATABASE IF NOT EXISTS LumiSafeDB
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE LumiSafeDB;

-- Drop existing tables in reverse foreign key order if re-initializing
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS ComplaintMedia;
DROP TABLE IF EXISTS SolarLightPoles;
DROP TABLE IF EXISTS ElectricalLightPoles;
DROP TABLE IF EXISTS LightComplaints;
DROP TABLE IF EXISTS LightPoles;
DROP TABLE IF EXISTS Citizens;
DROP TABLE IF EXISTS ElectricalOfficials;
DROP TABLE IF EXISTS WorkOrders;
DROP TABLE IF EXISTS WardCouncils;
DROP TABLE IF EXISTS ElectricalDivisions;
SET FOREIGN_KEY_CHECKS = 1;

-- ====================================================================
-- 1. ElectricalDivisions
-- Stores administrative electrical divisions managing city zones.
-- ====================================================================
CREATE TABLE ElectricalDivisions (
    div_id INT PRIMARY KEY AUTO_INCREMENT,
    div_name VARCHAR(100) NOT NULL,
    district VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

-- ====================================================================
-- 2. WardCouncils
-- Tracks local civic wards and council leaders.
-- ====================================================================
CREATE TABLE WardCouncils (
    ward_id INT PRIMARY KEY AUTO_INCREMENT,
    ward_name VARCHAR(100) NOT NULL,
    councillor_name VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

-- ====================================================================
-- 3. LightPoles
-- Master inventory of street light pole infrastructure.
-- Latitude checked between -90 and +90
-- ====================================================================
CREATE TABLE LightPoles (
    pole_id INT PRIMARY KEY AUTO_INCREMENT,
    pole_name VARCHAR(50) NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    is_high_risk BOOLEAN DEFAULT FALSE,
    CONSTRAINT chk_latitude CHECK (latitude >= -90.00000000 AND latitude <= 90.00000000),
    CONSTRAINT chk_longitude CHECK (longitude >= -180.00000000 AND longitude <= 180.00000000)
) ENGINE=InnoDB;

-- Sub-Entity 1 (IS-A Hierarchy): Solar Light Poles
CREATE TABLE SolarLightPoles (
    pole_id INT PRIMARY KEY,
    FOREIGN KEY (pole_id) REFERENCES LightPoles(pole_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Sub-Entity 2 (IS-A Hierarchy): Electrical Light Poles
CREATE TABLE ElectricalLightPoles (
    pole_id INT PRIMARY KEY,
    FOREIGN KEY (pole_id) REFERENCES LightPoles(pole_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ====================================================================
-- 4. Citizens
-- User registry for citizens reporting light failures.
-- Date of birth validated via triggers.
-- ====================================================================
CREATE TABLE Citizens (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_no VARCHAR(15) UNIQUE NOT NULL,
    date_of_birth DATE NOT NULL
) ENGINE=InnoDB;

-- ====================================================================
-- 5. LightComplaints
-- Central ticket table for street light faults and status tracking.
-- ====================================================================
CREATE TABLE LightComplaints (
    complaint_id INT PRIMARY KEY AUTO_INCREMENT,
    issue_type VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_priority CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    CONSTRAINT chk_status CHECK (status IN ('Open', 'In Progress', 'Resolved'))
) ENGINE=InnoDB;

-- ====================================================================
-- 6. ComplaintMedia (Weak Entity linked to LightComplaints)
-- Photo evidence and reporting attachments linked to complaints.
-- ====================================================================
CREATE TABLE ComplaintMedia (
    media_id INT PRIMARY KEY AUTO_INCREMENT,
    complaint_id INT NOT NULL,
    media_url VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES LightComplaints(complaint_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ====================================================================
-- 7. ElectricalOfficials
-- Government engineers and inspectors overseeing maintenance.
-- ====================================================================
CREATE TABLE ElectricalOfficials (
    official_id INT PRIMARY KEY AUTO_INCREMENT,
    official_name VARCHAR(50) NOT NULL,
    designation VARCHAR(50) NOT NULL,
    official_email VARCHAR(100) UNIQUE NOT NULL
) ENGINE=InnoDB;

-- ====================================================================
-- 8. WorkOrders
-- Third-party contractor repair assignments and cost management.
-- Estimated cost checked to be non-negative.
-- ====================================================================
CREATE TABLE WorkOrders (
    work_order_id INT PRIMARY KEY AUTO_INCREMENT,
    vendor_name VARCHAR(100) NOT NULL,
    issued_date DATE NOT NULL,
    est_cost DECIMAL(10,2) NOT NULL,
    completed_date DATE NULL,
    CONSTRAINT chk_est_cost CHECK (est_cost >= 0.00)
) ENGINE=InnoDB;

-- ====================================================================
-- TRIGGERS
-- ====================================================================

DELIMITER $$

-- Trigger 1: Validate Citizen Date of Birth on Insert
DROP TRIGGER IF EXISTS trg_validate_citizen_dob_insert $$
CREATE TRIGGER trg_validate_citizen_dob_insert
BEFORE INSERT ON Citizens
FOR EACH ROW
BEGIN
    IF NEW.date_of_birth > CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Citizen date of birth cannot be in the future';
    END IF;
END $$

-- Trigger 2: Validate Citizen Date of Birth on Update
DROP TRIGGER IF EXISTS trg_validate_citizen_dob_update $$
CREATE TRIGGER trg_validate_citizen_dob_update
BEFORE UPDATE ON Citizens
FOR EACH ROW
BEGIN
    IF NEW.date_of_birth > CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Citizen date of birth cannot be in the future';
    END IF;
END $$

-- Trigger 3: Validate Work Order Estimated Cost on Insert
DROP TRIGGER IF EXISTS trg_before_workorder_insert $$
CREATE TRIGGER trg_before_workorder_insert
BEFORE INSERT ON WorkOrders
FOR EACH ROW
BEGIN
    IF NEW.est_cost < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Estimated cost cannot be negative';
    END IF;
END $$

-- Trigger 4: Automatic Audit Media Insertion upon new Complaint
DROP TRIGGER IF EXISTS trg_after_complaint_insert $$
CREATE TRIGGER trg_after_complaint_insert
AFTER INSERT ON LightComplaints
FOR EACH ROW
BEGIN
    INSERT INTO ComplaintMedia (complaint_id, media_url, uploaded_at)
    VALUES (NEW.complaint_id, CONCAT('https://lumisafe.org/proofs/ticket_', NEW.complaint_id, '_created.jpg'), NOW());
END $$

-- Trigger 5: Automatic Audit Log upon Complaint Status Update
DROP TRIGGER IF EXISTS trg_after_complaint_status_update $$
CREATE TRIGGER trg_after_complaint_status_update
AFTER UPDATE ON LightComplaints
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO ComplaintMedia (complaint_id, media_url, uploaded_at)
        VALUES (NEW.complaint_id, CONCAT('https://lumisafe.org/proofs/ticket_', NEW.complaint_id, '_status_', LOWER(REPLACE(NEW.status, ' ', '_')), '.jpg'), NOW());
    END IF;
END $$

-- ====================================================================
-- STORED PROCEDURES & CURSORS
-- ====================================================================

-- Procedure 1: Process and Audit High & Critical Priority Complaints
DROP PROCEDURE IF EXISTS sp_process_high_priority_complaints $$
CREATE PROCEDURE sp_process_high_priority_complaints()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_complaint_id INT;
    DECLARE v_priority VARCHAR(20);

    DECLARE cur CURSOR FOR
        SELECT complaint_id, priority FROM LightComplaints WHERE priority IN ('High', 'Critical');

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_complaint_id, v_priority;
        IF done = 1 THEN LEAVE read_loop; END IF;

        INSERT INTO ComplaintMedia (complaint_id, media_url, uploaded_at)
        VALUES (v_complaint_id, CONCAT('https://lumisafe.org/reports/audit_priority_', LOWER(v_priority), '.jpg'), NOW());
    END LOOP;
    CLOSE cur;

    SELECT 'High and Critical priority complaints processed successfully.' AS message;
END $$

-- Procedure 2: Cursor-based High Cost Work Orders Auditor
DROP PROCEDURE IF EXISTS sp_high_cost_work_order_report $$
CREATE PROCEDURE sp_high_cost_work_order_report()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_work_order_id INT;
    DECLARE v_vendor VARCHAR(100);
    DECLARE v_est_cost DECIMAL(10,2);

    DECLARE cur CURSOR FOR
        SELECT work_order_id, vendor_name, est_cost FROM WorkOrders WHERE est_cost > 5000.00;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_work_order_id, v_vendor, v_est_cost;
        IF done = 1 THEN LEAVE read_loop; END IF;
        -- Can log to an audit table or print
    END LOOP;
    CLOSE cur;

    SELECT work_order_id, vendor_name, est_cost, issued_date
    FROM WorkOrders
    WHERE est_cost > 5000.00
    ORDER BY est_cost DESC;
END $$

-- Procedure 3: Summary Statistics of Active Faults
DROP PROCEDURE IF EXISTS sp_get_lumisafe_kpis $$
CREATE PROCEDURE sp_get_lumisafe_kpis()
BEGIN
    SELECT
        (SELECT COUNT(*) FROM LightPoles) AS total_poles,
        (SELECT COUNT(*) FROM SolarLightPoles) AS total_solar_poles,
        (SELECT COUNT(*) FROM ElectricalLightPoles) AS total_electrical_poles,
        (SELECT COUNT(*) FROM LightPoles WHERE is_high_risk = TRUE) AS high_risk_poles,
        (SELECT COUNT(*) FROM LightComplaints WHERE status = 'Open') AS open_complaints,
        (SELECT COUNT(*) FROM LightComplaints WHERE status = 'In Progress') AS in_progress_complaints,
        (SELECT COUNT(*) FROM LightComplaints WHERE status = 'Resolved') AS resolved_complaints,
        (SELECT COUNT(*) FROM WorkOrders WHERE completed_date IS NULL) AS pending_work_orders,
        (SELECT IFNULL(SUM(est_cost), 0) FROM WorkOrders) AS total_repair_budget;
END $$

DELIMITER ;

-- ====================================================================
-- VIEWS FOR STREAMLINED REPORTING
-- ====================================================================

DROP VIEW IF EXISTS vw_PolesOverview;
CREATE VIEW vw_PolesOverview AS
SELECT 
    p.pole_id,
    p.pole_name,
    p.latitude,
    p.longitude,
    p.is_high_risk,
    CASE 
        WHEN s.pole_id IS NOT NULL AND e.pole_id IS NOT NULL THEN 'Hybrid (Solar + Electrical)'
        WHEN s.pole_id IS NOT NULL THEN 'Solar'
        WHEN e.pole_id IS NOT NULL THEN 'Electrical'
        ELSE 'Standard'
    END AS pole_type
FROM LightPoles p
LEFT JOIN SolarLightPoles s ON p.pole_id = s.pole_id
LEFT JOIN ElectricalLightPoles e ON p.pole_id = e.pole_id;

DROP VIEW IF EXISTS vw_ActiveComplaints;
CREATE VIEW vw_ActiveComplaints AS
SELECT 
    c.complaint_id,
    c.issue_type,
    c.priority,
    c.status,
    c.created_at,
    COUNT(m.media_id) AS media_count
FROM LightComplaints c
LEFT JOIN ComplaintMedia m ON c.complaint_id = m.complaint_id
GROUP BY c.complaint_id, c.issue_type, c.priority, c.status, c.created_at;

-- ====================================================================
-- SEED DATA (MUNICIPAL CIVIC DATASET)
-- ====================================================================

-- 1. Electrical Divisions
INSERT INTO ElectricalDivisions (div_name, district) VALUES
('Central Division', 'Bengaluru Urban'),
('BESCOM South Division', 'Bengaluru Urban'),
('BESCOM East Division', 'Bengaluru East'),
('North Zone Power & Lighting', 'Bengaluru North');

-- 2. Ward Councils
INSERT INTO WardCouncils (ward_name, councillor_name) VALUES
('Ward 150 HSR Layout', 'K. Ramesh'),
('Ward 174 Bellandur', 'Sunita Reddy'),
('Ward 142 Koramangala', 'Manjunath Rao'),
('Ward 80 Indiranagar', 'Pooja Hegde');

-- 3. Light Poles
INSERT INTO LightPoles (pole_name, latitude, longitude, is_high_risk) VALUES
('P-BLR-101', 12.91210000, 77.64450000, FALSE),
('P-BLR-102', 12.91350000, 77.64620000, TRUE),
('P-BLR-103', 12.93520000, 77.62450000, FALSE),
('P-BLR-104', 12.93880000, 77.61890000, TRUE),
('P-BLR-105', 12.97190000, 77.64120000, FALSE),
('P-BLR-106', 12.97840000, 77.64080000, TRUE),
('P-BLR-107', 12.92980000, 77.68350000, FALSE),
('P-BLR-108', 12.93150000, 77.68900000, FALSE);

-- Sub-Entities
INSERT INTO SolarLightPoles (pole_id) VALUES (1), (3), (7);
INSERT INTO ElectricalLightPoles (pole_id) VALUES (2), (4), (5), (6), (8);

-- 4. Citizens
INSERT INTO Citizens (first_name, last_name, email, phone_no, date_of_birth) VALUES
('Aarav', 'Sharma', 'aarav.sharma@example.com', '9880123456', '1995-08-15'),
('Priya', 'Nair', 'priya.nair@example.com', '9880654321', '1992-04-22'),
('Rohan', 'Verma', 'rohan.verma@example.com', '9845012345', '1988-11-30'),
('Ananya', 'Deshmukh', 'ananya.d@example.com', '9845987654', '2001-02-10');

-- 5. Light Complaints (Trigger trg_after_complaint_insert will auto-insert initial audit media)
INSERT INTO LightComplaints (issue_type, priority, status) VALUES
('Bulb Failure (Pole: P-BLR-101)', 'Medium', 'Open'),
('Wiring Exposed (Pole: P-BLR-102)', 'Critical', 'In Progress'),
('Pole Leaning / Physical Damage (Pole: P-BLR-103)', 'High', 'Open'),
('Flickering Lamp (Pole: P-BLR-104)', 'Low', 'Resolved');

-- 6. Additional ComplaintMedia (Photo proofs uploaded by citizens / field inspectors)
INSERT INTO ComplaintMedia (complaint_id, media_url) VALUES
(1, 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500&auto=format&fit=crop&q=60'),
(2, 'https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=500&auto=format&fit=crop&q=60'),
(3, 'https://images.unsplash.com/photo-1516574187841-cb9cc2ca948b?w=500&auto=format&fit=crop&q=60');

-- 7. Electrical Officials
INSERT INTO ElectricalOfficials (official_name, designation, official_email) VALUES
('Suresh Kumar', 'Junior Engineer', 'suresh.k@bescom.gov.in'),
('Dr. Rajeshwari Swamy', 'Assistant Executive Engineer', 'rajeshwari.s@bescom.gov.in'),
('Venkatesh Babu', 'Chief Electrical Inspector', 'v.babu@lumisafe.gov.in'),
('Meera Krishnan', 'Safety Assurance Officer', 'meera.k@lumisafe.gov.in');

-- 8. Work Orders
INSERT INTO WorkOrders (vendor_name, issued_date, est_cost, completed_date) VALUES
('LumiTech Infrastructure Ltd', '2026-11-01', 4500.00, '2026-11-04'),
('VoltCare Municipal Repairs', '2026-11-03', 12500.00, NULL),
('Apex Solar Dynamics', '2026-11-05', 7800.00, NULL),
('BrightCity Maintenance Corp', '2026-10-20', 3200.00, '2026-10-25');

