from rest_framework import serializers
from .models import Wallet
from .services import get_account_balance


class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']

    def get_balance(self, obj):
        return get_account_balance(obj.account)
