import requests
import json
import time
import os
import logging
import mimetypes
from django.conf import settings
from openai import OpenAI
from elevenlabs import ElevenLabs
from datetime import date


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
eleven_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)


INDIAN_AVATAR_ID = "Aditya_public_1"

BASE_SCRIPTS = {
    "EMI_DUE": "Hello {customer_name}, your EMI of {emi_amount} for loan {loan_number} is due on {due_date}. Please make the payment to avoid penalties. Thank you.",
    "NACH_REMINDER": "Hello {customer_name}, this is a reminder for your NACH presentation for loan {loan_number}. Please ensure you have sufficient balance. Thank you.",
    "BOUNCE_REMINDER": "Hello {customer_name}, your recent EMI payment for loan {loan_number} has bounced. A penalty of {penalty_amount} has been applied. Please make the payment immediately. Thank you.",
}

def translate_text_openai(text, target_lang):
    # try:
    #     response = openai_client.chat.completions.create(
    #         model="gpt-4o-mini",
    #         messages=[
    #             {
    #                 "role": "system",
    #                 "content": f"Translate this sentence into {target_lang}. Use polite and natural tone with numerals in {target_lang} script.",
    #             },
    #             {"role": "user", "content": text},
    #         ],
    #         timeout=30,
    #     )
    #     return response.choices[0].message.content.strip()
    # except Exception as e:
    #     logging.error(f"Translation failed: {e}")
    #     return text
    text='''வணக்கம் கிற்னா, நான் உங்கள் நிதி உதவியாளர் பேசுகிறேன். 
    உங்கள் கடன் எண் EMI-123467ற்கான மாத தவணை ₹50,000.00, 27 அக்டோபர் 2025 அன்று செலுத்த வேண்டியுள்ளது. 
      தயவுசெய்து அதை நேரத்தில் செலுத்துங்கள்.EMI-யின் நன்மைகள்: பெரிய தொகையை ஒரே நேரத்தில் செலுத்த தேவையில்லை,
     மாதாந்திர கட்டணங்களால் நிதி சுமை குறையும்.குறைபாடுகள்: மாதந்தோறும் பொறுப்பு இருக்கும், தாமதம் ஏற்பட்டால் அபராதமும் க்ரெடிட் மதிப்பீட்டிலும் பாதிப்பும் ஏற்படும்.  நேரத்தில் செலுத்தி உங்கள் நிதி நலனை காப்பாற்றுங்கள்.  
நன்றி!'''
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
        penalty_amount="₹500",
    )

    customer_lang = getattr(customer, "preferred_language", "en")
    if customer_lang != "en":
        translated = translate_text_openai(english_script, customer_lang)
        logging.info(f"Translated Script ({customer_lang}): {translated}")
        return translated
    else:
        logging.info(f"English Script: {english_script}")
        return english_script


# def generate_voice(script):
#     try:
#         voice_id = "KSsyodh37PbfWy29kPtx"
#         output_path = "reminder_voice.mp3"

#         audio = eleven_client.text_to_speech.convert(
#             voice_id=voice_id,
#             model_id="eleven_multilingual_v2",
#             text=script
#         )

#         with open(output_path, "wb") as f:
#             for chunk in audio:
#                 f.write(chunk)

#         if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
#             logging.info(f"Voice generated successfully: {output_path}")
#             return output_path
#         else:
#             logging.error("Voice file was not created or is empty.")
#             return None
#     except Exception as e:
#         logging.error(f"ElevenLabs voice generation failed: {e}")
#         return None

# def upload_audio_to_heygen(mp3_path, retries=3, delay=3):
#     if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
#         logging.error(f"MP3 file does not exist or is empty: {mp3_path}")
#         return None

#     api_key = settings.HEYGEN_API_KEY
#     upload_url = "https://upload.heygen.com/v1/asset"

#     headers = {
#         "X-Api-Key": api_key,
#         "Content-Type": "audio/mpeg",
#         "Purpose": "audio",
#     }

#     for attempt in range(1, retries + 1):
#         try:
#             with open(mp3_path, "rb") as f:
#                 resp = requests.post(upload_url, data=f, headers=headers, timeout=60)

#             logging.info(f"Upload attempt {attempt}: {resp.status_code} {resp.text}")

#             if resp.status_code in [200, 201]:
#                 data = resp.json().get("data", {})
#                 asset_id = data.get("id")
#                 if asset_id:
#                     logging.info(f"Audio uploaded successfully: {asset_id}")
#                     return asset_id

#             time.sleep(delay)
#         except Exception as e:
#             logging.error(f"Attempt {attempt} failed: {e}")
#             time.sleep(delay)

#     logging.error("All attempts to upload audio failed.")
#     return None

def generate_video(script, customer, timeout=480, poll_interval=8):
    try:
        lang=getattr(customer, "preferred_language", "en")
        if lang =='Tamil':
            voice_id="f37bfc7d0be8494c8fa103a4a47eed33"  # Tamil voice ID
        elif lang =='Hindi':
            voice_id="dcf69bbbab5b41f2b75b9f86316c06c5"  # Hindi voice ID
        elif lang =='Kannada':
            voice_id="7d7d4ebc1c164e71a0542ecab97fdb43"  # Kannada voice ID
        elif lang =='Telugu':
            voice_id="8b06642340ad474e8d32b040928fe459"  # Telugu voice ID
        else:
            voice_id="97dd67ab8ce242b6a9e7689cb00c6414"  # Default to English

        logging.info("Step 1: Preparing HeyGen video generation payload...")
        url = "https://api.heygen.com/v2/video/generate"
        headers = {
            "X-Api-Key": settings.HEYGEN_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": "Adriana_Business_Front_public"
                    },
                    "voice": {
                        "type": "text",
                        "input_text": script,
                        "voice_id": voice_id,
                    }
                }
            ],
            "dimension": {"width": 640, "height": 360},
            "aspect_ratio": "16:9",
            "test": True
        }
        logging.info("Step 2: Requesting video generation from HeyGen...")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        logging.info(f"Video generation response: {resp.status_code} {resp.text}")

        if resp.status_code not in [200, 201]:
            logging.error(f"Video generation request failed: {resp.text}")
            return None

        data = resp.json().get("data", {})
        video_id = data.get("video_id")
        if not video_id:
            logging.error("No video_id returned from HeyGen.")
            return None

        logging.info(f"Video generation started. Video ID: {video_id}")
        status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"

        elapsed = 0
        attempt = 0

        while elapsed < timeout:
            attempt += 1
            logging.info(f"Polling attempt {attempt} (elapsed {elapsed}s)...")

            status_resp = requests.get(status_url, headers=headers, timeout=30)
            logging.info(f"Status response code: {status_resp.status_code}")

            if status_resp.status_code == 404:
                logging.warning("404 - Video not ready yet. Retrying...")
                time.sleep(poll_interval)
                elapsed += poll_interval
                continue

            if status_resp.status_code != 200:
                logging.error(f"Status check failed: {status_resp.text}")
                time.sleep(poll_interval)
                elapsed += poll_interval
                continue

            status_data = status_resp.json().get("data", {})
            status = status_data.get("status")
            video_url = status_data.get("video_url")

            logging.info(f"Video status: {status}")

            if status == "completed" and video_url:
                save_dir = os.path.join(settings.MEDIA_ROOT, "reminder_videos")
                os.makedirs(save_dir, exist_ok=True)
                clean_filename = f"{video_id}.mp4"
                video_path = os.path.join(save_dir, clean_filename)

                logging.info(f"Downloading video from {video_url} ...")
                video_resp = requests.get(video_url, stream=True, timeout=300)
                with open(video_path, "wb") as f:
                    for chunk in video_resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                logging.info(f"Video saved: {video_path}")
                web_url = f"{settings.MEDIA_URL}reminder_videos/{clean_filename}"
                return web_url

            elif status in ["failed", "error"]:
                logging.error(f"Video generation failed: {status_data}")
                return None

            elif status in ["processing", "pending"]:
                logging.info("Video still processing...")

            time.sleep(poll_interval)
            elapsed += poll_interval

        logging.error("Video generation timed out.")
        return None

    except Exception as e:
        import traceback
        logging.error(f"Unexpected error in video generation: {e}")
        logging.error(traceback.format_exc())
        return None

def send_whatsapp_video(to_number, video_url):
    logging.info(f"Sending WhatsApp video to {to_number}")
    logging.info(f"Video URL: {video_url}")
    return "simulated_message_sid"


