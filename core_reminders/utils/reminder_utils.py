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


INDIAN_AVATAR_ID = "Aditya_public_2"

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
    text="नमस्ते राज, आपके लोन E12345 की 20,000 की EMI 23 अक्टूबर को देय है। कृपया जुर्माने से बचने के लिए भुगतान कर दें। धन्यवाद"
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


def generate_voice(script, lang="hi"):
    try:
        voices = {
            "en": "TVtDNgumMv4lb9zzFzA2",
            "hi": "KSsyodh37PbfWy29kPtx",
            "hindi": "dxhwlBCxCrnzRlP4wPeE",
        }
        voice_id = voices.get(lang.lower(), "TVtDNgumMv4lb9zzFzA2")
        output_path = "reminder_voice.mp3"

        audio = eleven_client.text_to_speech.convert(
            voice_id=voice_id, model_id="eleven_multilingual_v2", text=script
        )

        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logging.info(f"Voice generated successfully: {output_path}")
            return output_path
        else:
            logging.error("Voice file was not created or is empty.")
            return None
    except Exception as e:
        logging.error(f"ElevenLabs voice generation failed: {e}")
        return None



def upload_audio_to_heygen(mp3_path, retries=3, delay=3):
    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
        logging.error(f"MP3 file does not exist or is empty: {mp3_path}")
        return None

    api_key = settings.HEYGEN_API_KEY
    upload_url = "https://upload.heygen.com/v1/asset"

    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "audio/mpeg",
        "Purpose": "audio",
    }

    for attempt in range(1, retries + 1):
        try:
            with open(mp3_path, "rb") as f:
                resp = requests.post(upload_url, data=f, headers=headers, timeout=60)

            logging.info(f"Upload attempt {attempt}: {resp.status_code} {resp.text}")

            if resp.status_code in [200, 201]:
                data = resp.json().get("data", {})
                asset_id = data.get("id")
                if asset_id:
                    logging.info(f"Audio uploaded successfully: {asset_id}")
                    return asset_id

            time.sleep(delay)
        except Exception as e:
            logging.error(f"Attempt {attempt} failed: {e}")
            time.sleep(delay)

    logging.error("All attempts to upload audio failed.")
    return None


def generate_video(script, customer, timeout=480, poll_interval=8):
    try:
        lang = getattr(customer, "preferred_language", "hi")

        logging.info("Step 1: Generating voice...")
        voice_file = generate_voice(script, lang)
        if not voice_file:
            return None

        logging.info("Step 2: Uploading audio...")
        audio_asset_id = upload_audio_to_heygen(voice_file)
        if not audio_asset_id:
            os.remove(voice_file)
            return None

        os.remove(voice_file)
        logging.info("Temporary voice file removed.")


        logging.info("Step 3: Requesting video generation...")
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
                        "avatar_id": INDIAN_AVATAR_ID,
                        "avatar_style": "normal",
                    },
                    "voice": {"type": "audio", "audio_asset_id": audio_asset_id},
                    "background": {"type": "color", "value": "#005DFD"},
                }
            ],
            "resolution": "360p",
            "caption": False,
            "preview": True,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        logging.info(f"Video generation response: {resp.status_code} {resp.text}")

        if resp.status_code not in [200, 201]:
            logging.error(f"Video generation request failed: {resp.text}")
            return None

        data = resp.json().get("data", {})
        video_id = data.get("video_id")
        status_url = data.get("status_url") or f"https://api.heygen.com/v2/video/status/{video_id}"

        if not video_id:
            logging.error("No video_id returned from HeyGen.")
            return None

        logging.info(f"Video generation started. Video ID: {video_id}")

        elapsed = 0
        attempt = 0
        time.sleep(20)
        elapsed += 20

        while elapsed < timeout:
            attempt += 1
            logging.info(f"Polling attempt {attempt} (elapsed {elapsed}s)...")

            try:
                status_resp = requests.get(status_url, headers=headers, timeout=30)
                if status_resp.status_code == 404:
                    logging.warning(f"404 - Video not ready yet. Retrying...")
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    continue

                status_data = status_resp.json().get("data", {})
                status = status_data.get("status")
                video_url = status_data.get("video_url")

                logging.info(f"Video status: {status}")

                if status == "completed" and video_url:
                    save_dir = os.path.join(settings.BASE_DIR, "reminder_videos")
                    os.makedirs(save_dir, exist_ok=True)
                    video_path = os.path.join(save_dir, f"{video_id}.mp4")

                    logging.info(f"Downloading video from {video_url} ...")
                    video_resp = requests.get(video_url, stream=True, timeout=300)
                    with open(video_path, "wb") as f:
                        for chunk in video_resp.iter_content(chunk_size=8192):
                            f.write(chunk)

                    logging.info(f"Video saved: {video_path}")
                    return video_path

                elif status in ["failed", "error"]:
                    logging.error(f"Video generation failed: {status_data}")
                    return None

            except Exception as e:
                logging.error(f"Polling error: {e}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        logging.error("Video generation timed out.")
        return None

    except Exception as e:
        logging.error(f"Unexpected error in video generation: {e}")
        return None






def send_whatsapp_video(to_number, video_url):
    logging.info(f"Sending WhatsApp video to {to_number}")
    logging.info(f"Video URL: {video_url}")
    return "simulated_message_sid"


