from django.contrib import admin
from .models import TelegramUser, CurrentCourse, Order, MainLtcReq


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username' if 'username' else 'None']


@admin.register(CurrentCourse)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(MainLtcReq)
class MainReqAdmin(admin.ModelAdmin):
    list_display = ['id']
