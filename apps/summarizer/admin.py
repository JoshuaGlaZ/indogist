from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Summary

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')


@admin.register(Summary)
class SummaryAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'method', 'compression_ratio',
                    'word_count_original', 'word_count_summary', 'created_at']
    list_filter = ['method', 'compression_ratio',
                   'created_at']
    search_fields = ['title', 'original_text',
                     'summary_text', 'user__username']
    readonly_fields = ['created_at',
                       'word_count_original', 'word_count_summary']

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'title', 'method', 'compression_ratio')
        }),
        ('Content', {
            'fields': ('original_text', 'summary_text', 'entities')
        }),
        ('Metadata', {
            'fields': ('created_at', 'word_count_original', 'word_count_summary')
        }),
    )

    ordering = ('-created_at',)
