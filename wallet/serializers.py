from decimal import Decimal
from rest_framework import serializers
from .models import Wallet, Transaction
from .services import get_account_balance


class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']

    def get_balance(self, obj):
        return get_account_balance(obj.account)


class TransactionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "type", "status", "amount", "description", "created_at"]


class AdminWalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            "id",
            "user",
            "balance",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_balance(self, obj):
        return get_account_balance(obj.account)


class DepositRequestSerializer(serializers.Serializer):
    """Documentation-only serializer for the deposit request body."""
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class WithdrawRequestSerializer(serializers.Serializer):
    """Documentation-only serializer for the withdraw request body."""
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class TransferRequestSerializer(serializers.Serializer):
    """Documentation-only serializer for the transfer request body."""
    to_user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class TransactionResponseSerializer(serializers.Serializer):
    """Documentation-only serializer for the transaction object returned by deposit/withdraw/transfer."""
    id = serializers.UUIDField()
    type = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.CharField()
