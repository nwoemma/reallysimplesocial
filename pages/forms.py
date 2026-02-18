from django import forms
from decimal import Decimal

class AddFundsForm(forms.Form):
    payment_method = forms.ChoiceField(label='Payment Method')
    amount = forms.DecimalField(
        label='Amount',
        min_value=Decimal('100.00'),
        max_value=Decimal('1000000.00'),
        decimal_places=2
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Payment methods will be populated dynamically
        