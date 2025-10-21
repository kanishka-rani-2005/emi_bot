from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from .models import Customer, Loan, Reminder
import os

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    pass

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    pass

class ReminderAdmin(admin.ModelAdmin):
    list_display = ('customer', 'loan', 'event_type', 'status', 'sent_at', 'video_preview')
    readonly_fields = ('video_preview',)

    def video_preview(self, obj):
        if obj.video_url:
            if obj.video_url.startswith('/') or obj.video_url.startswith('C:') or obj.video_url.startswith('/home'):
                filename = os.path.basename(obj.video_url)
                video_url = f"{settings.MEDIA_URL}reminder_videos/{filename}"
            else:
                video_url = obj.video_url
            
            return format_html(
                '<video width="480" height="240" controls preload="none">'
                '<source src="{}" type="video/mp4"></video>',
                video_url
            )
        return "Video not available"

    video_preview.short_description = 'Video'

admin.site.register(Reminder, ReminderAdmin)