from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from datetime import datetime

# Add the parent directory to sys.path to import the PlantDiagnosisSystem
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plant_diagnosis import PlantDiagnosisSystem

# Initialize the plant diagnosis system
plant_system = PlantDiagnosisSystem()

def handle_diagnosis_request():
    """Process new images and return results"""
    try:
        # Get images without diagnosis
        new_images = plant_system.get_new_images()
        
        if not new_images:
            return {"status": "success", "message": "No new images to process", "processed": 0}
        
        processed_count = 0
        results = []
        
        for image_record in new_images:
            try:
                image_id = image_record['id']
                storage_path = image_record['storage_path']
                title = image_record.get('title', '')
                
                if not storage_path:
                    results.append({"id": image_id, "status": "error", "message": "Missing storage path"})
                    continue

                # Get image from storage
                image = plant_system.get_image_from_storage(storage_path)
                if not image:
                    results.append({"id": image_id, "status": "error", "message": "Failed to download image"})
                    continue
                
                # Generate diagnosis
                diagnosis = plant_system.diagnose_plant(image, title)
                if not diagnosis:
                    results.append({"id": image_id, "status": "error", "message": "Failed to generate diagnosis"})
                    continue
                
                # Update database with diagnosis
                success = plant_system.update_diagnosis_in_db(image_id, diagnosis)
                if success:
                    processed_count += 1
                    results.append({"id": image_id, "status": "success", "diagnosis": json.loads(diagnosis)})
                else:
                    results.append({"id": image_id, "status": "error", "message": "Failed to update database"})
                    
            except Exception as e:
                results.append({"id": image_record.get('id', 'unknown'), "status": "error", "message": str(e)})
        
        return {
            "status": "success",
            "message": f"Processed {processed_count} of {len(new_images)} images",
            "processed": processed_count,
            "results": results
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

def handle_test_connection():
    """Test connection to Supabase storage"""
    success = plant_system.test_storage_connection()
    return {"status": "success" if success else "error", "connection": "ok" if success else "failed"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "success",
            "message": "Plant Diagnosis API is running",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.wfile.write(json.dumps(response).encode())
        return
    
    def do_POST(self):
        """Handle POST requests"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            action = data.get('action', '')
            
            if action == 'process':
                response = handle_diagnosis_request()
            elif action == 'test_connection':
                response = handle_test_connection()
            else:
                response = {"status": "error", "message": "Invalid action"}
                
        except json.JSONDecodeError:
            response = {"status": "error", "message": "Invalid JSON data"}
        except Exception as e:
            response = {"status": "error", "message": str(e)}
        
        self.wfile.write(json.dumps(response).encode())
        return

# For local development
def app(environ, start_response):
    """WSGI app for local development"""
    if environ['REQUEST_METHOD'] == 'POST':
        try:
            content_length = int(environ.get('CONTENT_LENGTH', '0'))
            post_data = environ['wsgi.input'].read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            action = data.get('action', '')
            
            if action == 'process':
                response = handle_diagnosis_request()
            elif action == 'test_connection':
                response = handle_test_connection()
            else:
                response = {"status": "error", "message": "Invalid action"}
                
        except Exception as e:
            response = {"status": "error", "message": str(e)}
    else:
        response = {
            "status": "success",
            "message": "Plant Diagnosis API is running",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    response_body = json.dumps(response).encode('utf-8')
    status = '200 OK'
    headers = [('Content-type', 'application/json'),
               ('Content-Length', str(len(response_body)))]
    
    start_response(status, headers)
    return [response_body]

# This handler will be invoked when deployed to Vercel
def handler(request, response):
    """Vercel serverless function handler"""
    if request.method == 'POST':
        try:
            data = request.json()
            action = data.get('action', '')
            
            if action == 'process':
                result = handle_diagnosis_request()
            elif action == 'test_connection':
                result = handle_test_connection()
            else:
                result = {"status": "error", "message": "Invalid action"}
                
        except Exception as e:
            result = {"status": "error", "message": str(e)}
    else:
        result = {
            "status": "success",
            "message": "Plant Diagnosis API is running",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return response.json(result) 