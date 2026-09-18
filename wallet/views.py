from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import WalletSerializer
from .services import (
    deposit_idempotent,
    get_or_create_user_wallet,
)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet = get_or_create_user_wallet(request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class DepositView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            return Response(
                {
                    "detail": "Idempotency-Key header is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.data.get("amount")

        if raw_amount is None:
            return Response(
                {
                    "detail": "Amount is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            return Response(
                {
                    "detail": "Invalid amount."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response_body, response_status = deposit_idempotent(
                user=request.user,
                amount=amount,
                idempotency_key=idempotency_key,
            )

        except ValidationError as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            response_body,
            status=response_status,
        )
