from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User


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


admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, UserAdmin)
