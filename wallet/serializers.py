from rest_framework import serializers
from .models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['id', 'account', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'account', 'created_at', 'updated_at']
