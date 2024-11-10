from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html

from .models import Voicemail


class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    filter_horizontal = ()
    list_display = ("username", "email", "first_name", "last_name", "is_superuser", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active")


class VoicemailAdmin(admin.ModelAdmin):
    empty_value_display = "Unknown"
    list_display = ("phone_number", "created_at", "location", "duration", "file_player")
    fields = ("phone_number", "created_at", "location", "duration", "file_player", "file")
    readonly_fields = ("file_player",)

    @admin.display(description="audio")
    def file_player(self, obj: Voicemail):
        return format_html('<audio controls src="{}" style="height: 28px" />', obj.file.url)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, UserAdmin)
admin.site.register(Voicemail, VoicemailAdmin)
