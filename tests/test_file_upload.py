import unittest
import os
import shutil
import sys
from io import BytesIO

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, DB_PATH, UPLOAD_FOLDER

class TestFileUpload(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = app.test_client()
        
        # Ensure upload folder exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        self.test_filename = "test_upload_doc.pdf"
        
    def tearDown(self):
        pass

    def login(self):
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['session_version'] = 1 # Mock version

    def test_upload_guide(self):
        self.login()
        
        data = {
            'guide_file': (BytesIO(b"dummy pdf content"), self.test_filename)
        }
        
        response = self.client.post('/how-to-guides/import', data=data, content_type='multipart/form-data', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT filename, original_filename FROM how_to_guides ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row, "No guide record found in DB")
        saved_filename = row[0]
        original_filename = row[1]
        self.assertEqual(original_filename, self.test_filename)
        
        full_path = os.path.join(UPLOAD_FOLDER, saved_filename)
        self.assertTrue(os.path.exists(full_path), f"File not found at {full_path}")
        print(f"SUCCESS: Guide uploaded to {full_path}")

    def test_upload_checklist(self):
        self.login()
        
        data = {
            'checklist_file': (BytesIO(b"dummy pdf content for checklist"), "test_checklist.pdf")
        }
        
        response = self.client.post('/cleaning-checklists/import', data=data, content_type='multipart/form-data', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT filename, original_filename FROM checklist_templates ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row, "No checklist record found in DB")
        saved_filename = row[0]
        original_filename = row[1]
        self.assertEqual(original_filename, "test_checklist.pdf")
        
        full_path = os.path.join(UPLOAD_FOLDER, saved_filename)
        self.assertTrue(os.path.exists(full_path), f"File not found at {full_path}")
        print(f"SUCCESS: Checklist uploaded to {full_path}")

if __name__ == '__main__':
    unittest.main()
