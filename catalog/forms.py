from django import forms


class CepCheckForm(forms.Form):
    cep = forms.CharField(
        label="CEP para entrega",
        max_length=9,
        widget=forms.TextInput(attrs={"placeholder": "00000-000", "class": "input-cep"}),
    )

    def clean_cep(self):
        cep = self.cleaned_data["cep"]
        digits = "".join(ch for ch in cep if ch.isdigit())
        if len(digits) != 8:
            raise forms.ValidationError("CEP inválido. Digite os 8 números do CEP.")
        return digits
