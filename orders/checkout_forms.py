"""Formulários do fluxo de pedido: 1) dados pessoais  2) como receber."""
import re
from datetime import date

from django import forms

DELIVERY_CHOICES = [
    ("retirada", "Retirar na loja"),
    ("entrega", "Entrega"),
]


def only_digits(value) -> str:
    return re.sub(r"\D", "", value or "")


def format_phone(digits: str) -> str:
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"


def format_cep(digits: str) -> str:
    return f"{digits[:5]}-{digits[5:]}" if len(digits) == 8 else digits


class CustomerInfoForm(forms.Form):
    phone = forms.CharField(label="Telefone", max_length=20)
    name = forms.CharField(label="Seu nome", max_length=100)
    birth_date = forms.DateField(
        label="Data de nascimento",
        input_formats=["%d/%m/%Y"],
        error_messages={"invalid": "Use o formato dd/mm/aaaa.", "required": "Informe sua data de nascimento."},
    )

    def clean_phone(self):
        digits = only_digits(self.cleaned_data["phone"])
        if digits.startswith("55") and len(digits) in (12, 13):
            digits = digits[2:]
        invalid = (
            len(digits) not in (10, 11)
            or digits[0] == "0"
            or (len(digits) == 11 and digits[2] != "9")
        )
        if invalid:
            raise forms.ValidationError("Digite um telefone com DDD, ex.: (21) 99999-9999.")
        return format_phone(digits)

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Digite seu nome.")
        return name

    def clean_birth_date(self):
        born = self.cleaned_data["birth_date"]
        today = date.today()
        if born >= today or born.year < 1900:
            raise forms.ValidationError("Confira a data de nascimento.")
        return born


class DeliveryForm(forms.Form):
    delivery_type = forms.ChoiceField(
        choices=DELIVERY_CHOICES,
        error_messages={"required": "Escolha como quer receber.", "invalid_choice": "Escolha como quer receber."},
    )
    cep = forms.CharField(required=False, max_length=9)
    address_text = forms.CharField(required=False, max_length=255)
    address_complement = forms.CharField(required=False, max_length=100)

    def clean(self):
        data = super().clean()
        if data.get("delivery_type") == "entrega":
            cep = only_digits(data.get("cep"))
            if len(cep) != 8:
                self.add_error("cep", "Digite um CEP com 8 números.")
            else:
                data["cep"] = cep  # só dígitos; a view formata ao salvar
            if len((data.get("address_text") or "").strip()) < 5:
                self.add_error("address_text", "Informe a rua e o número.")
        else:
            data["cep"] = ""
            data["address_text"] = ""
            data["address_complement"] = ""
        return data
