import requests
import json
import time
from django.conf import settings
from transformers import pipeline



translator = pipeline("translation", model="facebook/m2m100_418M")

BASE_SCRIPTS = {
    'EMI_DUE': "Hello {customer_name}, your EMI of {emi_amount} for loan {loan_number} is due on {due_date}. Please make the payment to avoid penalties. Thank you.",
    'NACH_REMINDER': "Hello {customer_name}, this is a reminder for your second NACH presentation for loan {loan_number}. Please ensure you have sufficient balance. Thank you.",
    'BOUNCE_REMINDER': "Hello {customer_name}, your recent EMI payment for loan {loan_number} has bounced. A penalty of {penalty_amount} has been applied. Please make the payment immediately to avoid further charges. Thank you.",
}

def generate_script(event_type, customer, loan):
    base_template = BASE_SCRIPTS.get(event_type)
    if not base_template:
        return "Default message: Please pay your EMI."
    penalty_amount = "₹500"
    english_script = base_template.format(
        customer_name=customer.name,
        emi_amount=loan.emi_amount,
        due_date=loan.due_date,
        loan_number=loan.loan_number,
        penalty_amount=penalty_amount,
    )
    if customer.preferred_language != 'en':
        try:
            translated_script = translator(english_script, src_lang="en", tgt_lang=customer.preferred_language)[0]['translation_text']
            return translated_script
        except Exception as e:
            print(f"Translation failed: {e}. Using English script instead.")
            return english_script
    else:
        return english_script


def generate_video(script):
    url = "https://api.heygen.com/v2/video/generate"

    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": "Abigail_expressive_2024112501", 
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": script, 
                    "voice_id": "73c0b6a2e29d4d38aca41454bf58c955" 
                },
                "background": {
                    "type": "color",
                    "value": "#0000FF"
                }
            }
        ],
        "dimension": {
            "width": 1280,
            "height": 720
        }
    }

    headers = {
        "X-Api-Key": settings.HEYGEN_API_KEY, 
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() 
        resp_json = response.json()

        if "data" not in resp_json or not resp_json["data"]:
            print("Video generation request failed. Response:", resp_json)
            return None

        video_id = resp_json["data"]["video_id"]
        status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"

        while True:
            status_resp = requests.get(status_url, headers={"X-Api-Key": settings.HEYGEN_API_KEY})
            status_resp.raise_for_status()
            status_json = status_resp.json()
            status = status_json.get("data", {}).get("status")
            if status in ["completed", "failed"]:
                break
            time.sleep(10)

        if status == "completed":
            video_url = status_json["data"]["video_url"]
            print("Video ready! URL:", video_url)
            return video_url
        else:
            print("Video generation failed:", status_json)
            return None

    except Exception as e:
        print(f"HeyGen API Error: {e}")
        return None

def send_whatsapp_video(to_number, video_url):

    print(f"Simulated sending WhatsApp message to {to_number} with video {video_url}")
    return "simulated_message_sid"



