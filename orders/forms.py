from django import forms


class CheckoutForm(forms.Form):
    DELIVERY_CHOICES = [("retirada", "Retirar na loja"), ("entrega", "Entrega")]

    customer_name = forms.CharField(label="Seu nome", max_length=100)
    customer_phone = forms.CharField(label="WhatsApp para contato", max_length=20)
    delivery_type = forms.ChoiceField(label="Como você quer receber?", choices=DELIVERY_CHOICES, widget=forms.RadioSelect)
    cep = forms.CharField(label="CEP", max_length=9, required=False)
    address_text = forms.CharField(label="Endereço (rua e número)", max_length=255, required=False)
    address_complement = forms.CharField(label="Complemento", max_length=100, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("delivery_type") == "entrega":
            digits = "".join(ch for ch in cleaned.get("cep", "") if ch.isdigit())
            if len(digits) != 8:
                self.add_error("cep", "Digite um CEP válido (8 números) para calcular a entrega.")
            else:
                cleaned["cep"] = digits
            if not cleaned.get("address_text"):
                self.add_error("address_text", "Informe a rua e o número para a entrega.")
        return cleaned


class OutOfRangeMessageForm(forms.Form):
    name = forms.CharField(label="Seu nome", max_length=100)
    phone = forms.CharField(label="WhatsApp", max_length=20)
    message = forms.CharField(label="Recado", widget=forms.Textarea(attrs={"rows": 3}), required=False)
