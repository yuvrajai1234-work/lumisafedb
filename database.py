import os
import re
import sqlite3
import datetime
from pathlib import Path
import pymysql
import pymysql.cursors
from config import Config, BASE_DIR

class DatabaseManager:
    def __init__(self):
        self.mysql_host = Config.MYSQL_HOST
        self.mysql_port = Config.MYSQL_PORT
        self.mysql_user = Config.MYSQL_USER
        self.mysql_password = Config.MYSQL_PASSWORD
        self.mysql_db = Config.MYSQL_DB
        self.sqlite_path = Config.SQLITE_PATH
        self.active_driver = 'sqlite'
        self.last_error = None
        
        # Attempt auto-detection of MySQL
        self.try_connect_mysql()
        
        # Ensure fallback SQLite DB exists and is initialized
        self.init_sqlite_if_needed()

    def try_connect_mysql(self, password=None):
        """Attempts to connect to MySQL Server."""
        # On Vercel serverless, skip localhost connection if not cloud-hosted
        if os.environ.get('VERCEL') and self.mysql_host in ('127.0.0.1', 'localhost'):
            self.active_driver = 'sqlite'
            self.last_error = "Localhost MySQL unreachable from cloud; using high-fidelity mirror."
            return False, self.last_error

        pwd = password if password is not None else self.mysql_password
        try:
            conn = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=pwd,
                charset='utf8mb4',
                connect_timeout=2,
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.mysql_db}` CHARACTER SET utf8mb4;")
            conn.select_db(self.mysql_db)
            conn.close()
            
            if password is not None:
                self.mysql_password = password
            self.active_driver = 'mysql'
            self.last_error = None
            return True, f"Successfully connected to MySQL Server on {self.mysql_host}:{self.mysql_port} (Database: {self.mysql_db})"
        except Exception as e:
            self.last_error = str(e)
            return False, f"MySQL connection failed: {str(e)}"

    def get_connection(self):
        """Returns a connection object based on active driver."""
        if self.active_driver == 'mysql':
            try:
                return pymysql.connect(
                    host=self.mysql_host,
                    port=self.mysql_port,
                    user=self.mysql_user,
                    password=self.mysql_password,
                    database=self.mysql_db,
                    charset='utf8mb4',
                    autocommit=True,
                    cursorclass=pymysql.cursors.DictCursor
                )
            except Exception as e:
                self.last_error = f"MySQL disconnected ({str(e)}), falling back to SQLite."
                self.active_driver = 'sqlite'
                
        # SQLite Connection
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def get_status(self):
        """Returns metadata about the active connection and server status."""
        mysql_live = False
        mysql_msg = ""
        try:
            c = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=self.mysql_password,
                connect_timeout=1
            )
            c.close()
            mysql_live = True
            mysql_msg = f"Connected as {self.mysql_user}@{self.mysql_host}:{self.mysql_port}"
        except Exception as e:
            mysql_msg = str(e)

        return {
            "active_driver": self.active_driver,
            "mysql_live": mysql_live,
            "mysql_msg": mysql_msg,
            "mysql_host": self.mysql_host,
            "mysql_port": self.mysql_port,
            "mysql_user": self.mysql_user,
            "mysql_db": self.mysql_db,
            "has_password": bool(self.mysql_password),
            "sqlite_file": str(self.sqlite_path.name),
            "last_error": self.last_error
        }

    def init_sqlite_if_needed(self):
        """Initializes SQLite schema matching the exact MySQL specifications."""
        try:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        need_init = not self.sqlite_path.exists() or self.sqlite_path.stat().st_size == 0
        if not need_init:
            return

        conn = sqlite3.connect(str(self.sqlite_path))
        cur = conn.cursor()
        cur.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS ElectricalDivisions (
            div_id INTEGER PRIMARY KEY AUTOINCREMENT,
            div_name TEXT NOT NULL,
            district TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS WardCouncils (
            ward_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ward_name TEXT NOT NULL,
            councillor_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS LightPoles (
            pole_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pole_name TEXT NOT NULL,
            latitude REAL NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
            longitude REAL NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
            is_high_risk INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS SolarLightPoles (
            pole_id INTEGER PRIMARY KEY,
            FOREIGN KEY (pole_id) REFERENCES LightPoles(pole_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ElectricalLightPoles (
            pole_id INTEGER PRIMARY KEY,
            FOREIGN KEY (pole_id) REFERENCES LightPoles(pole_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS Citizens (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone_no TEXT UNIQUE NOT NULL,
            date_of_birth TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS LightComplaints (
            complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type TEXT NOT NULL,
            priority TEXT NOT NULL CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
            status TEXT NOT NULL CHECK (status IN ('Open', 'In Progress', 'Resolved')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ComplaintMedia (
            media_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            media_url TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES LightComplaints(complaint_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ElectricalOfficials (
            official_id INTEGER PRIMARY KEY AUTOINCREMENT,
            official_name TEXT NOT NULL,
            designation TEXT NOT NULL,
            official_email TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS WorkOrders (
            work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL,
            issued_date TEXT NOT NULL,
            est_cost REAL NOT NULL CHECK (est_cost >= 0.0),
            completed_date TEXT
        );

        -- Trigger to validate citizen DOB
        CREATE TRIGGER IF NOT EXISTS trg_validate_dob_insert
        BEFORE INSERT ON Citizens
        FOR EACH ROW
        WHEN NEW.date_of_birth > date('now')
        BEGIN
            SELECT RAISE(ABORT, 'Citizen date of birth cannot be in the future');
        END;

        -- Trigger to validate citizen DOB update
        CREATE TRIGGER IF NOT EXISTS trg_validate_dob_update
        BEFORE UPDATE ON Citizens
        FOR EACH ROW
        WHEN NEW.date_of_birth > date('now')
        BEGIN
            SELECT RAISE(ABORT, 'Citizen date of birth cannot be in the future');
        END;

        -- Trigger after complaint insert to add audit proof
        CREATE TRIGGER IF NOT EXISTS trg_after_complaint_insert_sq
        AFTER INSERT ON LightComplaints
        FOR EACH ROW
        BEGIN
            INSERT INTO ComplaintMedia (complaint_id, media_url, uploaded_at)
            VALUES (NEW.complaint_id, 'https://lumisafe.org/proofs/ticket_' || NEW.complaint_id || '_created.jpg', datetime('now'));
        END;

        -- Seed initial records
        INSERT INTO ElectricalDivisions (div_name, district) VALUES
            ('Central Division', 'Bengaluru Urban'),
            ('BESCOM South Division', 'Bengaluru Urban'),
            ('BESCOM East Division', 'Bengaluru East'),
            ('North Zone Power & Lighting', 'Bengaluru North');

        INSERT INTO WardCouncils (ward_name, councillor_name) VALUES
            ('Ward 150 HSR Layout', 'K. Ramesh'),
            ('Ward 174 Bellandur', 'Sunita Reddy'),
            ('Ward 142 Koramangala', 'Manjunath Rao'),
            ('Ward 80 Indiranagar', 'Pooja Hegde');

        INSERT INTO LightPoles (pole_name, latitude, longitude, is_high_risk) VALUES
            ('P-BLR-101', 12.91210000, 77.64450000, 0),
            ('P-BLR-102', 12.91350000, 77.64620000, 1),
            ('P-BLR-103', 12.93520000, 77.62450000, 0),
            ('P-BLR-104', 12.93880000, 77.61890000, 1),
            ('P-BLR-105', 12.97190000, 77.64120000, 0),
            ('P-BLR-106', 12.97840000, 77.64080000, 1),
            ('P-BLR-107', 12.92980000, 77.68350000, 0),
            ('P-BLR-108', 12.93150000, 77.68900000, 0);

        INSERT INTO SolarLightPoles (pole_id) VALUES (1), (3), (7);
        INSERT INTO ElectricalLightPoles (pole_id) VALUES (2), (4), (5), (6), (8);

        INSERT INTO Citizens (first_name, last_name, email, phone_no, date_of_birth) VALUES
            ('Aarav', 'Sharma', 'aarav.sharma@example.com', '9880123456', '1995-08-15'),
            ('Priya', 'Nair', 'priya.nair@example.com', '9880654321', '1992-04-22'),
            ('Rohan', 'Verma', 'rohan.verma@example.com', '9845012345', '1988-11-30'),
            ('Ananya', 'Deshmukh', 'ananya.d@example.com', '9845987654', '2001-02-10');

        INSERT INTO LightComplaints (issue_type, priority, status) VALUES
            ('Bulb Failure', 'Medium', 'Open'),
            ('Wiring Exposed', 'Critical', 'In Progress'),
            ('Pole Leaning / Physical Damage', 'High', 'Open'),
            ('Flickering Lamp', 'Low', 'Resolved');

        INSERT INTO ComplaintMedia (complaint_id, media_url) VALUES
            (1, 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500&auto=format&fit=crop&q=60'),
            (2, 'https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=500&auto=format&fit=crop&q=60'),
            (3, 'https://images.unsplash.com/photo-1516574187841-cb9cc2ca948b?w=500&auto=format&fit=crop&q=60');

        INSERT INTO ElectricalOfficials (official_name, designation, official_email) VALUES
            ('Suresh Kumar', 'Junior Engineer', 'suresh.k@bescom.gov.in'),
            ('Dr. Rajeshwari Swamy', 'Assistant Executive Engineer', 'rajeshwari.s@bescom.gov.in'),
            ('Venkatesh Babu', 'Chief Electrical Inspector', 'v.babu@lumisafe.gov.in'),
            ('Meera Krishnan', 'Safety Assurance Officer', 'meera.k@lumisafe.gov.in');

        INSERT INTO WorkOrders (vendor_name, issued_date, est_cost, completed_date) VALUES
            ('LumiTech Infrastructure Ltd', '2026-11-01', 4500.00, '2026-11-04'),
            ('VoltCare Municipal Repairs', '2026-11-03', 12500.00, NULL),
            ('Apex Solar Dynamics', '2026-11-05', 7800.00, NULL),
            ('BrightCity Maintenance Corp', '2026-10-20', 3200.00, '2026-10-25');
        """)
        conn.commit()
        conn.close()

    def run_schema_file_on_mysql(self, sql_file_path=None):
        """Executes lumisafe_schema.sql directly on MySQL."""
        if not sql_file_path:
            sql_file_path = BASE_DIR / 'lumisafe_schema.sql'

        with open(sql_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        conn = pymysql.connect(
            host=self.mysql_host,
            port=self.mysql_port,
            user=self.mysql_user,
            password=self.mysql_password,
            charset='utf8mb4',
            autocommit=True
        )

        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.mysql_db}` CHARACTER SET utf8mb4;")
            cur.execute(f"USE `{self.mysql_db}`;")

            # Parse SQL statements with support for DELIMITER $$
            statements = []
            current_delimiter = ';'
            current_stmt = []

            for line in content.splitlines():
                stripped = line.strip()
                if stripped.upper().startswith('DELIMITER'):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        current_delimiter = parts[1]
                    continue

                if not stripped or stripped.startswith('--') or stripped.startswith('#'):
                    continue

                current_stmt.append(line)

                if current_delimiter == ';' and stripped.endswith(';'):
                    stmt = '\n'.join(current_stmt).strip()
                    if stmt:
                        statements.append(stmt)
                    current_stmt = []
                elif current_delimiter != ';' and stripped.endswith(current_delimiter):
                    stmt = '\n'.join(current_stmt).rstrip(current_delimiter).strip()
                    if stmt:
                        statements.append(stmt)
                    current_stmt = []

            # Execute each statement
            for stmt in statements:
                stmt_clean = stmt.strip()
                if stmt_clean and not stmt_clean.upper().startswith('USE '):
                    try:
                        cur.execute(stmt_clean)
                    except Exception as err:
                        # Log but continue for idempotent statements
                        print(f"Schema execution warning: {err} in statement: {stmt_clean[:60]}...")

        conn.close()
        self.active_driver = 'mysql'
        return True, f"Successfully executed {len(statements)} schema statements on MySQL '{self.mysql_db}'."

    def query(self, sql, params=None):
        """Executes a SELECT query returning a list of dictionaries."""
        conn = self.get_connection()
        try:
            if self.active_driver == 'mysql':
                with conn.cursor() as cur:
                    cur.execute(sql, params or ())
                    return cur.fetchall()
            else:
                cur = conn.cursor()
                # Adapt %s placeholder to ? for sqlite if needed
                adapted_sql = re.sub(r'%s', '?', sql)
                cur.execute(adapted_sql, params or ())
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        finally:
            conn.close()

    def execute(self, sql, params=None):
        """Executes INSERT/UPDATE/DELETE returning lastrowid and rowcount."""
        conn = self.get_connection()
        try:
            if self.active_driver == 'mysql':
                with conn.cursor() as cur:
                    cur.execute(sql, params or ())
                    rowid = cur.lastrowid
                    count = cur.rowcount
                    return {"lastrowid": rowid, "rowcount": count}
            else:
                cur = conn.cursor()
                adapted_sql = re.sub(r'%s', '?', sql)
                cur.execute(adapted_sql, params or ())
                conn.commit()
                rowid = cur.lastrowid
                count = cur.rowcount
                return {"lastrowid": rowid, "rowcount": count}
        finally:
            conn.close()

    def run_raw_sql(self, sql_query):
        """Runs arbitrary user query from SQL Workbench Console."""
        conn = self.get_connection()
        try:
            if self.active_driver == 'mysql':
                with conn.cursor() as cur:
                    cur.execute(sql_query)
                    if cur.description:
                        columns = [desc[0] for desc in cur.description]
                        rows = cur.fetchall()
                        # Convert any non-serializable objects (datetime, Decimal)
                        clean_rows = []
                        for row in rows:
                            clean_row = {}
                            for k, v in row.items():
                                if isinstance(v, (datetime.date, datetime.datetime)):
                                    clean_row[k] = v.isoformat()
                                elif hasattr(v, '__float__'):
                                    clean_row[k] = float(v)
                                else:
                                    clean_row[k] = v
                            clean_rows.append(clean_row)
                        return {"success": True, "type": "SELECT", "columns": columns, "rows": clean_rows, "count": len(clean_rows)}
                    else:
                        return {"success": True, "type": "COMMAND", "message": f"Query executed successfully. Affected rows: {cur.rowcount}"}
            else:
                cur = conn.cursor()
                cur.execute(sql_query)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    clean_rows = [dict(row) for row in rows]
                    return {"success": True, "type": "SELECT", "columns": columns, "rows": clean_rows, "count": len(clean_rows)}
                else:
                    conn.commit()
                    return {"success": True, "type": "COMMAND", "message": f"Query executed successfully. Affected rows: {cur.rowcount}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    # -------------------------------------------------------------
    # HIGH-LEVEL ENTITY OPERATIONS
    # -------------------------------------------------------------

    def get_kpis(self):
        """Retrieves dashboard KPIs."""
        poles_count = self.query("SELECT COUNT(*) AS c FROM LightPoles")[0]['c']
        solar_count = self.query("SELECT COUNT(*) AS c FROM SolarLightPoles")[0]['c']
        elec_count = self.query("SELECT COUNT(*) AS c FROM ElectricalLightPoles")[0]['c']
        risk_count = self.query("SELECT COUNT(*) AS c FROM LightPoles WHERE is_high_risk = 1")[0]['c']
        
        open_c = self.query("SELECT COUNT(*) AS c FROM LightComplaints WHERE status = 'Open'")[0]['c']
        prog_c = self.query("SELECT COUNT(*) AS c FROM LightComplaints WHERE status = 'In Progress'")[0]['c']
        res_c = self.query("SELECT COUNT(*) AS c FROM LightComplaints WHERE status = 'Resolved'")[0]['c']
        
        pending_wo = self.query("SELECT COUNT(*) AS c FROM WorkOrders WHERE completed_date IS NULL")[0]['c']
        total_budget = self.query("SELECT IFNULL(SUM(est_cost), 0) AS s FROM WorkOrders")[0]['s'] or 0
        citizens_count = self.query("SELECT COUNT(*) AS c FROM Citizens")[0]['c']
        officials_count = self.query("SELECT COUNT(*) AS c FROM ElectricalOfficials")[0]['c']

        return {
            "total_poles": poles_count,
            "solar_poles": solar_count,
            "electrical_poles": elec_count,
            "high_risk_poles": risk_count,
            "open_complaints": open_c,
            "in_progress_complaints": prog_c,
            "resolved_complaints": res_c,
            "pending_work_orders": pending_wo,
            "total_budget": float(total_budget),
            "citizens_count": citizens_count,
            "officials_count": officials_count
        }

    # 1. Electrical Divisions
    def get_divisions(self):
        return self.query("SELECT * FROM ElectricalDivisions ORDER BY div_id ASC")

    def create_division(self, div_name, district):
        return self.execute(
            "INSERT INTO ElectricalDivisions (div_name, district) VALUES (%s, %s)",
            (div_name, district)
        )

    def delete_division(self, div_id):
        return self.execute("DELETE FROM ElectricalDivisions WHERE div_id = %s", (div_id,))

    # 2. Ward Councils
    def get_wards(self):
        return self.query("SELECT * FROM WardCouncils ORDER BY ward_id ASC")

    def create_ward(self, ward_name, councillor_name):
        return self.execute(
            "INSERT INTO WardCouncils (ward_name, councillor_name) VALUES (%s, %s)",
            (ward_name, councillor_name)
        )

    def delete_ward(self, ward_id):
        return self.execute("DELETE FROM WardCouncils WHERE ward_id = %s", (ward_id,))

    # 3. Light Poles (Master + Sub-Entities)
    def get_poles(self):
        sql = """
        SELECT 
            p.pole_id,
            p.pole_name,
            p.latitude,
            p.longitude,
            p.is_high_risk,
            CASE 
                WHEN s.pole_id IS NOT NULL AND e.pole_id IS NOT NULL THEN 'Hybrid'
                WHEN s.pole_id IS NOT NULL THEN 'Solar'
                WHEN e.pole_id IS NOT NULL THEN 'Electrical'
                ELSE 'Standard'
            END AS pole_type,
            CASE WHEN s.pole_id IS NOT NULL THEN 1 ELSE 0 END AS is_solar,
            CASE WHEN e.pole_id IS NOT NULL THEN 1 ELSE 0 END AS is_electrical
        FROM LightPoles p
        LEFT JOIN SolarLightPoles s ON p.pole_id = s.pole_id
        LEFT JOIN ElectricalLightPoles e ON p.pole_id = e.pole_id
        ORDER BY p.pole_id ASC
        """
        return self.query(sql)

    def create_pole(self, pole_name, latitude, longitude, is_high_risk=False, pole_type='Electrical'):
        lat = float(latitude)
        lon = float(longitude)
        if not (-90.0 <= lat <= 90.0):
            raise ValueError("Latitude must be between -90 and +90 degrees.")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError("Longitude must be between -180 and +180 degrees.")

        res = self.execute(
            "INSERT INTO LightPoles (pole_name, latitude, longitude, is_high_risk) VALUES (%s, %s, %s, %s)",
            (pole_name, lat, lon, 1 if is_high_risk else 0)
        )
        new_id = res['lastrowid']

        if pole_type in ('Solar', 'Hybrid'):
            self.execute("INSERT INTO SolarLightPoles (pole_id) VALUES (%s)", (new_id,))
        if pole_type in ('Electrical', 'Hybrid'):
            self.execute("INSERT INTO ElectricalLightPoles (pole_id) VALUES (%s)", (new_id,))

        return new_id

    def delete_pole(self, pole_id):
        return self.execute("DELETE FROM LightPoles WHERE pole_id = %s", (pole_id,))

    # 4. Citizens
    def get_citizens(self):
        return self.query("SELECT * FROM Citizens ORDER BY user_id ASC")

    def create_citizen(self, first_name, last_name, email, phone_no, date_of_birth):
        # Trigger validation check
        dob = datetime.date.fromisoformat(str(date_of_birth))
        if dob > datetime.date.today():
            raise ValueError("Trigger Validation Error: Citizen date of birth cannot be in the future.")

        return self.execute(
            "INSERT INTO Citizens (first_name, last_name, email, phone_no, date_of_birth) VALUES (%s, %s, %s, %s, %s)",
            (first_name, last_name, email, phone_no, str(date_of_birth))
        )

    def delete_citizen(self, user_id):
        return self.execute("DELETE FROM Citizens WHERE user_id = %s", (user_id,))

    # 5. Light Complaints
    def get_pole_by_name(self, pole_name):
        if not pole_name:
            return None
        sql = "SELECT * FROM LightPoles WHERE UPPER(TRIM(pole_name)) = UPPER(TRIM(%s))"
        rows = self.query(sql, (pole_name,))
        return rows[0] if rows else None

    def get_complaints(self):
        sql = """
        SELECT 
            c.complaint_id,
            c.issue_type,
            c.priority,
            c.status,
            c.created_at,
            (SELECT COUNT(*) FROM ComplaintMedia m WHERE m.complaint_id = c.complaint_id) AS media_count
        FROM LightComplaints c
        ORDER BY c.complaint_id DESC
        """
        complaints = self.query(sql)

        # Enrich complaints with pole coordinates
        try:
            poles = self.get_poles()
            pole_lookup = {p['pole_name'].upper().strip(): p for p in poles}

            # Fallback map for original seed complaints 1..4 if not explicitly tagged
            seed_pole_map = {
                1: 'P-BLR-101',
                2: 'P-BLR-102',
                3: 'P-BLR-103',
                4: 'P-BLR-104'
            }

            for c in complaints:
                matched_pole = None
                issue = (c.get('issue_type') or '').upper()

                # Search registered pole names within issue_type (e.g. "(Pole: P-BLR-101)")
                for pname, pdata in pole_lookup.items():
                    if pname in issue:
                        matched_pole = pdata
                        break

                # Seed complaint fallback if pole wasn't written into issue_type
                if not matched_pole and c.get('complaint_id'):
                    cid = int(c['complaint_id'])
                    if cid in seed_pole_map and seed_pole_map[cid] in pole_lookup:
                        matched_pole = pole_lookup[seed_pole_map[cid]]

                if matched_pole:
                    c['pole_name'] = matched_pole['pole_name']
                    lat = float(matched_pole['latitude'])
                    lon = float(matched_pole['longitude'])
                    c['latitude'] = lat
                    c['longitude'] = lon
                    c['coordinates'] = f"{lat:.6f}, {lon:.6f}"
                else:
                    c['pole_name'] = None
                    c['latitude'] = None
                    c['longitude'] = None
                    c['coordinates'] = None
        except Exception as e:
            logger.warning(f"Failed enriching complaints with pole coordinates: {e}")

        return complaints

    def create_complaint(self, issue_type, priority, status='Open', media_url=None):
        if priority not in ('Low', 'Medium', 'High', 'Critical'):
            raise ValueError(f"Invalid priority '{priority}'")
        if status not in ('Open', 'In Progress', 'Resolved'):
            raise ValueError(f"Invalid status '{status}'")

        res = self.execute(
            "INSERT INTO LightComplaints (issue_type, priority, status) VALUES (%s, %s, %s)",
            (issue_type, priority, status)
        )
        new_id = res['lastrowid']

        # If user explicitly provided media, add it
        if media_url:
            self.execute(
                "INSERT INTO ComplaintMedia (complaint_id, media_url) VALUES (%s, %s)",
                (new_id, media_url)
            )

        return new_id

    def update_complaint_status(self, complaint_id, new_status):
        if new_status not in ('Open', 'In Progress', 'Resolved'):
            raise ValueError(f"Invalid status '{new_status}'")
        
        # When running on SQLite, replicate the trigger behavior if needed
        res = self.execute(
            "UPDATE LightComplaints SET status = %s WHERE complaint_id = %s",
            (new_status, complaint_id)
        )
        if self.active_driver == 'sqlite':
            audit_url = f"https://lumisafe.org/proofs/ticket_{complaint_id}_status_{new_status.lower().replace(' ', '_')}.jpg"
            self.execute(
                "INSERT INTO ComplaintMedia (complaint_id, media_url, uploaded_at) VALUES (%s, %s, datetime('now'))",
                (complaint_id, audit_url)
            )
        return res

    def delete_complaint(self, complaint_id):
        return self.execute("DELETE FROM LightComplaints WHERE complaint_id = %s", (complaint_id,))

    # 6. Complaint Media
    def get_media(self, complaint_id=None):
        if complaint_id:
            return self.query(
                "SELECT * FROM ComplaintMedia WHERE complaint_id = %s ORDER BY media_id DESC",
                (complaint_id,)
            )
        return self.query("SELECT * FROM ComplaintMedia ORDER BY media_id DESC")

    def create_media(self, complaint_id, media_url):
        return self.execute(
            "INSERT INTO ComplaintMedia (complaint_id, media_url) VALUES (%s, %s)",
            (complaint_id, media_url)
        )

    # 7. Electrical Officials
    def get_officials(self):
        return self.query("SELECT * FROM ElectricalOfficials ORDER BY official_id ASC")

    def create_official(self, official_name, designation, official_email):
        return self.execute(
            "INSERT INTO ElectricalOfficials (official_name, designation, official_email) VALUES (%s, %s, %s)",
            (official_name, designation, official_email)
        )

    def delete_official(self, official_id):
        return self.execute("DELETE FROM ElectricalOfficials WHERE official_id = %s", (official_id,))

    def find_citizen_by_email(self, email):
        rows = self.query("SELECT * FROM Citizens WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
        return rows[0] if rows else None

    def find_official_by_email(self, email):
        rows = self.query("SELECT * FROM ElectricalOfficials WHERE LOWER(official_email) = LOWER(%s)", (email.strip(),))
        return rows[0] if rows else None

    # 8. Work Orders
    def get_work_orders(self):
        return self.query("SELECT * FROM WorkOrders ORDER BY work_order_id DESC")

    def create_work_order(self, vendor_name, issued_date, est_cost, completed_date=None):
        cost = float(est_cost)
        if cost < 0:
            raise ValueError("Trigger & Constraint Error: Estimated cost cannot be negative.")

        comp_date = str(completed_date) if completed_date else None
        return self.execute(
            "INSERT INTO WorkOrders (vendor_name, issued_date, est_cost, completed_date) VALUES (%s, %s, %s, %s)",
            (vendor_name, str(issued_date), cost, comp_date)
        )

    def complete_work_order(self, work_order_id, completed_date=None):
        c_date = completed_date or str(datetime.date.today())
        return self.execute(
            "UPDATE WorkOrders SET completed_date = %s WHERE work_order_id = %s",
            (c_date, work_order_id)
        )

    def delete_work_order(self, work_order_id):
        return self.execute("DELETE FROM WorkOrders WHERE work_order_id = %s", (work_order_id,))

db = DatabaseManager()

