from django.db import models


class DeliveryMessage(models.Model):
    """
    Recado deixado por quem tentou pedir entrega fora do raio atendido.
    Aparece pro dono da loja decidir se quer atender por fora mesmo assim
    (ex: "posso ir buscar", vizinho de outro bairro, etc).
    """
    name = models.CharField("nome", max_length=100)
    phone = models.CharField("telefone/WhatsApp", max_length=20)
    cep = models.CharField("CEP informado", max_length=9)
    distance_km = models.DecimalField("distância calculada (km)", max_digits=6, decimal_places=2, null=True, blank=True)
    message = models.TextField("recado do cliente", blank=True)
    created_at = models.DateTimeField("recebido em", auto_now_add=True)
    attended = models.BooleanField("já foi respondido", default=False)

    class Meta:
        verbose_name = "recado de fora da área"
        verbose_name_plural = "recados de fora da área"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — CEP {self.cep}"
