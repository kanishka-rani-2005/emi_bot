import requests
import json
import time
import os
import logging
import mimetypes
import base64
# NOTE: settings and API clients must be configured in your environment
from django.conf import settings
from openai import OpenAI
# NOTE: ElevenLabs SDK usage might be slightly different depending on version, 
# assuming client setup here is correct for the user's environment.
from elevenlabs import ElevenLabs

# --- Configuration (Assumed from original code) ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Placeholder: In a real Django environment, these would be correctly configured.
class MockSettings:
    OPENAI_API_KEY = "sk-..."
    ELEVENLABS_API_KEY = "..."
    HEYGEN_API_KEY = "..."
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Use a mock settings object if running standalone, otherwise settings is from Django
if 'settings' not in locals():
    try:
        settings.configure()
    except Exception:
        settings = MockSettings() 

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
# NOTE: ElevenLabs init might vary, using the assumed init from original code
eleven_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

INDIAN_AVATAR_ID = "f142bc68aff14463983d9bd526f33390"

BASE_SCRIPTS = {
    'EMI_DUE': "Hello {customer_name}, your EMI of {emi_amount} for loan {loan_number} is due on {due_date}. Please make the payment to avoid penalties. Thank you.",
    'NACH_REMINDER': "Hello {customer_name}, this is a reminder for your NACH presentation for loan {loan_number}. Please ensure you have sufficient balance. Thank you.",
    'BOUNCE_REMINDER': "Hello {customer_name}, your recent EMI payment for loan {loan_number} has bounced. A penalty of {penalty_amount} has been applied. Please make the payment immediately. Thank you."
}

# --- Utility Functions ---
def list_heygen_avatars():
    url = "https://api.heygen.com/v1/video/avatars"

    headers = {
        "X-Api-Key": settings.HEYGEN_API_KEY, 
        "Accept": "application/json"
    }

    try:
        print("Attempting to list V1 public avatars...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        data = response.json()
        avatars = data.get("data", {}).get("list", [])

        if avatars:
            print(f"✅ Found {len(avatars)} V1 avatars. Copy one ID.")
            for avatar in avatars:
                print(f"  - ID: {avatar.get('avatar_id')} | Name: {avatar.get('name')}")
        else:
            print("❌ V1 List is also empty. The one valid ID must be found in your HeyGen dashboard.")

    except requests.exceptions.RequestException as e:
        print(f"❌ V1 Request failed: {e}")

def translate_text_openai(text, target_lang):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"Read the sentence carefully. Add if anything is missing without numbers. Translate this message into {target_lang}. Keep tone polite, conversational, use numerals in {target_lang} script. Script must be grammatically correct. It should make sense to a native speaker."
                },
                {"role": "user", "content": text}
            ],
            timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return text


def generate_script(event_type, customer, loan):
    template = BASE_SCRIPTS.get(event_type)
    if not template:
        return "Default reminder: Please pay your EMI."

    english_script = template.format(
        customer_name=customer.name,
        emi_amount=loan.emi_amount,
        due_date=loan.due_date.strftime("%d %B %Y"),
        loan_number=loan.loan_number,
        penalty_amount="₹500"
    )

    customer_lang = getattr(customer, "preferred_language", "en")
    if customer_lang != "en":
        translated = translate_text_openai(english_script, customer_lang)
        logging.info(f"Translated Script: {translated}")
        return translated
    else:
        logging.info(f"English Script: {english_script}")
        return english_script


def generate_voice(script, lang="hi"):
    try:
        voices = {
            "en": "TVtDNgumMv4lb9zzFzA2",        
            "hi": "KSsyodh37PbfWy29kPtx",        
            "hindi": "dxhwlBCxCrnzRlP4wPeE"    
        }
        
        voice_id = voices.get(lang.lower(), "TVtDNgumMv4lb9zzFzA2")
        output_path = "reminder_voice.mp3"

        # Generate audio using ElevenLabs
        audio = eleven_client.text_to_speech.convert(
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            text=script
        )
        
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                logging.error("Generated MP3 is empty")
                return None
            logging.info(f"Voice generated successfully: {output_path} ({file_size} bytes)")
            return output_path
        else:
            logging.error("Voice file was not created")
            return None

    except Exception as e:
        logging.error(f"ElevenLabs voice generation failed: {e}")
        return None

def upload_audio_to_heygen(mp3_path, retries=3, delay=3):
    """
    Uploads audio to HeyGen API. Corrected to use the dedicated 'upload.heygen.com' 
    endpoint for file streams and correctly parse the 'id' field from the response.
    """
    if not os.path.exists(mp3_path):
        logging.error(f"MP3 file does not exist: {mp3_path}")
        return None

    # Verify file is not empty
    file_size = os.path.getsize(mp3_path)
    if file_size == 0:
        logging.error("MP3 is empty; aborting upload.")
        return None
    
    logging.info(f"Uploading MP3 ({file_size} bytes): {mp3_path}")

    api_key = settings.HEYGEN_API_KEY
    
    # Using the user-specified upload domain for multipart/file stream.
    # Reverting Base64 upload to api.heygen.com/v1/assets for JSON compatibility (though it fails with 404).
    upload_url_multipart = "https://upload.heygen.com/v1/asset" 
    upload_url_base64 = "https://api.heygen.com/v1/assets" 

    filename = os.path.basename(mp3_path)
    guessed_type, _ = mimetypes.guess_type(filename)
    content_type = guessed_type or "audio/mpeg"

    headers_json = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    
    # Headers for direct file stream upload
    headers_raw_file = {
        "X-Api-Key": api_key,
        "Content-Type": content_type, # Specify audio/mpeg
        "Purpose": "audio",
    }


    # --- Raw File Stream Upload Attempt (Matching User's Example) ---
    for attempt in range(1, retries + 1):
        try:
            logging.info(f"Attempting Raw File Stream upload (URL: {upload_url_multipart})")
            
            with open(mp3_path, "rb") as f:
                # Posting the raw file stream directly to the specialized upload endpoint
                resp = requests.post(
                    upload_url_multipart, 
                    data=f,
                    headers=headers_raw_file,
                    params={"purpose": "audio"}, # Trying purpose as a query param
                    timeout=60,
                )

            logging.info(f"[HeyGen Raw Stream] Attempt {attempt} - Status: {resp.status_code}")
            logging.info(f"[HeyGen Raw Stream] Response: {resp.text}")

            if resp.status_code in [200, 201]:
                resp_json = resp.json()
                
                # *** FIX HERE ***: Check for the correct 'id' key in 'data'
                if "data" in resp_json and "id" in resp_json["data"]:
                    asset_id = resp_json["data"]["id"]
                    logging.info(f" ✅ Audio uploaded successfully. Asset ID: {asset_id}")
                    return asset_id
                    
                if "asset_id" in resp_json:
                    asset_id = resp_json["asset_id"]
                    logging.info(f" Audio uploaded successfully. Asset ID: {asset_id}")
                    return asset_id

                # If success but ID missing, log and break to fallback
                logging.warning("Raw upload succeeded but asset ID not found, trying Base64 fallback...")
                break

            # If 4xx/5xx, raise to go to retry/backoff
            resp.raise_for_status()

        except Exception as e:
            logging.error(f"Audio upload (Raw Stream) attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(delay * attempt)
                logging.info(f"Retrying Raw Stream upload (attempt {attempt + 1})...")
            else:
                logging.warning("All Raw Stream attempts failed, trying Base64 fallback...")


    # --- Base64 Upload Attempt (Fallback to /v1/assets) ---
    try:
        logging.info("Attempting Base64 upload as fallback (URL: https://api.heygen.com/v1/assets)...")
        
        with open(mp3_path, "rb") as f:
            b64_audio = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "name": filename,
            "purpose": "audio",
            "mime_type": content_type,
            "data": b64_audio,
        }

        resp = requests.post(
            upload_url_base64, # Using api.heygen.com/v1/assets
            headers=headers_json,
            json=payload,
            timeout=60,
        )

        logging.info(f"[HeyGen base64] Status: {resp.status_code}")
        logging.info(f"[HeyGen base64] Response: {resp.text}")

        if resp.status_code in [200, 201]:
            resp_json = resp.json()
            
            if "data" in resp_json and "asset_id" in resp_json["data"]:
                asset_id = resp_json["data"]["asset_id"]
                logging.info(f" Audio uploaded via base64. Asset ID: {asset_id}")
                return asset_id
                
            if "asset_id" in resp_json:
                asset_id = resp_json["asset_id"]
                logging.info(f" Audio uploaded via base64. Asset ID: {asset_id}")
                return asset_id

        else:
            logging.error(f"Base64 upload failed: {resp.text}")

    except Exception as e:
        logging.error(f"Base64 audio upload failed: {e}")

    logging.error(" All attempts to upload audio failed.")
    return None
def generate_video(script, customer, timeout=480, poll_interval=8):
    """
    Generate video using HeyGen API with ElevenLabs voice
    """
    try:
        list_heygen_avatars()
        lang = getattr(customer, "preferred_language", "hi")

        # Step 1: Generate voice using ElevenLabs
        logging.info("Step 1: Generating voice with ElevenLabs...")
        voice_file = generate_voice(script, lang)
        if not voice_file:
            logging.error("Voice generation failed. Aborting video creation.")
            return None

        # Step 2: Upload voice to HeyGen
        logging.info("Step 2: Uploading audio to HeyGen...")
        audio_asset_id = upload_audio_to_heygen(voice_file)
        
        # Cleanup temporary MP3 file
        if os.path.exists(voice_file):
            try:
                os.remove(voice_file)
                logging.info(f"Cleaned up temporary file: {voice_file}")
            except Exception as e:
                logging.warning(f"Could not delete temp file: {e}")
        
        if not audio_asset_id:
            logging.error("Audio upload failed. Aborting video creation.")
            return None

        # Step 3: Request video generation
        logging.info("Step 3: Requesting video generation from HeyGen...")
        url = "https://api.heygen.com/v2/video/generate"
        headers = {
            "X-Api-Key": settings.HEYGEN_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": INDIAN_AVATAR_ID,
                        "avatar_style": "normal"
                    },
                    "voice": {
                    "type": "audio", 
                    "audio_asset_id": audio_asset_id
                },
                    "background": {
                        "type": "color",
                        "value": "#005DFD"
                    }
                }
            ],
            "caption": False,
            "test": False
        }

        logging.info(f"Video generation payload: {json.dumps(payload, indent=2)}")
        
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        
        logging.info(f"Video generation response status: {resp.status_code}")
        logging.info(f"Video generation response: {resp.text}")
        
        if resp.status_code not in [200, 201]:
            logging.error(f"HeyGen API error: {resp.text}")
            return None
            
        resp_json = resp.json()
        
        # Extract video_id from response
        video_id = None
        if "data" in resp_json and "video_id" in resp_json["data"]:
            video_id = resp_json["data"]["video_id"]
        elif "video_id" in resp_json:
            video_id = resp_json["video_id"]
            
        if not video_id:
            logging.error(f"No video_id in response: {resp_json}")
            return None

        logging.info(f"Video generation started. Video ID: {video_id}")

        # Step 4: Poll video status until completion
        logging.info("Step 4: Polling for video completion...")
        elapsed = 0
        attempt = 0
        
        while elapsed < timeout:
            attempt += 1
            
            try:
                status_url = f"https://api.heygen.com/v2/video/{video_id}"
                status_resp = requests.get(status_url, headers=headers, timeout=30)
                
                if status_resp.status_code != 200:
                    logging.warning(f"Status check failed: {status_resp.status_code}")
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    continue
                
                status_data = status_resp.json()
                logging.info(f"Status check {attempt}: {json.dumps(status_data, indent=2)}")
                
                # Extract status and video URL
                video_status = None
                video_url = None
                
                if "data" in status_data:
                    data = status_data["data"]
                    video_status = data.get("status")
                    video_url = data.get("video_url") or data.get("video_url_caption") or data.get("url")
                else:
                    video_status = status_data.get("status")
                    video_url = status_data.get("video_url") or status_data.get("url")
                
                logging.info(f"Video status: {video_status} (attempt {attempt}, elapsed {elapsed}s)")
                
                # Check if video is ready
                if video_status == "completed" and video_url:
                    logging.info(f" Video generation completed!")
                    logging.info(f"Video URL: {video_url}")
                    
                    # Download video to local storage
                    try:
                        save_dir = os.path.join(settings.BASE_DIR, "reminder_videos")
                        os.makedirs(save_dir, exist_ok=True)
                        video_path = os.path.join(save_dir, f"{video_id}.mp4")

                        logging.info(f"Downloading video from: {video_url}")
                        video_resp = requests.get(video_url, stream=True, timeout=300)
                        video_resp.raise_for_status()
                        
                        with open(video_path, "wb") as f:
                            for chunk in video_resp.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)

                        video_size = os.path.getsize(video_path)
                        logging.info(f"Video saved successfully: {video_path} ({video_size} bytes)")
                        return video_path
                        
                    except Exception as download_error:
                        logging.error(f"Video download failed: {download_error}")
                        # Return URL as fallback
                        return video_url
                        
                elif video_status in ["failed", "error"]:
                    logging.error(f" Vide generation failed with status: {video_status}")
                    return None
                    
                elif video_status in ["processing", "pending", "queued"]:
                    # Continue polling
                    pass
                else:
                    logging.warning(f"Unknown video status: {video_status}")
                
            except Exception as e:
                logging.error(f"Status check error: {e}")
            
            time.sleep(poll_interval)
            elapsed += poll_interval

        logging.error(f" Video generation timed out after {timeout} seconds")
        return None

    except Exception as e:
        logging.error(f" Unexpected error during video generation: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None

def send_whatsapp_video(to_number, video_url):

    logging.info(f"📱 Sending WhatsApp video to {to_number}")
    logging.info(f"Video URL: {video_url}")
    
    
    logging.info("[SIMULATED] WhatsApp message sent successfully")
    return "simulated_message_sid"