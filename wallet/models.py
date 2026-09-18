from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Wallet({self.user}) - {self.balance}'


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', "Deposit"
        WITHDRAW = 'withdraw', 'Withdraw'
        TRANSFER = 'transfer', 'Transfer'

    class TransactionStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELED = 'canceled', 'Canceled'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    type = models.CharField(
        max_length=10,
        choices=TransactionType.choices
    )
    status = models.CharField(
        max_length=10,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.amount} - {self.type}'


class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        DEBIT = 'debit', 'Debit'
        CREDIT = 'credit', 'Credit'

    wallet = models.ForeignKey(
        'Wallet',
        on_delete=models.PROTECT,
        related_name='ledger_entries'
    )
    transaction = models.ForeignKey(
        'Transaction',
        on_delete=models.PROTECT,
        related_name='ledger_entries'
    )
    entry_type = models.CharField(
        max_length=6,
        choices=EntryType.choices,
        db_index=True,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    balance_after = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.wallet_id} | {self.entry_type} | {self.amount}'


class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True, db_index=True)
    response_data = models.JSONField()
    status_code = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.key
