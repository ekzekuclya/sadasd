import string
from django.db import models
import random


class TelegramUser(models.Model):
    user_id = models.IntegerField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    is_admin = models.BooleanField(default=False)
    last_message_time = models.DateTimeField(null=True, blank=True)
    is_operator = models.BooleanField(default=False)
    operator_percent = models.FloatField(null=True, blank=True)
    exchanges = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.username if self.username else "None"


class CurrentCourse(models.Model):
    usdt = models.IntegerField(blank=True)
    coms_5 = models.IntegerField(blank=True)
    coms_5_10 = models.IntegerField(blank=True)
    coms_10_20 = models.IntegerField(blank=True)
    coms_20_30 = models.IntegerField(blank=True)
    coms_30_70 = models.IntegerField(blank=True)
    coms_70_120 = models.IntegerField(blank=True)


class Order(models.Model):
    client = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="client")
    operator = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="operator")
    coms = models.IntegerField()
    kgs_sum = models.IntegerField()
    ltc_sum = models.FloatField()
    status = models.CharField(max_length=255)
    req = models.TextField(null=True, blank=True)
    sum_for_op = models.FloatField(null=True, blank=True)


class Requisites(models.Model):
    operator = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, blank=True)
    cart_name = models.CharField(max_length=255)
    requisites = models.TextField(null=True, blank=True)


class MainLtcReq(models.Model):
    req = models.TextField(null=True, blank=True)


class Ticket(models.Model):
    ticket = models.CharField(max_length=255, unique=True)
    activated = models.BooleanField(default=False)
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, null=True, blank=True)
    def generate_unique_ticket(self):
        while True:
            ticket_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            if not Ticket.objects.filter(ticket=ticket_code).exists():
                return ticket_code

    def save(self, *args, **kwargs):
        if not self.ticket:
            self.ticket = self.generate_unique_ticket()
        super().save(*args, **kwargs)


class Withdraw(models.Model):
    amount = models.FloatField()
    chat_id = models.CharField(max_length=255)
    req = models.CharField(max_length=2555)
    active = models.BooleanField()
    symbol = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)


class Client(models.Model):
    key = models.CharField(max_length=2555)
    secret = models.CharField(max_length=2555)