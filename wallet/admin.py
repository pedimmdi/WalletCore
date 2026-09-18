from django.contrib import admin
from .models import (
    Account,
    Wallet,
    Transaction,
    LedgerEntry,
    IdempotencyKey,
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "account_type",
        "is_active",
        "created_at",
    )
    list_filter = ("account_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "account",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "status",
        "amount",
        "initiated_by",
        "created_at",
    )
    list_filter = ("type", "status", "created_at")
    search_fields = (
        "id",
        "initiated_by__username",
        "initiated_by__email",
    )
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "account",
        "transaction",
        "entry_type",
        "amount",
        "balance_after",
        "created_at",
    )
    list_filter = ("entry_type", "created_at")
    search_fields = ("account__name", "transaction__id")
    readonly_fields = ("created_at",)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "key",
        "status_code",
        "created_at",
    )
    search_fields = ("key", "request_hash")
    readonly_fields = ("created_at",)
