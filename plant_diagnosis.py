## --- START OF FILE plant_diagnosis.py ---

import os
import time
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
# Removed asyncpg as we're using Supabase client directly
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import requests
from io import BytesIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('plant_diagnosis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PlantDiagnosisSystem:
    def __init__(self):
        # Initialize Supabase client
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # Use service role key
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Initialize Gemini
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Track processed images
        self.processed_images = set()
        
        # Plant diagnosis prompt
        self.diagnosis_prompt = """You are an expert botanist and plant pathologist. Your task is to accurately diagnose plant issues based on an image and a user's textual description.

Strict Output Requirements:
Your response MUST be ONLY in the JSON format specified below. You MUST NOT include any additional fields, comments, or prose outside of this JSON structure. You MUST adhere to the exact keys and data types defined in the JSON schema. If a field has no applicable data (e.g., no immediate actions are needed), return an empty array [] or an empty string "" as appropriate for the data type, but NEVER omit the field.

User Input:
Image: [The uploaded image of the plant. Focus your analysis on the visual cues from this image.]
Prompt: [User's textual description of the plant's symptoms or concerns, e.g., "My tomato plant has yellowing leaves and some spots. What's wrong with it?", "My rose bush leaves are curling and sticky.", "What's this disease on my cucumber plant?"]

Diagnosis Process:
1. Comprehensive Visual Analysis: Examine the provided image for all relevant visual symptoms: leaf discoloration (yellowing, browning, purpling), spots, lesions, wilting, drooping, abnormal growth, presence of pests, webbing, fungal growth, stem issues, etc.
2. Contextual Integration: Use the user's prompt to understand the specific plant type, observed symptoms, and any other relevant environmental conditions they mention.
3. Precise Identification: Identify the most probable plant disease, pest infestation, or nutrient deficiency. If multiple issues are evident, identify the primary one and mention secondary ones if significant. If unsure, state the most likely possibilities clearly.
4. Symptom Elaboration: Describe the specific symptoms observed that led to your diagnosis, correlating them directly with the image and prompt.
5. Severity Assessment: Assign a severity level: "Mild", "Moderate", or "Severe".
6. Actionable Recommendations: Provide clear, practical, and effective advice for treatment, management, and future prevention. Prioritize environmentally friendly and sustainable methods where feasible.

Response Format (JSON Schema - STRICTLY FOLLOW THIS):
{
  "diagnosis": {
    "title": "Diagnosis Summary",
    "identified_problem": "string",
    "severity": "string",
    "symptoms_observed": ["string"],
    "possible_causes": ["string"]
  },
  "recommendations": {
    "title": "Recommended Actions",
    "immediate_actions": ["string"],
    "long_term_care": ["string"],
    "prevention_tips": ["string"]
  },
  "disclaimer": "string"
}"""

    def get_image_from_storage(self, storage_path: str) -> Optional[Image.Image]:
        """Download image from Supabase storage using direct download or signed URL."""
        try:
            logger.info(f"Attempting to download image from path: {storage_path}")

            # Method 1: Try downloading directly using service role
            try:
                logger.info(f"Attempting direct download for: {storage_path}")
                download_response = self.supabase.storage.from_('images').download(storage_path)
                
                if download_response: # download_response contains image bytes on success
                    image = Image.open(BytesIO(download_response))
                    logger.info(f"Successfully downloaded image using direct download for: {storage_path}")
                    return image
                else:
                    # Supabase download() might return None or empty bytes without an exception for "not found"
                    # or certain permission issues not caught by an exception.
                    logger.warning(f"Direct download for {storage_path} returned no data. Trying signed URL method.")
                    
            except Exception as download_error: # Catches StorageException from supabase-py or other errors
                logger.warning(f"Direct download method for {storage_path} failed: {str(download_error)}. Trying signed URL method.")
            
            # Method 2: Try creating a signed URL
            try:
                logger.info(f"Attempting signed URL download for: {storage_path}")
                # create_signed_url returns a dict: {'signedURL': '...', 'error': None} or {'signedURL': None, 'error': '...'}
                # It can also raise an exception (e.g. for invalid path before returning a dict).
                signed_url_response = self.supabase.storage.from_('images').create_signed_url(storage_path, 3600)  # 1 hour expiry
                
                if signed_url_response and signed_url_response.get('signedURL'):
                    signed_url = signed_url_response['signedURL']
                    logger.info(f"Generated signed URL for {storage_path} (truncated): {signed_url[:70]}...")
                    
                    img_response = requests.get(signed_url, timeout=30)
                    img_response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
                    
                    image = Image.open(BytesIO(img_response.content))
                    logger.info(f"Successfully downloaded image using signed URL for: {storage_path}")
                    return image
                else:
                    error_detail = "Unknown reason"
                    if signed_url_response and signed_url_response.get('error'):
                        error_detail = signed_url_response.get('error')
                    elif not signed_url_response:
                         error_detail = "create_signed_url returned None or empty response."
                    logger.error(f"Failed to create signed URL for {storage_path}: {error_detail}")
                    
            except requests.exceptions.HTTPError as http_err: # Specific error for signed URL download failing at requests level
                logger.error(f"Signed URL download for {storage_path} failed with HTTP error: {str(http_err)}")
            except Exception as signed_url_error: # Other errors during signed URL process (e.g., supabase client error)
                logger.error(f"Signed URL method for {storage_path} failed: {str(signed_url_error)}")
            
            # If both direct download and signed URL methods have been attempted and failed to return an image
            logger.error(f"All download attempts (direct, signed URL) failed for {storage_path}.")
            return None
            
        except Exception as e: # Catch-all for truly unexpected issues in the function setup or logic not related to download methods.
            logger.error(f"Unexpected error in get_image_from_storage for {storage_path}: {str(e)}")
            return None

    def test_storage_connection(self):
        """Test storage bucket connection and list files"""
        try:
            logger.info("Testing storage bucket connection...")
            
            # List all files in the bucket
            files = self.supabase.storage.from_('images').list()
            logger.info(f"Found {len(files)} items in root of images bucket")
            
            for file in files[:5]:  # Show first 5 items
                logger.info(f"File: {file}")
                
            return True
            
        except Exception as e:
            logger.error(f"Storage connection test failed: {str(e)}")
            return False

    def diagnose_plant(self, image: Image.Image, user_prompt: str = "") -> Optional[str]:
        """Send image to Gemini for plant diagnosis"""
        try:
            # Prepare the full prompt
            full_prompt = f"{self.diagnosis_prompt}\n\nUser's description: {user_prompt}"
            
            # Generate diagnosis using Gemini
            response = self.model.generate_content([full_prompt, image])
            
            # Extract and validate JSON response
            raw_response_text = response.text.strip()
            
            # Attempt to clean markdown code fences
            cleaned_json_text = raw_response_text
            
            if cleaned_json_text.startswith("```json"):
                cleaned_json_text = cleaned_json_text[len("```json"):]
            elif cleaned_json_text.startswith("```"): 
                cleaned_json_text = cleaned_json_text[len("```"):]

            if cleaned_json_text.endswith("```"):
                cleaned_json_text = cleaned_json_text[:-len("```")]
            
            cleaned_json_text = cleaned_json_text.strip() 

            try:
                json.loads(cleaned_json_text)  
                return cleaned_json_text        
            except json.JSONDecodeError as e:
                logger.error(
                    f"Invalid JSON response from Gemini after cleaning. "
                    f"Error: {e}. \nCleaned text attempt: '{cleaned_json_text}'. "
                    f"\nOriginal text from Gemini: '{raw_response_text}'"
                )
                return None
                
        except Exception as e:
            logger.error(f"Error generating diagnosis: {str(e)}")
            return None

    def update_diagnosis_in_db(self, image_id: str, diagnosis: str) -> bool:
        """Update the diagnosis column in the database"""
        try:
            result = self.supabase.table('images').update({
                'diagnosis': diagnosis,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', image_id).execute()
            
            if result.data:
                logger.info(f"Successfully updated diagnosis for image {image_id}")
                return True
            else:
                logger.error(f"Failed to update diagnosis for image {image_id}. Response: {result}") # Added response detail
                return False
                
        except Exception as e:
            logger.error(f"Error updating database: {str(e)}")
            return False

    def get_new_images(self) -> list:
        """Get images that don't have a diagnosis yet"""
        try:
            result = self.supabase.table('images').select('*').is_('diagnosis', 'null').execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error fetching new images: {str(e)}")
            return []

    def process_new_images(self):
        """Process all new images without diagnosis"""
        new_images = self.get_new_images()
        
        if not new_images:
            logger.info("No new images to process")
            return
        
        logger.info(f"Found {len(new_images)} new images to process")
        
        for image_record in new_images:
            try:
                image_id = image_record['id']
                storage_path = image_record['storage_path']
                title = image_record.get('title', '') # Use .get for safer access
                
                if not storage_path:
                    logger.warning(f"Skipping image record {image_id} due to missing storage_path.")
                    continue

                logger.info(f"Processing image {image_id}: {storage_path}")
                
                image = self.get_image_from_storage(storage_path)
                if not image:
                    logger.error(f"Failed to download image {image_id} from {storage_path}. Skipping.")
                    # Optionally, update DB with an error status for this image
                    # self.update_diagnosis_in_db(image_id, json.dumps({"error": "Failed to download image"}))
                    continue
                
                diagnosis = self.diagnose_plant(image, title)
                if not diagnosis:
                    logger.error(f"Failed to generate diagnosis for image {image_id}. Skipping.")
                    # Optionally, update DB with an error status
                    # self.update_diagnosis_in_db(image_id, json.dumps({"error": "Failed to generate diagnosis"}))
                    continue
                
                if self.update_diagnosis_in_db(image_id, diagnosis):
                    logger.info(f"Successfully processed image {image_id}")
                else:
                    logger.error(f"Failed to update database for image {image_id} after successful diagnosis.")
                    
                time.sleep(2) # Consider making this configurable or adjusting based on API limits
                
            except Exception as e:
                logger.error(f"Error processing image record {image_record.get('id', 'unknown')}: {str(e)}")

    def run_continuous_monitoring(self, check_interval: int = 30):
        """Run continuous monitoring for new images"""
        logger.info("Starting continuous monitoring...")
        
        while True:
            try:
                self.process_new_images()
                logger.info(f"Waiting {check_interval} seconds before next check...")
                time.sleep(check_interval)
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(check_interval) # Wait before retrying loop to avoid rapid error logging

    def run_once(self):
        """Run the diagnosis process once"""
        logger.info("Running one-time diagnosis check...")
        
        if not self.test_storage_connection():
            logger.error("Storage connection test failed. Please check your bucket configuration and permissions.")
            return
            
        self.process_new_images()
        logger.info("One-time check completed")


def main():
    """Main function to run the plant diagnosis system"""
    required_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'GEMINI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return
    
    system = PlantDiagnosisSystem()
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        system.run_once()
    else:
        interval_arg = 30 # Default interval
        if len(sys.argv) > 1:
            try:
                interval_arg = int(sys.argv[1])
                if interval_arg <= 0:
                    logger.warning("Interval must be positive. Using default 30 seconds.")
                    interval_arg = 30
            except ValueError:
                logger.warning(f"Invalid interval '{sys.argv[1]}'. Using default 30 seconds.")
        
        system.run_continuous_monitoring(interval_arg)


if __name__ == "__main__":
    main()
## --- END OF FILE plant_diagnosis.py ---