from django.contrib import admin
from .models import TelegramUser, CurrentCourse, Order, MainLtcReq, Ticket, Withdraw, Client


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username' if 'username' else 'None']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(CurrentCourse)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(Withdraw)
class WithdrawAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(MainLtcReq)
class MainReqAdmin(admin.ModelAdmin):
    list_display = ['id']

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'activated']
