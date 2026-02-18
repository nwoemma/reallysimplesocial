from django import forms
from .models import User
class UserRegistion(forms.ModelForm):
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    class Meta:
        model = User
        fields =  ['username', 'email', 'first_name', 'last_name','password']
        
    def save(self, commit = True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
    
    def clean(self):
        clean_data = super().clean()
        password = clean_data.get('password')
        password2 = clean_data.get('password2')
        if password != password2:
            raise forms.ValidationError("Passwords do not match")
        return clean_data