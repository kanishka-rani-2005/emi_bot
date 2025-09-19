from django.contrib import admin
from .models import Customer, Loan, Reminder

admin.site.register(Customer)
admin.site.register(Loan)

from django.utils.html import format_html
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('customer', 'loan', 'event_type', 'status', 'sent_at', 'video_preview')
    readonly_fields = ('video_preview',)

    def video_preview(self, obj):
        if obj.video_url:
            return format_html(
                f'<video width="320" height="240" controls><source src="{obj.video_url}" type="video/mp4"></video>'
            )
        return "Video not available"
    
    video_preview.short_description = 'Video'

admin.site.register(Reminder, ReminderAdmin)