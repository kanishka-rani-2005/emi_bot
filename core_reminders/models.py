# core_reminders/models.py

from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255)
    whatsapp_number = models.CharField(max_length=20, unique=True)
    preferred_language = models.CharField(max_length=50, default='en')

    def __str__(self):
        return self.name

class Loan(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loans')
    loan_number = models.CharField(max_length=100, unique=True)
    emi_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    bounce_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Loan {self.loan_number} for {self.customer.name}"

class Reminder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('GENERATING', 'Generating Video'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]

    EVENT_CHOICES = [
        ('EMI_DUE', 'EMI Due Reminder'),
        ('NACH_REMINDER', 'NACH Reminder'),
        ('BOUNCE_REMINDER', 'Bounce Reminder'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    video_url = models.URLField(blank=True, null=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Reminder for {self.customer.name} - {self.event_type} - {self.status}"