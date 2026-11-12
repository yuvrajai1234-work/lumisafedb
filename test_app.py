#!/usr/bin/env python3
"""
LumiSafe Automated Verification Test
Tests Dual-Portal navigation, authentication, API routes, CRUD operations, and triggers.
"""

import unittest
import json
import datetime
from app import app
from database import db

class LumiSafeTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_landing_page(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Citizen Portal", res.data)
        self.assertIn(b"Official Portal", res.data)

    def test_status_endpoint(self):
        res = self.client.get('/api/status')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('active_driver', data)

    def test_kpis_endpoint(self):
        res = self.client.get('/api/kpis')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['data']['total_poles'], 0)

    def test_citizen_auth_and_my_complaints(self):
        # 1. Login with existing citizen email
        login_res = self.client.post('/api/auth/citizen/login', json={"email": "aarav.sharma@example.com"})
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(login_res.get_json()['success'])

        # 2. File a complaint as citizen
        comp_res = self.client.post('/api/complaints', json={
            "issue_type": "Bulb Failure",
            "priority": "Medium",
            "status": "Open",
            "media_url": "https://example.com/test_citizen_proof.jpg"
        })
        self.assertEqual(comp_res.status_code, 200)
        new_id = comp_res.get_json()['id']

        # 3. Check citizen's my-complaints
        my_res = self.client.get('/api/citizen/my-complaints')
        self.assertEqual(my_res.status_code, 200)
        my_data = my_res.get_json()
        self.assertIn(new_id, my_data['my_ids'])

    def test_official_auth(self):
        # 1. Valid official email
        res = self.client.post('/api/auth/official/login', json={"email": "suresh.k@bescom.gov.in"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # 2. Invalid official email
        bad_res = self.client.post('/api/auth/official/login', json={"email": "intruder@unknown.com"})
        self.assertEqual(bad_res.status_code, 403)

    def test_light_poles_crud(self):
        payload = {
            "pole_name": "P-TEST-999",
            "latitude": 12.9200,
            "longitude": 77.6500,
            "pole_type": "Solar",
            "is_high_risk": True
        }
        res = self.client.post('/api/poles', json=payload)
        self.assertEqual(res.status_code, 200)
        pole_id = res.get_json()['id']

        poles = self.client.get('/api/poles').get_json()['data']
        created = next((p for p in poles if p['pole_id'] == pole_id), None)
        self.assertIsNotNone(created)
        self.assertEqual(created['pole_type'], 'Solar')
        self.assertEqual(created['is_high_risk'], 1)

        del_res = self.client.delete(f'/api/poles/{pole_id}')
        self.assertEqual(del_res.status_code, 200)

    def test_citizen_dob_trigger_validation(self):
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        payload = {
            "first_name": "Test",
            "last_name": "Citizen",
            "email": "test.future@example.com",
            "phone_no": "9999900001",
            "date_of_birth": tomorrow
        }
        res = self.client.post('/api/citizens', json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot be in the future", res.get_json()['error'])

    def test_work_order_cost_validation(self):
        payload = {
            "vendor_name": "Faulty Vendor",
            "issued_date": "2026-11-01",
            "est_cost": -500.00
        }
        res = self.client.post('/api/workorders', json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot be negative", res.get_json()['error'])

    def test_interactive_sql_runner(self):
        res = self.client.post('/api/sql/run', json={"query": "SELECT COUNT(*) AS total FROM LightPoles;"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['type'], 'SELECT')

if __name__ == '__main__':
    unittest.main()
