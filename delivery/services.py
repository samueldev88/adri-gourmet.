"""
Cálculo de distância a partir de um CEP, sem depender de nenhuma API paga:

  1. ViaCEP           CEP  -> endereço (rua, bairro, cidade)
  2. Nominatim (OSM)   endereço -> latitude/longitude
  3. Haversine         duas coordenadas -> distância em linha reta (km)

Isso é suficiente para decidir "atende ou não atende" numa loja de bairro.
Se um dia o volume justificar, dá pra trocar por Google Distance Matrix
(que calcula distância de rota real, não linha reta) sem mexer em mais
nada além deste arquivo.
"""
import math
from dataclasses import dataclass

import requests
from django.conf import settings

VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_TIMEOUT = 6  # segundos


class CepLookupError(Exception):
    """Não foi possível transformar o CEP em coordenadas."""


@dataclass
class DeliveryCheckResult:
    within_range: bool
    distance_km: float | None
    address_label: str | None


def _fetch_address_from_cep(cep: str) -> dict:
    try:
        response = requests.get(VIACEP_URL.format(cep=cep), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise CepLookupError("Não consegui consultar o CEP agora. Tente novamente em instantes.") from exc

    if data.get("erro"):
        raise CepLookupError("Esse CEP não foi encontrado. Confira se digitou certo.")
    return data


def _geocode_address(address: dict) -> tuple[float, float]:
    query = f"{address.get('logradouro', '')}, {address.get('bairro', '')}, {address.get('localidade', '')}, {address.get('uf', '')}, Brasil"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "lojinha-mae-django/1.0"}

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        raise CepLookupError("Não consegui calcular a localização desse endereço agora.") from exc

    if not results:
        raise CepLookupError(
            "Não encontrei esse endereço no mapa. Isso é raro, mas pode acontecer com CEPs muito novos."
        )
    return float(results[0]["lat"]), float(results[0]["lon"])


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta entre duas coordenadas, em km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def check_delivery(cep: str) -> DeliveryCheckResult:
    """
    Função principal: recebe um CEP (só dígitos) e devolve se está dentro
    do raio de entrega configurado em settings.DELIVERY_RADIUS_KM.
    Levanta CepLookupError se não for possível calcular.
    """
    address = _fetch_address_from_cep(cep)
    lat, lon = _geocode_address(address)

    distance = haversine_km(settings.SHOP_LATITUDE, settings.SHOP_LONGITUDE, lat, lon)
    address_label = f"{address.get('logradouro', '')}, {address.get('bairro', '')} — {address.get('localidade', '')}/{address.get('uf', '')}"

    return DeliveryCheckResult(
        within_range=distance <= settings.DELIVERY_RADIUS_KM,
        distance_km=round(distance, 2),
        address_label=address_label,
    )
