def user_balance_processor(request):
    if request.user.is_authenticated:
        # Replace 'balance' with the actual field name on your User or Profile model
        # Example if you have a Profile model: balance = request.user.profile.balance
        balance = getattr(request.user, 'balance', 0)
        return {
            'user_balance': f"NGN {balance:,}" # Adds comma separators (e.g., NGN 1,000)
        }
    return {'user_balance': 'NGN 0'}