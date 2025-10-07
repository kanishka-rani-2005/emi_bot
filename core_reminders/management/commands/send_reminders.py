from django.core.management.base import BaseCommand
from core_reminders.models import Loan, Reminder
from core_reminders.utils.reminder_utils import generate_script, generate_video, send_whatsapp_video
from datetime import date, timedelta

class Command(BaseCommand):
    def handle(self, *args, **options):        
        due_date_threshold = date.today() + timedelta(days=3)

        upcoming_loans = Loan.objects.filter(
            due_date=due_date_threshold,
            is_active=True,
            reminder__isnull=True 
        )

        for loan in upcoming_loans:
            try:
                reminder = Reminder.objects.create(
                    customer=loan.customer,
                    loan=loan,
                    event_type='EMI_DUE',
                    status='GENERATING'
                )

                script = generate_script(reminder.event_type, loan.customer, loan)
                video_url = generate_video(script,customer=loan.customer)

                if not video_url:
                    reminder.status = 'FAILED'
                    reminder.save()
                    self.stdout.write(self.style.ERROR('Video generation failed.'))
                    continue

                whatsapp_sid = send_whatsapp_video(loan.customer.whatsapp_number, video_url)
                
                if whatsapp_sid:
                    reminder.status = 'SENT'
                    reminder.video_url = video_url
                    reminder.save()
                    self.stdout.write(self.style.SUCCESS(f'Successfully sent reminder for {loan.customer.name}!'))
                else:
                    reminder.status = 'FAILED'
                    reminder.save()
                    self.stdout.write(self.style.ERROR(f'Failed to send WhatsApp message for {loan.customer.name}.'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'An error occurred for loan {loan.loan_number}: {e}'))
                if 'reminder' in locals():
                    reminder.status = 'FAILED'
                    reminder.save()