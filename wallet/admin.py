from django.contrib import admin
from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'balance', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('balance', 'created_at', 'updated_at')
    list_editable = ('is_active',)
