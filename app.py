import os
import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from config import Config
from database import db

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# -------------------------------------------------------------
# Web Page Navigation Routes
# -------------------------------------------------------------
@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/citizen/login')
def citizen_login_page():
    if session.get('user_role') == 'citizen':
        return redirect('/citizen/dashboard')
    return render_template('citizen_login.html')

@app.route('/citizen/dashboard')
def citizen_dashboard():
    if session.get('user_role') != 'citizen':
        return redirect('/citizen/login')
    return render_template('citizen_dashboard.html', citizen=session.get('citizen'))

@app.route('/official/login')
def official_login_page():
    if session.get('user_role') == 'official':
        return redirect('/official/dashboard')
    return render_template('official_login.html')

@app.route('/official/dashboard')
def official_dashboard():
    if session.get('user_role') != 'official':
        return redirect('/official/login')
    return render_template('index.html', official=session.get('official'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# -------------------------------------------------------------
# Authentication APIs (Using Existing Attributes Only)
# -------------------------------------------------------------
@app.route('/api/auth/citizen/login', methods=['POST'])
def api_citizen_login():
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    citizen = db.find_citizen_by_email(email)
    if not citizen:
        return jsonify({
            "success": False,
            "error": "No citizen found with this email. Please register below."
        }), 404

    session['user_role'] = 'citizen'
    session['citizen'] = {
        "user_id": citizen['user_id'],
        "first_name": citizen['first_name'],
        "last_name": citizen['last_name'],
        "email": citizen['email'],
        "phone_no": citizen['phone_no'],
        "date_of_birth": str(citizen['date_of_birth'])
    }
    if 'my_complaints' not in session:
        session['my_complaints'] = []

    return jsonify({
        "success": True,
        "message": f"Welcome back, {citizen['first_name']} {citizen['last_name']}!",
        "redirect": "/citizen/dashboard"
    })

@app.route('/api/auth/citizen/register', methods=['POST'])
def api_citizen_register():
    data = request.json or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    phone_no = data.get('phone_no', '').strip()
    dob = data.get('date_of_birth', '').strip()

    if not all([first_name, last_name, email, phone_no, dob]):
        return jsonify({"success": False, "error": "All fields are mandatory for citizen registration."}), 400

    existing = db.find_citizen_by_email(email)
    if existing:
        return jsonify({"success": False, "error": "A citizen with this email address is already registered. Please log in directly."}), 400

    try:
        res = db.create_citizen(first_name, last_name, email, phone_no, dob)
        new_id = res['lastrowid']
        session['user_role'] = 'citizen'
        session['citizen'] = {
            "user_id": new_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone_no": phone_no,
            "date_of_birth": dob
        }
        if 'my_complaints' not in session:
            session['my_complaints'] = []

        return jsonify({
            "success": True,
            "message": f"Registration successful! Welcome to LumiSafe, {first_name}.",
            "redirect": "/citizen/dashboard"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/auth/official/login', methods=['POST'])
def api_official_login():
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email:
        return jsonify({"success": False, "error": "Official government email is required."}), 400

    official = db.find_official_by_email(email)
    if not official:
        return jsonify({
            "success": False,
            "error": "Access denied. Email not found in Electrical Officials registry. Please contact administration."
        }), 403

    session['user_role'] = 'official'
    session['official'] = {
        "official_id": official['official_id'],
        "official_name": official['official_name'],
        "designation": official['designation'],
        "official_email": official['official_email']
    }

    return jsonify({
        "success": True,
        "message": f"Authentication verified. Welcome Officer {official['official_name']}.",
        "redirect": "/official/dashboard"
    })

@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    return jsonify({
        "user_role": session.get('user_role'),
        "citizen": session.get('citizen'),
        "official": session.get('official')
    })

# -------------------------------------------------------------
# System & MySQL Workbench Connectivity APIs
# -------------------------------------------------------------
@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(db.get_status())

@app.route('/api/kpis', methods=['GET'])
def get_kpis():
    try:
        return jsonify({"success": True, "data": db.get_kpis()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/mysql/connect', methods=['POST'])
def connect_mysql():
    data = request.json or {}
    host = data.get('host', db.mysql_host)
    port = int(data.get('port', db.mysql_port))
    user = data.get('user', db.mysql_user)
    password = data.get('password', '')
    database_name = data.get('database', db.mysql_db)

    db.mysql_host = host
    db.mysql_port = port
    db.mysql_user = user
    db.mysql_db = database_name

    success, msg = db.try_connect_mysql(password=password)
    if success:
        return jsonify({"success": True, "message": msg, "status": db.get_status()})
    else:
        return jsonify({"success": False, "error": msg, "status": db.get_status()}), 400

@app.route('/api/mysql/init-schema', methods=['POST'])
def init_mysql_schema():
    try:
        success, msg = db.run_schema_file_on_mysql()
        return jsonify({"success": True, "message": msg, "status": db.get_status()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/sql/run', methods=['POST'])
def run_sql():
    data = request.json or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"success": False, "error": "Query cannot be empty"}), 400
    
    result = db.run_raw_sql(query)
    return jsonify(result)

# -------------------------------------------------------------
# 1. Electrical Divisions API
# -------------------------------------------------------------
@app.route('/api/divisions', methods=['GET', 'POST'])
def api_divisions():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_divisions()})
    data = request.json or {}
    div_name = data.get('div_name', '').strip()
    district = data.get('district', '').strip()
    if not div_name or not district:
        return jsonify({"success": False, "error": "Division name and district are required."}), 400
    try:
        res = db.create_division(div_name, district)
        return jsonify({"success": True, "id": res['lastrowid'], "message": "Division created successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/divisions/<int:div_id>', methods=['DELETE'])
def api_delete_division(div_id):
    try:
        db.delete_division(div_id)
        return jsonify({"success": True, "message": f"Division {div_id} deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 2. Ward Councils API
# -------------------------------------------------------------
@app.route('/api/wards', methods=['GET', 'POST'])
def api_wards():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_wards()})
    data = request.json or {}
    ward_name = data.get('ward_name', '').strip()
    councillor_name = data.get('councillor_name', '').strip()
    if not ward_name or not councillor_name:
        return jsonify({"success": False, "error": "Ward name and councillor name are required."}), 400
    try:
        res = db.create_ward(ward_name, councillor_name)
        return jsonify({"success": True, "id": res['lastrowid'], "message": "Ward Council added successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/wards/<int:ward_id>', methods=['DELETE'])
def api_delete_ward(ward_id):
    try:
        db.delete_ward(ward_id)
        return jsonify({"success": True, "message": f"Ward {ward_id} deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 3. Light Poles API (Master + Sub-Entities)
# -------------------------------------------------------------
@app.route('/api/poles', methods=['GET', 'POST'])
def api_poles():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_poles()})
    data = request.json or {}
    pole_name = data.get('pole_name', '').strip()
    try:
        lat = float(data.get('latitude', 0))
        lon = float(data.get('longitude', 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Latitude and Longitude must be valid decimal numbers."}), 400
        
    is_high_risk = bool(data.get('is_high_risk', False))
    pole_type = data.get('pole_type', 'Electrical')

    if not pole_name:
        return jsonify({"success": False, "error": "Pole name/code is required."}), 400

    try:
        new_id = db.create_pole(pole_name, lat, lon, is_high_risk, pole_type)
        return jsonify({"success": True, "id": new_id, "message": f"Light Pole {pole_name} created successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/poles/<int:pole_id>', methods=['DELETE'])
def api_delete_pole(pole_id):
    try:
        db.delete_pole(pole_id)
        return jsonify({"success": True, "message": f"Pole {pole_id} deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 4. Citizens API
# -------------------------------------------------------------
@app.route('/api/citizens', methods=['GET', 'POST'])
def api_citizens():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_citizens()})
    data = request.json or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    phone_no = data.get('phone_no', '').strip()
    dob = data.get('date_of_birth', '').strip()

    if not all([first_name, last_name, email, phone_no, dob]):
        return jsonify({"success": False, "error": "All citizen fields are mandatory."}), 400

    try:
        res = db.create_citizen(first_name, last_name, email, phone_no, dob)
        return jsonify({"success": True, "id": res['lastrowid'], "message": "Citizen registered successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/citizens/<int:user_id>', methods=['DELETE'])
def api_delete_citizen(user_id):
    try:
        db.delete_citizen(user_id)
        return jsonify({"success": True, "message": f"Citizen {user_id} deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 5. Light Complaints API
# -------------------------------------------------------------
@app.route('/api/complaints', methods=['GET', 'POST'])
def api_complaints():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_complaints()})
    data = request.json or {}
    issue_type = data.get('issue_type', '').strip()
    priority = data.get('priority', 'Medium').strip()
    status = data.get('status', 'Open').strip()
    media_url = data.get('media_url', '').strip() or None

    if not issue_type:
        return jsonify({"success": False, "error": "Issue type is required."}), 400

    try:
        new_id = db.create_complaint(issue_type, priority, status, media_url)
        
        my_list = session.get('my_complaints', [])
        if new_id not in my_list:
            my_list.append(new_id)
            session['my_complaints'] = my_list

        return jsonify({"success": True, "id": new_id, "message": f"Complaint #{new_id} submitted successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/citizen/my-complaints', methods=['GET'])
def api_citizen_my_complaints():
    my_ids = session.get('my_complaints', [])
    all_complaints = db.get_complaints()
    filtered = [c for c in all_complaints if c['complaint_id'] in my_ids]
    return jsonify({
        "success": True,
        "my_ids": my_ids,
        "data": filtered,
        "all_data": all_complaints
    })

@app.route('/api/complaints/<int:complaint_id>/status', methods=['POST'])
def api_update_complaint_status(complaint_id):
    data = request.json or {}
    status = data.get('status', '').strip()
    if not status:
        return jsonify({"success": False, "error": "Status is required."}), 400
    try:
        db.update_complaint_status(complaint_id, status)
        return jsonify({"success": True, "message": f"Complaint #{complaint_id} updated to '{status}'."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/complaints/<int:complaint_id>', methods=['DELETE'])
def api_delete_complaint(complaint_id):
    try:
        db.delete_complaint(complaint_id)
        return jsonify({"success": True, "message": f"Complaint #{complaint_id} removed."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 6. Complaint Media API
# -------------------------------------------------------------
@app.route('/api/media', methods=['GET', 'POST'])
def api_media():
    if request.method == 'GET':
        cid = request.args.get('complaint_id', type=int)
        return jsonify({"success": True, "data": db.get_media(cid)})
    data = request.json or {}
    complaint_id = data.get('complaint_id')
    media_url = data.get('media_url', '').strip()
    if not complaint_id or not media_url:
        return jsonify({"success": False, "error": "Complaint ID and Media URL are required."}), 400
    try:
        res = db.create_media(int(complaint_id), media_url)
        return jsonify({"success": True, "id": res['lastrowid'], "message": "Media proof uploaded."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 7. Electrical Officials API
# -------------------------------------------------------------
@app.route('/api/officials', methods=['GET', 'POST'])
def api_officials():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_officials()})
    data = request.json or {}
    name = data.get('official_name', '').strip()
    designation = data.get('designation', '').strip()
    email = data.get('official_email', '').strip()
    if not all([name, designation, email]):
        return jsonify({"success": False, "error": "Official name, designation, and official email are required."}), 400
    try:
        res = db.create_official(name, designation, email)
        return jsonify({"success": True, "id": res['lastrowid'], "message": "Official registered successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/officials/<int:official_id>', methods=['DELETE'])
def api_delete_official(official_id):
    try:
        db.delete_official(official_id)
        return jsonify({"success": True, "message": f"Official {official_id} deleted."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# -------------------------------------------------------------
# 8. Work Orders API
# -------------------------------------------------------------
@app.route('/api/workorders', methods=['GET', 'POST'])
def api_workorders():
    if request.method == 'GET':
        return jsonify({"success": True, "data": db.get_work_orders()})
    data = request.json or {}
    vendor_name = data.get('vendor_name', '').strip()
    issued_date = data.get('issued_date', '').strip()
    est_cost = data.get('est_cost')
    completed_date = data.get('completed_date', '').strip() or None

    if not vendor_name or not issued_date or est_cost is None:
        return jsonify({"success": False, "error": "Vendor name, issue date, and estimated cost are required."}), 400

    try:
        new_id = db.create_work_order(vendor_name, issued_date, est_cost, completed_date)
        return jsonify({"success": True, "id": new_id, "message": f"Work Order #{new_id} issued successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/workorders/<int:wo_id>/complete', methods=['POST'])
def api_complete_workorder(wo_id):
    data = request.json or {}
    c_date = data.get('completed_date')
    try:
        db.complete_work_order(wo_id, c_date)
        return jsonify({"success": True, "message": f"Work Order #{wo_id} marked as completed."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/workorders/<int:wo_id>', methods=['DELETE'])
def api_delete_workorder(wo_id):
    try:
        db.delete_work_order(wo_id)
        return jsonify({"success": True, "message": f"Work Order #{wo_id} removed."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n=======================================================")
    print(f"  LumiSafe Municipal Street Light App starting...")
    print(f"  Open in browser: http://127.0.0.1:{port}")
    print(f"=======================================================")
    app.run(host='127.0.0.1', port=port, debug=True)
